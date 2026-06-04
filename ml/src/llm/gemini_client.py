"""Google Gemini ``generateContent`` client (REST, no SDK)."""

from __future__ import annotations

import os

import httpx

from src.llm.base import BaseLLMClient


class GeminiClient(BaseLLMClient):
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        api_key: str | None = None,
        max_tokens: int = 256,
        temperature: float = 0.0,
        timeout: float = 30.0,
    ):
        self.model = model
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Gemini API key missing — set GEMINI_API_KEY env var "
                "or pass api_key explicitly.",
            )
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = httpx.AsyncClient(timeout=timeout)

    async def complete(self, system: str, user: str) -> str:
        url = f"{self.BASE_URL}/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_tokens,
            },
        }
        resp = await self._client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts).strip()

    async def aclose(self) -> None:
        await self._client.aclose()
