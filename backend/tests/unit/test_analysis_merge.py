import pytest

from app.services.analysis_merge import merge_analyses


def test_merge_dedupes_parties_and_dates():
    partials = [
        {
            "document_type": "Contract",
            "parties": [{"name": "Alice Corp", "role": "Buyer"}],
            "key_dates": [{"date": "2026-06-01", "description": "Closing", "type": "filing"}],
            "summary": "Section one.",
            "tags": ["real estate"],
        },
        {
            "document_type": "Contract",
            "parties": [{"name": "Alice Corp", "role": "Buyer"}, {"name": "Bob LLC", "role": "Seller"}],
            "key_dates": [{"date": "2026-06-01", "description": "Closing", "type": "filing"}],
            "summary": "Section two.",
            "tags": ["purchase"],
        },
    ]
    merged = merge_analyses(partials, "deal.pdf")
    assert merged["document_type"] == "Contract"
    assert len(merged["parties"]) == 2
    assert len(merged["key_dates"]) == 1
    assert merged["analysis_mode"] == "chunked"
    assert "Section one" in merged["summary"]


def test_merge_empty_returns_empty_dict():
    assert merge_analyses([]) == {}
