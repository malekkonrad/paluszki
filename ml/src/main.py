import argparse

import pandas as pd
import torch
from torch.utils.data import DataLoader, random_split

from src.data.collate import collate_fn
from src.data.how2sign_dataset import How2SignDataset
from src.data.tokenizer import SimpleTokenizer
from src.registry import PIPELINE_REGISTRY
from src.tracking.mlflow_logger import MLFlowLogger
from src.training.trainer import Trainer
from src.utils.config import ensure_dir, load_config
from src.utils.seed import set_seed


def parse_args():
    parser = argparse.ArgumentParser(description="Train sign-language translation model.")
    parser.add_argument(
        "--config",
        type=str,
        default="configs/base.yaml",
        help="Path to training config yaml file.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    cfg = load_config(args.config)
    set_seed(cfg["project"]["seed"])
    csv_separator = cfg["data"].get("csv_separator", ",")
    data_cfg = cfg["data"]
    has_explicit_train_val = "train_csv_path" in data_cfg and "val_csv_path" in data_cfg
    has_legacy_split = "csv_path" in data_cfg and "train_split" in data_cfg

    if not has_explicit_train_val and not has_legacy_split:
        raise ValueError(
            "Config data section must define either "
            "train_csv_path+val_csv_path (recommended) or csv_path+train_split (legacy)."
        )

    device = cfg["train"]["device"]
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"

    output_dir = ensure_dir(cfg["project"]["output_dir"])
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
    dataset_kwargs = {
        "tokenizer": tokenizer,
        "video_column": data_cfg["video_column"],
        "text_column": text_column,
        "num_frames": data_cfg["num_frames"],
        "image_size": data_cfg["image_size"],
        "max_text_len": data_cfg["max_text_len"],
        "csv_separator": csv_separator,
    }

    if has_explicit_train_val:
        train_ds = How2SignDataset(
            csv_path=train_csv_path,
            video_dir=train_video_dir,
            **dataset_kwargs,
        )
        val_ds = How2SignDataset(
            csv_path=val_csv_path,
            video_dir=val_video_dir,
            **dataset_kwargs,
        )
    else:
        dataset = How2SignDataset(
            csv_path=data_cfg["csv_path"],
            video_dir=data_cfg["video_dir"],
            **dataset_kwargs,
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

    pipeline_name = cfg["model"]["pipeline_name"]
    pipeline_cls = PIPELINE_REGISTRY[pipeline_name]
    model = pipeline_cls(cfg, tokenizer).to(device)

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=cfg["train"]["lr"],
        weight_decay=cfg["train"]["weight_decay"],
    )

    mlflow_logger = MLFlowLogger(cfg)
    mlflow_logger.start_run()
    mlflow_logger.log_params(cfg)
    mlflow_logger.set_tags({
        "project": cfg["project"]["name"],
        "pipeline": pipeline_name,
        "dataset": "how2sign",
    })

    trainer = Trainer(
        model=model,
        optimizer=optimizer,
        train_loader=train_loader,
        val_loader=val_loader,
        device=device,
        output_dir=output_dir,
        mlflow_logger=mlflow_logger,
    )

    trainer.fit(cfg["train"]["epochs"])
    mlflow_logger.end_run()


if __name__ == "__main__":
    main()
