import asyncio
import importlib.util
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODULE_PATH = ROOT / "app" / "services" / "ai_quota.py"
spec = importlib.util.spec_from_file_location("ai_quota", MODULE_PATH)
ai_quota = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = ai_quota
spec.loader.exec_module(ai_quota)

AIQuotaExceeded = ai_quota.AIQuotaExceeded
AIQuotaStatus = ai_quota.AIQuotaStatus
is_drafting_task = ai_quota.is_drafting_task


def test_identifies_drafting_tasks_only():
    assert is_drafting_task("drafting.legal_response") is True
    assert is_drafting_task("reader.rag_answer") is False
    assert is_drafting_task("embedding.document_chunk") is False


def test_quota_exception_keeps_safe_status_payload():
    status = AIQuotaStatus(
        limit_name="daily_ai_calls",
        used=1000,
        limit=1000,
        reset_at=datetime(2026, 7, 13),
    )

    exc = AIQuotaExceeded(status)

    assert exc.status.limit_name == "daily_ai_calls"
    assert exc.status.used == 1000
    assert "daily_ai_calls" in str(exc)


def test_notify_if_needed_sends_warning_at_80_percent(monkeypatch):
    calls = []

    async def fake_notify(**kwargs):
        calls.append(kwargs)
        return 1

    monkeypatch.setattr(ai_quota, "notify_ai_quota_threshold", fake_notify)

    asyncio.run(ai_quota._notify_if_needed(
        7,
        limit_name="daily_ai_calls",
        used=80,
        limit=100,
        reset_at=datetime(2026, 7, 13),
        window_start=datetime(2026, 7, 12),
    ))

    assert len(calls) == 1
    assert calls[0]["severity"] == "warning"
    assert calls[0]["limit_name"] == "daily_ai_calls"


def test_notify_if_needed_sends_hard_limit_at_100_percent(monkeypatch):
    calls = []

    async def fake_notify(**kwargs):
        calls.append(kwargs)
        return 1

    monkeypatch.setattr(ai_quota, "notify_ai_quota_threshold", fake_notify)

    asyncio.run(ai_quota._notify_if_needed(
        7,
        limit_name="monthly_drafting_calls",
        used=100,
        limit=100,
        reset_at=datetime(2026, 8, 1),
        window_start=datetime(2026, 7, 1),
    ))

    assert len(calls) == 1
    assert calls[0]["severity"] == "hard_limit"
    assert calls[0]["limit_name"] == "monthly_drafting_calls"


def test_notify_if_needed_ignores_usage_below_threshold(monkeypatch):
    calls = []

    async def fake_notify(**kwargs):
        calls.append(kwargs)
        return 1

    monkeypatch.setattr(ai_quota, "notify_ai_quota_threshold", fake_notify)

    asyncio.run(ai_quota._notify_if_needed(
        7,
        limit_name="daily_ai_calls",
        used=79,
        limit=100,
        reset_at=datetime(2026, 7, 13),
        window_start=datetime(2026, 7, 12),
    ))

    assert calls == []
