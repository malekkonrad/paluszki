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


def build_system_prompt(target_lang: str = "en", speaker_name: str | None = None) -> str:
    lang = _lang_label(target_lang)
    speaker = ""
    if speaker_name:
        speaker = (
            f'\nThe signer\'s name is "{speaker_name}". The sentence is spoken in '
            "their first-person voice — where the language marks gender (e.g. "
            "Polish past-tense verbs, adjectives), use the grammatical gender "
            "this first name most likely implies.\n"
        )
    return (
        f"You convert American Sign Language gloss predictions into one fluent, "
        f"natural {lang} sentence, as if said aloud in a video call.\n\n"
        "For each sign you receive top-5 candidate glosses with confidence "
        "scores. Top-1 is correct ~72% of the time and top-5 ~92%, so the true "
        "sign is almost always in the list — per slot, pick the candidate that "
        "makes the whole sentence coherent, even if it isn't top-1. If no "
        "candidate fits the context at all, you may skip that slot.\n"
        f"{speaker}\n"
        "Rules:\n"
        "- Each sign contributes EXACTLY ONE word, taken from that sign's own "
        "candidate list (or the sign is skipped). NEVER use two candidates "
        "from the same list — they are alternative readings of one sign, not "
        "separate words.\n"
        "- Never invent content that has no corresponding sign. One sign in, "
        "one word out: for a single sign just output that word as a minimal "
        f"{lang} utterance (e.g. a greeting or 'yes' stays one word).\n"
        "- Inflect the chosen words freely (tense, case, number, gender) so "
        f"the {lang} reads naturally.\n"
        f"- Add only the small function words {lang} needs (conjunctions, "
        "prepositions, copulas, pronouns).\n"
        "- Reorder into natural target-language syntax; the input follows ASL "
        "TOPIC-COMMENT order — do not copy it literally.\n"
        "- Output exactly one sentence — no explanation, no quotes, no markdown.\n\n"
        "Example (target Polish):\n"
        "Input:  Sign 1: yes(0.71), need(0.12), that(0.08), hear(0.05), computer(0.04)\n"
        "Output: Tak.\n"
        "(One sign → one word. 'need', 'that' etc. are alternative readings "
        "of the SAME sign, not extra words to weave in.)"
    )


def build_user_prompt(signs: Iterable[ClassifierOutput]) -> str:
    lines: List[str] = []
    for i, sign in enumerate(signs, start=1):
        tops = ", ".join(f"{g}({p:.2f})" for g, p in sign.top_k)
        lines.append(f"Sign {i}: {tops}")
    return "\n".join(lines)


class Postprocessor:
    def __init__(self, llm: BaseLLMClient, target_lang: str = "en", speaker_name: str | None = None):
        self.llm = llm
        self.target_lang = target_lang
        self._system_prompt = build_system_prompt(target_lang, speaker_name)

    async def translate(self, signs: List[ClassifierOutput]) -> str:
        if not signs:
            return ""
        user = build_user_prompt(signs)
        return await self.llm.complete(self._system_prompt, user)

    async def aclose(self) -> None:
        await self.llm.aclose()
