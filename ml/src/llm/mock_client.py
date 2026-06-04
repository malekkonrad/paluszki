"""Deterministic offline LLM client for tests / smoke runs.

Picks the top-1 candidate from each input ``Sign N: GLOSS(prob), ...`` line
and joins them lowercased. Useful for end-to-end testing the pipeline
without burning API credit.
"""

from __future__ import annotations

import re

from src.llm.base import BaseLLMClient


class MockLLMClient(BaseLLMClient):
    _SIGN_RE = re.compile(r"^Sign\s+\d+:\s*([A-Z0-9_]+)\(", re.MULTILINE)

    def __init__(self, prefix: str = "[mock] ", **_ignored):
        self.prefix = prefix

    async def complete(self, system: str, user: str) -> str:
        tops = self._SIGN_RE.findall(user)
        if not tops:
            return f"{self.prefix}(no signs)"
        words = [t.split("1")[0].split("2")[0].lower() for t in tops]
        return f"{self.prefix}{' '.join(words)}"
