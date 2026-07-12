from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AICostEstimate:
    input_cost_usd: Decimal
    output_cost_usd: Decimal
    total_cost_usd: Decimal
    pricing_configured: bool

    def as_float_dict(self) -> dict[str, float | bool]:
        return {
            "estimated_input_cost_usd": float(self.input_cost_usd),
            "estimated_output_cost_usd": float(self.output_cost_usd),
            "estimated_total_cost_usd": float(self.total_cost_usd),
            "pricing_configured": self.pricing_configured,
        }


_ZERO = Decimal("0.000000")
_QUANT = Decimal("0.000001")


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower()


def _parse_pricing() -> dict[str, Any]:
    raw = (settings.AI_COST_PRICING_JSON or "{}").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Invalid AI_COST_PRICING_JSON; cost estimates disabled: %s", exc)
        return {}
    if not isinstance(parsed, dict):
        logger.warning("AI_COST_PRICING_JSON must be a JSON object; cost estimates disabled")
        return {}
    return parsed


def _lookup_rates(provider: str, model: str | None) -> dict[str, Any] | None:
    pricing = _parse_pricing()
    provider_key = _normalize(provider)
    model_key = _normalize(model)

    provider_prices = pricing.get(provider_key) or pricing.get(provider) or pricing.get("*")
    if not isinstance(provider_prices, dict):
        return None

    exact = provider_prices.get(model_key) or (provider_prices.get(model or "") if model else None)
    wildcard = provider_prices.get("*")
    rates = exact or wildcard
    return rates if isinstance(rates, dict) else None


def _decimal_rate(rates: dict[str, Any], key: str) -> Decimal:
    value = rates.get(key, 0)
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def estimate_ai_cost(
    *,
    provider: str,
    model: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
) -> AICostEstimate:
    rates = _lookup_rates(provider, model)
    if not rates:
        return AICostEstimate(_ZERO, _ZERO, _ZERO, False)

    input_rate = _decimal_rate(rates, "input_per_1m")
    output_rate = _decimal_rate(rates, "output_per_1m")
    input_cost = (Decimal(input_tokens or 0) / Decimal(1_000_000) * input_rate).quantize(_QUANT, rounding=ROUND_HALF_UP)
    output_cost = (Decimal(output_tokens or 0) / Decimal(1_000_000) * output_rate).quantize(_QUANT, rounding=ROUND_HALF_UP)
    total = (input_cost + output_cost).quantize(_QUANT, rounding=ROUND_HALF_UP)
    return AICostEstimate(input_cost, output_cost, total, input_rate > 0 or output_rate > 0)
