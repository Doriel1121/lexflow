"""Deterministic merge of per-chunk legal analysis partials (map-reduce reduce step)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _norm_str(value: Any) -> str:
    return (str(value or "")).strip()


def _party_key(party: Any) -> str:
    if isinstance(party, dict):
        return _norm_str(party.get("name")).lower()
    return _norm_str(party).lower()


def _date_key(item: Any) -> str:
    if isinstance(item, dict):
        return f"{_norm_str(item.get('date'))}|{_norm_str(item.get('description'))}".lower()
    return _norm_str(item).lower()


def _dedupe_list(items: List[Any], key_fn) -> List[Any]:
    seen, out = set(), []
    for item in items or []:
        key = key_fn(item)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _dedupe_strings(items: List[Any]) -> List[str]:
    seen, out = set(), []
    for item in items or []:
        s = _norm_str(item if not isinstance(item, dict) else item.get("name") or item.get("amount"))
        if s and s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out


def _pick_document_type(partials: List[Dict[str, Any]]) -> str:
    for partial in partials:
        doc_type = _norm_str(partial.get("document_type"))
        if doc_type and doc_type.lower() not in ("unknown", "unclassified", ""):
            return doc_type
    for partial in partials:
        doc_type = _norm_str(partial.get("document_type"))
        if doc_type:
            return doc_type
    return "Unknown"


def _merge_summaries(partials: List[Dict[str, Any]], filename: str) -> str:
    parts = []
    for partial in partials:
        s = _norm_str(partial.get("summary"))
        if s and s not in parts:
            parts.append(s)
    if not parts:
        return f"Document: {filename} (multi-section analysis)"
    if len(parts) == 1:
        return parts[0]
    return " ".join(parts[:5])[:4000]


def merge_analyses(partials: List[Dict[str, Any]], filename: str = "") -> Dict[str, Any]:
    """
    Merge chunk-level partial JSON analyses into one document-level result.
    """
    valid = [p for p in (partials or []) if isinstance(p, dict)]
    if not valid:
        return {}

    merged: Dict[str, Any] = {
        "document_type": _pick_document_type(valid),
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
        "summary": _merge_summaries(valid, filename),
        "tags": [],
        "analysis_mode": "chunked",
        "chunks_analyzed": len(valid),
    }

    for partial in valid:
        if not merged["document_subtype"]:
            merged["document_subtype"] = _norm_str(partial.get("document_subtype"))
        if not merged["jurisdiction"]:
            merged["jurisdiction"] = _norm_str(partial.get("jurisdiction"))

        merged["parties"].extend(partial.get("parties") or [])
        merged["attorneys"].extend(partial.get("attorneys") or [])
        merged["key_dates"].extend(partial.get("key_dates") or [])
        merged["financial_terms"].extend(partial.get("financial_terms") or [])
        merged["case_numbers"].extend(partial.get("case_numbers") or [])
        merged["obligations"].extend(partial.get("obligations") or [])
        merged["key_clauses"].extend(partial.get("key_clauses") or [])
        merged["risks"].extend(partial.get("risks") or [])
        merged["missing_items"].extend(partial.get("missing_items") or [])
        merged["related_documents"].extend(partial.get("related_documents") or [])
        merged["tags"].extend(partial.get("tags") or [])

    merged["parties"] = _dedupe_list(merged["parties"], _party_key)
    merged["attorneys"] = _dedupe_list(
        merged["attorneys"],
        lambda a: _norm_str(a.get("name") if isinstance(a, dict) else a).lower(),
    )
    merged["key_dates"] = _dedupe_list(merged["key_dates"], _date_key)
    merged["financial_terms"] = _dedupe_list(
        merged["financial_terms"],
        lambda f: _norm_str(f.get("amount") if isinstance(f, dict) else f).lower()
        + "|"
        + _norm_str(f.get("description") if isinstance(f, dict) else ""),
    )
    merged["case_numbers"] = _dedupe_strings(merged["case_numbers"])
    merged["obligations"] = _dedupe_list(
        merged["obligations"],
        lambda o: (
            _norm_str(o.get("party") if isinstance(o, dict) else "")
            + "|"
            + _norm_str(o.get("obligation") if isinstance(o, dict) else "")
        ).lower(),
    )
    merged["key_clauses"] = _dedupe_list(
        merged["key_clauses"],
        lambda c: _norm_str(c.get("type") if isinstance(c, dict) else c).lower(),
    )
    merged["risks"] = _dedupe_strings(merged["risks"])
    merged["missing_items"] = _dedupe_strings(merged["missing_items"])
    merged["related_documents"] = _dedupe_strings(merged["related_documents"])
    merged["tags"] = _dedupe_strings(merged["tags"])

    return merged
