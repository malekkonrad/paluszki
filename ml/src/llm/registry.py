"""Build an LLM client from a config dict.

Supported ``type`` values:

- ``anthropic``         — Claude via Messages API
- ``openai_compat``     — OpenAI-shaped /v1/chat/completions (OpenAI / Ollama / vLLM / Groq / ...)
- ``gemini``            — Google Gemini via REST
- ``mock``              — deterministic offline stub for tests
"""

from __future__ import annotations

from typing import Any, Dict

from src.llm.base import BaseLLMClient


def build_llm_client(cfg: Dict[str, Any]) -> BaseLLMClient:
    """Instantiate an LLM client from a flat config dict.

    The caller passes the ``llm:`` section of ``serve.yaml`` augmented with
    any overrides. ``type`` selects the implementation; remaining keys are
    forwarded as constructor kwargs.
    """
    cfg = dict(cfg)  # don't mutate caller's dict
    kind = cfg.pop("type", None)
    if kind is None:
        raise ValueError("llm config must include a 'type' field")

    if kind == "anthropic":
        from src.llm.anthropic_client import AnthropicClient
        return AnthropicClient(**cfg)
    if kind == "openai_compat":
        from src.llm.openai_compat_client import OpenAICompatibleClient
        return OpenAICompatibleClient(**cfg)
    if kind == "gemini":
        from src.llm.gemini_client import GeminiClient
        return GeminiClient(**cfg)
    if kind == "mock":
        from src.llm.mock_client import MockLLMClient
        return MockLLMClient(**cfg)

    raise ValueError(f"Unknown llm.type: {kind!r}")
