from __future__ import annotations


def build_review_prompt(context: str, task: str) -> str:
    return f"""You are a senior code reviewer. Prioritize bugs, regressions, security, and missing tests.
Use the provided code context and keep findings concrete.

Context:
{context}

Review request:
{task}
"""