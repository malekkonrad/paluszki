"""OpenAI-compatible chat completions client.

Works with any service speaking the OpenAI ``/v1/chat/completions`` shape:
OpenAI, Groq, Together, vLLM, Ollama (via ``http://localhost:11434/v1``),
llama.cpp ``--api``, etc. Pluggable via ``base_url``.
"""

from __future__ import annotations

import os

import httpx

from src.llm.base import BaseLLMClient


class OpenAICompatibleClient(BaseLLMClient):
    def __init__(
        self,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        api_key: str | None = None,
        api_key_env: str = "OPENAI_API_KEY",
        max_tokens: int = 256,
        temperature: float = 0.0,
        timeout: float = 30.0,
        extra_body: dict | None = None,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        # Some local servers (Ollama) don't require a key.
        self.api_key = api_key or os.environ.get(api_key_env, "")
        self.max_tokens = max_tokens
        self.temperature = temperature
        # Provider-specific params forwarded verbatim into the request body,
        # e.g. {"reasoning_effort": "none"} to disable a thinking model's
        # chain-of-thought (Ollama gemma4:e2b) so it doesn't burn the token
        # budget on reasoning and leave `content` empty.
        self.extra_body = extra_body or {}
        self._client = httpx.AsyncClient(timeout=timeout)

    async def complete(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            **self.extra_body,
        }
        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["authorization"] = f"Bearer {self.api_key}"

        resp = await self._client.post(
            f"{self.base_url}/chat/completions", json=payload, headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()

    async def aclose(self) -> None:
        await self._client.aclose()
