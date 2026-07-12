import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "app" / "services" / "ask_ai_prompting.py"
spec = importlib.util.spec_from_file_location("ask_ai_prompting", MODULE_PATH)
ask_ai_prompting = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = ask_ai_prompting
spec.loader.exec_module(ask_ai_prompting)

AskAIIntent = ask_ai_prompting.AskAIIntent
build_ask_ai_json_prompt = ask_ai_prompting.build_ask_ai_json_prompt
build_ask_ai_prompt = ask_ai_prompting.build_ask_ai_prompt
render_ask_ai_answer = ask_ai_prompting.render_ask_ai_answer
detect_ask_ai_intent = ask_ai_prompting.detect_ask_ai_intent


def test_detects_legal_analysis_in_hebrew_question():
    intent = detect_ask_ai_intent("מה הטענות המשפטיות והסיכונים לפי המסמך?")

    assert intent == AskAIIntent.LEGAL_ANALYSIS


def test_detects_drafting_request_before_general_legal_terms():
    intent = detect_ask_ai_intent("Please draft a claim letter based on this document")

    assert intent == AskAIIntent.DRAFTING_REQUEST


def test_legal_prompt_separates_facts_from_interpretation():
    prompt = build_ask_ai_prompt(
        question="What are the legal risks?",
        retrieved_context="--- SOURCE 1 ---\nThe agreement requires payment by June 1.",
        document_brief="Document: agreement.pdf",
        intent=AskAIIntent.RISK_ANALYSIS,
        lang_hint="You MUST answer in English.",
    )

    assert "Separate facts found in documents from legal interpretation" in prompt
    assert "Do not invent statutes, case law, deadlines, or facts" in prompt
    assert "Risks or missing information" in prompt


def test_json_prompt_requires_json_not_markdown():
    prompt = build_ask_ai_json_prompt(
        question="What are the legal risks?",
        retrieved_context="--- SOURCE 1 ---\nThe agreement requires payment by June 1.",
        document_brief="Document: agreement.pdf",
        intent=AskAIIntent.RISK_ANALYSIS,
        lang_hint="You MUST answer in English.",
    )

    assert "Return ONLY valid JSON" in prompt
    assert "Do not repeat key names as answer text" in prompt
    assert "short_answer" in prompt


def test_renderer_drops_repeated_short_answer_loop():
    answer = render_ask_ai_answer(
        {
            "short_answer": "Short answer -Short answer -Short answer",
            "document_facts": ["The contract requires payment by June 1."],
            "legal_analysis": [],
            "risks_or_missing_information": [],
            "recommended_next_steps": [],
        },
        hebrew=False,
    )

    assert "Short answer -Short answer" not in answer
    assert "The contract requires payment by June 1." in answer
