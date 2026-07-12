import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODULE_PATH = ROOT / "app" / "services" / "ai_model_evaluation.py"
spec = importlib.util.spec_from_file_location("ai_model_evaluation", MODULE_PATH)
ai_model_evaluation = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = ai_model_evaluation
spec.loader.exec_module(ai_model_evaluation)

EvaluationResult = ai_model_evaluation.EvaluationResult
EvaluationScore = ai_model_evaluation.EvaluationScore
EvaluationTask = ai_model_evaluation.EvaluationTask
build_evaluation_prompt = ai_model_evaluation.build_evaluation_prompt
load_evaluation_tasks = ai_model_evaluation.load_evaluation_tasks
score_response = ai_model_evaluation.score_response
summarize_results = ai_model_evaluation.summarize_results
build_evaluation_report = ai_model_evaluation.build_evaluation_report
estimate_result_cost = ai_model_evaluation.estimate_result_cost


def test_loads_synthetic_legal_tasks():
    tasks = load_evaluation_tasks(ROOT / "app" / "evaluation" / "legal_model_tasks.json")

    assert len(tasks) >= 8
    assert any(task.language == "he" for task in tasks)
    assert all(task.expected_points for task in tasks)


def test_prompt_instructs_grounded_answer_only():
    task = EvaluationTask(
        id="t1",
        category="risk",
        language="en",
        title="Risk",
        context="The agreement has no confidentiality clause.",
        prompt="Identify risks.",
        expected_points=["no confidentiality clause"],
        required_format=["Risks"],
    )

    prompt = build_evaluation_prompt(task)

    assert "using ONLY the provided context" in prompt
    assert "Do not invent" in prompt
    assert "Risks" in prompt


def test_scoring_rewards_coverage_and_penalizes_forbidden_claims():
    task = EvaluationTask(
        id="t1",
        category="risk",
        language="en",
        title="Risk",
        context="",
        prompt="",
        expected_points=["no confidentiality clause", "30 day notice"],
        forbidden_claims=["New York law applies"],
        required_format=["Risks"],
    )

    score = score_response(
        task,
        "Risks: The document has no confidentiality clause and includes a 30 day notice. New York law applies.",
    )

    assert score.coverage == 1.0
    assert score.hallucination_resistance == 0.0
    assert "New York law applies" in score.forbidden_hits


def test_summary_orders_highest_score_first():
    results = [
        EvaluationResult(
            provider="a",
            model="m1",
            task_id="t1",
            category="risk",
            language="en",
            latency_ms=100,
            response_text="",
            score=EvaluationScore(0, 0, 0, 0, 0.2, [], [], []),
            cost=ai_model_evaluation.EvaluationCost(100, 50, 0, 0, 0, False),
        ),
        EvaluationResult(
            provider="b",
            model="m2",
            task_id="t1",
            category="risk",
            language="en",
            latency_ms=50,
            response_text="",
            score=EvaluationScore(0, 0, 0, 0, 0.9, [], [], []),
            cost=ai_model_evaluation.EvaluationCost(100, 50, 0, 0, 0, False),
        ),
    ]

    summary = summarize_results(results)

    assert summary[0]["provider"] == "b"
    assert summary[0]["avg_score"] == 0.9


def test_cost_estimation_uses_env_pricing(monkeypatch):
    monkeypatch.setenv(
        "AI_COST_PRICING_JSON",
        '{"gemini":{"gemini-2.0-flash":{"input_per_1m":0.1,"output_per_1m":0.4}}}',
    )

    cost = estimate_result_cost(
        provider="gemini",
        model="gemini-2.0-flash",
        input_text="a" * 4_000_000,
        output_text="b" * 1_000_000,
    )

    assert cost.pricing_configured is True
    assert cost.input_tokens == 1_000_000
    assert cost.output_tokens == 250_000
    assert cost.estimated_total_cost_usd == 0.2


def test_report_recommends_best_provider_by_category():
    results = [
        EvaluationResult(
            provider="slow-good",
            model="m1",
            task_id="t1",
            category="legal_risk_analysis",
            language="he",
            latency_ms=1000,
            response_text="",
            score=EvaluationScore(0, 0, 0, 0, 0.95, [], [], []),
            cost=ai_model_evaluation.EvaluationCost(100, 50, 0, 0, 0, False),
        ),
        EvaluationResult(
            provider="fast-ok",
            model="m2",
            task_id="t1",
            category="legal_risk_analysis",
            language="he",
            latency_ms=20,
            response_text="",
            score=EvaluationScore(0, 0, 0, 0, 0.8, [], [], []),
            cost=ai_model_evaluation.EvaluationCost(100, 50, 0, 0, 0, False),
        ),
    ]

    report = build_evaluation_report(results)

    assert report["recommendations"][0]["category"] == "legal_risk_analysis"
    assert report["recommendations"][0]["recommended_provider"] == "slow-good"
    assert report["by_category"][0]["avg_score"] == 0.95