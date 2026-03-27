from sacrebleu.metrics import BLEU as SacreBLEU
import jiwer


def compute_bleu4(hypotheses: list[str], references: list[str]) -> float:
    """Returns BLEU-4 score (0-100)."""
    bleu = SacreBLEU(effective_order=True)
    return bleu.corpus_score(hypotheses, [references]).score


def compute_wer(hypotheses: list[str], references: list[str]) -> float:
    """Returns Word Error Rate as percentage (0-100)."""
    return jiwer.wer(references, hypotheses) * 100
