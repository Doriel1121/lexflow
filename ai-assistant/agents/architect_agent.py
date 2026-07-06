from __future__ import annotations


def build_architect_prompt(context: str, task: str) -> str:
    return f"""You are a senior software architect analyzing a local full-stack codebase.
Use the structured context to explain architecture, flows, and tradeoffs.

Context:
{context}

Task:
{task}
"""