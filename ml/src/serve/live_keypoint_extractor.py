"""Frame-by-frame MediaPipe Holistic extractor for streaming use.

Sister of ``src.data.keypoint_extractor.extract_keypoints_from_video``,
which is batch (whole video → uniform sample → 32-frame array). Here we
keep the Holistic context open across calls, so each ``extract`` is an
incremental ~5-15ms pass.

Use ``static_image_mode=False`` (default) so MediaPipe uses temporal
tracking — slightly different from training (which uses static mode), but
faster and more stable for live streams. If accuracy degrades visibly, set
``static_image_mode=True`` via config to match training exactly.
"""

from __future__ import annotations

import mediapipe as mp
import numpy as np

from src.data.keypoint_extractor import _extract_frame_keypoints


class LiveKeypointExtractor:
    def __init__(
        self,
        static_image_mode: bool = False,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ):
        self._holistic = mp.solutions.holistic.Holistic(
            static_image_mode=static_image_mode,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

    def extract(self, frame_bgr: np.ndarray) -> np.ndarray:
        """Return (225,) float32 keypoint vector for a single BGR frame."""
        return _extract_frame_keypoints(frame_bgr, self._holistic)

    def close(self) -> None:
        self._holistic.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
