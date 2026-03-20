from pathlib import Path
import torch


class Trainer:
    def __init__(
        self,
        model,
        optimizer,
        train_loader,
        val_loader,
        device,
        output_dir,
        mlflow_logger=None,
    ):
        self.model = model
        self.optimizer = optimizer
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.device = device
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.mlflow_logger = mlflow_logger
        self.best_val_loss = float("inf")

    def _move_batch_to_device(self, batch):
        batch["frames"] = batch["frames"].to(self.device)
        batch["tokens"] = batch["tokens"].to(self.device)
        return batch

    def train_one_epoch(self):
        self.model.train()
        total_loss = 0.0

        for batch in self.train_loader:
            batch = self._move_batch_to_device(batch)

            self.optimizer.zero_grad()
            outputs = self.model(batch)
            loss_dict = self.model.compute_loss(batch, outputs)
            loss = loss_dict["loss"]

            loss.backward()
            self.optimizer.step()

            total_loss += loss.item()

        return {
            "train_loss": total_loss / len(self.train_loader)
        }

    @torch.no_grad()
    def validate(self):
        self.model.eval()
        total_loss = 0.0

        for batch in self.val_loader:
            batch = self._move_batch_to_device(batch)

            outputs = self.model(batch)
            loss_dict = self.model.compute_loss(batch, outputs)
            loss = loss_dict["loss"]

            total_loss += loss.item()

        return {
            "val_loss": total_loss / len(self.val_loader)
        }

    def save_checkpoint(self, name):
        path = self.output_dir / name
        torch.save(self.model.state_dict(), path)
        return str(path)

    def fit(self, epochs):
        for epoch in range(epochs):
            train_metrics = self.train_one_epoch()
            val_metrics = self.validate()

            print(
                f"Epoch {epoch + 1}/{epochs} | "
                f"train_loss={train_metrics['train_loss']:.4f} | "
                f"val_loss={val_metrics['val_loss']:.4f}"
            )

            if self.mlflow_logger:
                self.mlflow_logger.log_metrics(train_metrics, step=epoch)
                self.mlflow_logger.log_metrics(val_metrics, step=epoch)

            if val_metrics["val_loss"] < self.best_val_loss:
                self.best_val_loss = val_metrics["val_loss"]
                ckpt_path = self.save_checkpoint("best_model.pt")
                print(f"Saved best checkpoint: {ckpt_path}")
                if self.mlflow_logger:
                    self.mlflow_logger.log_artifact(ckpt_path)

        last_ckpt = self.save_checkpoint("last_model.pt")
        if self.mlflow_logger:
            self.mlflow_logger.log_artifact(last_ckpt)