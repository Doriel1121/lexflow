from typing import Dict, List, Any, Optional
import asyncio
import logging

from app.core.config import settings
from app.core.ai_router import AIIntent, AIRiskLevel, AITask, AITaskContext, ai_router
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.analysis_merge import merge_analyses
from app.services.ai_quota import enforce_ai_quota
from app.services.ai_usage_logger import track_ai_call

logger = logging.getLogger(__name__)

CHUNK_PARTIAL_SCHEMA = """
{
  "document_type": "string or empty",
  "parties": [{"name": "string", "role": "string", "id_number": "string or null", "contact": "string or null"}],
  "attorneys": [{"name": "string", "firm": "string", "representing": "string", "bar_number": "string or null"}],
  "key_dates": [{"date": "YYYY-MM-DD", "description": "string", "type": "hearing|filing|response|appeal|statute_of_limitations|other", "is_critical_deadline": true}],
  "financial_terms": [{"amount": "string", "currency": "string", "description": "string", "payer": "string or null", "payee": "string or null"}],
  "case_numbers": ["string"],
  "obligations": [{"party": "string", "obligation": "string", "deadline": "string or null"}],
  "key_clauses": [{"type": "string", "summary": "string"}],
  "risks": ["string"],
  "missing_items": ["string"],
  "tags": ["string (max 5 specific tags from this section ONLY: document-specific keywords, clause types, risk categories, or key concepts - NOT generic words like 'document', 'legal', 'agreement')"],
  "summary": "1-2 sentences for THIS section only"
}
"""

class DocumentIntelligenceService:
    def __init__(self):
        pass

    def _reader_provider(
        self,
        *,
        feature: str,
        intent: AIIntent,
        language: Optional[str],
        input_chars: int,
        risk_level: AIRiskLevel = AIRiskLevel.MEDIUM,
        requires_citations: bool = False,
    ):
        return ai_router.provider_for(
            AITask.READER,
            AITaskContext(
                task=AITask.READER,
                feature=feature,
                intent=intent,
                language=language or "",
                input_chars=input_chars,
                risk_level=risk_level,
                requires_citations=requires_citations,
            ),
        )

    def _language_instruction(self, language: Optional[str], text: str) -> str:
        lang = (language or "").lower()
        if lang.startswith("he") or any("\u0590" <= ch <= "\u05FF" for ch in text[:2000]):
            return "You MUST answer in Hebrew."
        if lang.startswith("ar"):
            return "You MUST answer in Arabic."
        if lang.startswith("ru"):
            return "You MUST answer in Russian."
        if lang.startswith("es"):
            return "You MUST answer in Spanish."
        if lang.startswith("fr"):
            return "You MUST answer in French."
        return "You MUST answer in the same language as the document."

    def _clean_and_limit_tags(self, tags: Any) -> List[str]:
        """Clean, deduplicate, and limit tags to max 5-7 relevant ones."""
        if not tags:
            return []

        # Ensure tags is a list
        if not isinstance(tags, list):
            return []

        # Generic/low-quality tags to filter out
        generic_tags = {
            'document', 'legal', 'agreement', 'contract', 'file', 'page',
            'text', 'content', 'document agreement', 'legal document',
            'other', 'miscellaneous', 'general', 'unknown', 'todo',
            'document type', 'section', 'undefined', 'pending',
        }

        cleaned = set()
        for tag in tags:
            if not isinstance(tag, str):
                continue

            tag = tag.strip()
            if not tag:  # Skip empty tags
                continue

            # Skip tags that are too short or too long
            if len(tag) < 3 or len(tag) > 50:
                continue

            # Skip generic tags (case-insensitive)
            if tag.lower() in generic_tags:
                continue

            # Skip tags that are only punctuation/numbers
            if not any(c.isalpha() for c in tag):
                continue

            cleaned.add(tag)

        # Convert back to list and limit to 5-7 tags
        result = list(cleaned)
        max_tags = 7
        if len(result) > max_tags:
            # If we have too many, keep only the first max_tags (preserves AI priority ordering)
            result = result[:max_tags]

        return sorted(result)  # Return sorted for consistency

    def should_use_chunked_analysis(self, text_length: int) -> bool:
        threshold = settings.AI_LONG_DOCUMENT_THRESHOLD_CHARS or 25000
        return text_length > threshold

    async def analyze_chunk(
        self,
        chunk_text: str,
        *,
        filename: str,
        chunk_index: int,
        total_chunks: int,
        page_number: Optional[int] = None,
        language: Optional[str] = None,
        db: Optional[AsyncSession] = None,
        organization_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Extract structured data from a single document section."""
        provider = self._reader_provider(
            feature="document_intelligence",
            intent=AIIntent.DOCUMENT_ANALYSIS,
            language=language,
            input_chars=len(chunk_text or ""),
            risk_level=AIRiskLevel.MEDIUM,
        )
        if not provider.active or not (chunk_text or "").strip():
            return {}

        lang_hint = self._language_instruction(language, chunk_text)
        page_hint = f"Page: {page_number}" if page_number else "Page: unknown"
        prompt = f"""Analyze this SECTION of a legal document. Extract only what appears in this section.

Document file: {filename}
Section {chunk_index + 1} of {total_chunks}
{page_hint}

Section text:
{chunk_text}

Language requirement: {lang_hint}

Return ONLY valid JSON matching this structure (use empty arrays when nothing found):
{CHUNK_PARTIAL_SCHEMA}

Party rule: include only primary legal/contract parties if this section identifies them. Do not list witnesses, guarantors, attorneys, family members, banks, municipalities, addresses, or generic role labels as parties.

Return ONLY JSON."""

        timeout = float(settings.AI_CHUNK_ANALYSIS_TIMEOUT_SECONDS or 90)
        try:
            await enforce_ai_quota(
                db,
                organization_id=organization_id,
                task_type="reader.chunk_analysis",
                input_chars=len(prompt or ""),
            )
            async with track_ai_call(
                db,
                organization_id=organization_id,
                task_type="reader.chunk_analysis",
                provider=provider,
                input_text=prompt,
            ) as usage:
                result = await asyncio.wait_for(
                    provider.generate_json(prompt),
                    timeout=timeout,
                )
                usage["output_chars"] = len(str(result)) if result is not None else 0
        except Exception as e:
            logger.warning(
                "Chunk %s/%s analysis failed for '%s': %s",
                chunk_index + 1,
                total_chunks,
                filename,
                e,
            )
            return {}

        return result if isinstance(result, dict) else {}

    async def analyze_document_chunked(
        self,
        chunks: List[Dict[str, Any]],
        filename: str,
        language: Optional[str] = None,
        *,
        document_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """Per-chunk analysis with bounded concurrency + deterministic merge."""
        max_chunks = settings.AI_CHUNK_ANALYSIS_MAX_CHUNKS or 40
        to_analyze = chunks[:max_chunks]
        partials: List[Dict[str, Any]] = []

        from app.services.processing_telemetry import track_stage

        concurrency = int(getattr(settings, "AI_CHUNK_ANALYSIS_CONCURRENCY", 3) or 3)
        concurrency = max(1, min(concurrency, 8))
        sem = asyncio.Semaphore(concurrency)

        async def _run_one(item: Dict[str, Any]) -> Dict[str, Any]:
            idx = item.get("index")
            if idx is None:
                idx = 0
            async with sem:
                async with track_stage(
                    document_id or 0,
                    organization_id,
                    "ai_chunk",
                    chunk_index=idx,
                    total_chunks=len(to_analyze),
                    filename=filename,
                ):
                    partial = await self.analyze_chunk(
                        item.get("text") or "",
                        filename=filename,
                        chunk_index=idx,
                        total_chunks=len(to_analyze),
                        page_number=item.get("page_number"),
                        language=language,
                        db=db,
                        organization_id=organization_id,
                    )
            if isinstance(partial, dict) and partial:
                partial["_chunk_index"] = idx
                return partial
            return {}

        # Run concurrently but keep deterministic merge ordering by _chunk_index.
        results = await asyncio.gather(*[_run_one(item) for item in to_analyze])
        for r in results:
            if r:
                partials.append(r)
        partials.sort(key=lambda p: int(p.get("_chunk_index", 0)))

        if not partials:
            return self._fallback_analysis("", filename)

        merged = merge_analyses(partials, filename)
        merged["analysis_mode"] = "chunked"
        merged["chunks_analyzed"] = len(partials)
        merged["chunks_total"] = len(chunks)
        if len(chunks) > max_chunks:
            merged["chunks_truncated"] = True
        merged["_chunk_partials"] = partials

        # Clean and limit tags after merge
        if "tags" in merged and merged["tags"]:
            merged["tags"] = self._clean_and_limit_tags(merged["tags"])
        else:
            merged["tags"] = []

        return merged

    async def analyze_document(
        self,
        text: str,
        filename: str,
        language: Optional[str] = None,
        *,
        chunks: Optional[List[Dict[str, Any]]] = None,
        force_single_pass: bool = False,
        document_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        Choose single-pass or chunked analysis based on document size.
        When chunked, `chunks` should be the output of document_chunker.chunk_document.
        """
        if (
            not force_single_pass
            and chunks
            and self.should_use_chunked_analysis(len(text))
        ):
            logger.info(
                "Using chunked analysis for '%s' (%s chars, %s chunks)",
                filename,
                len(text),
                len(chunks),
            )
            return await self.analyze_document_chunked(
                chunks,
                filename,
                language,
                document_id=document_id,
                organization_id=organization_id,
                db=db,
            )

        result = await self.analyze_legal_document(text, filename, language, db=db, organization_id=organization_id)
        if isinstance(result, dict):
            result["analysis_mode"] = "full"
        return result

    async def analyze_legal_document(
        self,
        text: str,
        filename: str,
        language: Optional[str] = None,
        *,
        db: Optional[AsyncSession] = None,
        organization_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Comprehensive legal document analysis extracting all critical information
        """
        provider = self._reader_provider(
            feature="document_intelligence",
            intent=AIIntent.DOCUMENT_ANALYSIS,
            language=language,
            input_chars=len(text or ""),
            risk_level=AIRiskLevel.MEDIUM,
        )
        if not provider.active:
            return self._fallback_analysis(text, filename)
        lang_hint = self._language_instruction(language, text)
        prompt = f"""Analyze this legal document and extract ALL relevant information in JSON format.

Document: {filename}
Content: {text}

Language requirement: {lang_hint}

Extract and return ONLY valid JSON with this exact structure:
{{
  "document_type": "string (e.g., Contract, NDA, Complaint, Motion, Lease, etc.)",
  "document_subtype": "string (specific type like Employment Agreement, Purchase Agreement)",
  "jurisdiction": "string (court, state, or country)",
  "parties": [
    {{"name": "string", "role": "string (e.g., Plaintiff, Defendant, Buyer, Seller)", "id_number": "string or null (ID, passport, tax ID)", "contact": "string or null"}}
  ],
  "attorneys": [
    {{"name": "string", "firm": "string", "representing": "string", "bar_number": "string or null"}}
  ],
  "key_dates": [
    {{
      "date": "YYYY-MM-DD",
      "description": "string (the semantic reason for this date, e.g., 'Last day to file response to motion')",
      "type": "string (hearing, filing, response, appeal, statute_of_limitations, other)",
      "is_critical_deadline": "boolean (true if this is a date a lawyer must not miss)"
    }}
  ],
  "financial_terms": [
    {{"amount": "string", "currency": "string", "description": "string (what this amount represents)", "payer": "string or null", "payee": "string or null"}}
  ],
  "case_numbers": ["string"],
  "obligations": [
    {{"party": "string", "obligation": "string", "deadline": "string or null"}}
  ],
  "key_clauses": [
    {{"type": "string (e.g., arbitration, jurisdiction, termination)", "summary": "string"}}
  ],
  "risks": ["string"],
  "missing_items": ["string"],
  "related_documents": ["string"],
  "summary": "string (2-3 sentence executive summary)",
  "tags": ["string (EXACTLY 5-7 specific tags: use document-specific keywords like clause types, key obligations, risk categories, party types, or jurisdictions. Examples: 'Non-Compete', 'IP Assignment', 'Termination Fee', 'Governing Law - NY', 'Automatic Renewal'. DO NOT use generic tags like 'document', 'legal', 'agreement', 'contract', 'file' or single-word vague terms)"]
}}

IMPORTANT:
- For parties: Extract ONLY the primary legal/contract parties to this document, exactly as written, with their roles and ANY identification numbers. For agreements, these are usually the named sides in the opening/caption/signature block, such as landlord/tenant, seller/buyer, employer/employee. Do NOT include guarantors, witnesses, family members, attorneys, municipalities, banks, contacts, addresses, account holders, or other mentioned entities unless the document explicitly defines them as a main party. If labels like Landlord/Tenant appear, put the label in role and the adjacent actual person/company name in name; do not use the generic label as the name.
- For financial_terms: ALWAYS include description of what the amount represents (e.g., "Purchase price", "Monthly rent", "Penalty fee")
- For financial_terms: Include who pays (payer) and who receives (payee) if mentioned
- For tags: Generate EXACTLY 5-7 tags maximum. Each tag must be specific and meaningful (not generic). Examples of GOOD tags: 'Non-Compete', 'IP Rights', 'Severance', 'Arbitration Clause'. Examples of BAD tags: 'agreement', 'legal', 'document', 'section'.
- Be thorough and extract ALL information found. If a field has no data, use empty array [] or empty string "" or null.
Return ONLY the JSON, no other text."""
        try:
            await enforce_ai_quota(
                db,
                organization_id=organization_id,
                task_type="reader.document_analysis",
                input_chars=len(prompt or ""),
            )
            async with track_ai_call(
                db,
                organization_id=organization_id,
                task_type="reader.document_analysis",
                provider=provider,
                input_text=prompt,
            ) as usage:
                result = await asyncio.wait_for(
                    provider.generate_json(prompt),
                    timeout=float(settings.AI_ANALYSIS_TIMEOUT_SECONDS or 120),
                )
                usage["output_chars"] = len(str(result)) if result is not None else 0
        except asyncio.TimeoutError:
            logger.error("AI analysis timed out for document '%s'. Falling back.", filename)
            return self._fallback_analysis(text, filename)
        except Exception as e:
            logger.error("AI analysis error for document '%s': %s. Falling back.", filename, e)
            return self._fallback_analysis(text, filename)

        if not result:
            # If it's literally empty, use fallback
            return self._fallback_analysis(text, filename)

        # Ensure result is a dict (json.loads can return a string if JSON is a plain string)
        if not isinstance(result, dict):
            logger.warning(
                "AI analyze_legal_document returned non-dict type %s. Using fallback.",
                type(result).__name__,
            )
            return self._fallback_analysis(text, filename)

        # Clean and limit tags
        if "tags" in result and result["tags"]:
            result["tags"] = self._clean_and_limit_tags(result["tags"])
        else:
            result["tags"] = []

        return result

    def _fallback_analysis(self, text: str, filename: str) -> Dict[str, Any]:
        """Fallback when AI is unavailable"""
        return {
            "document_type": "Unknown",
            "document_subtype": "",
            "jurisdiction": "",
            "parties": [],
            "attorneys": [],
            "key_dates": [],
            "financial_terms": [],
            "case_numbers": [],
            "obligations": [],
            "key_clauses": [],
            "risks": [],
            "missing_items": [],
            "related_documents": [],
            "summary": f"Document: {filename} ({len(text)} characters)",
            "tags": ["unprocessed"]
        }

document_intelligence_service = DocumentIntelligenceService()
