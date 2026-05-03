"""Evaluate a trained ASL Citizen checkpoint on the test split.

Loads the subset built by ``build_asl_citizen_subset.py`` plus a checkpoint,
runs the model over ``test.csv`` and reports overall top-1 / top-5 accuracy
along with per-class accuracy (sorted worst → best).

Usage:
    uv run -m scripts.eval_asl_citizen \\
        --config configs/asl_citizen100.yaml \\
        --checkpoint artifacts/asl_citizen100/best_model.pt
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from src.data.asl_citizen_dataset import ASLCitizenDataset
from src.data.collate import classification_collate_fn
from src.data.label_map import GlossLabelMap
from src.evaluation.metrics import compute_accuracy, compute_top_k_accuracy
from src.registry import PIPELINE_REGISTRY
from src.utils.config import load_config
from src.utils.seed import set_seed


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate ASL Citizen model on test split.")
    parser.add_argument("--config", type=str, required=True, help="Path to training config yaml.")
    parser.add_argument("--checkpoint", type=str, required=True, help="Path to .pt checkpoint.")
    parser.add_argument(
        "--split",
        type=str,
        default="test",
        choices=["train", "val", "test"],
        help="Which split CSV to evaluate (default: test).",
    )
    parser.add_argument(
        "--worst-n",
        type=int,
        default=15,
        help="How many worst/best classes to show in the per-class report.",
    )
    return parser.parse_args()


def build_loader(cfg, split: str, label_map: GlossLabelMap) -> DataLoader:
    data_cfg = cfg["data"]
    subset_dir = Path(data_cfg["subset_dir"])

    dataset = ASLCitizenDataset(
        csv_path=subset_dir / f"{split}.csv",
        video_dir=data_cfg["video_dir"],
        label_map=label_map,
        num_frames=data_cfg["num_frames"],
        cache_dir=data_cfg.get("keypoint_cache_dir"),
        normalize=data_cfg.get("normalize_keypoints", True),
    )

    return DataLoader(
        dataset,
        batch_size=cfg["train"]["batch_size"],
        shuffle=False,
        num_workers=cfg["train"]["num_workers"],
        collate_fn=classification_collate_fn,
    ), len(dataset)


@torch.no_grad()
def run_eval(model, loader, device):
    model.eval()
    all_logits = []
    all_labels = []

    for batch in loader:
        batch["frames"] = batch["frames"].to(device)
        batch["labels"] = batch["labels"].to(device)
        outputs = model(batch)
        all_logits.append(outputs["logits"].cpu())
        all_labels.append(batch["labels"].cpu())

    return torch.cat(all_logits), torch.cat(all_labels)


def per_class_accuracy(logits: torch.Tensor, labels: torch.Tensor, label_map: GlossLabelMap):
    preds = logits.argmax(dim=-1)
    correct = (preds == labels)

    counts = defaultdict(int)
    hits = defaultdict(int)
    for label, hit in zip(labels.tolist(), correct.tolist()):
        counts[label] += 1
        hits[label] += int(hit)

    rows = []
    for label_id in sorted(counts.keys()):
        n = counts[label_id]
        acc = 100.0 * hits[label_id] / n if n else 0.0
        rows.append((label_map.decode(label_id), acc, hits[label_id], n))
    return rows


def main():
    args = parse_args()
    cfg = load_config(args.config)
    set_seed(cfg["project"]["seed"])

    device = cfg["train"]["device"]
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"

    subset_dir = Path(cfg["data"]["subset_dir"])
    label_map = GlossLabelMap.load(subset_dir / "label_map.json")

    pipeline_cls = PIPELINE_REGISTRY[cfg["model"]["pipeline_name"]]
    model = pipeline_cls(cfg, len(label_map)).to(device)

    state = torch.load(args.checkpoint, map_location=device)
    model.load_state_dict(state)

    loader, n_samples = build_loader(cfg, args.split, label_map)
    print(f"Evaluating on {args.split}: {n_samples} samples, {len(label_map)} classes")
    print(f"Checkpoint: {args.checkpoint}\n")

    logits, labels = run_eval(model, loader, device)

    top1 = compute_accuracy(logits, labels)
    top5 = compute_top_k_accuracy(logits, labels, k=5)
    top10 = compute_top_k_accuracy(logits, labels, k=10)

    print("Overall:")
    print(f"  top-1:  {top1:.2f}%")
    print(f"  top-5:  {top5:.2f}%")
    print(f"  top-10: {top10:.2f}%\n")

    rows = per_class_accuracy(logits, labels, label_map)
    rows_sorted = sorted(rows, key=lambda r: r[1])

    n = min(args.worst_n, len(rows_sorted))
    print(f"Worst {n} classes:")
    for gloss, acc, hits, total in rows_sorted[:n]:
        print(f"  {gloss:20s} {acc:6.2f}%  ({hits}/{total})")

    print(f"\nBest {n} classes:")
    for gloss, acc, hits, total in rows_sorted[-n:][::-1]:
        print(f"  {gloss:20s} {acc:6.2f}%  ({hits}/{total})")

    perfect = sum(1 for r in rows if r[1] == 100.0)
    zero = sum(1 for r in rows if r[1] == 0.0)
    print(f"\nClasses at 100%: {perfect}/{len(rows)}")
    print(f"Classes at   0%: {zero}/{len(rows)}")


if __name__ == "__main__":
    main()
