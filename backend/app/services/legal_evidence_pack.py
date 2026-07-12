"""Build compact, source-backed evidence packs for legal drafting."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

MAX_EXCERPTS = 10
MAX_EXCERPT_CHARS = 1000
MAX_NORMALIZED_ITEMS = 12


@dataclass
class SourceExcerpt:
    text: str
    document_id: int
    page_number: Optional[int] = None
    chunk_index: Optional[int] = None
    reason: str = "relevant source excerpt"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LegalEvidencePack:
    case: Dict[str, Any]
    source_document: Dict[str, Any]
    parties: List[Any] = field(default_factory=list)
    claims: List[str] = field(default_factory=list)
    key_facts: List[str] = field(default_factory=list)
    dates: List[Any] = field(default_factory=list)
    amounts: List[Any] = field(default_factory=list)
    obligations: List[Any] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    missing_items: List[str] = field(default_factory=list)
    source_excerpts: List[SourceExcerpt] = field(default_factory=list)
    drafting_instructions: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["source_excerpts"] = [excerpt.to_dict() for excerpt in self.source_excerpts]
        return data


class LegalEvidencePackBuilder:
    """Create a just-in-time evidence pack from workflow, document metadata, and chunks."""

    async def build_for_workflow(
        self,
        db: Any,
        workflow: Any,
        drafting_instructions: Optional[str] = None,
    ) -> LegalEvidencePack:
        case = await self._get_case(db, workflow.case_id)
        document = await self._get_document(db, workflow.source_document_id)
        summary = await self._get_summary(db, workflow.source_document_id)
        metadata = await self._get_metadata(db, workflow.source_document_id)
        chunks = await self._get_chunks(db, workflow.source_document_id)

        analysis = self._analysis_from_document_records(document, summary, metadata)
        instructions = drafting_instructions
        if instructions is None:
            instructions = (workflow.metadata_json or {}).get("drafting_instructions")

        source_document = {
            "id": document.id if document else workflow.source_document_id,
            "filename": document.filename if document else "",
            "document_type": self._first_text(
                analysis.get("document_type"),
                analysis.get("classification"),
                document.classification if document else None,
                "Legal Document",
            ),
            "summary": self._first_text(
                analysis.get("summary"),
                summary.content if summary else None,
                "",
            ),
            "language": document.language if document else None,
            "page_count": document.page_count if document else None,
        }

        parties = self._normalize_parties(analysis.get("parties") or analysis.get("entities"))
        dates = self._normalize_dates(analysis.get("key_dates") or analysis.get("dates"))
        amounts = self._normalize_amounts(analysis.get("financial_terms") or analysis.get("amounts"))
        obligations = self._normalize_obligations(analysis.get("obligations"))
        risks = self._normalize_strings(analysis.get("risks"))
        missing_items = self._normalize_strings(
            analysis.get("missing_items") or analysis.get("missing_documents")
        )
        claims = self._normalize_strings(
            analysis.get("claims") or analysis.get("allegations") or analysis.get("legal_claims")
        )
        key_facts = self._build_key_facts(analysis, summary)

        excerpts = self.select_source_excerpts(
            chunks=chunks,
            document=document,
            parties=parties,
            dates=dates,
            amounts=amounts,
            claims=claims,
            risks=risks,
        )

        return LegalEvidencePack(
            case={
                "id": case.id if case else workflow.case_id,
                "title": case.title if case else "",
                "description": case.description if case else "",
            },
            source_document=source_document,
            parties=parties,
            claims=claims,
            key_facts=key_facts,
            dates=dates,
            amounts=amounts,
            obligations=obligations,
            risks=risks,
            missing_items=missing_items,
            source_excerpts=excerpts,
            drafting_instructions=instructions,
        )

    async def _get_case(self, db: Any, case_id: Optional[int]) -> Optional[Any]:
        if not case_id:
            return None
        from sqlalchemy import select
        from app.db.models.case import Case as DBCase

        result = await db.execute(select(DBCase).where(DBCase.id == case_id))
        return result.scalars().first()

    async def _get_document(self, db: Any, document_id: Optional[int]) -> Optional[Any]:
        if not document_id:
            return None
        from sqlalchemy import select
        from app.db.models.document import Document as DBDocument

        result = await db.execute(select(DBDocument).where(DBDocument.id == document_id))
        return result.scalars().first()

    async def _get_summary(self, db: Any, document_id: Optional[int]) -> Optional[Any]:
        if not document_id:
            return None
        from sqlalchemy import select
        from app.db.models.summary import Summary

        result = await db.execute(select(Summary).where(Summary.document_id == document_id))
        return result.scalars().first()

    async def _get_metadata(self, db: Any, document_id: Optional[int]) -> Optional[Any]:
        if not document_id:
            return None
        from sqlalchemy import select
        from app.db.models.document_metadata import DocumentMetadata

        result = await db.execute(select(DocumentMetadata).where(DocumentMetadata.document_id == document_id))
        return result.scalars().first()

    async def _get_chunks(self, db: Any, document_id: Optional[int]) -> List[Any]:
        if not document_id:
            return []
        from sqlalchemy import select
        from app.db.models.document import DocumentChunk

        result = await db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
        return list(result.scalars().all())

    def _analysis_from_document_records(
        self,
        document: Optional[Any],
        summary: Optional[Any],
        metadata: Optional[Any],
    ) -> Dict[str, Any]:
        analysis: Dict[str, Any] = {}
        if metadata:
            legacy_analysis = getattr(metadata, "analysis_json", None)
            if isinstance(legacy_analysis, dict):
                analysis.update(legacy_analysis)
            analysis.setdefault("dates", metadata.dates or [])
            analysis.setdefault("entities", metadata.entities or [])
            analysis.setdefault("amounts", metadata.amounts or [])
            analysis.setdefault("case_numbers", metadata.case_numbers or [])
            analysis.setdefault("classification", metadata.classification_category)
        if summary:
            analysis.setdefault("summary", summary.content)
            analysis.setdefault("key_dates", summary.key_dates or [])
            analysis.setdefault("parties", summary.parties or [])
            if summary.missing_documents_suggestion:
                analysis.setdefault(
                    "missing_documents",
                    [line.strip() for line in summary.missing_documents_suggestion.splitlines() if line.strip()],
                )
        if document:
            analysis.setdefault("classification", document.classification)
        return analysis

    def select_source_excerpts(
        self,
        *,
        chunks: Sequence[Any],
        document: Optional[Any],
        parties: Sequence[Any],
        dates: Sequence[Any],
        amounts: Sequence[Any],
        claims: Sequence[str],
        risks: Sequence[str],
    ) -> List[SourceExcerpt]:
        scored: List[tuple[int, int, Any, List[str]]] = []
        search_terms = self._search_terms(parties, dates, amounts, claims, risks)
        for order, chunk in enumerate(chunks):
            text = self._clean_text(getattr(chunk, "text_content", ""))
            if not text:
                continue
            score = 0
            reasons: List[str] = []
            if order == 0:
                score += 2
                reasons.append("opening context")
            lower_text = text.lower()
            for term, reason in search_terms:
                if term and term.lower() in lower_text:
                    score += 3
                    if reason not in reasons:
                        reasons.append(reason)
            for keyword in self._claim_keywords():
                if keyword in lower_text:
                    score += 1
                    if "possible claims or defenses" not in reasons:
                        reasons.append("possible claims or defenses")
            if score > 0:
                scored.append((score, order, chunk, reasons or ["relevant context"]))

        if not scored and document and document.content:
            fallback = self._clean_text(document.content)
            if fallback:
                return [
                    SourceExcerpt(
                        text=self._truncate(fallback),
                        document_id=document.id,
                        reason="fallback OCR excerpt",
                    )
                ]

        scored.sort(key=lambda item: (-item[0], item[1]))
        excerpts: List[SourceExcerpt] = []
        seen_chunks = set()
        for _, _, chunk, reasons in scored:
            chunk_index = getattr(chunk, "chunk_index", None)
            if chunk_index in seen_chunks:
                continue
            seen_chunks.add(chunk_index)
            excerpts.append(
                SourceExcerpt(
                    text=self._truncate(getattr(chunk, "text_content", "")),
                    document_id=getattr(chunk, "document_id", document.id if document else 0),
                    page_number=getattr(chunk, "page_number", None),
                    chunk_index=chunk_index,
                    reason=", ".join(reasons[:3]),
                )
            )
            if len(excerpts) >= MAX_EXCERPTS:
                break
        return excerpts

    def _search_terms(
        self,
        parties: Sequence[Any],
        dates: Sequence[Any],
        amounts: Sequence[Any],
        claims: Sequence[str],
        risks: Sequence[str],
    ) -> List[tuple[str, str]]:
        terms: List[tuple[str, str]] = []
        for party in parties:
            name = party.get("name") if isinstance(party, dict) else party
            if isinstance(name, str) and name.strip():
                terms.append((name.strip(), "mentions party"))
        for date in dates:
            value = date.get("date") if isinstance(date, dict) else date
            if isinstance(value, str) and value.strip():
                terms.append((value.strip(), "supports date or deadline"))
        for amount in amounts:
            value = amount.get("amount") or amount.get("value") if isinstance(amount, dict) else amount
            if isinstance(value, str) and value.strip():
                terms.append((value.strip(), "supports amount"))
        for claim in list(claims)[:5]:
            if isinstance(claim, str) and claim.strip():
                terms.append((claim.strip()[:80], "supports claim"))
        for risk in list(risks)[:5]:
            if isinstance(risk, str) and risk.strip():
                terms.append((risk.strip()[:80], "supports risk"))
        return terms

    def _normalize_parties(self, value: Any) -> List[Any]:
        return self._normalize_items(value, preferred_keys=("name", "role", "id_number", "contact"))

    def _normalize_dates(self, value: Any) -> List[Any]:
        return self._normalize_items(value, preferred_keys=("date", "description", "type", "is_critical_deadline"))

    def _normalize_amounts(self, value: Any) -> List[Any]:
        return self._normalize_items(value, preferred_keys=("amount", "value", "currency", "description"))

    def _normalize_obligations(self, value: Any) -> List[Any]:
        return self._normalize_items(value, preferred_keys=("party", "obligation", "deadline"))

    def _normalize_items(self, value: Any, preferred_keys: Iterable[str]) -> List[Any]:
        items = value if isinstance(value, list) else ([value] if value else [])
        normalized: List[Any] = []
        seen = set()
        for item in items:
            if isinstance(item, dict):
                candidate = {key: item.get(key) for key in preferred_keys if item.get(key) not in (None, "", [])}
                if not candidate:
                    candidate = {key: val for key, val in item.items() if val not in (None, "", [])}
            elif isinstance(item, str):
                candidate = item.strip()
            else:
                candidate = item
            key = str(candidate).strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            normalized.append(candidate)
            if len(normalized) >= MAX_NORMALIZED_ITEMS:
                break
        return normalized

    def _normalize_strings(self, value: Any) -> List[str]:
        items = value if isinstance(value, list) else ([value] if value else [])
        normalized: List[str] = []
        seen = set()
        for item in items:
            text = item.get("description") if isinstance(item, dict) else item
            text = str(text or "").strip()
            if not text or text.lower() in seen:
                continue
            seen.add(text.lower())
            normalized.append(text)
            if len(normalized) >= MAX_NORMALIZED_ITEMS:
                break
        return normalized

    def _build_key_facts(self, analysis: Dict[str, Any], summary: Optional[Any]) -> List[str]:
        facts = self._normalize_strings(
            analysis.get("key_facts") or analysis.get("facts") or analysis.get("main_facts")
        )
        if facts:
            return facts[:8]
        summary_text = self._first_text(analysis.get("summary"), summary.content if summary else None)
        if not summary_text:
            return []
        sentences = [sentence.strip() for sentence in summary_text.replace("\n", " ").split(".") if sentence.strip()]
        return sentences[:5]

    def _claim_keywords(self) -> List[str]:
        return [
            "claim",
            "allegation",
            "breach",
            "damages",
            "relief",
            "lawsuit",
            "defendant",
            "plaintiff",
            "טענה",
            "תביעה",
            "הפרה",
            "נזק",
            "סעד",
            "נתבע",
            "תובע",
        ]

    def _clean_text(self, text: Any) -> str:
        return " ".join(str(text or "").split())

    def _truncate(self, text: Any) -> str:
        clean = self._clean_text(text)
        if len(clean) <= MAX_EXCERPT_CHARS:
            return clean
        return clean[: MAX_EXCERPT_CHARS - 1].rstrip() + "…"

    def _first_text(self, *values: Any) -> str:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""


legal_evidence_pack_builder = LegalEvidencePackBuilder()
