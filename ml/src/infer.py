import argparse
from pathlib import Path

import cv2
import pandas as pd
import torch
import torchvision.transforms as T
from PIL import Image

from src.data.keypoint_extractor import extract_keypoints_from_video
from src.data.tokenizer import SimpleTokenizer
from src.registry import PIPELINE_REGISTRY
from src.utils.config import load_config


def parse_args():
    parser = argparse.ArgumentParser(description="Run inference for sign-language model.")
    parser.add_argument(
        "--checkpoint", type=str, required=True,
        help="Path to model checkpoint (.pt)",
    )
    parser.add_argument(
        "--video", type=str, required=True,
        help="Path to input video (.mp4).",
    )
    parser.add_argument(
        "--config", type=str, default="configs/base.yaml",
        help="Path to config file.",
    )
    parser.add_argument(
        "--device", type=str, default=None,
        help="Device override: cpu/cuda.",
    )
    parser.add_argument(
        "--max-len", type=int, default=None,
        help="Maximum generated token length (translation only).",
    )
    parser.add_argument(
        "--top-k", type=int, default=5,
        help="Number of top predictions to show (classification only).",
    )
    parser.add_argument(
        "--use-pretrained-backbone", action="store_true",
        help="Initialize ResNet18 with pretrained weights before loading checkpoint.",
    )
    return parser.parse_args()


def sample_video_frames(video_path: Path, num_frames: int, image_size: int) -> torch.Tensor:
    transform = T.Compose([
        T.Resize((image_size, image_size)),
        T.ToTensor(),
    ])

    cap = cv2.VideoCapture(str(video_path))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if total_frames <= 0:
        cap.release()
        return torch.zeros(num_frames, 3, image_size, image_size)

    indices = torch.linspace(0, max(total_frames - 1, 0), steps=num_frames).long().tolist()
    target_set = set(indices)

    frames = []
    frame_id = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        if frame_id in target_set:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(frame)
            frames.append(transform(image))
            if len(frames) == num_frames:
                break

        frame_id += 1

    cap.release()

    while len(frames) < num_frames:
        if frames:
            frames.append(frames[-1].clone())
        else:
            frames.append(torch.zeros(3, image_size, image_size))

    return torch.stack(frames)


def resolve_device(cfg, device_override):
    device = device_override or cfg["train"]["device"]
    if device == "cuda" and not torch.cuda.is_available():
        return "cpu"
    return device


def build_tokenizer_from_config(cfg):
    csv_separator = cfg["data"].get("csv_separator", ",")
    csv_path = cfg["data"].get("csv_path") or cfg["data"].get("train_csv_path")
    df = pd.read_csv(csv_path, sep=csv_separator)
    texts = df[cfg["data"]["text_column"]].astype(str).tolist()
    return SimpleTokenizer(texts)


def _infer_classification(args, cfg, device):
    from src.data.label_map import GlossLabelMap

    checkpoint_path = Path(args.checkpoint)
    video_path = Path(args.video)

    # Load label map from alongside the checkpoint, or rebuild from JSON
    ckpt_dir = checkpoint_path.parent
    label_map_path = ckpt_dir / "label_map.json"

    if label_map_path.exists():
        label_map = GlossLabelMap.load(label_map_path)
    else:
        label_map = GlossLabelMap.from_wlasl_json(
            cfg["data"]["json_path"],
            num_classes=cfg["data"]["num_classes"],
        )

    num_classes = len(label_map)
    pipeline_name = cfg["model"]["pipeline_name"]
    pipeline_cls = PIPELINE_REGISTRY[pipeline_name]
    model = pipeline_cls(cfg, num_classes).to(device)

    state_dict = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(state_dict)
    model.eval()

    kp = extract_keypoints_from_video(str(video_path), cfg["data"]["num_frames"])
    keypoints = torch.from_numpy(kp).to(device)

    result = model.classify(keypoints, top_k=args.top_k)

    print(f"video: {video_path}")
    print(f"checkpoint: {checkpoint_path}")
    print(f"\nTop-{args.top_k} predictions:")
    for rank, (cls_id, prob) in enumerate(
        zip(result["top_k_ids"], result["top_k_probs"]), 1
    ):
        gloss = label_map.decode(cls_id)
        print(f"  {rank}. {gloss} ({prob:.1%})")


def _infer_translation(args, cfg, device):
    checkpoint_path = Path(args.checkpoint)
    video_path = Path(args.video)

    tokenizer = build_tokenizer_from_config(cfg)
    cfg["model"]["pretrained_backbone"] = args.use_pretrained_backbone

    pipeline_name = cfg["model"]["pipeline_name"]
    pipeline_cls = PIPELINE_REGISTRY[pipeline_name]
    model = pipeline_cls(cfg, tokenizer).to(device)

    state_dict = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(state_dict)
    model.eval()

    dataset_type = cfg["data"].get("dataset_type", "video")
    if dataset_type == "keypoint":
        kp = extract_keypoints_from_video(str(video_path), cfg["data"]["num_frames"])
        frames = torch.from_numpy(kp).to(device)
    else:
        frames = sample_video_frames(
            video_path=video_path,
            num_frames=cfg["data"]["num_frames"],
            image_size=cfg["data"]["image_size"],
        ).to(device)

    max_len = args.max_len or cfg["data"]["max_text_len"]
    token_ids = model.greedy_decode(frames, max_len=max_len)
    translation = tokenizer.decode(token_ids)

    print(f"video: {video_path}")
    print(f"checkpoint: {checkpoint_path}")
    print(f"translation: {translation}")


def main():
    args = parse_args()

    cfg = load_config(args.config)
    device = resolve_device(cfg, args.device)

    checkpoint_path = Path(args.checkpoint)
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

    video_path = Path(args.video)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    task_type = cfg["data"].get("task", "translation")

    if task_type == "classification":
        _infer_classification(args, cfg, device)
    else:
        _infer_translation(args, cfg, device)


if __name__ == "__main__":
    main()
