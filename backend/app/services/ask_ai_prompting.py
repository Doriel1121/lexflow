from enum import Enum
import json
from typing import Any, Iterable, Mapping


class AskAIIntent(str, Enum):
    FACT_LOOKUP = "fact_lookup"
    SUMMARY = "summary"
    LEGAL_ANALYSIS = "legal_analysis"
    RISK_ANALYSIS = "risk_analysis"
    DEADLINES_OBLIGATIONS = "deadlines_obligations"
    NEXT_STEPS = "next_steps"
    DRAFTING_REQUEST = "drafting_request"


INTENT_KEYWORDS = {
    AskAIIntent.DRAFTING_REQUEST: (
        "draft", "write", "prepare", "compose", "letter", "claim", "motion",
        "נסח", "לנסח", "כתוב", "תכתוב", "הכן", "להכין", "מכתב", "כתב תביעה", "כתב הגנה",
    ),
    AskAIIntent.LEGAL_ANALYSIS: (
        "legal", "law", "rights", "liability", "argument", "defense", "claim", "merits",
        "case strength", "cause of action", "breach", "negligence",
        "משפטי", "חוקי", "זכויות", "אחריות", "טענה", "טענות", "הגנה", "עילה", "סיכוי", "הפרה", "רשלנות",
    ),
    AskAIIntent.RISK_ANALYSIS: (
        "risk", "risks", "exposure", "weakness", "problem", "red flag",
        "סיכון", "סיכונים", "חשיפה", "חולשה", "בעיה", "בעיות", "דגל אדום",
    ),
    AskAIIntent.DEADLINES_OBLIGATIONS: (
        "deadline", "deadlines", "date", "due", "obligation", "obligations", "must", "shall",
        "מועד", "מועדים", "תאריך", "דדליין", "חובה", "חובות", "התחייבות", "התחייבויות", "צריך",
    ),
    AskAIIntent.NEXT_STEPS: (
        "next step", "next steps", "what should", "questions for", "ask the client", "strategy",
        "מה לעשות", "צעדים", "הצעד הבא", "שאלות", "לשאול את הלקוח", "אסטרטגיה",
    ),
    AskAIIntent.SUMMARY: (
        "summary", "summarize", "brief", "overview", "main points",
        "סיכום", "סכם", "תסכם", "תקציר", "עיקרי הדברים",
    ),
}


def detect_ask_ai_intent(question: str) -> AskAIIntent:
    normalized = question.lower()
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return intent
    return AskAIIntent.FACT_LOOKUP


def build_document_brief(items: Iterable[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in items:
        lines.append(f"Document: {item.get('filename', 'Unknown')} (ID: {item.get('id')})")
        if item.get("classification"):
            lines.append(f"- Classification: {item['classification']}")
        if item.get("language"):
            lines.append(f"- Language: {item['language']}")
        if item.get("page_count"):
            lines.append(f"- Pages: {item['page_count']}")
        if item.get("summary"):
            lines.append(f"- Summary: {_shorten(str(item['summary']), 900)}")
        if item.get("parties"):
            lines.append(f"- Parties: {_format_value(item['parties'])}")
        if item.get("key_dates"):
            lines.append(f"- Key dates: {_format_value(item['key_dates'])}")
        if item.get("dates"):
            lines.append(f"- Extracted dates: {_format_value(item['dates'])}")
        if item.get("entities"):
            lines.append(f"- Entities: {_format_value(item['entities'])}")
        if item.get("amounts"):
            lines.append(f"- Amounts: {_format_value(item['amounts'])}")
        if item.get("case_numbers"):
            lines.append(f"- Case numbers: {_format_value(item['case_numbers'])}")
        if item.get("keywords"):
            lines.append(f"- Keywords: {_format_value(item['keywords'])}")
        if item.get("missing_documents_suggestion"):
            lines.append(
                f"- Missing-document suggestion: {_shorten(str(item['missing_documents_suggestion']), 500)}"
            )
        lines.append("")
    return "\n".join(lines).strip()


def build_ask_ai_prompt(
    *,
    question: str,
    retrieved_context: str,
    document_brief: str,
    intent: AskAIIntent,
    lang_hint: str,
) -> str:
    response_shape = _response_shape_for_intent(intent)
    return f"""You are LexFlow's legal AI assistant for lawyers.

Your task is to answer the user's question using the retrieved document evidence and document-level facts below.

QUESTION INTENT:
{intent.value}

DOCUMENT BRIEF:
{document_brief or "No document-level metadata was available."}

RETRIEVED EVIDENCE:
{retrieved_context}

USER QUESTION:
{question}

ANSWER RULES:
1. {lang_hint}
2. Be concise and practical. Do not describe your process.
3. Separate facts found in documents from legal interpretation.
4. Ground document-specific claims in the retrieved evidence.
5. Do not invent statutes, case law, deadlines, or facts not present in the evidence.
6. If external legal research is needed, say so clearly and explain what must be verified by a lawyer.
7. For legal reasoning, provide issue-focused analysis, risks, and recommended next steps.
8. For drafting requests, do not generate a full filing from incomplete context; give a short drafting plan and list missing facts/evidence.
9. Do not include technical Source IDs or Document IDs inside normal prose.

RESPONSE FORMAT:
{response_shape}
"""


def build_ask_ai_json_prompt(
    *,
    question: str,
    retrieved_context: str,
    document_brief: str,
    intent: AskAIIntent,
    lang_hint: str,
) -> str:
    schema = {
        "short_answer": "one concise paragraph",
        "document_facts": ["fact grounded in retrieved evidence"],
        "legal_analysis": ["legal or practical interpretation, with uncertainty when needed"],
        "risks_or_missing_information": ["risk, gap, or external verification needed"],
        "recommended_next_steps": ["practical lawyer next step"],
    }
    return f"""You are LexFlow's legal AI assistant for lawyers.

Return ONLY valid JSON. Do not return markdown. Do not repeat key names as answer text.
Each list may contain 0-4 items. Each item must be concise.

QUESTION INTENT: {intent.value}
LANGUAGE RULE: {lang_hint}

DOCUMENT BRIEF:
{document_brief or "No document-level metadata was available."}

RETRIEVED EVIDENCE:
{retrieved_context}

USER QUESTION:
{question}

SAFETY RULES:
- Separate document facts from legal interpretation.
- Ground document-specific claims in the retrieved evidence.
- Do not invent statutes, case law, deadlines, or facts not present in the evidence.
- If external legal research is needed, state that in risks_or_missing_information.
- For drafting requests, do not generate a full filing from incomplete context; provide drafting preparation steps only.

JSON SCHEMA:
{json.dumps(schema, ensure_ascii=False, indent=2)}
"""


def render_ask_ai_answer(data: Mapping[str, Any], *, hebrew: bool) -> str:
    headings = {
        "short_answer": "תשובה קצרה" if hebrew else "Short answer",
        "document_facts": "עובדות מהמסמכים" if hebrew else "Document facts",
        "legal_analysis": "ניתוח משפטי / משמעות מעשית" if hebrew else "Legal analysis / practical meaning",
        "risks_or_missing_information": "סיכונים או מידע חסר" if hebrew else "Risks or missing information",
        "recommended_next_steps": "צעדים מומלצים" if hebrew else "Recommended next steps",
    }
    parts: list[str] = []

    short_answer = _clean_text(data.get("short_answer"))
    if short_answer:
        parts.append(f"{headings['short_answer']}: {short_answer}")

    for key in (
        "document_facts",
        "legal_analysis",
        "risks_or_missing_information",
        "recommended_next_steps",
    ):
        values = _clean_list(data.get(key))
        if not values:
            continue
        parts.append(f"{headings[key]}:")
        parts.extend(f"- {value}" for value in values[:4])

    if parts:
        return "\n".join(parts)
    return (
        "לא נמצא מספיק מידע במסמכים כדי לענות בביטחון."
        if hebrew
        else "I could not find enough information in the documents to answer confidently."
    )


def _clean_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_clean_text(item) for item in value if _clean_text(item)]
    cleaned = _clean_text(value)
    return [cleaned] if cleaned else []


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).split())
    repeated_labels = (
        "Short answer -Short answer",
        "Short answer - Short answer",
        "תשובה קצרה -תשובה קצרה",
    )
    if any(label in text for label in repeated_labels):
        return ""
    return text.strip(" -")


def _response_shape_for_intent(intent: AskAIIntent) -> str:
    if intent in {
        AskAIIntent.LEGAL_ANALYSIS,
        AskAIIntent.RISK_ANALYSIS,
        AskAIIntent.NEXT_STEPS,
        AskAIIntent.DRAFTING_REQUEST,
    }:
        return """- Short answer
- Relevant document facts
- Legal analysis / practical meaning
- Risks or missing information
- Recommended next steps"""
    if intent == AskAIIntent.DEADLINES_OBLIGATIONS:
        return """- Short answer
- Dates / deadlines found
- Obligations found
- Uncertainties or missing information"""
    if intent == AskAIIntent.SUMMARY:
        return """- Short summary
- Key parties / facts
- Key dates / amounts
- Open issues"""
    return """- Direct answer
- Supporting facts from the documents
- If not found, say exactly what is missing"""


def _format_value(value: Any) -> str:
    if isinstance(value, list):
        return _shorten(", ".join(str(item) for item in value), 500)
    if isinstance(value, dict):
        return _shorten(", ".join(f"{key}: {val}" for key, val in value.items()), 500)
    return _shorten(str(value), 500)


def _shorten(value: str, limit: int) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[:limit - 3].rstrip()}..."
