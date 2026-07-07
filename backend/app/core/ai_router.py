import logging
from enum import Enum

from app.core.ai_provider import BaseAIProvider, get_ai_provider
from app.core.config import settings

logger = logging.getLogger(__name__)


class AITask(str, Enum):
    READER = "reader"
    DRAFTING = "drafting"
    EMBEDDING = "embedding"


class AIRouter:
    """Resolve the correct AI provider for each task type."""

    def provider_for(self, task: AITask | str) -> BaseAIProvider:
        task_name = task.value if isinstance(task, AITask) else str(task)
        configured = self._configured_provider(task_name)
        provider = get_ai_provider(configured)

        if getattr(provider, "active", False):
            logger.debug("AI task '%s' routed to provider '%s'.", task_name, configured)
            return provider

        fallback_name = (settings.AI_FALLBACK_PROVIDER or settings.AI_PROVIDER or "").strip()
        if fallback_name and fallback_name.lower() != configured.lower():
            fallback = get_ai_provider(fallback_name)
            if getattr(fallback, "active", False):
                logger.warning(
                    "AI provider '%s' inactive for task '%s'; using fallback '%s'.",
                    configured,
                    task_name,
                    fallback_name,
                )
                return fallback

        return provider

    def _configured_provider(self, task_name: str) -> str:
        task_provider = {
            AITask.READER.value: settings.AI_READER_PROVIDER,
            AITask.DRAFTING.value: settings.AI_DRAFTING_PROVIDER,
            AITask.EMBEDDING.value: settings.AI_EMBEDDING_PROVIDER,
        }.get(task_name, "")
        return (task_provider or settings.AI_PROVIDER or "gemini").strip().lower()


ai_router = AIRouter()
