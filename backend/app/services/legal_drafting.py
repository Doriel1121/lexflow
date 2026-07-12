"""
legal_drafting.py
----------------=
Generates AI-drafted legal response documents for the workflow engine.

Input: source document OCR text, document intelligence analysis, case metadata,
       optional deadlines, and workflow metadata instructions.

Output: A TipTap/ProseMirror JSON document stored as a LegalDraft row.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ai_router import AIIntent, AIRiskLevel, AITask, AITaskContext, ai_router
from app.core.legal_workflow_constants import LegalDraftStatus
from app.services.ai_quota import AIQuotaExceeded, enforce_ai_quota
from app.services.ai_usage_logger import track_ai_call
from app.crud.legal_workflow import legal_workflow_crud
from app.db.models.case import Case as DBCase
from app.db.models.document import Document as DBDocument
from app.db.models.legal_workflow import LegalDraft as DBLegalDraft, LegalWorkflow as DBLegalWorkflow
from app.schemas.legal_workflow import LegalDraftCreate
from app.services.legal_evidence_pack import LegalEvidencePack, legal_evidence_pack_builder

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: plain-text → TipTap JSON converter
# ---------------------------------------------------------------------------

def _plain_text_to_tiptap(text: str) -> Dict[str, Any]:
    """
    Convert plain text (with Markdown-ish headings) to a minimal TipTap JSON
    document compatible with @tiptap/starter-kit.

    Supported tokens:
      # Heading 1
      ## Heading 2
      ### Heading 3
      blank line → paragraph separator
      otherwise  → paragraph text
    """
    nodes: List[Dict[str, Any]] = []
    current_paragraph_texts: List[str] = []

    def _flush_paragraph():
        if current_paragraph_texts:
            combined = " ".join(current_paragraph_texts).strip()
            if combined:
                nodes.append(
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": combined}],
                    }
                )
            current_paragraph_texts.clear()

    for line in text.splitlines():
        stripped = line.strip()

        # Heading detection
        heading_match = re.match(r"^(#{1,3})\s+(.*)", stripped)
        if heading_match:
            _flush_paragraph()
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()
            if heading_text:
                nodes.append(
                    {
                        "type": "heading",
                        "attrs": {"level": level},
                        "content": [{"type": "text", "text": heading_text}],
                    }
                )
            continue

        # Blank line = paragraph break
        if not stripped:
            _flush_paragraph()
            continue

        current_paragraph_texts.append(stripped)

    _flush_paragraph()

    # Ensure at least one node so TipTap is happy
    if not nodes:
        nodes.append({"type": "paragraph", "content": [{"type": "text", "text": ""}]})

    return {"type": "doc", "content": nodes}


def _tiptap_to_html(tiptap_json: Dict[str, Any]) -> str:
    """
    Convert a TipTap JSON document to a simple HTML snapshot for PDF generation.
    """
    html_parts: List[str] = ["<div class='legal-draft'>"]

    for node in tiptap_json.get("content", []):
        node_type = node.get("type", "")
        content_nodes = node.get("content", [])
        text_content = "".join(n.get("text", "") for n in content_nodes if n.get("type") == "text")

        if node_type == "heading":
            level = node.get("attrs", {}).get("level", 1)
            html_parts.append(f"<h{level}>{text_content}</h{level}>")
        elif node_type == "paragraph":
            html_parts.append(f"<p>{text_content}</p>")
        elif node_type == "bulletList":
            items = node.get("content", [])
            html_parts.append("<ul>")
            for item in items:
                item_text = "".join(
                    n.get("text", "")
                    for para in item.get("content", [])
                    for n in para.get("content", [])
                    if n.get("type") == "text"
                )
                html_parts.append(f"<li>{item_text}</li>")
            html_parts.append("</ul>")
        elif node_type == "orderedList":
            items = node.get("content", [])
            html_parts.append("<ol>")
            for item in items:
                item_text = "".join(
                    n.get("text", "")
                    for para in item.get("content", [])
                    for n in para.get("content", [])
                    if n.get("type") == "text"
                )
                html_parts.append(f"<li>{item_text}</li>")
            html_parts.append("</ol>")
        elif node_type == "blockquote":
            quote_text = "".join(
                n.get("text", "")
                for para in content_nodes
                for n in para.get("content", [])
                if n.get("type") == "text"
            )
            html_parts.append(f"<blockquote>{quote_text}</blockquote>")

    html_parts.append("</div>")
    return "\n".join(html_parts)


def _tiptap_to_plain_text(tiptap_json: Dict[str, Any]) -> str:
    """
    Extract plain text from a TipTap document for search and AI context.
    """
    lines: List[str] = []

    def _extract_text(node: Dict[str, Any]) -> str:
        if node.get("type") == "text":
            return node.get("text", "")
        return "".join(_extract_text(child) for child in node.get("content", []))

    for node in tiptap_json.get("content", []):
        lines.append(_extract_text(node))

    return "\n\n".join(filter(None, lines))


# ---------------------------------------------------------------------------
# Draft input collector
# ---------------------------------------------------------------------------

class DraftInputCollector:
    """
    Gathers all available context needed for draft generation:
    - Source document OCR text
    - Document intelligence analysis
    - Case metadata
    - Workflow metadata (jurisdiction, instructions, etc.)
    - Deadlines from the document metadata
    """

    async def collect(
        self,
        db: AsyncSession,
        workflow: DBLegalWorkflow,
    ) -> Dict[str, Any]:
        context: Dict[str, Any] = {
            "case_id": workflow.case_id,
            "organization_id": workflow.organization_id,
            "workflow_type": workflow.workflow_type,
            "workflow_metadata": workflow.metadata_json or {},
            "ocr_text": "",
            "document_analysis": {},
            "case_title": "",
            "case_description": "",
            "deadlines": [],
            "source_filename": "",
            "source_document_id": workflow.source_document_id,
        }

        # Fetch case metadata
        case_result = await db.execute(select(DBCase).where(DBCase.id == workflow.case_id))
        case = case_result.scalars().first()
        if case:
            context["case_title"] = case.title or ""
            context["case_description"] = case.description or ""

        # Fetch source document
        if workflow.source_document_id:
            doc_result = await db.execute(
                select(DBDocument).where(DBDocument.id == workflow.source_document_id)
            )
            doc = doc_result.scalars().first()
            if doc:
                context["source_filename"] = doc.filename or ""
                context["ocr_text"] = doc.content or ""
                # Try to get document metadata (AI analysis)
                if hasattr(doc, "document_metadata") and doc.document_metadata:
                    metadata = doc.document_metadata
                    if hasattr(metadata, "analysis_json") and metadata.analysis_json:
                        context["document_analysis"] = metadata.analysis_json
                    # Extract deadlines
                    if hasattr(metadata, "deadlines_json") and metadata.deadlines_json:
                        context["deadlines"] = metadata.deadlines_json

        return context


# ---------------------------------------------------------------------------
# Legal Drafting Service
# ---------------------------------------------------------------------------

class LegalDraftingService:
    """
    Orchestrates AI draft generation for legal response workflows.
    """

    def __init__(self):
        self.collector = DraftInputCollector()
        self.evidence_pack_builder = legal_evidence_pack_builder

    async def generate_draft(
        self,
        db: AsyncSession,
        workflow: DBLegalWorkflow,
        instructions: Optional[str] = None,
    ) -> DBLegalDraft:
        """
        Main entry point: collect inputs, call AI, normalize to TipTap JSON,
        store and return the draft.
        """
        # 1. Collect context
        context = await self.collector.collect(db, workflow)

        # 2. Merge any instructions from call-site or workflow metadata
        if instructions is None:
            instructions = (workflow.metadata_json or {}).get("drafting_instructions")
        evidence_pack = await self.evidence_pack_builder.build_for_workflow(
            db,
            workflow,
            drafting_instructions=instructions,
        )
        context["evidence_pack"] = evidence_pack

        # 3. Generate draft text (AI or fallback)
        draft_text = await self._call_ai(db, context, instructions)

        # 4. Convert to TipTap JSON
        tiptap_json = _plain_text_to_tiptap(draft_text)
        html_snapshot = _tiptap_to_html(tiptap_json)
        content_text = _tiptap_to_plain_text(tiptap_json)

        # 5. Derive a meaningful draft title
        case_title = context.get("case_title") or f"Case {workflow.case_id}"
        filename = context.get("source_filename") or "source document"
        draft_title = f"Response Draft – {case_title}"

        # 6. Check idempotency: if an active draft already exists, skip creation
        existing = await self._get_existing_draft(db, workflow.id)
        if existing:
            logger.info(
                "Draft already exists (id=%s) for workflow %s – skipping creation.",
                existing.id,
                workflow.id,
            )
            return existing

        # 7. Persist the draft
        draft_in = LegalDraftCreate(
            title=draft_title,
            content_json=tiptap_json,
            content_text=content_text,
            html_snapshot=html_snapshot,
            status=LegalDraftStatus.AI_GENERATED,
            editor_format="tiptap_json",
            source_document_id=workflow.source_document_id,
            created_by="ai",
        )
        draft = await legal_workflow_crud.create_draft(db, workflow, draft_in)
        logger.info(
            "AI draft created (id=%s) for workflow %s.",
            draft.id,
            workflow.id,
        )
        return draft

    def _has_hebrew(self, text: str) -> bool:
        return any("֐" <= ch <= "׿" for ch in (text or "")[:4000])

    async def _call_ai(
        self,
        db: AsyncSession,
        context: Dict[str, Any],
        instructions: Optional[str],
    ) -> str:
        """
        Call the AI provider with a structured legal drafting prompt.
        Returns raw text; falls back to a structured placeholder if AI is unavailable.
        """
        prompt = self._build_prompt(context, instructions)
        provider = ai_router.provider_for(
            AITask.DRAFTING,
            AITaskContext(
                task=AITask.DRAFTING,
                feature="legal_workflow_drafting",
                intent=AIIntent.DRAFTING,
                language="he" if self._has_hebrew(prompt) else "",
                input_chars=len(prompt or ""),
                risk_level=AIRiskLevel.HIGH,
                requires_citations=True,
            ),
        )
        if not provider or not getattr(provider, "active", False):
            logger.warning("AI provider inactive – returning structured placeholder draft.")
            return self._placeholder_draft(context)

        try:
            await enforce_ai_quota(
                db,
                organization_id=context.get("organization_id"),
                task_type="drafting.legal_response",
                input_chars=len(prompt or ""),
            )
            async with track_ai_call(
                db,
                organization_id=context.get("organization_id"),
                task_type="drafting.legal_response",
                provider=provider,
                input_text=prompt,
            ) as usage:
                result = await asyncio.wait_for(
                    provider.generate_text(prompt),
                    timeout=120.0,
                )
                usage["output_chars"] = len(result or "")
            if result:
                return result.strip()
        except AIQuotaExceeded:
            raise
        except asyncio.TimeoutError:
            logger.error("AI draft generation timed out for workflow %s.", context.get("case_id"))
        except Exception as exc:
            logger.error("AI draft generation failed: %s", exc, exc_info=True)

        return self._placeholder_draft(context)

    def _build_prompt(
        self,
        context: Dict[str, Any],
        instructions: Optional[str],
    ) -> str:
        """
        Construct the legal drafting prompt from a compact evidence pack.
        """
        jurisdiction = context.get("workflow_metadata", {}).get("jurisdiction", "")
        court_profile = context.get("workflow_metadata", {}).get("court_profile", {})
        evidence_pack = context.get("evidence_pack")
        if isinstance(evidence_pack, LegalEvidencePack):
            pack = evidence_pack
        else:
            pack = self._fallback_evidence_pack(context, instructions)

        source_doc = pack.source_document
        doc_type = source_doc.get("document_type") or "Legal Document"
        doc_summary = source_doc.get("summary") or "No summary available."
        parties = self._format_list(pack.parties)
        claims = self._format_list(pack.claims)
        key_facts = self._format_list(pack.key_facts)
        dates = self._format_list(pack.dates)
        amounts = self._format_list(pack.amounts)
        obligations = self._format_list(pack.obligations)
        risks = self._format_list(pack.risks)
        missing_items = self._format_list(pack.missing_items)
        excerpts = self._format_source_excerpts(pack.source_excerpts)

        extra_instructions = ""
        if pack.drafting_instructions or instructions:
            extra_instructions = (
                "\n\nAdditional Instructions from the supervising lawyer:\n"
                f"{pack.drafting_instructions or instructions}\n"
            )

        prompt = f"""You are a senior Israeli litigation attorney drafting a formal legal response document.

CASE INFORMATION
----------------
Case Title: {pack.case.get('title') or context.get('case_title', 'Unknown Case')}
Case Description: {pack.case.get('description') or context.get('case_description', '')}
Source Document Type: {doc_type}
Jurisdiction: {jurisdiction or 'Israel'}
Court Profile: {court_profile or {}}

DOCUMENT SUMMARY
----------------
{doc_summary}

PARTIES
-------
{parties}

CLAIMS / ALLEGATIONS
----------------====
{claims}

KEY FACTS
-------==
{key_facts}

DATES / DEADLINES
----------------=
{dates}

AMOUNTS
-------
{amounts}

OBLIGATIONS
-------====
{obligations}

IDENTIFIED RISKS
----------------
{risks}

MISSING OR WEAK EVIDENCE
-----------------------=
{missing_items}

SOURCE EXCERPTS WITH REFERENCES
------------------------------=
{excerpts}

{extra_instructions}

DRAFTING INSTRUCTIONS
----------------=====
Draft a complete, professional legal response document with the following structure:

# [Document Title — e.g., "Statement of Defense" or "Response to Claim"]

## Introduction
Brief introduction identifying the responding party and the matter.

## Factual Background
Summary of relevant facts from our client's perspective.

## Legal Arguments
Numbered legal arguments responding to each claim or issue in the source document.
Each argument should reference applicable law where relevant.

## Relief Requested
Clear statement of what the responding party is requesting from the court.

## Conclusion
Brief closing paragraph.

REQUIREMENTS:
- Write in formal legal Hebrew if the source document is in Hebrew, otherwise in English.
- Use markdown headings (# ## ###) to structure the document.
- Be thorough and professional.
- Ground factual assertions in the provided evidence pack and source excerpts.
- Do not invent facts, parties, dates, amounts, laws, or procedural history.
- If evidence is missing or weak, draft cautiously and phrase the point as subject to lawyer review.
- Use the source excerpt references internally to stay grounded, but do not output raw citation labels unless useful to the document.
- Do not include placeholder instructions; write the actual substantive content.
- Output ONLY the document text, no preamble or explanation.
"""
        return prompt

    def _fallback_evidence_pack(
        self,
        context: Dict[str, Any],
        instructions: Optional[str],
    ) -> LegalEvidencePack:
        analysis = context.get("document_analysis") or {}
        return LegalEvidencePack(
            case={
                "id": context.get("case_id"),
                "title": context.get("case_title", ""),
                "description": context.get("case_description", ""),
            },
            source_document={
                "id": context.get("source_document_id"),
                "filename": context.get("source_filename", ""),
                "document_type": analysis.get("document_type") or analysis.get("classification") or "Legal Document",
                "summary": analysis.get("summary") or "",
            },
            parties=analysis.get("parties") or [],
            claims=analysis.get("claims") or analysis.get("allegations") or [],
            key_facts=analysis.get("key_facts") or analysis.get("facts") or [],
            dates=analysis.get("key_dates") or context.get("deadlines") or [],
            amounts=analysis.get("financial_terms") or analysis.get("amounts") or [],
            obligations=analysis.get("obligations") or [],
            risks=analysis.get("risks") or [],
            missing_items=analysis.get("missing_items") or analysis.get("missing_documents") or [],
            drafting_instructions=instructions,
        )

    def _format_list(self, items: List[Any]) -> str:
        if not items:
            return "  (none identified)"
        lines = []
        for item in items[:12]:
            if isinstance(item, dict):
                details = ", ".join(
                    f"{key}: {value}"
                    for key, value in item.items()
                    if value not in (None, "", [])
                )
                lines.append(f"  - {details or item}")
            else:
                lines.append(f"  - {item}")
        return "\n".join(lines)

    def _format_source_excerpts(self, excerpts: List[Any]) -> str:
        if not excerpts:
            return "  (no source excerpts available)"
        lines = []
        for index, excerpt in enumerate(excerpts, start=1):
            data = excerpt if isinstance(excerpt, dict) else excerpt.to_dict()
            reference = (
                f"doc={data.get('document_id')}, "
                f"page={data.get('page_number') or 'n/a'}, "
                f"chunk={data.get('chunk_index') if data.get('chunk_index') is not None else 'n/a'}"
            )
            lines.append(
                f"[E{index}] {reference}; reason: {data.get('reason')}\n"
                f"{data.get('text')}"
            )
        return "\n\n".join(lines)

    def _placeholder_draft(self, context: Dict[str, Any]) -> str:
        """
        Structured placeholder draft for when AI is unavailable.
        """
        case_title = context.get("case_title") or f"Case {context.get('case_id', 'Unknown')}"
        doc_type = (context.get("document_analysis") or {}).get("document_type", "the submitted document")
        return f"""# Statement of Defense

## Introduction

This document constitutes the formal response of the defendant in the matter of {case_title}.
The responding party hereby addresses the claims raised in {doc_type}.

## Factual Background

The facts of this matter, as understood by the responding party, are as follows:

The matter arose from circumstances that are described in detail in the source document provided to this workflow.
The responding party disputes the characterization of events as presented by the opposing side.

## Legal Arguments

### Argument 1: Standing and Jurisdiction

The court has jurisdiction over this matter pursuant to applicable law. The parties have properly submitted to the jurisdiction of this court.

### Argument 2: Response to Principal Claims

The responding party denies the principal claims as stated and asserts that the evidence supports a contrary conclusion.

### Argument 3: Applicable Legal Standards

Under the applicable legal standards, the burden of proof rests with the party making the affirmative claim. The responding party submits that this burden has not been met.

## Relief Requested

For the foregoing reasons, the responding party respectfully requests that the court:

1. Dismiss the claims in their entirety, or in the alternative;
2. Grant such other relief as the court deems just and proper.

## Conclusion

The responding party respectfully submits this response and requests that the court accept and consider it in full.

*[This draft was generated automatically. Please review and edit before submission.]*
"""

    async def _get_existing_draft(
        self, db: AsyncSession, workflow_id: int
    ) -> Optional[DBLegalDraft]:
        result = await db.execute(
            select(DBLegalDraft)
            .where(DBLegalDraft.workflow_id == workflow_id)
            .order_by(DBLegalDraft.version.desc(), DBLegalDraft.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()


legal_drafting_service = LegalDraftingService()
