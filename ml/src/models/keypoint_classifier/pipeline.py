"""Classification pipeline: MediaPipe keypoints → Transformer Encoder → class label.

Designed for isolated sign-language recognition (e.g. WLASL).

The encoder is factored out as :class:`KeypointEncoder` so it can be:
- pre-trained with self-supervised objectives (SignBERT-style),
- shared across different downstream heads,
- combined with other modalities in an ensemble.
"""

import torch
import torch.nn as nn

from src.data.keypoint_extractor import KEYPOINT_DIM
from src.models.base import BasePipeline


class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_len: int = 512):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float32).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2, dtype=torch.float32)
            * (-torch.log(torch.tensor(10000.0)) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.pe[:, : x.size(1), :]


class KeypointEncoder(nn.Module):
    """Temporal transformer encoder over per-frame MediaPipe keypoints.

    Input:  [B, T, keypoint_dim]
    Output: [B, d_model]  (pooled representation)

    The encoder can be used standalone for pre-training or plugged into
    any downstream head.
    """

    def __init__(
        self,
        keypoint_dim: int = KEYPOINT_DIM,
        d_model: int = 256,
        nhead: int = 8,
        num_layers: int = 4,
        dropout: float = 0.3,
        pooling: str = "mean",
    ):
        super().__init__()
        self.pooling = pooling

        self.kp_proj = nn.Sequential(
            nn.Linear(keypoint_dim, d_model),
            nn.LayerNorm(d_model),
        )
        self.pos_enc = PositionalEncoding(d_model)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=4 * d_model,
            dropout=dropout,
            batch_first=True,
        )
        self.temporal_encoder = nn.TransformerEncoder(
            encoder_layer, num_layers=num_layers,
        )

    def forward(self, keypoints: torch.Tensor) -> torch.Tensor:
        """
        Args:
            keypoints: [B, T, keypoint_dim]
        Returns:
            [B, d_model] pooled feature vector
        """
        x = self.kp_proj(keypoints)
        x = self.pos_enc(x)
        x = self.temporal_encoder(x)       # [B, T, d_model]

        if self.pooling == "mean":
            return x.mean(dim=1)           # [B, d_model]
        elif self.pooling == "cls":
            return x[:, 0, :]
        else:
            raise ValueError(f"Unknown pooling: {self.pooling}")


class KeypointClassifierPipeline(BasePipeline):
    """End-to-end: keypoints → encoder → classification head.

    Constructor expects ``cfg`` dict and ``num_classes`` (int).
    """

    def __init__(self, cfg: dict, num_classes: int):
        super().__init__()
        model_cfg = cfg["model"]

        d_model = model_cfg["d_model"]
        dropout = model_cfg["dropout"]

        self.encoder = KeypointEncoder(
            keypoint_dim=model_cfg.get("keypoint_dim", KEYPOINT_DIM),
            d_model=d_model,
            nhead=model_cfg["nhead"],
            num_layers=model_cfg.get("num_encoder_layers", model_cfg.get("num_layers", 4)),
            dropout=dropout,
            pooling=model_cfg.get("pooling", "mean"),
        )

        classifier_hidden = model_cfg.get("classifier_hidden", d_model * 2)
        self.classifier = nn.Sequential(
            nn.LayerNorm(d_model),
            nn.Dropout(dropout),
            nn.Linear(d_model, classifier_hidden),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(classifier_hidden, num_classes),
        )

        self.criterion = nn.CrossEntropyLoss(
            label_smoothing=model_cfg.get("label_smoothing", 0.1),
        )
        self.num_classes = num_classes

    def forward(self, batch: dict) -> dict:
        keypoints = batch["frames"]                 # [B, T, kp_dim]
        features = self.encoder(keypoints)           # [B, d_model]
        logits = self.classifier(features)           # [B, num_classes]
        return {"logits": logits}

    def compute_loss(self, batch: dict, outputs: dict) -> dict:
        logits = outputs["logits"]                   # [B, num_classes]
        labels = batch["labels"]                     # [B]
        loss = self.criterion(logits, labels)
        return {"loss": loss}

    @torch.no_grad()
    def classify(self, keypoints: torch.Tensor, top_k: int = 5) -> dict:
        """Single-sample inference.

        Args:
            keypoints: [T, kp_dim] — single video, no batch dim.
            top_k: Return top-k predictions.
        Returns:
            dict with ``"top_k_ids"`` and ``"top_k_probs"``.
        """
        self.eval()
        keypoints = keypoints.unsqueeze(0)           # [1, T, kp_dim]
        features = self.encoder(keypoints)
        logits = self.classifier(features).squeeze(0)  # [num_classes]
        probs = torch.softmax(logits, dim=0)

        top_probs, top_ids = probs.topk(top_k)
        return {
            "top_k_ids": top_ids.tolist(),
            "top_k_probs": top_probs.tolist(),
        }
