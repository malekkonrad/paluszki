"""Build a unified GlossLabelMap by ranking signs across MS-ASL + WLASL
by the number of *actually available* training samples.

This ensures the top-N classes are those with the most real data,
regardless of which dataset they come from.
"""

import hashlib
import json
from collections import Counter
from pathlib import Path

from src.data.label_map import GlossLabelMap


def _msasl_video_id(sample: dict) -> str:
    raw = f"{sample['url']}_{sample.get('start_time', 0)}_{sample.get('end_time', 0)}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _has_data(video_id: str, video_dir: Path, kp_dir: Path | None) -> bool:
    if kp_dir and (kp_dir / f"{video_id}.npy").exists():
        return True
    return (video_dir / f"{video_id}.mp4").exists()


def build_merged_label_map(
    msasl_dir: str | Path,
    wlasl_json: str | Path,
    wlasl_video_dir: str | Path,
    num_classes: int = 30,
    wlasl_kp_dir: str | Path | None = None,
    msasl_kp_dir: str | Path | None = None,
) -> GlossLabelMap:
    """Rank all glosses by available train samples across both datasets.

    Returns a GlossLabelMap with the top *num_classes* glosses.
    """
    msasl_dir = Path(msasl_dir)
    wlasl_video_dir = Path(wlasl_video_dir)
    wlasl_kp_dir = Path(wlasl_kp_dir) if wlasl_kp_dir else None
    msasl_kp_dir = Path(msasl_kp_dir) if msasl_kp_dir else (msasl_dir / "keypoints")
    msasl_video_dir = msasl_dir / "videos"

    # -- Count available MS-ASL train samples per gloss --
    with open(msasl_dir / "MSASL_classes.json") as f:
        msasl_classes = json.load(f)
    with open(msasl_dir / "MSASL_train.json") as f:
        msasl_train = json.load(f)

    msasl_counts: Counter = Counter()
    for s in msasl_train:
        vid = _msasl_video_id(s)
        if _has_data(vid, msasl_video_dir, msasl_kp_dir):
            gloss = msasl_classes[s["label"]].lower()
            msasl_counts[gloss] += 1

    # -- Count available WLASL train samples per gloss --
    with open(wlasl_json) as f:
        wlasl_data = json.load(f)

    wlasl_counts: Counter = Counter()
    for entry in wlasl_data:
        gloss = entry["gloss"].lower()
        for inst in entry["instances"]:
            if inst["split"] != "train":
                continue
            vid = inst["video_id"]
            if _has_data(vid, wlasl_video_dir, wlasl_kp_dir):
                wlasl_counts[gloss] += 1

    # -- Merge: sum available samples per gloss --
    all_glosses = set(msasl_counts.keys()) | set(wlasl_counts.keys())
    combined: dict[str, int] = {}
    for g in all_glosses:
        combined[g] = msasl_counts.get(g, 0) + wlasl_counts.get(g, 0)

    # Sort by combined count descending
    ranked = sorted(combined.keys(), key=lambda g: combined[g], reverse=True)
    selected = ranked[:num_classes]

    print(f"\nMerged label map — top {num_classes} by available train data:")
    print(f"{'Sign':<20} {'MS-ASL':>7} {'WLASL':>7} {'Total':>7}")
    print(f"{'-'*20} {'-'*7} {'-'*7} {'-'*7}")
    for g in selected:
        m = msasl_counts.get(g, 0)
        w = wlasl_counts.get(g, 0)
        print(f"{g:<20} {m:>7} {w:>7} {m+w:>7}")
    total_m = sum(msasl_counts.get(g, 0) for g in selected)
    total_w = sum(wlasl_counts.get(g, 0) for g in selected)
    print(f"{'-'*20} {'-'*7} {'-'*7} {'-'*7}")
    print(f"{'TOTAL':<20} {total_m:>7} {total_w:>7} {total_m+total_w:>7}")

    return GlossLabelMap(selected)
