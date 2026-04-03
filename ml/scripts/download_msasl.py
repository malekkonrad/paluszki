"""Download and prepare the MS-ASL dataset.

MS-ASL provides YouTube URLs with start/end timestamps and bounding boxes.
This script downloads videos via yt-dlp, clips them, and extracts keypoints.

Usage:
    # 1. Download videos for top-N classes
    uv run scripts/download_msasl.py --download-videos --num-classes 100

    # 2. Validate coverage
    uv run scripts/download_msasl.py --validate --num-classes 100

    # 3. Extract MediaPipe keypoints
    uv run scripts/download_msasl.py --extract-keypoints --num-classes 100 --num-frames 32
"""

import argparse
import json
import subprocess
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

ROOT = SCRIPT_DIR.parent / "datasets" / "ms-asl"
VIDEO_DIR = ROOT / "videos"
KEYPOINT_DIR = ROOT / "keypoints"

SPLITS = {
    "train": ROOT / "MSASL_train.json",
    "val": ROOT / "MSASL_val.json",
    "test": ROOT / "MSASL_test.json",
}
CLASSES_PATH = ROOT / "MSASL_classes.json"


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def load_classes() -> list[str]:
    with open(CLASSES_PATH) as f:
        return json.load(f)


def load_split(split: str) -> list[dict]:
    with open(SPLITS[split]) as f:
        return json.load(f)


def get_top_n_labels(n: int) -> set[int]:
    """Return the label IDs of the top-N most frequent classes in train."""
    train = load_split("train")
    counts = Counter(s["label"] for s in train)
    return {label for label, _ in counts.most_common(n)}


def _video_id(sample: dict) -> str:
    """Stable video ID from URL + timestamps."""
    import hashlib

    url = sample["url"]
    start = sample.get("start_time", 0)
    end = sample.get("end_time", 0)
    raw = f"{url}_{start}_{end}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


# -- Download videos --------------------------------------------------------


def _download_single(sample: dict, output_path: Path) -> bool:
    """Download a single clip from YouTube using yt-dlp.

    Downloads the full video, then clips to start/end time and crops to
    the bounding box provided by MS-ASL.
    """
    if output_path.exists():
        return True

    url = sample["url"]
    start_time = sample.get("start_time", 0)
    end_time = sample.get("end_time", 0)
    duration = end_time - start_time

    if duration <= 0:
        return False

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "raw.mp4"

        # Download with yt-dlp, clipping to time range
        cmd = [
            "yt-dlp",
            "--quiet", "--no-warnings",
            "-f", "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best",
            "--download-sections", f"*{start_time}-{end_time}",
            "--force-keyframes-at-cuts",
            "-o", str(tmp_path),
            url,
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return False

        if not tmp_path.exists():
            return False

        # Crop to bounding box using ffmpeg if box is provided
        box = sample.get("box")
        width = sample.get("width", 640)
        height = sample.get("height", 360)

        if box and len(box) == 4:
            x1, y1, x2, y2 = box
            crop_x = int(x1 * width)
            crop_y = int(y1 * height)
            crop_w = int((x2 - x1) * width)
            crop_h = int((y2 - y1) * height)

            # Ensure even dimensions (required by some codecs)
            crop_w = max(crop_w - crop_w % 2, 2)
            crop_h = max(crop_h - crop_h % 2, 2)

            crop_path = Path(tmp) / "cropped.mp4"
            crop_cmd = [
                "ffmpeg", "-y", "-i", str(tmp_path),
                "-vf", f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-an",  # drop audio, we only need video
                str(crop_path),
            ]
            try:
                subprocess.run(crop_cmd, check=True, capture_output=True, timeout=60)
                if crop_path.exists():
                    shutil.move(str(crop_path), str(output_path))
                    return True
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                pass

        # Fallback: use uncropped clip
        shutil.move(str(tmp_path), str(output_path))
        return True


def download_videos(num_classes: int, workers: int = 4):
    """Download videos for the top-N classes across all splits."""
    if shutil.which("yt-dlp") is None:
        print("yt-dlp not found. Install it: pip install yt-dlp")
        sys.exit(1)

    top_labels = get_top_n_labels(num_classes)
    classes = load_classes()
    ensure_dir(VIDEO_DIR)

    # Collect all unique samples across splits
    all_samples: dict[str, dict] = {}
    for split in ["train", "val", "test"]:
        for s in load_split(split):
            if s["label"] in top_labels:
                vid = _video_id(s)
                all_samples[vid] = s

    total = len(all_samples)
    print(f"Top-{num_classes} classes: {total} unique clips to download")

    already = sum(1 for vid in all_samples if (VIDEO_DIR / f"{vid}.mp4").exists())
    if already:
        print(f"  Already downloaded: {already}")

    downloaded = 0
    failed = 0

    for i, (vid, sample) in enumerate(all_samples.items()):
        output_path = VIDEO_DIR / f"{vid}.mp4"
        if output_path.exists():
            continue

        success = _download_single(sample, output_path)
        if success:
            downloaded += 1
        else:
            failed += 1

        if (i + 1) % 25 == 0:
            print(
                f"  Progress: {i + 1}/{total} "
                f"(downloaded={downloaded}, failed={failed}, cached={already})"
            )

    print(f"\nDone: {downloaded} new, {already} cached, {failed} failed out of {total}")


# -- Validate ---------------------------------------------------------------


def validate(num_classes: int):
    top_labels = get_top_n_labels(num_classes)
    classes = load_classes()

    print(f"\n=== MS-ASL top-{num_classes} validation ===\n")

    for split in ["train", "val", "test"]:
        data = load_split(split)
        filtered = [s for s in data if s["label"] in top_labels]
        available = sum(1 for s in filtered if (VIDEO_DIR / f"{_video_id(s)}.mp4").exists())
        pct = available / len(filtered) * 100 if filtered else 0
        print(f"  {split:5s}: {available:>5d} / {len(filtered):>5d} videos ({pct:.1f}%)")

    # Per-class breakdown
    train = [s for s in load_split("train") if s["label"] in top_labels]
    label_total = Counter(s["label"] for s in train)
    label_avail = Counter(
        s["label"] for s in train if (VIDEO_DIR / f"{_video_id(s)}.mp4").exists()
    )

    empty_classes = []
    low_classes = []
    for label in sorted(top_labels):
        avail = label_avail.get(label, 0)
        total = label_total.get(label, 0)
        if avail == 0:
            empty_classes.append(classes[label])
        elif avail < total * 0.5:
            low_classes.append((classes[label], avail, total))

    if empty_classes:
        print(f"\n  Classes with NO videos ({len(empty_classes)}): {', '.join(empty_classes[:15])}")
    if low_classes:
        print(f"  Classes with <50% coverage ({len(low_classes)}):")
        for name, a, t in low_classes[:10]:
            print(f"    {name}: {a}/{t}")
    if not empty_classes and not low_classes:
        print("\n  All classes have good coverage!")


# -- Extract keypoints -------------------------------------------------------


def extract_keypoints(num_classes: int, num_frames: int):
    from src.data.keypoint_extractor import extract_keypoints_from_video

    import numpy as np

    top_labels = get_top_n_labels(num_classes)
    ensure_dir(KEYPOINT_DIR)

    # Collect all video IDs
    video_ids: set[str] = set()
    for split in ["train", "val", "test"]:
        for s in load_split(split):
            if s["label"] in top_labels:
                video_ids.add(_video_id(s))

    already = 0
    extracted = 0
    skipped = 0

    for vid in sorted(video_ids):
        cache_path = KEYPOINT_DIR / f"{vid}.npy"
        if cache_path.exists():
            already += 1
            continue

        video_path = VIDEO_DIR / f"{vid}.mp4"
        if not video_path.exists():
            skipped += 1
            continue

        kp = extract_keypoints_from_video(str(video_path), num_frames)
        np.save(cache_path, kp)
        extracted += 1

        if (extracted + already) % 100 == 0:
            print(f"  Progress: {extracted} extracted, {already} cached, {skipped} skipped")

    print(f"\nDone: {extracted} new, {already} cached, {skipped} missing videos")


# -- CLI --------------------------------------------------------------------


def parse_args():
    p = argparse.ArgumentParser(description="Download & prepare MS-ASL dataset")
    p.add_argument("--download-videos", action="store_true",
                    help="Download clips from YouTube via yt-dlp")
    p.add_argument("--validate", action="store_true",
                    help="Check video availability for top-N classes")
    p.add_argument("--extract-keypoints", action="store_true",
                    help="Extract MediaPipe keypoints from downloaded videos")
    p.add_argument("--num-classes", type=int, default=100,
                    help="Use top-N classes by frequency (default: 100)")
    p.add_argument("--num-frames", type=int, default=32,
                    help="Frames to sample per video (default: 32)")
    p.add_argument("--workers", type=int, default=4,
                    help="Parallel download workers (default: 4)")
    return p.parse_args()


def main():
    args = parse_args()

    if not any([args.download_videos, args.validate, args.extract_keypoints]):
        print("No action specified. Use --help for usage.")
        sys.exit(1)

    if args.download_videos:
        download_videos(args.num_classes, args.workers)

    if args.validate:
        validate(args.num_classes)

    if args.extract_keypoints:
        extract_keypoints(args.num_classes, args.num_frames)


if __name__ == "__main__":
    main()
