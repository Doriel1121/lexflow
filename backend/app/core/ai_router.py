import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.core.ai_provider import BaseAIProvider, get_ai_provider
from app.core.config import settings

logger = logging.getLogger(__name__)


class AITask(str, Enum):
    READER = "reader"
    DRAFTING = "drafting"
    EMBEDDING = "embedding"


class AIIntent(str, Enum):
    DOCUMENT_ANALYSIS = "document_analysis"
    DOCUMENT_QA = "document_qa"
    LEGAL_REASONING = "legal_reasoning"
    SUMMARIZATION = "summarization"
    CLASSIFICATION = "classification"
    DRAFTING = "drafting"
    EMBEDDING = "embedding"
    EVALUATION = "evaluation"
    GENERAL = "general"


class AIRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class AITaskContext:
    """Policy inputs used to choose the best provider for an AI operation."""

    task: AITask | str
    feature: str = ""
    intent: AIIntent | str = AIIntent.GENERAL
    language: str = ""
    input_chars: int = 0
    risk_level: AIRiskLevel | str = AIRiskLevel.MEDIUM
    requires_citations: bool = False

    @property
    def task_name(self) -> str:
        return self.task.value if isinstance(self.task, AITask) else str(self.task)

    @property
    def intent_name(self) -> str:
        return self.intent.value if isinstance(self.intent, AIIntent) else str(self.intent)

    @property
    def risk_name(self) -> str:
        return self.risk_level.value if isinstance(self.risk_level, AIRiskLevel) else str(self.risk_level)

    @property
    def is_hebrew(self) -> bool:
        return self.language.lower().startswith("he")


class AIRouter:
    """Resolve the correct AI provider using task defaults plus policy context."""

    def __init__(self) -> None:
        self._provider_cache: dict[str, BaseAIProvider] = {}

    def provider_for(
        self,
        task: AITask | str,
        context: Optional[AITaskContext] = None,
    ) -> BaseAIProvider:
        task_name = task.value if isinstance(task, AITask) else str(task)
        effective_context = context or AITaskContext(task=task_name)
        configured = self._policy_provider(task_name, effective_context)
        provider = self._get_provider(configured)

        if getattr(provider, "active", False):
            logger.debug(
                "AI task '%s' intent='%s' feature='%s' routed to provider '%s'.",
                task_name,
                effective_context.intent_name,
                effective_context.feature,
                configured,
            )
            return provider

        fallback_name = (settings.AI_FALLBACK_PROVIDER or settings.AI_PROVIDER or "").strip().lower()
        if fallback_name and fallback_name != configured.lower():
            fallback = self._get_provider(fallback_name)
            if getattr(fallback, "active", False):
                logger.warning(
                    "AI provider '%s' inactive for task '%s' intent='%s'; using fallback '%s'.",
                    configured,
                    task_name,
                    effective_context.intent_name,
                    fallback_name,
                )
                return fallback

        return provider

    def clear_cache(self) -> None:
        """Clear cached provider instances, mainly useful for tests or env reloads."""
        self._provider_cache.clear()

    def _get_provider(self, provider_name: str) -> BaseAIProvider:
        normalized = (provider_name or settings.AI_PROVIDER or "gemini").strip().lower()
        if normalized not in self._provider_cache:
            self._provider_cache[normalized] = get_ai_provider(normalized)
        return self._provider_cache[normalized]

    def _policy_provider(self, task_name: str, context: AITaskContext) -> str:
        if task_name == AITask.EMBEDDING.value:
            return self._configured_provider(task_name)

        if task_name == AITask.DRAFTING.value:
            return self._first_configured(
                getattr(settings, "AI_LEGAL_DRAFTING_PROVIDER", ""),
                settings.AI_DRAFTING_PROVIDER,
                settings.AI_PROVIDER,
                default="gemini",
            )

        if task_name == AITask.READER.value:
            return self._reader_policy_provider(context)

        return self._configured_provider(task_name)

    def _reader_policy_provider(self, context: AITaskContext) -> str:
        intent = context.intent_name.lower()
        risk = context.risk_name.lower()
        is_long_context = context.input_chars >= int(getattr(settings, "AI_LONG_DOCUMENT_THRESHOLD_CHARS", 25000) or 25000)

        if intent == AIIntent.LEGAL_REASONING.value or context.requires_citations or risk == AIRiskLevel.HIGH.value:
            return self._first_configured(
                getattr(settings, "AI_LEGAL_REASONING_PROVIDER", ""),
                settings.AI_READER_PROVIDER,
                settings.AI_PROVIDER,
                default="gemini",
            )

        if intent == AIIntent.DOCUMENT_ANALYSIS.value and context.feature in {"document_intelligence", "document_processing"}:
            return self._first_configured(
                getattr(settings, "AI_DOCUMENT_ANALYSIS_PROVIDER", ""),
                getattr(settings, "AI_LONG_CONTEXT_PROVIDER", ""),
                settings.AI_READER_PROVIDER,
                settings.AI_PROVIDER,
                default="gemini",
            )

        if is_long_context or intent in {AIIntent.DOCUMENT_ANALYSIS.value, AIIntent.DOCUMENT_QA.value}:
            return self._first_configured(
                getattr(settings, "AI_LONG_CONTEXT_PROVIDER", ""),
                settings.AI_READER_PROVIDER,
                settings.AI_PROVIDER,
                default="gemini",
            )

        if intent == AIIntent.CLASSIFICATION.value:
            return self._first_configured(
                getattr(settings, "AI_CLASSIFICATION_PROVIDER", ""),
                settings.AI_READER_PROVIDER,
                settings.AI_PROVIDER,
                default="gemini",
            )

        if intent == AIIntent.SUMMARIZATION.value and risk == AIRiskLevel.LOW.value:
            return self._first_configured(
                getattr(settings, "AI_LOW_RISK_PROVIDER", ""),
                settings.AI_READER_PROVIDER,
                settings.AI_PROVIDER,
                default="gemini",
            )

        return self._configured_provider(AITask.READER.value)

    def _configured_provider(self, task_name: str) -> str:
        task_provider = {
            AITask.READER.value: settings.AI_READER_PROVIDER,
            AITask.DRAFTING.value: settings.AI_DRAFTING_PROVIDER,
            AITask.EMBEDDING.value: settings.AI_EMBEDDING_PROVIDER,
        }.get(task_name, "")
        return self._first_configured(task_provider, settings.AI_PROVIDER, default="gemini")

    def _first_configured(self, *values: str, default: str) -> str:
        for value in values:
            if value and str(value).strip():
                return str(value).strip().lower()
        return default


ai_router = AIRouter()
