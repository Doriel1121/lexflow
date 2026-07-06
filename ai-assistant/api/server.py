from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from api.ollama_client import OllamaClient, OllamaRequestError
from api.prompt_builder import PromptBuilder
from api.schemas import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    DebugRetrieveRequest,
    DebugRetrieveResponse,
)
from config import DEFAULT_CONFIG, AppConfig
from retrieval.context_retriever import ContextRetriever

app = FastAPI(title="LexFlow Local AI", version="0.0.1")


@lru_cache(maxsize=1)
def get_retriever() -> ContextRetriever:
    return ContextRetriever(DEFAULT_CONFIG)


@lru_cache(maxsize=1)
def get_ollama_client() -> OllamaClient:
    return OllamaClient(DEFAULT_CONFIG)


@lru_cache(maxsize=1)
def get_prompt_builder() -> PromptBuilder:
    return PromptBuilder(DEFAULT_CONFIG)


def resolve_model(requested_model: str, config: AppConfig = DEFAULT_CONFIG) -> str:
    normalized = (requested_model or "").lower()
    if normalized in {"", "lexflow-local", "lexflow-local-coder"}:
        return config.default_chat_model
    if "architect" in normalized or normalized == "lexflow-local-architect":
        return config.default_architect_model
    return requested_model


def latest_user_message(messages: list[ChatMessage]) -> str:
    for message in reversed(messages):
        if message.role == "user":
            return message.content
    return messages[-1].content if messages else ""


def message_to_dict(message: ChatMessage) -> dict[str, str]:
    if hasattr(message, "model_dump"):
        return message.model_dump()
    return message.dict()


def sse_event(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def completion_chunk(
    *,
    completion_id: str,
    created: int,
    model: str,
    content: str = "",
    role: str | None = None,
    finish_reason: str | None = None,
) -> dict[str, Any]:
    delta: dict[str, str] = {}
    if role is not None:
        delta["role"] = role
    if content:
        delta["content"] = content
    return {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason,
            }
        ],
    }


def build_prompt(request: ChatCompletionRequest) -> tuple[str, str]:
    query = latest_user_message(request.messages)
    retrieved = get_retriever().retrieve(query, top_k=DEFAULT_CONFIG.top_k)
    prompt = get_prompt_builder().build(
        messages=[message_to_dict(message) for message in request.messages],
        retrieved=retrieved,
    )
    model = resolve_model(request.model)
    return prompt, model


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "lexflow-local-ai",
        "index_exists": DEFAULT_CONFIG.index_path.exists(),
        "metadata_exists": DEFAULT_CONFIG.metadata_path.exists(),
        "graph_exists": DEFAULT_CONFIG.graph_path.exists(),
        "chat_model": DEFAULT_CONFIG.default_chat_model,
        "architect_model": DEFAULT_CONFIG.default_architect_model,
    }


@app.post("/debug/retrieve", response_model=DebugRetrieveResponse)
def debug_retrieve(request: DebugRetrieveRequest) -> DebugRetrieveResponse:
    try:
        results = get_retriever().retrieve(request.query, top_k=request.top_k)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="Index files are missing. Run python index_project.py first.") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {exc}") from exc
    return DebugRetrieveResponse(query=request.query, results=results)


@app.post("/v1/chat/completions", response_model=None)
def chat_completions(request: ChatCompletionRequest):
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages must contain at least one item")

    try:
        prompt, model = build_prompt(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="Index files are missing. Run python index_project.py first.") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {exc}") from exc

    if request.stream:
        return StreamingResponse(
            stream_chat_completion(request=request, prompt=prompt, model=model),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    try:
        answer = get_ollama_client().generate(
            model=model,
            prompt=prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
    except OllamaRequestError as exc:
        raise HTTPException(status_code=502, detail=f"Ollama request failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat completion failed: {exc}") from exc

    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex}",
        created=int(time.time()),
        model=model,
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content=answer),
                finish_reason="stop",
            )
        ],
    )


def stream_chat_completion(*, request: ChatCompletionRequest, prompt: str, model: str) -> Iterator[str]:
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())
    yield sse_event(completion_chunk(completion_id=completion_id, created=created, model=model, role="assistant"))
    try:
        for token in get_ollama_client().stream_generate(
            model=model,
            prompt=prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        ):
            yield sse_event(completion_chunk(completion_id=completion_id, created=created, model=model, content=token))
        yield sse_event(completion_chunk(completion_id=completion_id, created=created, model=model, finish_reason="stop"))
        yield "data: [DONE]\n\n"
    except OllamaRequestError as exc:
        yield sse_event({"error": {"message": f"Ollama request failed: {exc}", "type": "ollama_error"}})
        yield "data: [DONE]\n\n"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.server:app", host=DEFAULT_CONFIG.api_host, port=DEFAULT_CONFIG.api_port, reload=False)

