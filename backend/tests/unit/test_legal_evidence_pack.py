from types import SimpleNamespace
import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[2] / "app" / "services" / "legal_evidence_pack.py"
spec = importlib.util.spec_from_file_location("legal_evidence_pack", MODULE_PATH)
legal_evidence_pack = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = legal_evidence_pack
spec.loader.exec_module(legal_evidence_pack)

MAX_EXCERPT_CHARS = legal_evidence_pack.MAX_EXCERPT_CHARS
MAX_EXCERPTS = legal_evidence_pack.MAX_EXCERPTS
LegalEvidencePackBuilder = legal_evidence_pack.LegalEvidencePackBuilder


def test_source_excerpts_are_capped_and_keep_references():
    builder = LegalEvidencePackBuilder()
    chunks = [
        SimpleNamespace(
            document_id=9,
            chunk_index=index,
            page_number=index + 1,
            text_content=f"Plaintiff alleges breach and damages on 2025-01-{index:02d}. " + ("x" * 1500),
        )
        for index in range(20)
    ]

    excerpts = builder.select_source_excerpts(
        chunks=chunks,
        document=None,
        parties=[{"name": "Plaintiff"}],
        dates=[{"date": "2025-01-01"}],
        amounts=[],
        claims=["breach"],
        risks=["damages"],
    )

    assert len(excerpts) == MAX_EXCERPTS
    assert all(len(excerpt.text) <= MAX_EXCERPT_CHARS for excerpt in excerpts)
    assert all(excerpt.document_id == 9 for excerpt in excerpts)
    assert all(excerpt.page_number is not None for excerpt in excerpts)
    assert all(excerpt.chunk_index is not None for excerpt in excerpts)
    assert {excerpt.chunk_index for excerpt in excerpts}


def test_source_excerpts_fallback_to_capped_document_content():
    builder = LegalEvidencePackBuilder()
    document = SimpleNamespace(id=33, content="Important fallback OCR text. " + ("y" * 2000))

    excerpts = builder.select_source_excerpts(
        chunks=[],
        document=document,
        parties=[],
        dates=[],
        amounts=[],
        claims=[],
        risks=[],
    )

    assert len(excerpts) == 1
    assert excerpts[0].document_id == 33
    assert excerpts[0].reason == "fallback OCR excerpt"
    assert len(excerpts[0].text) <= MAX_EXCERPT_CHARS
