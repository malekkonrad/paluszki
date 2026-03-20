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


def main():
    cfg = load_config("configs/base.yaml")
    set_seed(cfg["project"]["seed"])
    csv_separator = cfg["data"].get("csv_separator", ",")

    device = cfg["train"]["device"]
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"

    output_dir = ensure_dir(cfg["project"]["output_dir"])

    df = pd.read_csv(cfg["data"]["csv_path"], sep=csv_separator)
    texts = df[cfg["data"]["text_column"]].astype(str).tolist()
    tokenizer = SimpleTokenizer(texts)

    dataset = How2SignDataset(
        csv_path=cfg["data"]["csv_path"],
        csv_separator=csv_separator,
        video_dir=cfg["data"]["video_dir"],
        tokenizer=tokenizer,
        video_column=cfg["data"]["video_column"],
        text_column=cfg["data"]["text_column"],
        num_frames=cfg["data"]["num_frames"],
        image_size=cfg["data"]["image_size"],
        max_text_len=cfg["data"]["max_text_len"],
    )

    train_size = int(cfg["data"]["train_split"] * len(dataset))
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
