"""Download and prepare the WLASL dataset.

Usage:
    # 1. Download metadata (WLASL_v0.3.json from GitHub)
    uv run scripts/download_wlasl.py --download-metadata

    # 2. Download videos from Kaggle (requires `kaggle` CLI configured)
    uv run scripts/download_wlasl.py --download-videos

    # 3. Validate how many videos you have for a given subset
    uv run scripts/download_wlasl.py --validate --num-classes 100

    # 4. Extract MediaPipe keypoints for available videos
    uv run scripts/download_wlasl.py --extract-keypoints --num-classes 100 --num-frames 32
"""

import argparse
import json
import subprocess
import shutil
import sys
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))
ROOT = SCRIPT_DIR.parent / "datasets" / "WLASL"

WLASL_JSON_URL = (
    "https://raw.githubusercontent.com/dxli94/WLASL/master/start_kit/WLASL_v0.3.json"
)
WLASL_JSON_PATH = ROOT / "WLASL_v0.3.json"
VIDEO_DIR = ROOT / "videos"
KEYPOINT_DIR = ROOT / "keypoints"

KAGGLE_DATASET = "risangbaskoro/wlasl-processed"


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def load_json() -> list[dict]:
    if not WLASL_JSON_PATH.exists():
        print(f"Metadata not found at {WLASL_JSON_PATH}")
        print("Run with --download-metadata first.")
        sys.exit(1)
    with open(WLASL_JSON_PATH) as f:
        return json.load(f)


# ── Download metadata ────────────────────────────────────────────────


def download_metadata():
    ensure_dir(ROOT)
    if WLASL_JSON_PATH.exists():
        print(f"Already exists: {WLASL_JSON_PATH}")
        return

    print(f"Downloading WLASL_v0.3.json ...")
    urllib.request.urlretrieve(WLASL_JSON_URL, WLASL_JSON_PATH)

    data = load_json()
    print(f"OK — {len(data)} glosses loaded.")


# ── Download videos ──────────────────────────────────────────────────


def download_videos():
    """Download pre-collected WLASL videos from Kaggle."""
    if shutil.which("kaggle") is None:
        print("'kaggle' CLI not found. Install it:")
        print("  pip install kaggle")
        print("Then place your API token at ~/.kaggle/kaggle.json")
        print()
        print("Alternatively, download manually from:")
        print(f"  https://www.kaggle.com/datasets/{KAGGLE_DATASET}")
        print(f"and extract videos to: {VIDEO_DIR}/")
        sys.exit(1)

    tmp_dir = ROOT / "_kaggle_download"
    ensure_dir(tmp_dir)

    print(f"Downloading {KAGGLE_DATASET} from Kaggle ...")
    subprocess.run(
        [
            "kaggle", "datasets", "download",
            "-d", KAGGLE_DATASET,
            "-p", str(tmp_dir),
            "--unzip",
        ],
        check=True,
    )

    # Find the videos directory in the download
    ensure_dir(VIDEO_DIR)
    candidates = list(tmp_dir.rglob("*.mp4"))

    if not candidates:
        print("No .mp4 files found in Kaggle download!")
        sys.exit(1)

    moved = 0
    for mp4 in candidates:
        dst = VIDEO_DIR / mp4.name
        if not dst.exists():
            shutil.move(str(mp4), str(dst))
            moved += 1

    print(f"Moved {moved} videos to {VIDEO_DIR}")

    # Also grab JSON if it came with the download
    for json_file in tmp_dir.rglob("WLASL_v0.3.json"):
        if not WLASL_JSON_PATH.exists():
            shutil.copy(str(json_file), str(WLASL_JSON_PATH))
            print(f"Copied metadata: {WLASL_JSON_PATH}")

    shutil.rmtree(tmp_dir, ignore_errors=True)
    print("Done.")


# ── Validate ─────────────────────────────────────────────────────────


def validate(num_classes: int):
    data = load_json()
    glosses = data[:num_classes]

    print(f"\n=== WLASL{num_classes} validation ===\n")

    total = 0
    available = 0

    split_stats: dict[str, dict[str, int]] = {}

    for gloss_entry in glosses:
        for inst in gloss_entry["instances"]:
            split = inst["split"]
            vid = inst["video_id"]
            exists = (VIDEO_DIR / f"{vid}.mp4").exists()

            if split not in split_stats:
                split_stats[split] = {"total": 0, "available": 0}

            split_stats[split]["total"] += 1
            total += 1
            if exists:
                split_stats[split]["available"] += 1
                available += 1

    pct = available / total * 100 if total else 0
    print(f"Total: {available}/{total} videos available ({pct:.1f}%)")
    print()
    for split in ["train", "val", "test"]:
        s = split_stats.get(split, {"total": 0, "available": 0})
        sp = s["available"] / s["total"] * 100 if s["total"] else 0
        print(f"  {split:5s}: {s['available']:>5d} / {s['total']:>5d}  ({sp:.1f}%)")
    print()

    # Per-gloss breakdown for missing
    missing_glosses = []
    for gloss_entry in glosses:
        gloss = gloss_entry["gloss"]
        instances = gloss_entry["instances"]
        avail = sum(
            1 for i in instances if (VIDEO_DIR / f"{i['video_id']}.mp4").exists()
        )
        if avail < len(instances):
            missing_glosses.append((gloss, avail, len(instances)))

    if missing_glosses:
        print(f"Glosses with missing videos: {len(missing_glosses)}/{num_classes}")
        fully_missing = [g for g, a, t in missing_glosses if a == 0]
        if fully_missing:
            print(f"  Fully missing ({len(fully_missing)}): {', '.join(fully_missing[:20])}")
            if len(fully_missing) > 20:
                print(f"    ... and {len(fully_missing) - 20} more")
    else:
        print("All glosses have complete video coverage!")


# ── Extract keypoints ────────────────────────────────────────────────


def extract_keypoints(num_classes: int, num_frames: int):
    from src.data.keypoint_extractor import extract_keypoints_from_video

    import numpy as np

    data = load_json()
    glosses = data[:num_classes]

    ensure_dir(KEYPOINT_DIR)

    video_ids = set()
    for gloss_entry in glosses:
        for inst in gloss_entry["instances"]:
            video_ids.add(inst["video_id"])

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

    print(f"\nDone: {extracted} new, {already} already cached, {skipped} missing videos")


# ── CLI ──────────────────────────────────────────────────────────────


def parse_args():
    p = argparse.ArgumentParser(description="Download & prepare WLASL dataset")
    p.add_argument("--download-metadata", action="store_true",
                    help="Download WLASL_v0.3.json from GitHub")
    p.add_argument("--download-videos", action="store_true",
                    help="Download videos from Kaggle (requires kaggle CLI)")
    p.add_argument("--validate", action="store_true",
                    help="Check video availability for a subset")
    p.add_argument("--extract-keypoints", action="store_true",
                    help="Extract MediaPipe keypoints for available videos")
    p.add_argument("--num-classes", type=int, default=100,
                    choices=[100, 300, 1000, 2000],
                    help="WLASL subset size (default: 100)")
    p.add_argument("--num-frames", type=int, default=32,
                    help="Frames to sample per video for keypoint extraction (default: 32)")
    return p.parse_args()


def main():
    args = parse_args()

    if not any([args.download_metadata, args.download_videos,
                args.validate, args.extract_keypoints]):
        print("No action specified. Use --help for usage.")
        sys.exit(1)

    if args.download_metadata:
        download_metadata()

    if args.download_videos:
        download_videos()

    if args.validate:
        validate(args.num_classes)

    if args.extract_keypoints:
        extract_keypoints(args.num_classes, args.num_frames)


if __name__ == "__main__":
    main()
