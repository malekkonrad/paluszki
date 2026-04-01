from pathlib import Path
import torch

from src.evaluation.metrics import (
    compute_accuracy,
    compute_bleu4,
    compute_top_k_accuracy,
    compute_wer,
)


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
        max_eval_samples=32,
        task_type="translation",
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
        self.max_eval_samples = max_eval_samples
        self.task_type = task_type

    def _move_batch_to_device(self, batch):
        batch["frames"] = batch["frames"].to(self.device)
        if "tokens" in batch:
            batch["tokens"] = batch["tokens"].to(self.device)
        if "labels" in batch:
            batch["labels"] = batch["labels"].to(self.device)
        return batch

    def _compute_grad_norm(self) -> float:
        total_norm = 0.0
        for p in self.model.parameters():
            if p.grad is not None:
                total_norm += p.grad.data.norm(2).item() ** 2
        return total_norm ** 0.5

    def train_one_epoch(self):
        self.model.train()
        total_loss = 0.0
        total_grad_norm = 0.0

        for batch in self.train_loader:
            batch = self._move_batch_to_device(batch)

            self.optimizer.zero_grad()
            outputs = self.model(batch)
            loss_dict = self.model.compute_loss(batch, outputs)
            loss = loss_dict["loss"]

            loss.backward()
            total_grad_norm += self._compute_grad_norm()
            self.optimizer.step()

            total_loss += loss.item()

        n = len(self.train_loader)
        return {
            "train_loss": total_loss / n,
            "train_grad_norm": total_grad_norm / n,
        }

    @torch.no_grad()
    def _validate_translation(self):
        self.model.eval()
        total_loss = 0.0
        hypotheses = []
        references = []

        for batch in self.val_loader:
            batch = self._move_batch_to_device(batch)

            outputs = self.model(batch)
            loss_dict = self.model.compute_loss(batch, outputs)
            total_loss += loss_dict["loss"].item()

            if len(hypotheses) < self.max_eval_samples:
                frames = batch["frames"]
                tokens = batch["tokens"]
                remaining = self.max_eval_samples - len(hypotheses)
                for i in range(min(frames.size(0), remaining)):
                    pred_ids = self.model.greedy_decode(frames[i])
                    pred_text = self.model.tokenizer.decode(pred_ids)
                    ref_text = self.model.tokenizer.decode(tokens[i].tolist())
                    hypotheses.append(pred_text)
                    references.append(ref_text)

        metrics = {"val_loss": total_loss / len(self.val_loader)}

        if hypotheses:
            metrics["val_bleu4"] = compute_bleu4(hypotheses, references)
            metrics["val_wer"] = compute_wer(hypotheses, references)

        return metrics

    @torch.no_grad()
    def _validate_classification(self):
        self.model.eval()
        total_loss = 0.0
        all_logits = []
        all_labels = []

        for batch in self.val_loader:
            batch = self._move_batch_to_device(batch)

            outputs = self.model(batch)
            loss_dict = self.model.compute_loss(batch, outputs)
            total_loss += loss_dict["loss"].item()

            all_logits.append(outputs["logits"].cpu())
            all_labels.append(batch["labels"].cpu())

        all_logits = torch.cat(all_logits)
        all_labels = torch.cat(all_labels)

        metrics = {
            "val_loss": total_loss / len(self.val_loader),
            "val_acc": compute_accuracy(all_logits, all_labels),
            "val_top5_acc": compute_top_k_accuracy(all_logits, all_labels, k=5),
        }
        return metrics

    def validate(self):
        if self.task_type == "classification":
            return self._validate_classification()
        return self._validate_translation()

    def save_checkpoint(self, name):
        path = self.output_dir / name
        torch.save(self.model.state_dict(), path)
        return str(path)

    def _format_epoch_line(self, epoch, epochs, train_metrics, val_metrics):
        base = (
            f"Epoch {epoch + 1}/{epochs} | "
            f"train_loss={train_metrics['train_loss']:.4f} | "
            f"val_loss={val_metrics['val_loss']:.4f}"
        )
        if self.task_type == "classification":
            return (
                f"{base} | "
                f"val_acc={val_metrics.get('val_acc', 0):.2f}% | "
                f"val_top5={val_metrics.get('val_top5_acc', 0):.2f}%"
            )
        return (
            f"{base} | "
            f"val_bleu4={val_metrics.get('val_bleu4', 0):.2f} | "
            f"val_wer={val_metrics.get('val_wer', 0):.2f}%"
        )

    def fit(self, epochs):
        for epoch in range(epochs):
            train_metrics = self.train_one_epoch()
            val_metrics = self.validate()

            print(self._format_epoch_line(epoch, epochs, train_metrics, val_metrics))

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
