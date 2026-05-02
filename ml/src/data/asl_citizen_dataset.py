"""ASL Citizen dataset for isolated sign-language recognition (classification).

Reads CSV splits with columns ``Participant ID, Video file, Gloss, ASL-LEX Code``
and resolves video files from a single ``videos/`` directory shared across
all splits.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset

from src.data.keypoint_extractor import extract_keypoints_from_video
from src.data.keypoint_normalization import normalize_keypoints
from src.data.label_map import GlossLabelMap


class ASLCitizenDataset(Dataset):
    """One isolated sign clip → (keypoints, label).

    Args:
        csv_path: Path to a split CSV (typically the filtered subset CSV).
        video_dir: Directory containing the .mp4 files (shared across splits).
        label_map: Pre-built :class:`GlossLabelMap`. Samples whose gloss
            isn't in the map are skipped.
        num_frames: Frames to uniformly sample per clip.
        cache_dir: If set, cache extracted keypoints as ``.npy``.
        normalize: Apply body-centered normalization.
        transform: Optional augmentation callable applied to (T, 225).
    """

    def __init__(
        self,
        csv_path: str | Path,
        video_dir: str | Path,
        label_map: GlossLabelMap,
        num_frames: int = 32,
        cache_dir: str | Path | None = None,
        normalize: bool = True,
        transform=None,
    ):
        self.video_dir = Path(video_dir)
        self.num_frames = num_frames
        self.label_map = label_map
        self.normalize = normalize
        self.transform = transform
        self.cache_dir = Path(cache_dir) if cache_dir else None

        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        df = pd.read_csv(csv_path)

        self.samples: list[tuple[str, str, int]] = []  # (video_file, gloss, label)
        for _, row in df.iterrows():
            gloss = str(row["Gloss"])
            if gloss not in label_map:
                continue
            video_file = str(row["Video file"])
            if not self._has_data(video_file):
                continue
            label = label_map.encode(gloss)
            self.samples.append((video_file, gloss, label))

    def _cache_key(self, video_file: str) -> str:
        return Path(video_file).stem

    def _has_data(self, video_file: str) -> bool:
        if self.cache_dir and (self.cache_dir / f"{self._cache_key(video_file)}.npy").exists():
            return True
        return (self.video_dir / video_file).exists()

    def _load_keypoints(self, video_file: str) -> np.ndarray:
        if self.cache_dir:
            cache_path = self.cache_dir / f"{self._cache_key(video_file)}.npy"
            if cache_path.exists():
                return np.load(cache_path)

        video_path = self.video_dir / video_file
        keypoints = extract_keypoints_from_video(str(video_path), self.num_frames)

        if self.cache_dir:
            np.save(self.cache_dir / f"{self._cache_key(video_file)}.npy", keypoints)

        return keypoints

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> dict:
        video_file, gloss, label = self.samples[idx]
        keypoints = self._load_keypoints(video_file)

        if self.normalize:
            keypoints = normalize_keypoints(keypoints)

        if self.transform is not None:
            keypoints = self.transform(keypoints)

        return {
            "frames": torch.from_numpy(keypoints).float(),
            "label": label,
            "gloss": gloss,
            "video_id": self._cache_key(video_file),
        }
