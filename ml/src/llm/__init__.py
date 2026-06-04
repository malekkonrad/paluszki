"""Pluggable LLM clients for the translation postprocessor.

All clients share :class:`BaseLLMClient` interface so the pipeline can
swap providers (Anthropic, OpenAI-compatible, Gemini, local) via config.
"""

from src.llm.base import BaseLLMClient
from src.llm.registry import build_llm_client

__all__ = ["BaseLLMClient", "build_llm_client"]
