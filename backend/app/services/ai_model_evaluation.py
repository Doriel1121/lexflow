from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable, Optional


@dataclass(frozen=True)
class EvaluationTask:
    id: str
    category: str
    language: str
    title: str
    context: str
    prompt: str
    expected_points: list[str]
    forbidden_claims: list[str] = field(default_factory=list)
    required_format: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass(frozen=True)
class EvaluationScore:
    coverage: float
    hallucination_resistance: float
    format_adherence: float
    language_match: float
    total: float
    covered_points: list[str]
    missing_points: list[str]
    forbidden_hits: list[str]


@dataclass(frozen=True)
class EvaluationCost:
    input_tokens: int
    output_tokens: int
    estimated_input_cost_usd: float
    estimated_output_cost_usd: float
    estimated_total_cost_usd: float
    pricing_configured: bool


@dataclass(frozen=True)
class EvaluationResult:
    provider: str
    model: Optional[str]
    task_id: str
    category: str
    language: str
    latency_ms: int
    response_text: str
    score: EvaluationScore
    cost: EvaluationCost = field(default_factory=lambda: EvaluationCost(0, 0, 0.0, 0.0, 0.0, False))


def load_evaluation_tasks(path: str | Path) -> list[EvaluationTask]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    tasks = raw.get("tasks", raw)
    return [EvaluationTask(**task) for task in tasks]


def build_evaluation_prompt(task: EvaluationTask) -> str:
    expected_format = "\n".join(f"- {item}" for item in task.required_format) or "- Clear structured answer"
    language_instruction = "Hebrew" if task.language.lower().startswith("he") else "English"
    return f"""You are evaluating a legal AI assistant for LexFlow.

Answer the user task using ONLY the provided context.
Do not invent facts, laws, statutes, case law, or dates.
If the context is insufficient, say exactly what must be verified.
Answer in {language_instruction}.

CONTEXT:
{task.context}

USER TASK:
{task.prompt}

REQUIRED FORMAT:
{expected_format}
"""


def score_response(task: EvaluationTask, response_text: str) -> EvaluationScore:
    normalized = _normalize(response_text)
    expected = [_normalize(point) for point in task.expected_points]
    forbidden = [_normalize(item) for item in task.forbidden_claims]

    covered_points = [
        original
        for original, point in zip(task.expected_points, expected)
        if _contains_meaningful_terms(normalized, point)
    ]
    missing_points = [point for point in task.expected_points if point not in covered_points]
    forbidden_hits = [
        original
        for original, item in zip(task.forbidden_claims, forbidden)
        if item and item in normalized
    ]

    coverage = _ratio_score(len(covered_points), len(task.expected_points))
    hallucination_resistance = max(0.0, 1.0 - (len(forbidden_hits) / max(1, len(task.forbidden_claims))))
    format_adherence = _format_score(task.required_format, response_text)
    language_match = _language_score(task.language, response_text)
    total = round(
        (coverage * 0.40)
        + (hallucination_resistance * 0.30)
        + (format_adherence * 0.15)
        + (language_match * 0.15),
        4,
    )

    return EvaluationScore(
        coverage=round(coverage, 4),
        hallucination_resistance=round(hallucination_resistance, 4),
        format_adherence=round(format_adherence, 4),
        language_match=round(language_match, 4),
        total=total,
        covered_points=covered_points,
        missing_points=missing_points,
        forbidden_hits=forbidden_hits,
    )


async def run_model_evaluation(
    *,
    provider_names: Iterable[str],
    tasks: list[EvaluationTask],
) -> list[EvaluationResult]:
    from app.core.ai_provider import get_ai_provider
    from app.services.ai_usage_logger import provider_model, provider_name

    results: list[EvaluationResult] = []
    for provider_name_arg in provider_names:
        provider = get_ai_provider(provider_name_arg)
        if not getattr(provider, "active", False):
            continue

        for task in tasks:
            prompt = build_evaluation_prompt(task)
            started = time.perf_counter()
            response_text = await provider.generate_text(prompt)
            latency_ms = int((time.perf_counter() - started) * 1000)
            response_text = response_text or ""
            provider_label = provider_name(provider)
            model_label = provider_model(provider)
            results.append(
                EvaluationResult(
                    provider=provider_label,
                    model=model_label,
                    task_id=task.id,
                    category=task.category,
                    language=task.language,
                    latency_ms=latency_ms,
                    response_text=response_text,
                    score=score_response(task, response_text),
                    cost=estimate_result_cost(
                        provider=provider_label,
                        model=model_label,
                        input_text=prompt,
                        output_text=response_text,
                    ),
                )
            )
    return results


def write_results(path: str | Path, results: list[EvaluationResult]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps([_result_to_dict(result) for result in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def summarize_results(results: list[EvaluationResult]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, Optional[str]], list[EvaluationResult]] = {}
    for result in results:
        grouped.setdefault((result.provider, result.model), []).append(result)

    summary = []
    for (provider, model), provider_results in grouped.items():
        quality = _avg(result.score.total for result in provider_results)
        latency = _avg(result.latency_ms for result in provider_results)
        cost = sum(result.cost.estimated_total_cost_usd for result in provider_results)
        quality_cost_index = _quality_cost_index(quality, latency, cost, len(provider_results))
        summary.append({
            "provider": provider,
            "model": model,
            "tasks": len(provider_results),
            "avg_score": round(quality, 4),
            "avg_latency_ms": round(latency, 1),
            "estimated_total_cost_usd": round(cost, 6),
            "pricing_configured": any(result.cost.pricing_configured for result in provider_results),
            "quality_cost_index": round(quality_cost_index, 4),
        })
    return sorted(summary, key=lambda item: (item["avg_score"], item["quality_cost_index"]), reverse=True)


def summarize_results_by_category(results: list[EvaluationResult]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, Optional[str]], list[EvaluationResult]] = {}
    for result in results:
        grouped.setdefault((result.category, result.provider, result.model), []).append(result)

    rows = []
    for (category, provider, model), category_results in grouped.items():
        quality = _avg(result.score.total for result in category_results)
        latency = _avg(result.latency_ms for result in category_results)
        cost = sum(result.cost.estimated_total_cost_usd for result in category_results)
        rows.append({
            "category": category,
            "provider": provider,
            "model": model,
            "tasks": len(category_results),
            "avg_score": round(quality, 4),
            "avg_latency_ms": round(latency, 1),
            "estimated_total_cost_usd": round(cost, 6),
            "pricing_configured": any(result.cost.pricing_configured for result in category_results),
            "quality_cost_index": round(_quality_cost_index(quality, latency, cost, len(category_results)), 4),
        })
    return sorted(rows, key=lambda item: (item["category"], -item["avg_score"], -item["quality_cost_index"]))


def recommend_providers_by_category(results: list[EvaluationResult]) -> list[dict[str, Any]]:
    rows = summarize_results_by_category(results)
    recommendations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        category = row["category"]
        if category in seen:
            continue
        seen.add(category)
        recommendations.append({
            "category": category,
            "recommended_provider": row["provider"],
            "recommended_model": row["model"],
            "avg_score": row["avg_score"],
            "avg_latency_ms": row["avg_latency_ms"],
            "estimated_total_cost_usd": row["estimated_total_cost_usd"],
            "reason": _recommendation_reason(row),
        })
    return recommendations


def build_evaluation_report(results: list[EvaluationResult]) -> dict[str, Any]:
    return {
        "summary": summarize_results(results),
        "by_category": summarize_results_by_category(results),
        "recommendations": recommend_providers_by_category(results),
    }


def estimate_result_cost(
    *,
    provider: str,
    model: Optional[str],
    input_text: str,
    output_text: str,
) -> EvaluationCost:
    input_tokens = estimate_tokens(input_text)
    output_tokens = estimate_tokens(output_text)
    rates = _lookup_pricing_rates(provider, model)
    if not rates:
        return EvaluationCost(input_tokens, output_tokens, 0.0, 0.0, 0.0, False)

    input_rate = _decimal_rate(rates, "input_per_1m")
    output_rate = _decimal_rate(rates, "output_per_1m")
    input_cost = _money(Decimal(input_tokens) / Decimal(1_000_000) * input_rate)
    output_cost = _money(Decimal(output_tokens) / Decimal(1_000_000) * output_rate)
    total = _money(input_cost + output_cost)
    return EvaluationCost(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_input_cost_usd=float(input_cost),
        estimated_output_cost_usd=float(output_cost),
        estimated_total_cost_usd=float(total),
        pricing_configured=input_rate > 0 or output_rate > 0,
    )


def estimate_tokens(text_or_count: Any) -> int:
    if text_or_count is None:
        return 0
    if isinstance(text_or_count, int):
        chars = text_or_count
    elif isinstance(text_or_count, str):
        chars = len(text_or_count)
    else:
        chars = len(str(text_or_count))
    return max(1, round(chars / 4)) if chars > 0 else 0


def run_evaluation_sync(provider_names: Iterable[str], tasks: list[EvaluationTask]) -> list[EvaluationResult]:
    return asyncio.run(run_model_evaluation(provider_names=provider_names, tasks=tasks))


def _result_to_dict(result: EvaluationResult) -> dict[str, Any]:
    return asdict(result)


def _ratio_score(count: int, total: int) -> float:
    if total <= 0:
        return 1.0
    return min(1.0, count / total)


def _format_score(required_format: list[str], response_text: str) -> float:
    if not required_format:
        return 1.0
    normalized = _normalize(response_text)
    hits = sum(1 for item in required_format if _contains_meaningful_terms(normalized, _normalize(item)))
    return _ratio_score(hits, len(required_format))


def _language_score(language: str, response_text: str) -> float:
    if not response_text.strip():
        return 0.0
    has_hebrew = any("\u0590" <= char <= "\u05FF" for char in response_text)
    if language.lower().startswith("he"):
        return 1.0 if has_hebrew else 0.0
    return 0.7 if has_hebrew else 1.0


def _contains_meaningful_terms(haystack: str, needle: str) -> bool:
    terms = [term for term in needle.split() if len(term) >= 4]
    if not terms:
        return needle in haystack
    required_hits = max(1, min(len(terms), round(len(terms) * 0.55)))
    hits = sum(1 for term in terms if term in haystack)
    return hits >= required_hits


def _normalize(value: str) -> str:
    return " ".join((value or "").lower().split())


def _avg(values: Iterable[float]) -> float:
    items = list(values)
    return sum(items) / max(1, len(items))


def _quality_cost_index(avg_score: float, avg_latency_ms: float, total_cost_usd: float, task_count: int) -> float:
    avg_cost = total_cost_usd / max(1, task_count)
    latency_penalty = min(0.20, avg_latency_ms / 120_000)
    cost_penalty = min(0.20, avg_cost / 0.25)
    return max(0.0, avg_score - latency_penalty - cost_penalty)


def _recommendation_reason(row: dict[str, Any]) -> str:
    if row.get("pricing_configured"):
        return "Highest quality score for this task category, with latency and configured cost included in the value index."
    return "Highest quality score for this task category. Pricing is not configured, so cost is not part of this recommendation."


def _lookup_pricing_rates(provider: str, model: Optional[str]) -> dict[str, Any] | None:
    pricing = _parse_pricing_json()
    provider_key = _normalize_key(provider)
    model_key = _normalize_key(model)
    provider_prices = pricing.get(provider_key) or pricing.get(provider) or pricing.get("*")
    if not isinstance(provider_prices, dict):
        return None
    rates = provider_prices.get(model_key) or (provider_prices.get(model or "") if model else None) or provider_prices.get("*")
    return rates if isinstance(rates, dict) else None


def _parse_pricing_json() -> dict[str, Any]:
    raw = (os.getenv("AI_COST_PRICING_JSON") or "{}").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _normalize_key(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _decimal_rate(rates: dict[str, Any], key: str) -> Decimal:
    try:
        return Decimal(str(rates.get(key, 0)))
    except Exception:
        return Decimal("0")


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
