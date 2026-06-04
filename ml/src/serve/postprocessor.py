"""LLM postprocessor: top-K candidate sequence → fluent sentence.

Builds a system prompt explaining the task + the model's known accuracy
characteristics (top-1 ~72%, top-5 ~92%) so the LLM knows the truth is
almost always among the candidates and biases its choice accordingly.
"""

from __future__ import annotations

from typing import Iterable, List

from src.llm.base import BaseLLMClient
from src.serve.schemas import ClassifierOutput


_LANG_NAMES = {"en": "English", "pl": "Polish"}


def _lang_label(target_lang: str) -> str:
    return _LANG_NAMES.get(target_lang.lower(), target_lang)


def build_system_prompt(target_lang: str = "en") -> str:
    lang = _lang_label(target_lang)
    return (
        f"You convert ASL gloss predictions into a fluent {lang} sentence.\n\n"
        "For each sign in the sequence you receive top-5 candidate glosses with "
        "confidence scores. Top-1 is correct ~72% of the time, top-5 ~92%, so "
        "the true sign is almost always somewhere in the candidate list.\n\n"
        "Rules:\n"
        "- Use ONLY content words from the candidate lists. Pick the most "
        "contextually plausible candidate per slot, even if it isn't top-1.\n"
        f"- You may insert minimal connector words appropriate for {lang} "
        "(articles, copulas, conjunctions).\n"
        "- Preserve approximate ASL ordering (TOPIC-COMMENT). Output one "
        "sentence.\n"
        "- No explanation, no quotes, no markdown — just the sentence."
    )


def build_user_prompt(signs: Iterable[ClassifierOutput]) -> str:
    lines: List[str] = []
    for i, sign in enumerate(signs, start=1):
        tops = ", ".join(f"{g}({p:.2f})" for g, p in sign.top_k)
        lines.append(f"Sign {i}: {tops}")
    return "\n".join(lines)


class Postprocessor:
    def __init__(self, llm: BaseLLMClient, target_lang: str = "en"):
        self.llm = llm
        self.target_lang = target_lang
        self._system_prompt = build_system_prompt(target_lang)

    async def translate(self, signs: List[ClassifierOutput]) -> str:
        if not signs:
            return ""
        user = build_user_prompt(signs)
        return await self.llm.complete(self._system_prompt, user)

    async def aclose(self) -> None:
        await self.llm.aclose()
