import argparse
from pathlib import Path

import pandas as pd
import torch
from torch.utils.data import ConcatDataset, DataLoader, random_split

from src.data.collate import classification_collate_fn, collate_fn
from src.data.how2sign_dataset import How2SignDataset
from src.data.keypoint_dataset import KeypointDataset
from src.data.tokenizer import SimpleTokenizer
from src.registry import PIPELINE_REGISTRY
from src.tracking.mlflow_logger import MLFlowLogger
from src.training.trainer import Trainer
from src.utils.config import ensure_dir, load_config
from src.utils.seed import set_seed


def parse_args():
    parser = argparse.ArgumentParser(description="Train sign-language model.")
    parser.add_argument(
        "--config",
        type=str,
        default="configs/base.yaml",
        help="Path to training config yaml file.",
    )
    return parser.parse_args()


def _build_classification_loaders(cfg):
    """Build train/val DataLoaders for WLASL or MS-ASL classification."""
    from src.data.label_map import GlossLabelMap

    data_cfg = cfg["data"]
    dataset_type = data_cfg.get("dataset_type", "wlasl")

    if dataset_type == "merged":
        return _build_merged_loaders(cfg)
    if dataset_type == "msasl":
        return _build_msasl_loaders(cfg)
    if dataset_type == "asl_citizen":
        return _build_asl_citizen_loaders(cfg)

    # Default: WLASL
    from src.data.wlasl_dataset import WLASLDataset

    label_map = GlossLabelMap.from_wlasl_json(
        data_cfg["json_path"],
        num_classes=data_cfg["num_classes"],
    )

    shared = dict(
        json_path=data_cfg["json_path"],
        video_dir=data_cfg["video_dir"],
        num_classes=data_cfg["num_classes"],
        num_frames=data_cfg["num_frames"],
        cache_dir=data_cfg.get("keypoint_cache_dir"),
        label_map=label_map,
    )

    train_ds = WLASLDataset(split="train", **shared)
    val_ds = WLASLDataset(split="val", **shared)

    print(f"WLASL{data_cfg['num_classes']}: {len(train_ds)} train, {len(val_ds)} val samples")

    train_loader = DataLoader(
        train_ds,
        batch_size=cfg["train"]["batch_size"],
        shuffle=True,
        num_workers=cfg["train"]["num_workers"],
        collate_fn=classification_collate_fn,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=cfg["train"]["batch_size"],
        shuffle=False,
        num_workers=cfg["train"]["num_workers"],
        collate_fn=classification_collate_fn,
    )

    return train_loader, val_loader, label_map


def _build_msasl_loaders(cfg):
    """Build train/val DataLoaders for MS-ASL classification.

    If the val split has too few samples (< 10% of train), automatically
    splits the train set 80/20.
    """
    from src.data.keypoint_augmentation import KeypointAugmentor
    from src.data.msasl_dataset import MSASLDataset, build_msasl_label_map

    data_cfg = cfg["data"]
    aug_cfg = cfg.get("augmentation", {})

    label_map = build_msasl_label_map(
        data_cfg["data_dir"],
        num_classes=data_cfg["num_classes"],
    )

    # Log selected classes
    print(f"\nSelected {len(label_map)} classes (ranked by available data):")
    for i, gloss in enumerate(label_map.glosses):
        print(f"  {i:3d}. {gloss}")

    normalize = data_cfg.get("normalize_keypoints", True)
    train_transform = KeypointAugmentor(aug_cfg) if aug_cfg.get("enabled", False) else None

    shared = dict(
        data_dir=data_cfg["data_dir"],
        num_frames=data_cfg["num_frames"],
        cache_dir=data_cfg.get("keypoint_cache_dir"),
        label_map=label_map,
        normalize=normalize,
    )

    train_ds = MSASLDataset(split="train", transform=train_transform, **shared)
    val_ds = MSASLDataset(split="val", **shared)

    # Auto-split train if val is too small
    val_split = data_cfg.get("val_split", 0.2)
    if len(val_ds) < len(train_ds) * 0.1:
        print(f"  Val set too small ({len(val_ds)}), splitting train {1-val_split:.0%}/{val_split:.0%}")
        total = len(train_ds)
        val_size = int(total * val_split)
        train_size = total - val_size
        train_ds, val_ds = random_split(train_ds, [train_size, val_size])

    print(f"MS-ASL top-{data_cfg['num_classes']}: {len(train_ds)} train, {len(val_ds)} val samples")

    train_loader = DataLoader(
        train_ds,
        batch_size=cfg["train"]["batch_size"],
        shuffle=True,
        num_workers=cfg["train"]["num_workers"],
        collate_fn=classification_collate_fn,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=cfg["train"]["batch_size"],
        shuffle=False,
        num_workers=cfg["train"]["num_workers"],
        collate_fn=classification_collate_fn,
    )

    return train_loader, val_loader, label_map


def _build_asl_citizen_loaders(cfg):
    """Build train/val DataLoaders for the ASL Citizen subset.

    Expects ``data.subset_dir`` to point at the directory produced by
    ``scripts/build_asl_citizen_subset.py`` (containing ``label_map.json``
    and filtered ``train.csv`` / ``val.csv`` / ``test.csv``).
    """
    from src.data.asl_citizen_dataset import ASLCitizenDataset
    from src.data.keypoint_augmentation import KeypointAugmentor
    from src.data.label_map import GlossLabelMap

    data_cfg = cfg["data"]
    aug_cfg = cfg.get("augmentation", {})

    subset_dir = Path(data_cfg["subset_dir"])
    label_map = GlossLabelMap.load(subset_dir / "label_map.json")

    print(f"\nASL Citizen: {len(label_map)} classes")
    for i, gloss in enumerate(label_map.glosses):
        print(f"  {i:3d}. {gloss}")

    normalize = data_cfg.get("normalize_keypoints", True)
    train_transform = KeypointAugmentor(aug_cfg) if aug_cfg.get("enabled", False) else None

    shared = dict(
        video_dir=data_cfg["video_dir"],
        label_map=label_map,
        num_frames=data_cfg["num_frames"],
        cache_dir=data_cfg.get("keypoint_cache_dir"),
        normalize=normalize,
    )

    train_ds = ASLCitizenDataset(
        csv_path=subset_dir / "train.csv", transform=train_transform, **shared,
    )
    val_ds = ASLCitizenDataset(csv_path=subset_dir / "val.csv", **shared)

    print(f"ASL Citizen: {len(train_ds)} train, {len(val_ds)} val samples")

    train_loader = DataLoader(
        train_ds,
        batch_size=cfg["train"]["batch_size"],
        shuffle=True,
        num_workers=cfg["train"]["num_workers"],
        collate_fn=classification_collate_fn,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=cfg["train"]["batch_size"],
        shuffle=False,
        num_workers=cfg["train"]["num_workers"],
        collate_fn=classification_collate_fn,
    )

    return train_loader, val_loader, label_map


def _build_merged_loaders(cfg):
    """Build train/val DataLoaders from MS-ASL + WLASL combined."""
    from src.data.keypoint_augmentation import KeypointAugmentor
    from src.data.merged_label_map import build_merged_label_map
    from src.data.msasl_dataset import MSASLDataset
    from src.data.wlasl_dataset import WLASLDataset

    data_cfg = cfg["data"]
    aug_cfg = cfg.get("augmentation", {})

    label_map = build_merged_label_map(
        msasl_dir=data_cfg["msasl_dir"],
        wlasl_json=data_cfg["wlasl_json"],
        wlasl_video_dir=data_cfg["wlasl_video_dir"],
        num_classes=data_cfg["num_classes"],
        wlasl_kp_dir=data_cfg.get("wlasl_kp_dir"),
        msasl_kp_dir=data_cfg.get("msasl_kp_dir"),
    )

    normalize = data_cfg.get("normalize_keypoints", True)
    train_transform = KeypointAugmentor(aug_cfg) if aug_cfg.get("enabled", False) else None

    # MS-ASL datasets
    msasl_train = MSASLDataset(
        data_dir=data_cfg["msasl_dir"],
        split="train",
        label_map=label_map,
        num_frames=data_cfg["num_frames"],
        cache_dir=data_cfg.get("msasl_kp_dir"),
        normalize=normalize,
        transform=train_transform,
    )
    msasl_val = MSASLDataset(
        data_dir=data_cfg["msasl_dir"],
        split="val",
        label_map=label_map,
        num_frames=data_cfg["num_frames"],
        cache_dir=data_cfg.get("msasl_kp_dir"),
        normalize=normalize,
    )

    # WLASL datasets — num_classes high enough to include all glosses
    wlasl_shared = dict(
        json_path=data_cfg["wlasl_json"],
        video_dir=data_cfg["wlasl_video_dir"],
        num_classes=2000,  # don't filter — label_map already selects
        num_frames=data_cfg["num_frames"],
        cache_dir=data_cfg.get("wlasl_kp_dir"),
        label_map=label_map,
        normalize=normalize,
    )
    wlasl_train = WLASLDataset(split="train", transform=train_transform, **wlasl_shared)
    wlasl_val = WLASLDataset(split="val", **wlasl_shared)

    # Concat
    train_ds = ConcatDataset([msasl_train, wlasl_train])
    val_ds = ConcatDataset([msasl_val, wlasl_val])

    # Auto-split if val too small
    val_split = data_cfg.get("val_split", 0.2)
    if len(val_ds) < len(train_ds) * 0.1:
        print(f"  Val set too small ({len(val_ds)}), splitting all data {1-val_split:.0%}/{val_split:.0%}")
        all_ds = ConcatDataset([train_ds, val_ds])
        total = len(all_ds)
        val_size = int(total * val_split)
        train_size = total - val_size
        train_ds, val_ds = random_split(all_ds, [train_size, val_size])

    print(f"\nMerged: {len(train_ds)} train, {len(val_ds)} val samples")
    print(f"  MS-ASL: {len(msasl_train)} train, {len(msasl_val)} val")
    print(f"  WLASL:  {len(wlasl_train)} train, {len(wlasl_val)} val")

    train_loader = DataLoader(
        train_ds,
        batch_size=cfg["train"]["batch_size"],
        shuffle=True,
        num_workers=cfg["train"]["num_workers"],
        collate_fn=classification_collate_fn,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=cfg["train"]["batch_size"],
        shuffle=False,
        num_workers=cfg["train"]["num_workers"],
        collate_fn=classification_collate_fn,
    )

    return train_loader, val_loader, label_map


def _build_translation_loaders(cfg):
    """Build train/val DataLoaders for How2Sign translation."""
    csv_separator = cfg["data"].get("csv_separator", ",")
    data_cfg = cfg["data"]
    has_explicit_train_val = "train_csv_path" in data_cfg and "val_csv_path" in data_cfg
    has_legacy_split = "csv_path" in data_cfg and "train_split" in data_cfg

    if not has_explicit_train_val and not has_legacy_split:
        raise ValueError(
            "Config data section must define either "
            "train_csv_path+val_csv_path (recommended) or csv_path+train_split (legacy)."
        )

    text_column = data_cfg["text_column"]

    if has_explicit_train_val:
        train_csv_path = data_cfg["train_csv_path"]
        val_csv_path = data_cfg["val_csv_path"]
        train_video_dir = data_cfg.get("train_video_dir", data_cfg.get("video_dir"))
        val_video_dir = data_cfg.get("val_video_dir", data_cfg.get("video_dir"))

        if train_video_dir is None or val_video_dir is None:
            raise ValueError(
                "When using train_csv_path/val_csv_path provide train_video_dir and val_video_dir "
                "or a shared video_dir."
            )

        train_df = pd.read_csv(train_csv_path, sep=csv_separator)
        texts = train_df[text_column].astype(str).tolist()
    else:
        df = pd.read_csv(data_cfg["csv_path"], sep=csv_separator)
        texts = df[text_column].astype(str).tolist()

    tokenizer = SimpleTokenizer(texts)

    dataset_type = data_cfg.get("dataset_type", "video")
    shared_kwargs = {
        "tokenizer": tokenizer,
        "video_column": data_cfg["video_column"],
        "text_column": text_column,
        "num_frames": data_cfg["num_frames"],
        "max_text_len": data_cfg["max_text_len"],
        "csv_separator": csv_separator,
    }

    if dataset_type == "keypoint":
        DatasetClass = KeypointDataset
        extra_kwargs = {"cache_dir": data_cfg.get("keypoint_cache_dir")}
    else:
        DatasetClass = How2SignDataset
        extra_kwargs = {"image_size": data_cfg["image_size"]}

    dataset_kwargs = {**shared_kwargs, **extra_kwargs}

    if has_explicit_train_val:
        train_ds = DatasetClass(
            csv_path=train_csv_path, video_dir=train_video_dir, **dataset_kwargs,
        )
        val_ds = DatasetClass(
            csv_path=val_csv_path, video_dir=val_video_dir, **dataset_kwargs,
        )
    else:
        dataset = DatasetClass(
            csv_path=data_cfg["csv_path"], video_dir=data_cfg["video_dir"], **dataset_kwargs,
        )
        train_size = int(data_cfg["train_split"] * len(dataset))
        val_size = len(dataset) - train_size
        train_ds, val_ds = random_split(dataset, [train_size, val_size])

    train_loader = DataLoader(
        train_ds,
        batch_size=cfg["train"]["batch_size"],
        shuffle=True,
        num_workers=cfg["train"]["num_workers"],
        collate_fn=collate_fn,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=cfg["train"]["batch_size"],
        shuffle=False,
        num_workers=cfg["train"]["num_workers"],
        collate_fn=collate_fn,
    )

    return train_loader, val_loader, tokenizer


def _build_scheduler(optimizer, cfg):
    """Build an LR scheduler from config. Returns None if disabled."""
    name = cfg["train"].get("scheduler", "none")
    if name in (None, "none", "None", False):
        return None

    epochs = cfg["train"]["epochs"]
    if name == "cosine":
        warmup = cfg["train"].get("warmup_epochs", 0)
        if warmup > 0:
            warmup_sched = torch.optim.lr_scheduler.LinearLR(
                optimizer, start_factor=1e-3, end_factor=1.0, total_iters=warmup,
            )
            cosine_sched = torch.optim.lr_scheduler.CosineAnnealingLR(
                optimizer, T_max=max(epochs - warmup, 1),
            )
            return torch.optim.lr_scheduler.SequentialLR(
                optimizer, schedulers=[warmup_sched, cosine_sched], milestones=[warmup],
            )
        return torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    raise ValueError(f"Unknown scheduler: {name}")


def main():
    args = parse_args()
    cfg = load_config(args.config)
    set_seed(cfg["project"]["seed"])

    device = cfg["train"]["device"]
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"

    output_dir = ensure_dir(cfg["project"]["output_dir"])
    task_type = cfg["data"].get("task", "translation")
    pipeline_name = cfg["model"]["pipeline_name"]

    if task_type == "classification":
        train_loader, val_loader, label_map = _build_classification_loaders(cfg)
        num_classes = len(label_map)
        pipeline_cls = PIPELINE_REGISTRY[pipeline_name]
        model = pipeline_cls(cfg, num_classes).to(device)

        # Save label map alongside checkpoints
        label_map.save(output_dir / "label_map.json")
    else:
        train_loader, val_loader, tokenizer = _build_translation_loaders(cfg)
        pipeline_cls = PIPELINE_REGISTRY[pipeline_name]
        model = pipeline_cls(cfg, tokenizer).to(device)

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=cfg["train"]["lr"],
        weight_decay=cfg["train"]["weight_decay"],
    )

    scheduler = _build_scheduler(optimizer, cfg)

    mlflow_logger = MLFlowLogger(cfg)
    mlflow_logger.start_run()
    mlflow_logger.log_params(cfg)
    mlflow_logger.set_tags({
        "project": cfg["project"]["name"],
        "pipeline": pipeline_name,
        "task": task_type,
        "dataset": cfg["data"].get("dataset_type", "how2sign"),
    })

    trainer = Trainer(
        model=model,
        optimizer=optimizer,
        train_loader=train_loader,
        val_loader=val_loader,
        device=device,
        output_dir=output_dir,
        mlflow_logger=mlflow_logger,
        task_type=task_type,
        scheduler=scheduler,
        early_stopping_patience=cfg["train"].get("early_stopping_patience", 0),
    )

    trainer.fit(cfg["train"]["epochs"])
    mlflow_logger.end_run()


if __name__ == "__main__":
    main()
