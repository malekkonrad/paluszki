from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset

from src.data.keypoint_extractor import KEYPOINT_DIM, extract_keypoints_from_video


class KeypointDataset(Dataset):
    """Dataset that extracts MediaPipe keypoints instead of raw video frames.

    Stores keypoints as batch["frames"] with shape [T, KEYPOINT_DIM] so that
    the existing Trainer / collate_fn work without modification.

    Args:
        cache_dir: If provided, extracted keypoints are saved as .npy files
                   here and reloaded on subsequent runs (avoids re-running
                   MediaPipe on every epoch).
    """

    def __init__(
        self,
        csv_path,
        video_dir,
        tokenizer,
        video_column="video_name",
        text_column="text",
        num_frames=16,
        max_text_len=40,
        csv_separator=",",
        cache_dir=None,
    ):
        self.df = pd.read_csv(csv_path, sep=csv_separator)
        self.video_dir = Path(video_dir)
        self.tokenizer = tokenizer
        self.video_column = video_column
        self.text_column = text_column
        self.num_frames = num_frames
        self.max_text_len = max_text_len
        self.cache_dir = Path(cache_dir) if cache_dir else None

        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def __len__(self):
        return len(self.df)

    def _load_keypoints(self, video_name: str) -> np.ndarray:
        if self.cache_dir:
            cache_path = self.cache_dir / f"{video_name}.npy"
            if cache_path.exists():
                return np.load(cache_path)

        video_file = video_name if Path(video_name).suffix else f"{video_name}.mp4"
        video_path = self.video_dir / video_file

        keypoints = extract_keypoints_from_video(str(video_path), self.num_frames)

        if self.cache_dir:
            np.save(self.cache_dir / f"{video_name}.npy", keypoints)

        return keypoints

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        video_name = str(row[self.video_column])
        text = row[self.text_column]

        keypoints = self._load_keypoints(video_name)
        frames = torch.from_numpy(keypoints)  # [T, KEYPOINT_DIM]
        tokens = self.tokenizer.encode(text, max_len=self.max_text_len)

        return {
            "frames": frames,      # reuses "frames" key for Trainer compatibility
            "tokens": tokens,
            "text": text,
            "video_name": video_name,
        }
