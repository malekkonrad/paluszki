"""Real-time sign-translation service.

Public API:

    from src.serve import TranslationSession, build_session_from_config

    session = build_session_from_config("configs/serve.yaml")
    result = await session.push_frame(bgr_frame, ts=time.time())
    if result is not None:
        print(result.text)

The pipeline is: frame → MediaPipe keypoints → motion segmenter → classifier
→ top-K buffer → LLM postprocessor → ``TranslationResult``.

Both the classifier and the LLM are pluggable via the YAML config — see
``ml/configs/serve.yaml``.
"""

from src.serve.schemas import (
    ClassifierOutput,
    SegmentEvent,
    TranslationResult,
)
from src.serve.session import TranslationSession
from src.serve.config import build_session_from_config

__all__ = [
    "ClassifierOutput",
    "SegmentEvent",
    "TranslationResult",
    "TranslationSession",
    "build_session_from_config",
]
