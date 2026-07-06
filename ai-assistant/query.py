from __future__ import annotations

import requests

from agents.architect_agent import build_architect_prompt
from config import DEFAULT_CONFIG
from retrieval.hybrid_search import HybridSearch


def trim_context(context: str, limit: int) -> str:
    if len(context) <= limit:
        return context
    return context[:limit] + "\n\n[Context truncated to keep local generation responsive.]"


def ask_ollama(prompt: str) -> str:
    try:
        response = requests.post(
            f"{DEFAULT_CONFIG.ollama_url}/api/generate",
            json={"model": DEFAULT_CONFIG.llm_model, "prompt": prompt, "stream": False},
            timeout=DEFAULT_CONFIG.ollama_timeout_seconds,
        )
        response.raise_for_status()
        return response.json()["response"]
    except requests.exceptions.ReadTimeout:
        return (
            "Ollama is still working after the configured timeout. "
            "Try a smaller question, reduce max_context_chars in config.py, "
            "or use a smaller local model such as qwen2.5:7b."
        )
    except requests.exceptions.ConnectionError:
        return "Could not connect to Ollama. Make sure Ollama is running on http://localhost:11434."


def main() -> None:
    retrieval = HybridSearch(DEFAULT_CONFIG)
    while True:
        question = input("Ask: ").strip()
        if question.lower() in {"exit", "quit"}:
            break
        context = retrieval.retrieve_context(question, k=6)
        prompt = build_architect_prompt(trim_context(context, DEFAULT_CONFIG.max_context_chars), question)
        print(ask_ollama(prompt))


if __name__ == "__main__":
    main()