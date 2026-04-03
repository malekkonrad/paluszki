"""MS-ASL dataset for isolated sign-language recognition (classification).

Loads the MS-ASL JSON metadata (train/val/test), filters to the top-N most
frequent classes, and returns MediaPipe keypoints + integer class labels.
"""

import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset

from src.data.keypoint_extractor import extract_keypoints_from_video
from src.data.keypoint_normalization import normalize_keypoints
from src.data.label_map import GlossLabelMap


def _video_id(sample: dict) -> str:
    """Stable video ID from URL + timestamps (must match download script)."""
    url = sample["url"]
    start = sample.get("start_time", 0)
    end = sample.get("end_time", 0)
    raw = f"{url}_{start}_{end}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


class MSASLDataset(Dataset):
    """Each sample is one isolated sign video -> (keypoints, label).

    Args:
        data_dir: Root directory containing MSASL_*.json and videos/ subdir.
        split: One of ``"train"``, ``"val"``, ``"test"``.
        label_map: Pre-built :class:`GlossLabelMap` for consistent labels.
        num_frames: Frames to sample per video.
        cache_dir: If set, cache extracted keypoints as ``.npy`` files.
        normalize: Whether to apply body-centered normalization.
        transform: Optional callable applied to keypoints array (T, 225)
            after normalization but before converting to tensor (e.g.
            :class:`KeypointAugmentor`).
    """

    def __init__(
        self,
        data_dir: str | Path,
        split: str,
        label_map: GlossLabelMap,
        num_frames: int = 32,
        cache_dir: str | Path | None = None,
        normalize: bool = True,
        transform=None,
    ):
        self.data_dir = Path(data_dir)
        self.video_dir = self.data_dir / "videos"
        self.num_frames = num_frames
        self.label_map = label_map
        self.normalize = normalize
        self.transform = transform
        self.cache_dir = Path(cache_dir) if cache_dir else None

        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        classes_path = self.data_dir / "MSASL_classes.json"
        with open(classes_path) as f:
            self.classes: list[str] = json.load(f)

        split_path = self.data_dir / f"MSASL_{split}.json"
        with open(split_path) as f:
            raw_samples: list[dict] = json.load(f)

        # Build sample list filtered to classes in label_map
        self.samples: list[tuple[str, str, int]] = []  # (video_id, gloss, label)

        for s in raw_samples:
            gloss = self.classes[s["label"]]
            if gloss not in label_map:
                continue

            vid = _video_id(s)
            if not self._has_data(vid):
                continue

            label = label_map.encode(gloss)
            self.samples.append((vid, gloss, label))

    def _has_data(self, video_id: str) -> bool:
        if self.cache_dir and (self.cache_dir / f"{video_id}.npy").exists():
            return True
        return (self.video_dir / f"{video_id}.mp4").exists()

    def _load_keypoints(self, video_id: str) -> np.ndarray:
        if self.cache_dir:
            cache_path = self.cache_dir / f"{video_id}.npy"
            if cache_path.exists():
                return np.load(cache_path)

        video_path = self.video_dir / f"{video_id}.mp4"
        keypoints = extract_keypoints_from_video(str(video_path), self.num_frames)

        if self.cache_dir:
            np.save(self.cache_dir / f"{video_id}.npy", keypoints)

        return keypoints

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> dict:
        video_id, gloss, label = self.samples[idx]
        keypoints = self._load_keypoints(video_id)  # (T, 225)

        if self.normalize:
            keypoints = normalize_keypoints(keypoints)

        if self.transform is not None:
            keypoints = self.transform(keypoints)

        return {
            "frames": torch.from_numpy(keypoints).float(),
            "label": label,
            "gloss": gloss,
            "video_id": video_id,
        }


def build_msasl_label_map(
    data_dir: str | Path,
    num_classes: int = 100,
    rank_by_available: bool = True,
) -> GlossLabelMap:
    """Build a GlossLabelMap from the top-N MS-ASL train classes.

    Args:
        data_dir: Root directory with MSASL JSONs, videos/, and keypoints/.
        num_classes: How many classes to include.
        rank_by_available: If True, rank by number of samples that have
            a downloaded video or cached keypoints (not by total dataset
            frequency). Falls back to dataset frequency for ties.
    """
    data_dir = Path(data_dir)
    video_dir = data_dir / "videos"
    cache_dir = data_dir / "keypoints"

    with open(data_dir / "MSASL_classes.json") as f:
        classes = json.load(f)
    with open(data_dir / "MSASL_train.json") as f:
        train = json.load(f)

    if rank_by_available:
        avail_counts: Counter = Counter()
        total_counts: Counter = Counter()
        for s in train:
            vid = _video_id(s)
            total_counts[s["label"]] += 1
            has_cache = cache_dir.exists() and (cache_dir / f"{vid}.npy").exists()
            has_video = (video_dir / f"{vid}.mp4").exists()
            if has_cache or has_video:
                avail_counts[s["label"]] += 1

        # Sort by available count desc, break ties by total count desc
        ranked = sorted(
            avail_counts.keys(),
            key=lambda l: (avail_counts[l], total_counts[l]),
            reverse=True,
        )
        top_labels = ranked[:num_classes]
    else:
        counts = Counter(s["label"] for s in train)
        top_labels = [label for label, _ in counts.most_common(num_classes)]

    glosses = [classes[label] for label in top_labels]
    return GlossLabelMap(glosses)
