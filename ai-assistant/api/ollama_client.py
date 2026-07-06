from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any
from urllib import error, request

from config import DEFAULT_CONFIG, AppConfig


class OllamaRequestError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, config: AppConfig = DEFAULT_CONFIG) -> None:
        self.base_url = config.ollama_base_url.rstrip("/")
        self.timeout = config.ollama_timeout_seconds

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        payload = self._build_payload(
            model=model,
            prompt=prompt,
            stream=False,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        try:
            with request.urlopen(self._request(payload), timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.URLError as exc:
            raise OllamaRequestError(str(exc)) from exc
        except json.JSONDecodeError as exc:
            raise OllamaRequestError(f"Invalid Ollama JSON response: {exc}") from exc
        return str(data.get("response", "")).strip()

    def stream_generate(
        self,
        *,
        model: str,
        prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        payload = self._build_payload(
            model=model,
            prompt=prompt,
            stream=True,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        try:
            with request.urlopen(self._request(payload), timeout=self.timeout) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise OllamaRequestError(f"Invalid Ollama stream JSON response: {exc}") from exc
                    token = data.get("response")
                    if token:
                        yield str(token)
                    if data.get("done"):
                        break
        except error.URLError as exc:
            raise OllamaRequestError(str(exc)) from exc

    def _build_payload(
        self,
        *,
        model: str,
        prompt: str,
        stream: bool,
        temperature: float | None,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        options: dict[str, Any] = {}
        if temperature is not None:
            options["temperature"] = temperature
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
        }
        if options:
            payload["options"] = options
        return payload

    def _request(self, payload: dict[str, Any]) -> request.Request:
        body = json.dumps(payload).encode("utf-8")
        return request.Request(
            f"{self.base_url}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
