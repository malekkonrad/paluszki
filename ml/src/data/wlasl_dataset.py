"""WLASL dataset for isolated sign-language recognition (classification).

Loads the official WLASL JSON, filters to a requested subset (100/300/1000/2000),
and returns MediaPipe keypoints + integer class labels.
"""

import json
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset

from src.data.keypoint_extractor import extract_keypoints_from_video
from src.data.label_map import GlossLabelMap


class WLASLDataset(Dataset):
    """Each sample is one isolated sign video → (keypoints, label).

    Args:
        json_path: Path to WLASL_v0.3.json.
        video_dir: Directory containing ``<video_id>.mp4`` files.
        split: One of ``"train"``, ``"val"``, ``"test"``.
        label_map: Pre-built :class:`GlossLabelMap` (ensures consistent
            label assignment across splits).
        num_classes: How many glosses to include (100 / 300 / 1000 / 2000).
            Only used to filter the JSON; the actual class count comes from
            *label_map*.
        num_frames: Frames to sample per video.
        cache_dir: If set, cache extracted keypoints as ``.npy`` files here.
        require_video: If ``True`` (default), skip instances whose video
            file (or cached keypoints) is missing.  Set to ``False`` only
            for dry-run / validation purposes.
    """

    def __init__(
        self,
        json_path: str | Path,
        video_dir: str | Path,
        split: str,
        label_map: GlossLabelMap,
        num_classes: int = 100,
        num_frames: int = 32,
        cache_dir: str | Path | None = None,
        require_video: bool = True,
    ):
        self.video_dir = Path(video_dir)
        self.num_frames = num_frames
        self.label_map = label_map
        self.cache_dir = Path(cache_dir) if cache_dir else None

        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        with open(json_path) as f:
            data = json.load(f)

        # Build sample list: (video_id, gloss, label)
        self.samples: list[tuple[str, str, int]] = []

        for gloss_entry in data[:num_classes]:
            gloss = gloss_entry["gloss"]
            if gloss not in label_map:
                continue
            label = label_map.encode(gloss)

            for inst in gloss_entry["instances"]:
                if inst["split"] != split:
                    continue

                vid = inst["video_id"]

                if require_video and not self._has_data(vid):
                    continue

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
        keypoints = self._load_keypoints(video_id)

        return {
            "frames": torch.from_numpy(keypoints),          # [T, 225]
            "label": label,
            "gloss": gloss,
            "video_id": video_id,
        }
