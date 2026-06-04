"""Abstract base for LLM clients used by the translation postprocessor."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLLMClient(ABC):
    """Minimal contract: take a (system, user) prompt pair, return text."""

    @abstractmethod
    async def complete(self, system: str, user: str) -> str:
        """Return the model's text response to ``user`` under ``system`` instructions.

        Implementations should set ``temperature=0`` and a small ``max_tokens``
        to keep outputs deterministic and cheap (the postprocessor expects
        a single short sentence).
        """
        raise NotImplementedError

    async def aclose(self) -> None:
        """Optional: release async resources (e.g. HTTP clients)."""
        return None
