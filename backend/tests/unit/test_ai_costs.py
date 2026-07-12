from app.core.config import settings
from app.services.ai_costs import estimate_ai_cost


def test_estimate_ai_cost_uses_exact_model_rates(monkeypatch):
    monkeypatch.setattr(
        settings,
        "AI_COST_PRICING_JSON",
        '{"gemini":{"gemini-2.0-flash":{"input_per_1m":0.1,"output_per_1m":0.4}}}',
    )

    cost = estimate_ai_cost(
        provider="gemini",
        model="gemini-2.0-flash",
        input_tokens=1_000_000,
        output_tokens=500_000,
    )

    assert cost.pricing_configured is True
    assert float(cost.input_cost_usd) == 0.1
    assert float(cost.output_cost_usd) == 0.2
    assert float(cost.total_cost_usd) == 0.3


def test_estimate_ai_cost_uses_provider_wildcard(monkeypatch):
    monkeypatch.setattr(
        settings,
        "AI_COST_PRICING_JSON",
        '{"openrouter":{"*":{"input_per_1m":2,"output_per_1m":6}}}',
    )

    cost = estimate_ai_cost(
        provider="openrouter",
        model="some/model",
        input_tokens=250_000,
        output_tokens=100_000,
    )

    assert cost.pricing_configured is True
    assert float(cost.total_cost_usd) == 1.1


def test_estimate_ai_cost_marks_missing_pricing_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "AI_COST_PRICING_JSON", "{}")

    cost = estimate_ai_cost(
        provider="gemini",
        model="unknown",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )

    assert cost.pricing_configured is False
    assert float(cost.total_cost_usd) == 0.0
