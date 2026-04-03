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


_error_counts: dict[str, int] = {}
_MAX_ERROR_EXAMPLES = 5
_errors_shown = 0


def _download_single(sample: dict, output_path: Path, verbose: bool = False) -> bool:
    """Download a single clip from YouTube using yt-dlp.

    Two-step approach for reliability:
    1. Download full video with yt-dlp (simple format selection)
    2. Clip to start/end time + crop to bounding box with ffmpeg
    """
    global _errors_shown

    if output_path.exists():
        return True

    url = sample["url"]
    start_time = sample.get("start_time", 0)
    end_time = sample.get("end_time", 0)
    duration = end_time - start_time

    if duration <= 0:
        return False

    with tempfile.TemporaryDirectory() as tmp:
        # Step 1: Download full video with yt-dlp
        raw_path = Path(tmp) / "full.%(ext)s"
        cmd = [
            "yt-dlp",
            "-f", "best[height<=480]/best",
            "--no-playlist",
            "--no-check-certificates",
            "-o", str(raw_path),
            url,
        ]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                if _errors_shown < _MAX_ERROR_EXAMPLES:
                    _errors_shown += 1
                    stderr = result.stderr.strip().split("\n")[-1] if result.stderr else "unknown"
                    print(f"    yt-dlp error ({url}): {stderr}")
                return False
        except subprocess.TimeoutExpired:
            if _errors_shown < _MAX_ERROR_EXAMPLES:
                _errors_shown += 1
                print(f"    yt-dlp timeout ({url})")
            return False

        # Find the downloaded file (extension varies)
        downloaded = list(Path(tmp).glob("full.*"))
        if not downloaded:
            return False
        src_path = downloaded[0]

        # Step 2: Clip + optionally crop with ffmpeg
        box = sample.get("box")
        width = sample.get("width", 640)
        height = sample.get("height", 360)

        vf_filters = []

        # Crop to bounding box if available
        if box and len(box) == 4:
            x1, y1, x2, y2 = box
            crop_x = max(int(x1 * width), 0)
            crop_y = max(int(y1 * height), 0)
            crop_w = int((x2 - x1) * width)
            crop_h = int((y2 - y1) * height)
            # Ensure even dimensions
            crop_w = max(crop_w - crop_w % 2, 2)
            crop_h = max(crop_h - crop_h % 2, 2)
            vf_filters.append(f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y}")

        # Always ensure even output dimensions
        vf_filters.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")

        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_time),
            "-i", str(src_path),
            "-t", str(duration),
            "-vf", ",".join(vf_filters),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-an",
            str(output_path),
        ]

        try:
            result = subprocess.run(
                ffmpeg_cmd, capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                if _errors_shown < _MAX_ERROR_EXAMPLES:
                    _errors_shown += 1
                    stderr = result.stderr.strip().split("\n")[-1] if result.stderr else "unknown"
                    print(f"    ffmpeg error: {stderr}")
                return False
        except subprocess.TimeoutExpired:
            return False

        return output_path.exists()


def download_videos(num_classes: int, workers: int = 4):
    """Download videos for the top-N classes across all splits."""
    global _errors_shown

    for tool in ["yt-dlp", "ffmpeg"]:
        if shutil.which(tool) is None:
            print(f"{tool} not found. Install it first.")
            sys.exit(1)

    # Check yt-dlp version
    result = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True)
    print(f"yt-dlp version: {result.stdout.strip()}")

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

    # Deduplicate by URL (same video, different clips)
    unique_urls = set(s["url"] for s in all_samples.values())

    total = len(all_samples)
    print(f"Top-{num_classes} classes: {total} clips from {len(unique_urls)} unique YouTube videos")

    already = sum(1 for vid in all_samples if (VIDEO_DIR / f"{vid}.mp4").exists())
    if already:
        print(f"  Already downloaded: {already}")

    print(f"  First errors will be shown for debugging:\n")
    _errors_shown = 0

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

        if (i + 1) % 50 == 0:
            print(
                f"  Progress: {i + 1}/{total} "
                f"(downloaded={downloaded}, failed={failed}, cached={already})"
            )

    print(f"\nDone: {downloaded} new, {already} cached, {failed} failed out of {total}")

    if failed > total * 0.8:
        print("\n*** Most downloads failed. Common causes:")
        print("  - Videos removed from YouTube (MS-ASL is from 2018-2019)")
        print("  - yt-dlp needs update: pip install -U yt-dlp")
        print("  - Network/geo restrictions")
        print("  - Check errors above for details")


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
