"""TranslationSession — orchestrates the full pipeline.

    frame  →  extractor  →  segmenter  →  classifier  →  buffer  →  LLM  →  text

Two input modes:
- ``push_frame(bgr_frame)`` — the session does MediaPipe extraction.
- ``push_keypoints(kp)``    — for callers that already have keypoints.

The session is stateful and not thread-safe: each connection should hold
its own instance.
"""

from __future__ import annotations

import time
from typing import Optional

import numpy as np

from src.serve.buffer import TopKBuffer
from src.serve.classifier_runner import ClassifierRunner
from src.serve.live_keypoint_extractor import LiveKeypointExtractor
from src.serve.postprocessor import Postprocessor
from src.serve.schemas import ClassifierOutput, TranslationResult
from src.serve.segmenter import Segmenter


class TranslationSession:
    def __init__(
        self,
        classifier: ClassifierRunner,
        segmenter: Segmenter,
        buffer: TopKBuffer,
        postprocessor: Postprocessor,
        extractor: Optional[LiveKeypointExtractor] = None,
        min_confidence: float = 0.5,
        target_lang: str = "en",
    ):
        self.classifier = classifier
        self.segmenter = segmenter
        self.buffer = buffer
        self.postprocessor = postprocessor
        self.extractor = extractor
        self.min_confidence = min_confidence
        self.target_lang = target_lang

    async def push_frame(
        self, frame_bgr: np.ndarray, ts: Optional[float] = None,
    ) -> Optional[TranslationResult]:
        if self.extractor is None:
            raise RuntimeError(
                "push_frame called but no extractor configured; "
                "either provide extractor or use push_keypoints.",
            )
        ts = time.time() if ts is None else ts
        kp = self.extractor.extract(frame_bgr)
        return await self._on_keypoints(kp, ts)

    async def push_keypoints(
        self, kp: np.ndarray, ts: Optional[float] = None,
    ) -> Optional[TranslationResult]:
        ts = time.time() if ts is None else ts
        return await self._on_keypoints(kp, ts)

    async def tick(self, ts: Optional[float] = None) -> Optional[TranslationResult]:
        """Periodic check with no input. Use when the frame stream pauses
        but you still want pause-based flush to fire."""
        ts = time.time() if ts is None else ts
        if self.buffer.should_flush(ts):
            return await self._flush()
        return None

    async def flush(self) -> Optional[TranslationResult]:
        """Force-flush whatever's buffered. Used at end of session."""
        return await self._flush()

    async def _on_keypoints(
        self, kp: np.ndarray, ts: float,
    ) -> Optional[TranslationResult]:
        seg = self.segmenter.push(kp, ts)
        if seg is not None:
            classified = self.classifier.predict(
                seg.keypoints,
                started_at=seg.started_at,
                ended_at=seg.ended_at,
            )
            if classified.raw_argmax_conf >= self.min_confidence:
                self.buffer.push(classified, ts)

        if self.buffer.should_flush(ts):
            return await self._flush()
        return None

    async def _flush(self) -> Optional[TranslationResult]:
        signs = self.buffer.flush()
        if not signs:
            return None
        text = await self.postprocessor.translate(signs)
        return TranslationResult(
            text=text,
            source_signs=signs,
            started_at=signs[0].started_at,
            ended_at=signs[-1].ended_at,
            target_lang=self.target_lang,
        )

    async def aclose(self) -> None:
        if self.extractor is not None:
            self.extractor.close()
        await self.postprocessor.aclose()

    # Sync convenience for resource cleanup in non-async contexts.
    def close(self) -> None:
        if self.extractor is not None:
            self.extractor.close()
