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


def get_ai_provider() -> BaseAIProvider:
    """Factory — returns the configured AI provider singleton."""
    return GeminiProvider()
