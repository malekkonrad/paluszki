"""Keypoint augmentation for sign-language recognition.

All augmentations operate on numpy arrays of shape ``(T, 225)`` —
normalized MediaPipe keypoints (pose + left hand + right hand).

Augmentations are composed via :class:`KeypointAugmentor` which reads
its config from the YAML ``augmentation`` section.
"""

import numpy as np

from src.data.keypoint_extractor import (
    HAND_DIM,
    HAND_LANDMARKS,
    KEYPOINT_DIM,
    POSE_DIM,
    POSE_LANDMARKS,
)


# -- Spatial augmentations ---------------------------------------------------


def random_rotation(keypoints: np.ndarray, max_angle_deg: float = 15.0) -> np.ndarray:
    """Rotate all (x, y) coordinates by a random angle around the origin."""
    angle = np.random.uniform(-max_angle_deg, max_angle_deg)
    rad = np.radians(angle)
    cos_a, sin_a = np.cos(rad), np.sin(rad)

    out = keypoints.copy()
    T = out.shape[0]

    for t in range(T):
        # Process all landmarks: reshape to (N, 3), rotate x/y
        frame = out[t].reshape(-1, 3)
        x, y = frame[:, 0].copy(), frame[:, 1].copy()
        frame[:, 0] = cos_a * x - sin_a * y
        frame[:, 1] = sin_a * x + cos_a * y
        out[t] = frame.flatten()

    return out


def random_scale(keypoints: np.ndarray, scale_range: tuple = (0.85, 1.15)) -> np.ndarray:
    """Uniformly scale all coordinates."""
    scale = np.random.uniform(*scale_range)
    out = keypoints.copy()

    for t in range(out.shape[0]):
        frame = out[t].reshape(-1, 3)
        frame *= scale
        out[t] = frame.flatten()

    return out


def random_translate(keypoints: np.ndarray, max_shift: float = 0.05) -> np.ndarray:
    """Shift all (x, y) coordinates by a random offset."""
    dx = np.random.uniform(-max_shift, max_shift)
    dy = np.random.uniform(-max_shift, max_shift)

    out = keypoints.copy()
    for t in range(out.shape[0]):
        frame = out[t].reshape(-1, 3)
        frame[:, 0] += dx
        frame[:, 1] += dy
        out[t] = frame.flatten()

    return out


# -- Temporal augmentations --------------------------------------------------


def random_time_warp(keypoints: np.ndarray, speed_range: tuple = (0.8, 1.2)) -> np.ndarray:
    """Resample the temporal axis at a random speed (stretch/compress).

    This simulates signers performing signs at different speeds.
    """
    T = keypoints.shape[0]
    speed = np.random.uniform(*speed_range)
    new_T = max(int(T / speed), 1)

    # Resample to new_T frames, then re-sample back to T
    indices_new = np.linspace(0, T - 1, new_T)
    indices_orig = np.linspace(0, new_T - 1, T)

    # Interpolate: for each output frame, find its position in the warped timeline
    source_indices = np.interp(indices_orig, np.arange(new_T), indices_new)

    out = np.zeros_like(keypoints)
    for i in range(T):
        src = source_indices[i]
        lo = int(np.floor(src))
        hi = min(lo + 1, T - 1)
        alpha = src - lo
        out[i] = (1 - alpha) * keypoints[lo] + alpha * keypoints[hi]

    return out


def random_frame_drop(keypoints: np.ndarray, drop_prob: float = 0.1) -> np.ndarray:
    """Randomly drop frames and duplicate neighbors to maintain length.

    Simulates camera frame drops or irregular sampling.
    """
    T = keypoints.shape[0]
    mask = np.random.random(T) > drop_prob
    # Keep at least one frame
    if not mask.any():
        mask[T // 2] = True

    kept = keypoints[mask]

    # Resample back to T frames
    if len(kept) == T:
        return kept

    indices = np.linspace(0, len(kept) - 1, T)
    out = np.zeros_like(keypoints)
    for i in range(T):
        lo = int(np.floor(indices[i]))
        hi = min(lo + 1, len(kept) - 1)
        alpha = indices[i] - lo
        out[i] = (1 - alpha) * kept[lo] + alpha * kept[hi]

    return out


# -- Noise augmentations -----------------------------------------------------


def gaussian_noise(keypoints: np.ndarray, std: float = 0.01) -> np.ndarray:
    """Add Gaussian noise to all coordinates."""
    noise = np.random.normal(0, std, keypoints.shape).astype(np.float32)
    # Don't add noise to zero (missing) landmarks
    mask = (keypoints != 0).astype(np.float32)
    return keypoints + noise * mask


def random_landmark_dropout(keypoints: np.ndarray, drop_prob: float = 0.05) -> np.ndarray:
    """Zero out random landmarks to simulate occlusion.

    Operates per-frame: each landmark has ``drop_prob`` chance of being zeroed.
    """
    out = keypoints.copy()
    T = out.shape[0]

    for t in range(T):
        frame = out[t].reshape(-1, 3)
        n_landmarks = frame.shape[0]
        mask = np.random.random(n_landmarks) > drop_prob
        frame *= mask[:, None]
        out[t] = frame.flatten()

    return out


# -- Compose -----------------------------------------------------------------


class KeypointAugmentor:
    """Configurable augmentation pipeline for keypoint sequences.

    Reads settings from a dict (typically the ``augmentation`` section of
    the YAML config). Only enabled augmentations are applied.

    Example config::

        augmentation:
          enabled: true
          rotation_max_deg: 15
          scale_range: [0.85, 1.15]
          translate_max: 0.05
          time_warp_range: [0.8, 1.2]
          frame_drop_prob: 0.1
          gaussian_std: 0.01
          landmark_dropout_prob: 0.05
    """

    def __init__(self, cfg: dict):
        self.enabled = cfg.get("enabled", True)
        self.rotation_max_deg = cfg.get("rotation_max_deg", 15.0)
        self.scale_range = tuple(cfg.get("scale_range", [0.85, 1.15]))
        self.translate_max = cfg.get("translate_max", 0.05)
        self.time_warp_range = tuple(cfg.get("time_warp_range", [0.8, 1.2]))
        self.frame_drop_prob = cfg.get("frame_drop_prob", 0.1)
        self.gaussian_std = cfg.get("gaussian_std", 0.01)
        self.landmark_dropout_prob = cfg.get("landmark_dropout_prob", 0.05)

    def __call__(self, keypoints: np.ndarray) -> np.ndarray:
        """Apply augmentations to a keypoint sequence ``(T, 225)``.

        Each augmentation is applied with 50% probability (except noise
        and dropout which are always applied when enabled).
        """
        if not self.enabled:
            return keypoints

        kp = keypoints

        # Spatial — each applied with 50% chance
        if self.rotation_max_deg > 0 and np.random.random() < 0.5:
            kp = random_rotation(kp, self.rotation_max_deg)

        if self.scale_range != (1.0, 1.0) and np.random.random() < 0.5:
            kp = random_scale(kp, self.scale_range)

        if self.translate_max > 0 and np.random.random() < 0.5:
            kp = random_translate(kp, self.translate_max)

        # Temporal — each applied with 50% chance
        if self.time_warp_range != (1.0, 1.0) and np.random.random() < 0.5:
            kp = random_time_warp(kp, self.time_warp_range)

        if self.frame_drop_prob > 0 and np.random.random() < 0.5:
            kp = random_frame_drop(kp, self.frame_drop_prob)

        # Noise — always applied (they're mild)
        if self.gaussian_std > 0:
            kp = gaussian_noise(kp, self.gaussian_std)

        if self.landmark_dropout_prob > 0:
            kp = random_landmark_dropout(kp, self.landmark_dropout_prob)

        return kp
