"""Anthropic Messages API client (Claude).

Uses ``httpx`` directly — no SDK dependency. Set ``ANTHROPIC_API_KEY`` in
the environment or pass ``api_key`` explicitly.
"""

from __future__ import annotations

import os

import httpx

from src.llm.base import BaseLLMClient


class AnthropicClient(BaseLLMClient):
    API_URL = "https://api.anthropic.com/v1/messages"
    API_VERSION = "2023-06-01"

    def __init__(
        self,
        model: str = "claude-haiku-4-5-20251001",
        api_key: str | None = None,
        max_tokens: int = 256,
        temperature: float = 0.0,
        timeout: float = 30.0,
    ):
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key missing — set ANTHROPIC_API_KEY env var "
                "or pass api_key explicitly."
            )
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = httpx.AsyncClient(timeout=timeout)

    async def complete(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.API_VERSION,
            "content-type": "application/json",
        }
        resp = await self._client.post(self.API_URL, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        # data["content"] is a list of content blocks; pick the first text block.
        for block in data.get("content", []):
            if block.get("type") == "text":
                return block.get("text", "").strip()
        return ""

    async def aclose(self) -> None:
        await self._client.aclose()
