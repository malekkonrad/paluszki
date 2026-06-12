"""TranslationSession — orchestrates the full pipeline.

    frame  →  extractor  →  segmenter  →  classifier  →  buffer  →  LLM  →  text

Two input modes:
- ``push_frame(bgr_frame)`` — the session does MediaPipe extraction.
- ``push_keypoints(kp)``    — for callers that already have keypoints.

The session is stateful and not thread-safe: each connection should hold
its own instance.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import List, Optional

import numpy as np

logger = logging.getLogger("paluszki.serve")

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
        # Most recent classified segment, kept until consumed — lets the HTTP
        # layer surface live per-sign detections, not just flushed sentences.
        self._new_sign: Optional[tuple[ClassifierOutput, bool]] = None
        # Incremental sentence translation runs as a background task so the
        # LLM call (~1s) doesn't stall frame processing mid-next-sign. The
        # finished sentence parks in _pending_result until the next frame/tick
        # response picks it up.
        self._sentence_task: Optional[asyncio.Task] = None
        self._pending_result: Optional[TranslationResult] = None

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
        """Periodic check with no input: delivers a finished incremental
        translation (if one is parked) and closes the sentence after the
        signer has been idle for ``buffer.flush_pause_ms``."""
        ts = time.time() if ts is None else ts
        if self.buffer.should_reset(ts):
            closed = self.buffer.flush()
            logger.info(
                "sentence closed after idle (%d signs) — next sign starts fresh",
                len(closed),
            )
        return self._consume_pending()

    async def flush(self) -> Optional[TranslationResult]:
        """Force-translate whatever's buffered. Used at end of session and
        by the offline test scripts."""
        signs = self.buffer.flush()
        if not signs:
            return self._consume_pending()
        return await self._translate(signs)

    def consume_new_sign(self) -> Optional[tuple[ClassifierOutput, bool]]:
        """Return the segment classified during the last push (and whether it
        passed min_confidence), once — subsequent calls return None until the
        next sign. Callers run under the per-session lock."""
        sign = self._new_sign
        self._new_sign = None
        return sign

    async def _on_keypoints(
        self, kp: np.ndarray, ts: float,
    ) -> Optional[TranslationResult]:
        # The signer going idle closes the sentence even when frames keep
        # arriving (camera on, hands still).
        if self.buffer.should_reset(ts):
            closed = self.buffer.flush()
            logger.info(
                "sentence closed after idle (%d signs) — next sign starts fresh",
                len(closed),
            )

        seg = self.segmenter.push(kp, ts)
        if seg is not None:
            classified = self.classifier.predict(
                seg.keypoints,
                started_at=seg.started_at,
                ended_at=seg.ended_at,
            )
            top1, conf = classified.top_k[0] if classified.top_k else ("?", 0.0)
            accepted = classified.raw_argmax_conf >= self.min_confidence
            self._new_sign = (classified, accepted)
            if accepted:
                self.buffer.push(classified, ts)
                logger.info(
                    "sign accepted: %s (%.2f) — sentence=%d [%s]",
                    top1, conf, len(self.buffer),
                    ", ".join(s.top_k[0][0] for s in self.buffer._entries),
                )
                # Retranslate the whole sentence-so-far with the new sign.
                self._launch_translation(self.buffer.snapshot())
                if self.buffer.is_full():
                    # Cap reached: commit the sentence; next sign starts fresh.
                    self.buffer.flush()
                    logger.info("sentence committed (max_segments reached)")
            else:
                logger.info(
                    "sign dropped (conf %.2f < min %.2f): %s",
                    conf, self.min_confidence, top1,
                )

        return self._consume_pending()

    def _launch_translation(self, signs: List[ClassifierOutput]) -> None:
        """(Re)start the background sentence translation. A still-running
        older translation is superseded — its sentence is already stale."""
        if self._sentence_task is not None and not self._sentence_task.done():
            self._sentence_task.cancel()
        self._sentence_task = asyncio.create_task(self._translate_in_background(signs))

    async def _translate_in_background(self, signs: List[ClassifierOutput]) -> None:
        try:
            result = await self._translate(signs)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("incremental translation failed")
            return
        self._pending_result = result

    async def _translate(self, signs: List[ClassifierOutput]) -> Optional[TranslationResult]:
        if not signs:
            return None
        glosses = [s.top_k[0][0] for s in signs]
        logger.info("LLM translating %d sign(s) -> %s", len(signs), glosses)
        t0 = time.perf_counter()
        text = await self.postprocessor.translate(signs)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        logger.info("LLM done in %.0f ms -> %r", dt_ms, text)
        return TranslationResult(
            text=text,
            source_signs=signs,
            started_at=signs[0].started_at,
            ended_at=signs[-1].ended_at,
            target_lang=self.target_lang,
        )

    def _consume_pending(self) -> Optional[TranslationResult]:
        result = self._pending_result
        self._pending_result = None
        return result

    async def aclose(self) -> None:
        if self._sentence_task is not None and not self._sentence_task.done():
            self._sentence_task.cancel()
        if self.extractor is not None:
            self.extractor.close()
        await self.postprocessor.aclose()

    # Sync convenience for resource cleanup in non-async contexts.
    def close(self) -> None:
        if self.extractor is not None:
            self.extractor.close()
