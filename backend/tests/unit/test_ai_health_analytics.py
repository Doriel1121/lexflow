"""Smoke tests for AI health merge helpers (DB queries tested in integration)."""

from app.services.processing_telemetry import emit_stage, get_ai_provider_name


def test_emit_stage_does_not_raise(capsys):
    emit_stage(
        document_id=1,
        organization_id=2,
        stage="ocr",
        duration_ms=120,
        status="ok",
    )
    assert get_ai_provider_name()  # may be inactive provider class name
