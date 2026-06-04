"""Adapter that loads any pipeline from PIPELINE_REGISTRY and exposes a
uniform ``predict(keypoints) -> ClassifierOutput`` interface.

A segment can have a variable number of frames; the runner resamples it
uniformly to ``num_frames`` (matching the training config) before calling
the pipeline's ``classify`` method.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch

from src.data.keypoint_normalization import normalize_keypoints
from src.data.label_map import GlossLabelMap
from src.registry import PIPELINE_REGISTRY
from src.serve.schemas import ClassifierOutput
from src.utils.config import load_config


class ClassifierRunner:
    """Loads a checkpoint + label map; classifies arbitrary-length keypoint
    sequences.

    Args:
        config_path: Path to the training-time config yaml (so we know how
            to instantiate the pipeline + the label map location).
        checkpoint_path: Path to the ``.pt`` state dict.
        label_map_path: Optional explicit path to ``label_map.json``. If
            omitted, defaults to ``<output_dir>/label_map.json`` per the
            training config.
        device: ``"cuda"`` or ``"cpu"``. Falls back to CPU if CUDA unavailable.
        top_k: Number of candidates to return per prediction.
    """

    def __init__(
        self,
        config_path: str | Path,
        checkpoint_path: str | Path,
        label_map_path: str | Path | None = None,
        device: str = "cuda",
        top_k: int = 5,
    ):
        cfg = load_config(str(config_path))
        self._cfg = cfg

        if device == "cuda" and not torch.cuda.is_available():
            device = "cpu"
        self.device = device

        # Resolve label map location.
        if label_map_path is None:
            data_cfg = cfg["data"]
            if "subset_dir" in data_cfg:
                label_map_path = Path(data_cfg["subset_dir"]) / "label_map.json"
            else:
                label_map_path = Path(cfg["project"]["output_dir"]) / "label_map.json"
        self.label_map = GlossLabelMap.load(label_map_path)

        pipeline_cls = PIPELINE_REGISTRY[cfg["model"]["pipeline_name"]]
        self.model = pipeline_cls(cfg, len(self.label_map)).to(device)
        state = torch.load(str(checkpoint_path), map_location=device)
        self.model.load_state_dict(state)
        self.model.eval()

        self.num_frames = int(cfg["data"]["num_frames"])
        self.normalize = bool(cfg["data"].get("normalize_keypoints", True))
        self.top_k = top_k

    def predict(
        self,
        keypoints: np.ndarray,
        started_at: float = 0.0,
        ended_at: float = 0.0,
    ) -> ClassifierOutput:
        """Classify a (T, 225) keypoint sequence.

        Resamples to ``self.num_frames`` (uniform indices), optionally
        normalizes, and runs the model's ``classify`` to obtain top-K.
        """
        kp = self._resample(keypoints, self.num_frames)
        if self.normalize:
            kp = normalize_keypoints(kp)

        kp_t = torch.from_numpy(kp).float().to(self.device)
        with torch.no_grad():
            result = self.model.classify(kp_t, top_k=self.top_k)

        ids = result["top_k_ids"]
        probs = result["top_k_probs"]
        top = [(self.label_map.decode(int(i)), float(p)) for i, p in zip(ids, probs)]
        return ClassifierOutput(
            top_k=top,
            raw_argmax_conf=top[0][1] if top else 0.0,
            started_at=started_at,
            ended_at=ended_at,
        )

    @staticmethod
    def _resample(kp: np.ndarray, target_n: int) -> np.ndarray:
        T = kp.shape[0]
        if T == target_n:
            return kp
        if T == 0:
            return np.zeros((target_n, kp.shape[1]) if kp.ndim == 2 else (target_n,), dtype=np.float32)
        idx = np.linspace(0, T - 1, target_n).round().astype(int)
        return kp[idx]
