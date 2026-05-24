"""Build AI analysis payload for Smart Collections (shared by pipeline and backfill)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.services.document_intelligence import document_intelligence_service
from app.services.metadata_extraction import metadata_extraction_service


async def build_ai_analysis_for_collections(
    content: str,
    filename: str,
    *,
    language: Optional[str] = None,
    run_llm: bool = True,
) -> Dict[str, Any]:
    """Run intelligence + regex routing merge (same as pipeline / bulk backfill)."""
    if run_llm:
        from app.services.document_chunker import document_chunker

        chunks = document_chunker.chunk_document(content or "")
        ai_analysis = await document_intelligence_service.analyze_document(
            content,
            filename,
            language=language,
            chunks=chunks if chunks else None,
        )
        ai_analysis.pop("_chunk_partials", None)
    else:
        ai_analysis = {}

    if not isinstance(ai_analysis, dict):
        ai_analysis = {}

    try:
        regex_meta = await metadata_extraction_service.extract_metadata(
            content or "", language or "en"
        )
        if not ai_analysis.get("parties"):
            ai_analysis["parties"] = regex_meta.get("entities", [])
        if not ai_analysis.get("key_dates") and not ai_analysis.get("dates"):
            ai_analysis["key_dates"] = regex_meta.get("dates", [])
        if not ai_analysis.get("financial_terms") and not ai_analysis.get("amounts"):
            ai_analysis["financial_terms"] = regex_meta.get("amounts", [])
        if not ai_analysis.get("case_numbers"):
            ai_analysis["case_numbers"] = regex_meta.get("case_numbers", [])
        ai_analysis["routing_ids"] = regex_meta.get("routing_ids", []) or []
        ai_analysis["routing_projects"] = regex_meta.get("routing_projects", []) or []
        ai_analysis["routing_organizations"] = regex_meta.get("routing_organizations", []) or []
    except Exception:
        ai_analysis.setdefault("routing_ids", [])
        ai_analysis.setdefault("routing_projects", [])
        ai_analysis.setdefault("routing_organizations", [])

    return ai_analysis


def classification_from_analysis(ai_analysis: Dict[str, Any]) -> str:
    doc_type = (ai_analysis.get("document_type") or "").strip()
    if doc_type and doc_type.lower() not in ("unknown", "unclassified", ""):
        return doc_type
    legacy = (ai_analysis.get("classification") or "").strip()
    if legacy:
        return legacy
    return "Unknown"
