"""Shared helpers for AI provider outputs (embeddings, vectors)."""
from __future__ import annotations

from typing import List, Optional


def embedding_dimension() -> int:
    from app.core.ai_provider import get_ai_provider

    provider = get_ai_provider()
    return int(getattr(provider, "embedding_dimension", None) or getattr(provider, "EMBEDDING_DIMENSION", 768))


def is_zero_vector(vector: Optional[List[float]], *, tolerance: float = 1e-9) -> bool:
    """True if vector is missing, empty, or all zeros (failed / inactive provider)."""
    if not vector:
        return True
    return all(abs(float(v)) <= tolerance for v in vector)


def valid_embedding(vector: Optional[List[float]]) -> bool:
    return not is_zero_vector(vector)
