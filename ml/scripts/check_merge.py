"""Check WLASL + MS-ASL merge potential.

Run on the external machine where both datasets have downloaded videos/keypoints.

Usage:
    uv run scripts/check_merge.py
    uv run scripts/check_merge.py --msasl-label-map artifacts/msasl25/label_map.json
"""

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

WLASL_JSON = ROOT / "datasets" / "WLASL" / "WLASL_v0.3.json"
WLASL_VIDEO_DIR = ROOT / "datasets" / "WLASL" / "videos"
WLASL_KP_DIR = ROOT / "datasets" / "WLASL" / "keypoints"

MSASL_DIR = ROOT / "datasets" / "ms-asl"
MSASL_VIDEO_DIR = MSASL_DIR / "videos"
MSASL_KP_DIR = MSASL_DIR / "keypoints"


def msasl_video_id(sample: dict) -> str:
    raw = f"{sample['url']}_{sample.get('start_time', 0)}_{sample.get('end_time', 0)}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def has_data(video_id: str, video_dir: Path, kp_dir: Path) -> bool:
    if kp_dir.exists() and (kp_dir / f"{video_id}.npy").exists():
        return True
    return (video_dir / f"{video_id}.mp4").exists()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--msasl-label-map",
        default=None,
        help="Path to label_map.json from MS-ASL training (shows which classes were used)",
    )
    args = parser.parse_args()

    # -- MS-ASL available data --
    with open(MSASL_DIR / "MSASL_classes.json") as f:
        msasl_classes = json.load(f)

    msasl_splits = {}
    for split in ["train", "val", "test"]:
        with open(MSASL_DIR / f"MSASL_{split}.json") as f:
            msasl_splits[split] = json.load(f)

    # If label_map provided, use those classes; otherwise find top-25 by available
    if args.msasl_label_map:
        with open(args.msasl_label_map) as f:
            msasl_selected = json.load(f)
        print(f"MS-ASL classes (from label_map): {len(msasl_selected)}")
    else:
        avail = Counter()
        for s in msasl_splits["train"]:
            vid = msasl_video_id(s)
            if has_data(vid, MSASL_VIDEO_DIR, MSASL_KP_DIR):
                avail[s["label"]] += 1
        top25 = [l for l, _ in avail.most_common(25)]
        msasl_selected = [msasl_classes[l] for l in top25]
        print(f"MS-ASL top-25 by available data:")

    print(f"  Classes: {msasl_selected}\n")

    # Count available per class in MS-ASL
    msasl_gloss_to_label = {msasl_classes[i]: i for i in range(len(msasl_classes))}
    msasl_avail = {}
    for gloss in msasl_selected:
        label = msasl_gloss_to_label.get(gloss)
        if label is None:
            continue
        for split in ["train", "val", "test"]:
            count = sum(
                1 for s in msasl_splits[split]
                if s["label"] == label and has_data(msasl_video_id(s), MSASL_VIDEO_DIR, MSASL_KP_DIR)
            )
            msasl_avail.setdefault(gloss, {})[split] = count

    # -- WLASL available data --
    if not WLASL_JSON.exists():
        print(f"WLASL JSON not found at {WLASL_JSON}")
        sys.exit(1)

    with open(WLASL_JSON) as f:
        wlasl_data = json.load(f)

    wlasl_glosses = {entry["gloss"].lower(): entry for entry in wlasl_data}

    # -- Find overlap --
    overlap = []
    only_msasl = []

    for gloss in msasl_selected:
        gloss_lower = gloss.lower()
        if gloss_lower in wlasl_glosses:
            entry = wlasl_glosses[gloss_lower]
            wlasl_counts = {"train": 0, "val": 0, "test": 0}
            for inst in entry["instances"]:
                sp = inst["split"]
                vid = inst["video_id"]
                if has_data(vid, WLASL_VIDEO_DIR, WLASL_KP_DIR):
                    wlasl_counts[sp] += 1
            overlap.append((gloss, msasl_avail.get(gloss, {}), wlasl_counts))
        else:
            only_msasl.append((gloss, msasl_avail.get(gloss, {})))

    # -- Report --
    print(f"{'='*70}")
    print(f"OVERLAP: {len(overlap)} signs in both MS-ASL and WLASL")
    print(f"{'='*70}")
    print(f"{'Sign':<15} {'MS-ASL train':>12} {'WLASL train':>12} {'Combined':>10}")
    print(f"{'-'*15} {'-'*12} {'-'*12} {'-'*10}")

    total_msasl = 0
    total_wlasl = 0
    for gloss, ms_counts, wl_counts in sorted(overlap, key=lambda x: x[0]):
        ms_tr = ms_counts.get("train", 0)
        wl_tr = wl_counts.get("train", 0)
        total_msasl += ms_tr
        total_wlasl += wl_tr
        print(f"{gloss:<15} {ms_tr:>12} {wl_tr:>12} {ms_tr + wl_tr:>10}")

    print(f"{'-'*15} {'-'*12} {'-'*12} {'-'*10}")
    print(f"{'TOTAL':<15} {total_msasl:>12} {total_wlasl:>12} {total_msasl + total_wlasl:>10}")

    if only_msasl:
        print(f"\n{'='*70}")
        print(f"ONLY IN MS-ASL: {len(only_msasl)} signs (no WLASL match)")
        print(f"{'='*70}")
        for gloss, ms_counts in only_msasl:
            print(f"  {gloss:<15} train={ms_counts.get('train', 0)}")

    # -- WLASL signs NOT in MS-ASL selection but with good data --
    print(f"\n{'='*70}")
    print(f"WLASL signs with most available data (NOT in current MS-ASL selection)")
    print(f"{'='*70}")
    msasl_set = {g.lower() for g in msasl_selected}
    wlasl_extra = []
    for entry in wlasl_data[:100]:  # top-100 WLASL
        gloss = entry["gloss"].lower()
        if gloss in msasl_set:
            continue
        avail_train = sum(
            1 for inst in entry["instances"]
            if inst["split"] == "train" and has_data(inst["video_id"], WLASL_VIDEO_DIR, WLASL_KP_DIR)
        )
        if avail_train > 0:
            wlasl_extra.append((gloss, avail_train))

    wlasl_extra.sort(key=lambda x: x[1], reverse=True)
    for gloss, cnt in wlasl_extra[:20]:
        print(f"  {gloss:<15} train={cnt}")


if __name__ == "__main__":
    main()
