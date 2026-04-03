"""Keypoint normalization for signer-invariant representations.

Transforms raw MediaPipe coordinates (frame-relative 0-1) into a
body-centered, scale-invariant coordinate system:

1. **Center** on the mid-shoulder point (avg of left/right shoulder).
2. **Scale** by inter-shoulder distance so body size is normalized.
3. **Hands relative to wrist** — hand landmark positions are expressed
   relative to their wrist, so only finger shape matters, not arm position.

This eliminates variation from camera distance, signer height/position,
and body proportions — focusing the model on the actual sign gestures.
"""

import numpy as np

from src.data.keypoint_extractor import (
    HAND_DIM,
    HAND_LANDMARKS,
    POSE_DIM,
    POSE_LANDMARKS,
)

# MediaPipe Pose landmark indices (0-based)
_LEFT_SHOULDER = 11
_RIGHT_SHOULDER = 12
_LEFT_WRIST = 15
_RIGHT_WRIST = 16


def _reshape_pose(flat: np.ndarray) -> np.ndarray:
    """(99,) -> (33, 3)"""
    return flat.reshape(POSE_LANDMARKS, 3)


def _reshape_hand(flat: np.ndarray) -> np.ndarray:
    """(63,) -> (21, 3)"""
    return flat.reshape(HAND_LANDMARKS, 3)


def normalize_keypoints(
    keypoints: np.ndarray,
    center_on_shoulders: bool = True,
    scale_by_shoulders: bool = True,
    hands_relative_to_wrist: bool = True,
    fallback_scale: float = 0.3,
) -> np.ndarray:
    """Normalize a keypoint sequence in-place-safe manner.

    Args:
        keypoints: Array of shape ``(T, 225)`` — raw MediaPipe output.
        center_on_shoulders: Subtract mid-shoulder from all landmarks.
        scale_by_shoulders: Divide by inter-shoulder distance.
        hands_relative_to_wrist: Express hand landmarks relative to wrist.
        fallback_scale: Scale value when shoulders are not detected.

    Returns:
        Normalized array of same shape ``(T, 225)``.
    """
    T = keypoints.shape[0]
    out = keypoints.copy()

    for t in range(T):
        pose_flat = out[t, :POSE_DIM]
        lh_flat = out[t, POSE_DIM : POSE_DIM + HAND_DIM]
        rh_flat = out[t, POSE_DIM + HAND_DIM :]

        pose = _reshape_pose(pose_flat)     # (33, 3)
        lh = _reshape_hand(lh_flat)         # (21, 3)
        rh = _reshape_hand(rh_flat)         # (21, 3)

        # Check if pose landmarks are present (non-zero)
        ls = pose[_LEFT_SHOULDER]
        rs = pose[_RIGHT_SHOULDER]
        has_pose = np.any(ls != 0) or np.any(rs != 0)

        # Mask of which landmarks are present (non-zero)
        pose_present = np.any(pose != 0, axis=1, keepdims=True)  # (33, 1)

        if has_pose and center_on_shoulders:
            center = (ls + rs) / 2.0
            # Only shift non-zero landmarks
            pose -= center * pose_present
            if np.any(lh != 0):
                lh -= center
            if np.any(rh != 0):
                rh -= center

        if has_pose and scale_by_shoulders:
            shoulder_dist = np.linalg.norm(
                pose[_LEFT_SHOULDER] - pose[_RIGHT_SHOULDER]
            )
            if shoulder_dist < 1e-6:
                shoulder_dist = fallback_scale
            # Only scale non-zero (detected) landmarks
            pose = np.where(pose_present, pose / shoulder_dist, 0.0)
            if np.any(lh != 0):
                lh /= shoulder_dist
            if np.any(rh != 0):
                rh /= shoulder_dist

        if hands_relative_to_wrist:
            # Left hand relative to hand-model wrist (landmark 0)
            if np.any(lh != 0):
                lh = lh - lh[0]
            # Right hand relative to hand-model wrist (landmark 0)
            if np.any(rh != 0):
                rh = rh - rh[0]

        out[t, :POSE_DIM] = pose.flatten()
        out[t, POSE_DIM : POSE_DIM + HAND_DIM] = lh.flatten()
        out[t, POSE_DIM + HAND_DIM :] = rh.flatten()

    return out
