"""Real-time webcam demo for sign language classification.

Usage:
    uv run -m src.webcam_demo \
        --checkpoint artifacts/merged30/best_model.pt \
        --config configs/merged30.yaml

Keys:
    q / ESC  — quit
    r        — reset frame buffer
"""

import argparse
import collections
import time

import cv2
import mediapipe as mp
import numpy as np
import torch

from src.data.keypoint_extractor import KEYPOINT_DIM, _extract_frame_keypoints
from src.data.keypoint_normalization import normalize_keypoints
from src.data.label_map import GlossLabelMap
from src.registry import PIPELINE_REGISTRY
from src.utils.config import load_config


def parse_args():
    p = argparse.ArgumentParser(description="Webcam sign-language demo")
    p.add_argument("--checkpoint", required=True, help="Path to model .pt")
    p.add_argument("--config", default="configs/merged30.yaml")
    p.add_argument("--device", default=None)
    p.add_argument("--camera", type=int, default=0, help="Camera index")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument(
        "--classify-every", type=int, default=8,
        help="Run classification every N frames (lower = more responsive, higher = faster)",
    )
    return p.parse_args()


def load_model(cfg, checkpoint_path, device):
    label_map_path = checkpoint_path.parent / "label_map.json"
    if label_map_path.exists():
        label_map = GlossLabelMap.load(label_map_path)
    else:
        label_map = GlossLabelMap.from_wlasl_json(
            cfg["data"]["json_path"], num_classes=cfg["data"]["num_classes"],
        )

    num_classes = len(label_map)
    pipeline_cls = PIPELINE_REGISTRY[cfg["model"]["pipeline_name"]]
    model = pipeline_cls(cfg, num_classes).to(device)

    state_dict = torch.load(checkpoint_path, map_location=device, weights_only=True)
    model.load_state_dict(state_dict)
    model.eval()
    return model, label_map


def draw_overlay(frame, predictions, fps):
    h, w = frame.shape[:2]

    # Semi-transparent background for predictions
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 10), (350, 40 + len(predictions) * 35), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    # FPS
    cv2.putText(frame, f"FPS: {fps:.0f}", (w - 130, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    # Predictions
    for i, (gloss, prob) in enumerate(predictions):
        y = 40 + i * 35
        bar_width = int(prob * 250)

        # Probability bar
        color = (0, 200, 0) if i == 0 else (100, 100, 100)
        cv2.rectangle(frame, (15, y - 2), (15 + bar_width, y + 18), color, -1)

        # Text
        text = f"{gloss}: {prob:.0%}"
        text_color = (255, 255, 255) if i == 0 else (200, 200, 200)
        cv2.putText(frame, text, (20, y + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, text_color, 1)

    return frame


def draw_hand_landmarks(frame, results):
    """Draw simple hand landmark connections on the frame."""
    h, w = frame.shape[:2]

    for hand_landmarks, color in [
        (results.left_hand_landmarks, (255, 100, 100)),   # blue-ish for left
        (results.right_hand_landmarks, (100, 100, 255)),  # red-ish for right
    ]:
        if hand_landmarks is None:
            continue
        points = []
        for lm in hand_landmarks.landmark:
            px, py = int(lm.x * w), int(lm.y * h)
            points.append((px, py))
            cv2.circle(frame, (px, py), 3, color, -1)

        # Draw connections between adjacent landmarks
        connections = mp.solutions.hands.HAND_CONNECTIONS
        for c in connections:
            cv2.line(frame, points[c[0]], points[c[1]], color, 1)


def main():
    args = parse_args()
    from pathlib import Path

    cfg = load_config(args.config)
    device = args.device or cfg["train"]["device"]
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"

    checkpoint_path = Path(args.checkpoint)
    model, label_map = load_model(cfg, checkpoint_path, device)

    num_frames = cfg["data"]["num_frames"]  # 32
    do_normalize = cfg["data"].get("normalize_keypoints", False)

    # Frame buffer — circular buffer of keypoints
    kp_buffer = collections.deque(maxlen=num_frames)

    # Current predictions
    predictions = []
    frame_count = 0
    fps = 0.0
    prev_time = time.time()

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"Cannot open camera {args.camera}")
        return

    print(f"Model loaded: {checkpoint_path}")
    print(f"Classes: {label_map.glosses}")
    print(f"Buffer size: {num_frames} frames, classify every {args.classify_every} frames")
    print("Press 'q' or ESC to quit, 'r' to reset buffer")

    with mp.solutions.holistic.Holistic(
        static_image_mode=False,
        model_complexity=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    ) as holistic:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)  # Mirror for natural interaction

            # Extract keypoints
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = holistic.process(frame_rgb)

            kp = _extract_frame_keypoints(frame, holistic)
            kp_buffer.append(kp)

            # Draw hand landmarks
            draw_hand_landmarks(frame, results)

            # Classify when buffer is full, every N frames
            frame_count += 1
            if len(kp_buffer) == num_frames and frame_count % args.classify_every == 0:
                keypoints = np.stack(list(kp_buffer))  # (T, 225)

                if do_normalize:
                    keypoints = normalize_keypoints(keypoints)

                kp_tensor = torch.from_numpy(keypoints).float().to(device)
                result = model.classify(kp_tensor, top_k=args.top_k)

                predictions = [
                    (label_map.decode(cls_id), prob)
                    for cls_id, prob in zip(result["top_k_ids"], result["top_k_probs"])
                ]

            # FPS calculation
            now = time.time()
            fps = 0.9 * fps + 0.1 * (1.0 / max(now - prev_time, 1e-6))
            prev_time = now

            # Status indicator
            buf_fill = len(kp_buffer) / num_frames
            if buf_fill < 1.0:
                cv2.putText(frame, f"Buffering... {buf_fill:.0%}", (10, frame.shape[0] - 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)

            frame = draw_overlay(frame, predictions, fps)
            cv2.imshow("Sign Language Demo", frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):  # q or ESC
                break
            elif key == ord("r"):
                kp_buffer.clear()
                predictions = []
                print("Buffer reset")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
