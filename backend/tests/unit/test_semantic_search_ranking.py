from types import SimpleNamespace

from app.api.v1.endpoints.documents import _dedupe_ranked_documents


def test_dedupe_ranked_documents_keeps_best_document_order():
    doc_a = SimpleNamespace(id=1)
    doc_b = SimpleNamespace(id=2)
    doc_c = SimpleNamespace(id=3)

    rows = [
        (doc_a, "best chunk for a", 0.12),
        (doc_a, "second chunk for a", 0.15),
        (doc_b, "best chunk for b", 0.2),
        (doc_a, "third chunk for a", 0.3),
        (doc_c, "best chunk for c", 0.4),
    ]

    assert _dedupe_ranked_documents(rows, limit=3) == [doc_a, doc_b, doc_c]


def test_dedupe_ranked_documents_respects_limit():
    doc_a = SimpleNamespace(id=1)
    doc_b = SimpleNamespace(id=2)

    rows = [
        (doc_a, "best chunk for a", 0.12),
        (doc_b, "best chunk for b", 0.2),
    ]

    assert _dedupe_ranked_documents(rows, limit=1) == [doc_a]
