from __future__ import annotations

import re
from typing import Any

from config import DEFAULT_CONFIG, AppConfig

_SECRET_ASSIGNMENT = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)(\s*=\s*)(.+)$", re.MULTILINE)
_ALLOWED_HISTORY_ROLES = {"user", "assistant"}


def _sanitize_text(path: str, text: str) -> str:
    if path.endswith(".env") or "/.env" in path.replace("\\", "/"):
        return _SECRET_ASSIGNMENT.sub(r"\1\2<redacted>", text)
    return text


def _format_metadata(metadata: dict[str, Any]) -> str:
    symbols = ", ".join(str(item) for item in metadata.get("symbols", [])[:12])
    imports = ", ".join(str(item) for item in metadata.get("imports", [])[:8])
    route = metadata.get("route") or ""
    return (
        f"path={metadata.get('path', '')}\n"
        f"layer={metadata.get('layer', '')} language={metadata.get('language', '')} "
        f"framework={metadata.get('framework', '')} type={metadata.get('chunk_type', '')}\n"
        f"route={route}\n"
        f"symbols={symbols}\n"
        f"imports={imports}"
    )


class PromptBuilder:
    def __init__(self, config: AppConfig = DEFAULT_CONFIG) -> None:
        self.config = config

    def build(self, *, messages: list[dict[str, str]], retrieved: list[dict[str, Any]]) -> str:
        user_message = self._latest_user_message(messages)
        history = self._format_history(messages)
        context = self._format_context(retrieved)
        return f"""You are LexFlow Local AI, a senior software engineering assistant running over this local repository.

Rules:
- Answer the user's concrete question using the repository context below.
- Treat the repository context as more important than generic model knowledge.
- Cite concrete file paths when explaining code.
- Do not describe how this might typically work. Describe only what this repository actually does.
- If retrieved context is unrelated or incomplete, say exactly which part is missing instead of guessing.
- Never reveal .env secret values. If env files appear, discuss key names only.
- Keep answers concise: 3-7 bullets or 1-3 short paragraphs unless the user asks for detail.
- Do not start with phrases like "Sure", "I can help", "Here is", or "I will".
- Do not describe what you intend to do. Give the answer directly.
- Start with the concrete finding, file, or command, not a generic introduction.
- Include only the most relevant files unless the user asks for a full trace.

Repository context:
{context}

Conversation:
{history}

User request:
{user_message}

Answer:"""

    def _format_context(self, retrieved: list[dict[str, Any]]) -> str:
        if not retrieved:
            return "No indexed context was retrieved."

        parts: list[str] = []
        current_chars = 0
        for index, result in enumerate(retrieved, start=1):
            metadata = result.get("metadata", {}) or {}
            path = str(metadata.get("path", ""))
            text = _sanitize_text(path, str(result.get("text", "")))
            related = result.get("related", [])
            related_text = f"\nrelated={related}" if related else ""
            block = f"[Context {index}] source={result.get('source', '')} rank={result.get('rank_score', '')} score={result.get('score', '')}\n{_format_metadata(metadata)}{related_text}\n```\n{text}\n```"
            if current_chars + len(block) > self.config.max_context_chars:
                break
            current_chars += len(block)
            parts.append(block)
        return "\n\n---\n\n".join(parts)

    def _format_history(self, messages: list[dict[str, str]]) -> str:
        formatted = []
        filtered_messages = [message for message in messages if message.get("role") in _ALLOWED_HISTORY_ROLES]
        for message in filtered_messages[-8:]:
            role = message.get("role", "user")
            content = message.get("content", "")
            formatted.append(f"{role}: {content}")
        return "\n".join(formatted)

    def _latest_user_message(self, messages: list[dict[str, str]]) -> str:
        for message in reversed(messages):
            if message.get("role") == "user":
                return message.get("content", "")
        return messages[-1].get("content", "") if messages else ""


