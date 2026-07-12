from app.core import ai_router as router_module
from app.core.ai_router import AIIntent, AIRiskLevel, AIRouter, AITask, AITaskContext


class DummyProvider:
    def __init__(self, name: str, active: bool = True):
        self.name = name
        self.active = active


def set_base_settings(monkeypatch):
    monkeypatch.setattr(router_module.settings, "AI_PROVIDER", "cohere")
    monkeypatch.setattr(router_module.settings, "AI_READER_PROVIDER", "gemini")
    monkeypatch.setattr(router_module.settings, "AI_DRAFTING_PROVIDER", "openrouter")
    monkeypatch.setattr(router_module.settings, "AI_EMBEDDING_PROVIDER", "cohere")
    monkeypatch.setattr(router_module.settings, "AI_FALLBACK_PROVIDER", "gemini")
    monkeypatch.setattr(router_module.settings, "AI_LEGAL_REASONING_PROVIDER", "dictalm")
    monkeypatch.setattr(router_module.settings, "AI_LEGAL_DRAFTING_PROVIDER", "")
    monkeypatch.setattr(router_module.settings, "AI_LONG_CONTEXT_PROVIDER", "gemini")
    monkeypatch.setattr(router_module.settings, "AI_CLASSIFICATION_PROVIDER", "cohere")
    monkeypatch.setattr(router_module.settings, "AI_LOW_RISK_PROVIDER", "cohere")
    monkeypatch.setattr(router_module.settings, "AI_LONG_DOCUMENT_THRESHOLD_CHARS", 1000)


def mock_providers(monkeypatch, inactive_names=None):
    inactive_names = set(inactive_names or [])

    def fake_get_ai_provider(name=None):
        provider_name = (name or "gemini").lower()
        return DummyProvider(provider_name, active=provider_name not in inactive_names)

    monkeypatch.setattr(router_module, "get_ai_provider", fake_get_ai_provider)


def test_task_defaults_route_to_task_specific_providers(monkeypatch):
    set_base_settings(monkeypatch)
    mock_providers(monkeypatch)
    router = AIRouter()

    assert router.provider_for(AITask.EMBEDDING).name == "cohere"
    assert router.provider_for(AITask.DRAFTING).name == "openrouter"
    assert router.provider_for(AITask.READER).name == "gemini"


def test_reader_policy_routes_legal_reasoning_to_override(monkeypatch):
    set_base_settings(monkeypatch)
    mock_providers(monkeypatch)
    router = AIRouter()

    provider = router.provider_for(
        AITask.READER,
        AITaskContext(
            task=AITask.READER,
            feature="ask_ai",
            intent=AIIntent.LEGAL_REASONING,
            language="he",
            input_chars=500,
            risk_level=AIRiskLevel.HIGH,
            requires_citations=True,
        ),
    )

    assert provider.name == "dictalm"


def test_reader_policy_routes_long_context_and_classification(monkeypatch):
    set_base_settings(monkeypatch)
    mock_providers(monkeypatch)
    router = AIRouter()

    long_context = router.provider_for(
        AITask.READER,
        AITaskContext(
            task=AITask.READER,
            feature="document_intelligence",
            intent=AIIntent.DOCUMENT_ANALYSIS,
            input_chars=5000,
        ),
    )
    classification = router.provider_for(
        AITask.READER,
        AITaskContext(
            task=AITask.READER,
            feature="tags",
            intent=AIIntent.CLASSIFICATION,
            input_chars=200,
            risk_level=AIRiskLevel.LOW,
        ),
    )

    assert long_context.name == "gemini"
    assert classification.name == "cohere"


def test_inactive_policy_provider_falls_back(monkeypatch):
    set_base_settings(monkeypatch)
    mock_providers(monkeypatch, inactive_names={"dictalm"})
    router = AIRouter()

    provider = router.provider_for(
        AITask.READER,
        AITaskContext(
            task=AITask.READER,
            feature="ask_ai",
            intent=AIIntent.LEGAL_REASONING,
            risk_level=AIRiskLevel.HIGH,
        ),
    )

    assert provider.name == "gemini"
