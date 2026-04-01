from sacrebleu.metrics import BLEU as SacreBLEU
import jiwer
import torch


def compute_bleu4(hypotheses: list[str], references: list[str]) -> float:
    """Returns BLEU-4 score (0-100)."""
    bleu = SacreBLEU(effective_order=True)
    return bleu.corpus_score(hypotheses, [references]).score


def compute_wer(hypotheses: list[str], references: list[str]) -> float:
    """Returns Word Error Rate as percentage (0-100)."""
    return jiwer.wer(references, hypotheses) * 100


def compute_accuracy(logits: torch.Tensor, labels: torch.Tensor) -> float:
    """Top-1 accuracy as percentage (0-100)."""
    preds = logits.argmax(dim=-1)
    return (preds == labels).float().mean().item() * 100


def compute_top_k_accuracy(logits: torch.Tensor, labels: torch.Tensor, k: int = 5) -> float:
    """Top-k accuracy as percentage (0-100)."""
    if logits.size(-1) < k:
        k = logits.size(-1)
    _, top_k_preds = logits.topk(k, dim=-1)
    correct = top_k_preds.eq(labels.unsqueeze(-1)).any(dim=-1)
    return correct.float().mean().item() * 100
