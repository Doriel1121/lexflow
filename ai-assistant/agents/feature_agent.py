from __future__ import annotations


def build_feature_prompt(context: str, task: str) -> str:
    return f"""You are a senior product-minded engineer preparing an implementation plan.
Ground the plan in the provided code context and call out files likely to change.

Context:
{context}

Feature request:
{task}
"""