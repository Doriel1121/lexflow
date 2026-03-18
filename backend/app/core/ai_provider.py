import asyncio
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Dict, List, Optional

import google.generativeai as genai
import httpx
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Shared thread-pool for running sync Gemini SDK calls off the event loop
_thread_pool = ThreadPoolExecutor(max_workers=4)


async def _run_sync(fn, *args, **kwargs):
    """Run a blocking (synchronous) call in a thread pool so it doesn't block the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_thread_pool, partial(fn, *args, **kwargs))


class BaseAIProvider(ABC):
    """Abstract base class for all AI model providers."""

    @abstractmethod
    async def generate_text(self, prompt: str) -> Optional[str]:
        pass

    @abstractmethod
    async def generate_json(self, prompt: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    async def generate_embedding(self, text: str) -> List[float]:
        pass


class GeminiProvider(BaseAIProvider):
    """Concrete implementation for Google Gemini API."""

    EMBEDDING_DIMENSION = 768  # text-embedding-004
    MAX_RETRIES = 10
    INITIAL_BACKOFF = 15  # seconds - much more patient for Free Tier

    def __init__(self):
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        self.active = False
        self.model = None

        if not api_key:
            logger.warning("GEMINI_API_KEY not set — AI Provider is inactive.")
            return

        try:
            genai.configure(api_key=api_key)
            # Use gemini-2.0-flash which has separate quota
            self.model = genai.GenerativeModel("gemini-2.0-flash")
            self.embedding_model = "models/text-embedding-004"
            self.active = True
            logger.info("Gemini AI Provider initialised successfully with gemini-2.0-flash.")
        except Exception as e:
            logger.error(f"Failed to initialise Gemini: {e}")

    # ------------------------------------------------------------------
    # Internal Retry Wrapper
    # ------------------------------------------------------------------
    
    async def _call_with_retry(self, fn, *args, **kwargs):
        """Helper to call Gemini with exponential backoff on 429 errors."""
        retries = 0
        backoff = self.INITIAL_BACKOFF
        
        while retries < self.MAX_RETRIES:
            try:
                return await _run_sync(fn, *args, **kwargs)
            except Exception as e:
                err_msg = str(e).lower()
                if "429" in err_msg or "quota" in err_msg or "rate limit" in err_msg:
                    retries += 1
                    if retries >= self.MAX_RETRIES:
                        logger.error(f"Gemini quota exceeded after {retries} retries: {e}")
                        raise
                    
                    logger.warning(f"Gemini quota hit. Retrying in {backoff}s... (Attempt {retries}/{self.MAX_RETRIES})")
                    await asyncio.sleep(backoff)
                    backoff *= 2 # Exponential backoff
                else:
                    # Not a quota error, just re-raise
                    raise

    # ------------------------------------------------------------------
    # Public API — all calls are properly offloaded to a thread pool
    # ------------------------------------------------------------------

    async def generate_text(self, prompt: str) -> Optional[str]:
        if not self.active or not self.model:
            logger.warning("AI Provider inactive — skipping generate_text.")
            return None
        try:
            response = await self._call_with_retry(self.model.generate_content, prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini generate_text error: {e}")
            raise

    async def generate_json(self, prompt: str) -> Optional[Dict[str, Any]]:
        if not self.active or not self.model:
            logger.warning("AI Provider inactive — skipping generate_json.")
            return None
        try:
            response = await self._call_with_retry(self.model.generate_content, prompt)
            result_text = response.text.strip()

            # Strip markdown code fences if present
            for fence in ("```json", "```"):
                if result_text.startswith(fence):
                    result_text = result_text[len(fence):]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
            result_text = result_text.strip()

            try:
                return json.loads(result_text)
            except json.JSONDecodeError:
                logger.error(
                    "Gemini returned invalid JSON (first 300 chars): %s",
                    result_text[:300],
                )
                return None
        except Exception as e:
            logger.error(f"Gemini generate_json error: {e}")
            raise

    async def generate_embedding(self, text: str) -> List[float]:
        if not self.active:
            logger.warning("AI Provider inactive — returning zero vector for embedding.")
            return [0.0] * self.EMBEDDING_DIMENSION
        try:
            result = await self._call_with_retry(
                genai.embed_content,
                model=self.embedding_model,
                content=text,
                task_type="retrieval_document",
            )
            return result["embedding"]
        except Exception as e:
            logger.error(f"Gemini embedding error: {e}")
            # If embedding fails completely, return zero vector so pipeline continues
            return [0.0] * self.EMBEDDING_DIMENSION


class OpenRouterProvider(BaseAIProvider):
    """OpenRouter (OpenAI-compatible) chat + embeddings API."""

    def __init__(self):
        load_dotenv()
        self.base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        self.api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        self.model = os.getenv("OPENROUTER_MODEL", "").strip()
        self.embedding_model = os.getenv("OPENROUTER_EMBEDDING_MODEL", "").strip()
        self.embedding_dimension = int(os.getenv("OPENROUTER_EMBEDDING_DIM", "768"))
        self.timeout_s = float(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "120"))
        self.app_url = os.getenv("OPENROUTER_APP_URL", "").strip()
        self.app_name = os.getenv("OPENROUTER_APP_NAME", "").strip()
        self.active = bool(self.api_key and self.model)

        if not self.active:
            logger.warning("OpenRouter API key/model not set — provider inactive.")
        else:
            logger.info("OpenRouter Provider initialised. model=%s", self.model)

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.app_url:
            headers["HTTP-Referer"] = self.app_url
        if self.app_name:
            headers["X-Title"] = self.app_name
        return headers

    async def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = self.base_url.rstrip("/") + path
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            resp = await client.post(url, json=payload, headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    async def generate_text(self, prompt: str) -> Optional[str]:
        if not self.active:
            logger.warning("OpenRouter Provider inactive — skipping generate_text.")
            return None
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        result = await self._post("/chat/completions", payload)
        try:
            return result["choices"][0]["message"]["content"]
        except Exception:
            return None

    async def generate_json(self, prompt: str) -> Optional[Dict[str, Any]]:
        if not self.active:
            logger.warning("OpenRouter Provider inactive — skipping generate_json.")
            return None
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }
        result = await self._post("/chat/completions", payload)
        content = None
        try:
            content = result["choices"][0]["message"]["content"]
        except Exception:
            content = None
        if not content:
            return None
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.error("OpenRouter returned invalid JSON (first 300 chars): %s", content[:300])
            return None

    async def generate_embedding(self, text: str) -> List[float]:
        if not self.active:
            logger.warning("OpenRouter Provider inactive — returning zero vector for embedding.")
            return [0.0] * self.embedding_dimension
        if not self.embedding_model:
            logger.warning("OpenRouter embedding model not set — returning zero vector.")
            return [0.0] * self.embedding_dimension
        payload = {
            "model": self.embedding_model,
            "input": text,
        }
        result = await self._post("/embeddings", payload)
        data = result.get("data") or []
        if not data:
            return [0.0] * self.embedding_dimension
        vector = data[0].get("embedding") or []
        if len(vector) != self.embedding_dimension:
            if len(vector) > self.embedding_dimension:
                vector = vector[: self.embedding_dimension]
            else:
                vector = vector + ([0.0] * (self.embedding_dimension - len(vector)))
        return vector


class CohereProvider(BaseAIProvider):
    """Cohere chat + embeddings API."""

    def __init__(self):
        load_dotenv()
        raw_url = os.getenv("COHERE_BASE_URL", "https://api.cohere.com")
        compat_raw = os.getenv("COHERE_COMPAT_BASE_URL", "https://api.cohere.ai/compatibility/v1")
        # Native (v2) base URL
        self.base_url = raw_url.rstrip("/").replace("/compatibility/v1", "").replace("/v1", "")
        # Compatibility (OpenAI-style) base URL
        self.compat_base_url = compat_raw.rstrip("/")
        self.api_key = os.getenv("COHERE_API_KEY", "").strip()
        self.model = os.getenv("COHERE_MODEL", "command-r").strip()
        self.embedding_model = os.getenv("COHERE_EMBEDDING_MODEL", "embed-english-v3.0").strip()
        self.embedding_dimension = int(os.getenv("COHERE_EMBEDDING_DIM", "768"))
        self.timeout_s = float(os.getenv("COHERE_TIMEOUT_SECONDS", "120"))
        self.active = bool(self.api_key and self.model)

        if not self.active:
            logger.warning("Cohere API key/model not set — provider inactive.")
        else:
            logger.info("Cohere Provider initialised. model=%s", self.model)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _post(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            resp = await client.post(url, json=payload, headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    async def generate_text(self, prompt: str) -> Optional[str]:
        if not self.active:
            logger.warning("Cohere Provider inactive — skipping generate_text.")
            return None
        compat_url = self.compat_base_url + "/chat/completions"
        native_url = self.base_url.rstrip("/") + "/v2/chat"

        compat_payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            result = await self._post(compat_url, compat_payload)
            return result["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            if e.response.status_code not in (404, 405):
                raise

        native_payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        result = await self._post(native_url, native_payload)
        try:
            # v2 returns message.content as a list of parts
            parts = result.get("message", {}).get("content") or []
            return "".join([p.get("text", "") for p in parts if isinstance(p, dict)])
        except Exception:
            return result.get("text")

    async def generate_json(self, prompt: str) -> Optional[Dict[str, Any]]:
        if not self.active:
            logger.warning("Cohere Provider inactive — skipping generate_json.")
            return None
        compat_url = self.compat_base_url + "/chat/completions"
        native_url = self.base_url.rstrip("/") + "/v2/chat"

        content = ""
        # Try OpenAI-compatible endpoint first
        compat_payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }
        try:
            result = await self._post(compat_url, compat_payload)
            content = (result["choices"][0]["message"]["content"] or "").strip()
        except Exception as e:
            logger.debug("Cohere compat JSON failed (expected if endpoint missing): %s", e)
            content = ""

        # Fallback to native Cohere Chat API (v2)
        if not content:
            native_payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            }
            try:
                result = await self._post(native_url, native_payload)
                parts = result.get("message", {}).get("content") or []
                content = "".join([p.get("text", "") for p in parts if isinstance(p, dict)]).strip()
            except Exception as e:
                logger.error("Cohere native JSON failed: %s", e)
                return None

        if not content:
            return None

        # Clean up markdown code fences if the model ignored response_format
        for fence in ("```json", "```"):
            if content.startswith(fence):
                content = content[len(fence):]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.error("Cohere returned invalid JSON (first 300 chars): %s", content[:300])
            return None

    async def generate_embedding(self, text: str) -> List[float]:
        if not self.active:
            logger.warning("Cohere Provider inactive — returning zero vector for embedding.")
            return [0.0] * self.embedding_dimension
        if not self.embedding_model:
            logger.warning("Cohere embedding model not set — returning zero vector.")
            return [0.0] * self.embedding_dimension
        
        compat_url = self.compat_base_url + "/embeddings"
        native_url = self.base_url.rstrip("/") + "/v2/embed"

        embeddings = []
        # Try compat first
        compat_payload = {
            "model": self.embedding_model,
            "input": [text],
        }
        try:
            result = await self._post(compat_url, compat_payload)
            data = result.get("data") or []
            if data and isinstance(data[0], dict):
                embeddings = [data[0].get("embedding")]
        except Exception:
            embeddings = []

        # Fallback to native
        if not embeddings:
            native_payload = {
                "model": self.embedding_model,
                "texts": [text],
                "input_type": "search_document", # Required for v3 models
                "embedding_types": ["float"],
            }
            try:
                result = await self._post(native_url, native_payload)
                if isinstance(result.get("embeddings"), dict):
                    embeddings = result.get("embeddings", {}).get("float") or []
                else:
                    embeddings = result.get("embeddings") or []
            except Exception as e:
                logger.error("Cohere native embedding failed: %s", e)
                return [0.0] * self.embedding_dimension

        if not embeddings:
            return [0.0] * self.embedding_dimension
        
        vector = embeddings[0]
        if not vector:
            return [0.0] * self.embedding_dimension
            
        if len(vector) != self.embedding_dimension:
            if len(vector) > self.embedding_dimension:
                vector = vector[: self.embedding_dimension]
            else:
                vector = vector + ([0.0] * (self.embedding_dimension - len(vector)))
        return vector


def get_ai_provider() -> BaseAIProvider:
    """Factory — returns the configured AI provider singleton."""
    load_dotenv()
    provider_name = (os.getenv("AI_PROVIDER") or "gemini").strip().lower()
    
    if provider_name == "ollama":
        provider = OllamaProvider()
    elif provider_name == "openrouter":
        provider = OpenRouterProvider()
    elif provider_name == "cohere":
        provider = CohereProvider()
    else:
        provider = GeminiProvider()
        
    if not getattr(provider, "active", False):
        logger.warning(f"AI Provider '{provider_name}' is INACTIVE. Check your API keys and configuration.")
        
    return provider


class OllamaProvider(BaseAIProvider):
    """Concrete implementation for local Ollama REST API."""

    def __init__(self):
        load_dotenv()
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "").strip()
        self.embedding_model = os.getenv("OLLAMA_EMBEDDING_MODEL", "").strip() or self.model
        self.embedding_dimension = int(os.getenv("OLLAMA_EMBEDDING_DIM", "768"))
        self.timeout_s = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
        self.active = bool(self.model)

        if not self.active:
            logger.warning("OLLAMA_MODEL not set â€” Ollama Provider is inactive.")
        else:
            logger.info("Ollama Provider initialised. base_url=%s, model=%s", self.base_url, self.model)

    def _api_url(self, path: str) -> str:
        base = self.base_url.rstrip("/")
        if base.endswith("/api"):
            return f"{base}{path}"
        return f"{base}/api{path}"

    async def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = self._api_url(path)
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()

    async def generate_text(self, prompt: str) -> Optional[str]:
        if not self.active:
            logger.warning("Ollama Provider inactive â€” skipping generate_text.")
            return None
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        result = await self._post("/generate", payload)
        return result.get("response")

    async def generate_json(self, prompt: str) -> Optional[Dict[str, Any]]:
        if not self.active:
            logger.warning("Ollama Provider inactive â€” skipping generate_json.")
            return None
        payload = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
        }
        result = await self._post("/generate", payload)
        raw = (result.get("response") or "").strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.error("Ollama returned invalid JSON (first 300 chars): %s", raw[:300])
            return None

    async def generate_embedding(self, text: str) -> List[float]:
        if not self.active:
            logger.warning("Ollama Provider inactive â€” returning zero vector for embedding.")
            return [0.0] * self.embedding_dimension
        payload = {
            "model": self.embedding_model,
            "input": text,
            "truncate": True,
        }
        result = await self._post("/embed", payload)
        embeddings = result.get("embeddings") or []
        if not embeddings:
            return [0.0] * self.embedding_dimension
        vector = embeddings[0]
        # Ensure correct dimensionality for pgvector column
        if len(vector) != self.embedding_dimension:
            if len(vector) > self.embedding_dimension:
                vector = vector[: self.embedding_dimension]
            else:
                vector = vector + ([0.0] * (self.embedding_dimension - len(vector)))
        return vector
