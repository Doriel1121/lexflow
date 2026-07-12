"""Shared helpers for AI provider outputs (embeddings, vectors)."""
from __future__ import annotations

from typing import List, Optional


def embedding_dimension() -> int:
    from app.core.ai_router import AITask, AITaskContext, AIIntent, AIRiskLevel, ai_router

    provider = ai_router.provider_for(
        AITask.EMBEDDING,
        AITaskContext(
            task=AITask.EMBEDDING,
            feature="embedding",
            intent=AIIntent.EMBEDDING,
            risk_level=AIRiskLevel.LOW,
        ),
    )
    return int(getattr(provider, "embedding_dimension", None) or getattr(provider, "EMBEDDING_DIMENSION", 768))


def is_zero_vector(vector: Optional[List[float]], *, tolerance: float = 1e-9) -> bool:
    """True if vector is missing, empty, or all zeros (failed / inactive provider)."""
    if not vector:
        return True
    return all(abs(float(v)) <= tolerance for v in vector)


def valid_embedding(vector: Optional[List[float]]) -> bool:
    return not is_zero_vector(vector)
