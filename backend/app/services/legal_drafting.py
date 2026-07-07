"""
legal_drafting.py
=================
Generates AI-drafted legal response documents for the workflow engine.

Input: source document OCR text, document intelligence analysis, case metadata,
       optional deadlines, and workflow metadata instructions.

Output: A TipTap/ProseMirror JSON document stored as a LegalDraft row.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ai_router import AITask, ai_router
from app.core.legal_workflow_constants import LegalDraftStatus
from app.services.ai_usage_logger import track_ai_call
from app.crud.legal_workflow import legal_workflow_crud
from app.db.models.case import Case as DBCase
from app.db.models.document import Document as DBDocument
from app.db.models.legal_workflow import LegalDraft as DBLegalDraft, LegalWorkflow as DBLegalWorkflow
from app.schemas.legal_workflow import LegalDraftCreate

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
        self.provider = ai_router.provider_for(AITask.DRAFTING)
        self.collector = DraftInputCollector()

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
        if not self.provider or not getattr(self.provider, "active", False):
            logger.warning("AI provider inactive – returning structured placeholder draft.")
            return self._placeholder_draft(context)

        prompt = self._build_prompt(context, instructions)

        try:
            async with track_ai_call(
                db,
                organization_id=context.get("organization_id"),
                task_type="drafting.legal_response",
                provider=self.provider,
                input_text=prompt,
            ) as usage:
                result = await asyncio.wait_for(
                    self.provider.generate_text(prompt),
                    timeout=120.0,
                )
                usage["output_chars"] = len(result or "")
            if result:
                return result.strip()
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
        Construct the legal drafting prompt from gathered context.
        """
        jurisdiction = context.get("workflow_metadata", {}).get("jurisdiction", "")
        court_profile = context.get("workflow_metadata", {}).get("court_profile", {})
        analysis = context.get("document_analysis", {})
        deadlines = context.get("deadlines", [])

        # Summarize analysis fields
        parties = analysis.get("parties", [])
        party_names = ", ".join(
            p.get("name", "") for p in parties if isinstance(p, dict)
        ) if parties else "Unknown parties"

        doc_type = analysis.get("document_type", "Legal Document")
        doc_summary = analysis.get("summary", "")
        obligations = analysis.get("obligations", [])
        risks = analysis.get("risks", [])

        # Format deadlines
        deadline_lines = "\n".join(
            f"  - {d.get('date', 'TBD')}: {d.get('description', d.get('type', ''))}"
            for d in deadlines[:5]
        ) if deadlines else "  (none specified)"

        # Format obligations
        obligation_lines = "\n".join(
            f"  - {o.get('party', '')}: {o.get('obligation', '')}"
            for o in obligations[:5]
        ) if obligations else "  (none identified)"

        # Format risks
        risk_lines = "\n".join(f"  - {r}" for r in risks[:5]) if risks else "  (none identified)"

        ocr_excerpt = (context.get("ocr_text") or "")[:3000]

        extra_instructions = ""
        if instructions:
            extra_instructions = f"\n\nAdditional Instructions from the supervising lawyer:\n{instructions}\n"

        prompt = f"""You are a senior Israeli litigation attorney drafting a formal legal response document.

CASE INFORMATION
================
Case Title: {context.get('case_title', 'Unknown Case')}
Case Description: {context.get('case_description', '')}
Source Document Type: {doc_type}
Parties: {party_names}
Jurisdiction: {jurisdiction or 'Israel'}

DOCUMENT SUMMARY
================
{doc_summary or 'No summary available.'}

KEY DEADLINES
=============
{deadline_lines}

OBLIGATIONS
===========
{obligation_lines}

IDENTIFIED RISKS
================
{risk_lines}

SOURCE DOCUMENT TEXT (first 3000 chars)
========================================
{ocr_excerpt or '(no OCR text available)'}

{extra_instructions}

DRAFTING INSTRUCTIONS
=====================
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
- Do not include placeholder instructions; write the actual substantive content.
- Output ONLY the document text, no preamble or explanation.
"""
        return prompt

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
