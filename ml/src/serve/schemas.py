"""Public dataclasses passed across the serve pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np


@dataclass
class ClassifierOutput:
    """Result of classifying a single segment."""

    top_k: List[Tuple[str, float]]      # [(gloss, prob), ...]  sorted desc
    raw_argmax_conf: float              # = top_k[0][1]
    started_at: float                   # segment start (seconds)
    ended_at: float                     # segment end (seconds)


@dataclass
class SegmentEvent:
    """A finalized "one sign" produced by the segmenter."""

    keypoints: np.ndarray               # (T, 225) raw keypoints
    started_at: float
    ended_at: float

    @property
    def n_frames(self) -> int:
        return self.keypoints.shape[0]


@dataclass
class TranslationResult:
    """LLM-postprocessed sentence, returned to the caller."""

    text: str
    source_signs: List[ClassifierOutput] = field(default_factory=list)
    started_at: float = 0.0             # first sign start
    ended_at: float = 0.0               # last sign end
    target_lang: str = "en"
