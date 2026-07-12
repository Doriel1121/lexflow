import importlib.util
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODULE_PATH = ROOT / "app" / "services" / "ai_quota_notifications.py"
spec = importlib.util.spec_from_file_location("ai_quota_notifications", MODULE_PATH)
ai_quota_notifications = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = ai_quota_notifications
spec.loader.exec_module(ai_quota_notifications)


def test_warning_title_and_message_are_org_admin_friendly():
    title = ai_quota_notifications._title("daily_ai_calls", "warning")
    message = ai_quota_notifications._message(
        "daily_ai_calls",
        used=80,
        limit=100,
        reset_at=datetime(2026, 7, 13, 10, 0),
        severity="warning",
    )

    assert title == "AI quota warning: Daily AI calls"
    assert "80%" in message
    assert "80/100" in message


def test_hard_limit_message_explains_ai_may_be_blocked():
    message = ai_quota_notifications._message(
        "monthly_drafting_calls",
        used=100,
        limit=100,
        reset_at=datetime(2026, 8, 1),
        severity="hard_limit",
    )

    assert "has reached its limit" in message
    assert "AI actions may be blocked" in message
