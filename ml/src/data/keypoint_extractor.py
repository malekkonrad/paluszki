"""MediaPipe-based keypoint extraction utilities.

Extracts pose + left hand + right hand landmarks from video frames.
Output shape per frame: (KEYPOINT_DIM,) = (225,)
  - pose:       33 landmarks × 3 coords = 99
  - left hand:  21 landmarks × 3 coords = 63
  - right hand: 21 landmarks × 3 coords = 63
"""

import cv2
import numpy as np
import torch

POSE_LANDMARKS = 33
HAND_LANDMARKS = 21
POSE_DIM = POSE_LANDMARKS * 3     # 99
HAND_DIM = HAND_LANDMARKS * 3     # 63
KEYPOINT_DIM = POSE_DIM + HAND_DIM + HAND_DIM  # 225


def _extract_frame_keypoints(frame_bgr, holistic) -> np.ndarray:
    """Extract keypoints from a single BGR frame using an open Holistic context."""
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    result = holistic.process(frame_rgb)

    pose = np.zeros(POSE_DIM, dtype=np.float32)
    left_hand = np.zeros(HAND_DIM, dtype=np.float32)
    right_hand = np.zeros(HAND_DIM, dtype=np.float32)

    if result.pose_landmarks:
        for i, lm in enumerate(result.pose_landmarks.landmark):
            pose[i * 3: i * 3 + 3] = [lm.x, lm.y, lm.z]

    if result.left_hand_landmarks:
        for i, lm in enumerate(result.left_hand_landmarks.landmark):
            left_hand[i * 3: i * 3 + 3] = [lm.x, lm.y, lm.z]

    if result.right_hand_landmarks:
        for i, lm in enumerate(result.right_hand_landmarks.landmark):
            right_hand[i * 3: i * 3 + 3] = [lm.x, lm.y, lm.z]

    return np.concatenate([pose, left_hand, right_hand])


def extract_keypoints_from_video(video_path: str, num_frames: int) -> np.ndarray:
    """Sample `num_frames` uniformly from a video and extract MediaPipe keypoints.

    Returns:
        np.ndarray of shape (num_frames, KEYPOINT_DIM), dtype float32.
        Missing landmarks are zero-padded.
    """
    import mediapipe as mp  # lazy import so the rest of the codebase works without mediapipe

    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if total_frames <= 0:
        cap.release()
        return np.zeros((num_frames, KEYPOINT_DIM), dtype=np.float32)

    indices = torch.linspace(0, max(total_frames - 1, 0), steps=num_frames).long().tolist()
    target_set = set(indices)

    keypoints = []
    frame_id = 0

    mp_holistic = mp.solutions.holistic
    with mp_holistic.Holistic(
        static_image_mode=True,
        min_detection_confidence=0.3,
        min_tracking_confidence=0.3,
    ) as holistic:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if frame_id in target_set:
                kp = _extract_frame_keypoints(frame, holistic)
                keypoints.append(kp)
                if len(keypoints) == num_frames:
                    break

            frame_id += 1

    cap.release()

    while len(keypoints) < num_frames:
        if keypoints:
            keypoints.append(keypoints[-1].copy())
        else:
            keypoints.append(np.zeros(KEYPOINT_DIM, dtype=np.float32))

    return np.stack(keypoints)  # (num_frames, 225)
