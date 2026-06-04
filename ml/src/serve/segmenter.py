"""Motion-based sign segmenter.

A sign is bracketed by motion. Between signs (and before/after) the hands
are still or absent. We track an exponentially-smoothed hand velocity and
flip a 3-state automaton:

    IDLE         no motion seen yet
    SIGNING      hands moving above threshold; collecting frames
    PAUSED       motion dropped; counting frames toward end-of-sign

When PAUSED runs for ``pause_frames`` consecutive frames we finalize the
collected segment and reset to IDLE. Segments shorter than
``min_segment_frames`` are discarded; segments longer than
``max_segment_frames`` are flushed early to bound latency.

Velocity is computed as mean-absolute-difference of the hand portion of
the keypoint vector (indices 99..225), so it ignores the stationary pose
landmarks.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from src.data.keypoint_extractor import POSE_DIM
from src.serve.schemas import SegmentEvent


class Segmenter:
    def __init__(
        self,
        motion_threshold: float = 0.02,
        pause_frames: int = 9,
        min_segment_frames: int = 12,
        max_segment_frames: int = 90,
        velocity_smoothing: float = 0.5,
    ):
        self.motion_threshold = motion_threshold
        self.pause_frames = pause_frames
        self.min_segment_frames = min_segment_frames
        self.max_segment_frames = max_segment_frames
        self.velocity_smoothing = velocity_smoothing

        self._state = "IDLE"
        self._kp_buffer: list[np.ndarray] = []
        self._ts_buffer: list[float] = []
        self._last_kp: np.ndarray | None = None
        self._smoothed_vel = 0.0
        self._pause_count = 0

    def reset(self) -> None:
        self._state = "IDLE"
        self._kp_buffer = []
        self._ts_buffer = []
        self._last_kp = None
        self._smoothed_vel = 0.0
        self._pause_count = 0

    def push(self, kp: np.ndarray, ts: float) -> Optional[SegmentEvent]:
        """Push one frame's keypoints. Returns a SegmentEvent if a sign just
        finalized (and is long enough), else ``None``.
        """
        velocity = self._update_velocity(kp)
        moving = velocity > self.motion_threshold
        finalized: Optional[SegmentEvent] = None

        if self._state == "IDLE":
            if moving:
                self._state = "SIGNING"
                self._kp_buffer = [kp.copy()]
                self._ts_buffer = [ts]
                self._pause_count = 0

        elif self._state == "SIGNING":
            self._kp_buffer.append(kp.copy())
            self._ts_buffer.append(ts)

            if not moving:
                self._pause_count += 1
                if self._pause_count >= self.pause_frames:
                    finalized = self._finalize()
            else:
                self._pause_count = 0

            if (
                finalized is None
                and len(self._kp_buffer) >= self.max_segment_frames
            ):
                finalized = self._finalize()

        return finalized

    def _update_velocity(self, kp: np.ndarray) -> float:
        if self._last_kp is None:
            self._last_kp = kp.copy()
            return 0.0
        # Hand portion only — pose landmarks barely move during signing.
        diff = np.abs(kp[POSE_DIM:] - self._last_kp[POSE_DIM:]).mean()
        self._last_kp = kp.copy()
        # Exponential smoothing dampens single-frame noise / dropped landmarks.
        a = self.velocity_smoothing
        self._smoothed_vel = a * float(diff) + (1.0 - a) * self._smoothed_vel
        return self._smoothed_vel

    def _finalize(self) -> Optional[SegmentEvent]:
        # Trim trailing pause frames so we keep only the active part.
        kept = max(len(self._kp_buffer) - self._pause_count, 0)
        kp = np.stack(self._kp_buffer[:kept]) if kept else np.empty((0, 225), dtype=np.float32)
        ts_buf = self._ts_buffer[:kept]

        n_frames = kp.shape[0]
        # Reset state regardless of whether we keep this segment.
        self._state = "IDLE"
        self._kp_buffer = []
        self._ts_buffer = []
        self._pause_count = 0
        self._smoothed_vel = 0.0

        if n_frames < self.min_segment_frames:
            return None

        return SegmentEvent(
            keypoints=kp,
            started_at=ts_buf[0],
            ended_at=ts_buf[-1],
        )
