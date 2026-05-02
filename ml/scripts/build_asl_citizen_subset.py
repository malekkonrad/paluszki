"""Build a 100-class conversational subset of ASL Citizen.

Reads ``train.csv`` / ``val.csv`` / ``test.csv``, intersects with a curated
list of conversational glosses, picks the best gloss variant per concept
(by train-sample count), and writes a self-contained subset:

    <dataset>/subset100/
        label_map.json   # final list of 100 gloss strings (= class order)
        train.csv        # filtered to selected glosses
        val.csv
        test.csv
        stats.json       # per-class sample counts (train/val/test)

Run from ``ml/``::

    uv run scripts/build_asl_citizen_subset.py
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd

# ----------------------------------------------------------------------------
# Curated conversational vocabulary
#
# Goal: signs that are useful in a basic video-call demo. We deliberately
# over-specify (~130 candidates) and let the script keep the top 100 that
# actually have the most samples in the dataset — some words may be missing
# or rare in ASL Citizen.
# ----------------------------------------------------------------------------

CURATED_CONCEPTS: list[str] = [
    # Greetings / politeness
    "HELLO", "BYE", "THANKYOU", "SORRY", "PLEASE", "WELCOME",
    # Yes / no / agreement
    "YES", "NO", "MAYBE", "OK",
    # Pronouns
    "ME", "YOU", "HE", "SHE", "WE", "THEY", "MY", "YOUR",
    # People / family
    "FRIEND", "FAMILY", "MOTHER", "FATHER", "BROTHER", "SISTER",
    "BABY", "BOY", "GIRL", "MAN", "WOMAN", "PEOPLE",
    "NAME", "TEACHER", "STUDENT", "DOCTOR",
    # Question words
    "WHAT", "WHERE", "WHEN", "WHO", "WHY", "HOW", "WHICH",
    # Common verbs
    "WANT", "NEED", "LIKE", "LOVE", "HATE",
    "EAT", "DRINK", "SLEEP",
    "GO", "COME", "WAIT", "MEET",
    "WORK", "STUDY", "LEARN", "KNOW", "UNDERSTAND", "REMEMBER", "FORGET",
    "HELP", "STOP", "START", "FINISH",
    "SEE", "HEAR", "SAY", "ASK", "TELL",
    "GIVE", "TAKE", "MAKE", "DO", "HAVE", "BUY",
    "READ", "WRITE", "PLAY", "LIVE", "THINK", "FEEL",
    # Daily life
    "HOME", "SCHOOL", "FOOD", "WATER", "MONEY",
    "CAR", "PHONE", "BOOK", "COMPUTER", "CITY", "COUNTRY",
    # Time
    "TODAY", "TOMORROW", "YESTERDAY", "NOW", "LATER",
    "MORNING", "NIGHT", "DAY", "WEEK", "MONTH", "YEAR", "TIME",
    # Feelings / states
    "HAPPY", "SAD", "TIRED", "HUNGRY", "SICK",
    "GOOD", "BAD", "FINE", "COLD", "HOT",
    "BUSY", "NICE", "BORED", "EXCITED", "ANGRY", "SCARED",
    # Modifiers
    "BIG", "SMALL", "MORE", "LESS", "NEW", "OLD",
    "FAST", "SLOW", "MANY", "FEW",
    # Misc useful
    "AGAIN", "ALL", "EVERYTHING", "ALWAYS", "NEVER",
    "SAME", "DIFFERENT", "EASY", "HARD",
]


# A gloss in ASL Citizen is the concept name optionally followed by digits
# marking a sign variant — e.g. FINE / FINE1 / FINE2 are different signs
# for the same English word. We pick whichever variant has the most train
# samples, so the model doesn't have to disambiguate near-identical labels.
_VARIANT_RE = re.compile(r"^([A-Z]+(?:[ /][A-Z]+)*)(\d*)$")


def _concept_of(gloss: str) -> str | None:
    """Strip numeric variant suffix from a gloss. Returns None on mismatch."""
    m = _VARIANT_RE.match(gloss)
    if not m:
        return None
    return m.group(1)


def select_best_variants(
    train_df: pd.DataFrame,
    concepts: list[str],
    min_train_samples: int,
) -> list[str]:
    """For each concept, pick the gloss variant with the most train samples."""
    train_counts = Counter(train_df["Gloss"].astype(str))

    selected: list[tuple[str, int]] = []  # (chosen_gloss, train_count)
    missing: list[str] = []

    for concept in concepts:
        candidates = [
            (g, c) for g, c in train_counts.items() if _concept_of(g) == concept
        ]
        if not candidates:
            missing.append(concept)
            continue

        best_gloss, best_count = max(candidates, key=lambda x: x[1])
        if best_count < min_train_samples:
            missing.append(f"{concept} (best variant {best_gloss} has only {best_count})")
            continue
        selected.append((best_gloss, best_count))

    if missing:
        print(f"Skipped {len(missing)} concepts with no usable variant:")
        for m in missing:
            print(f"  - {m}")

    selected.sort(key=lambda x: x[1], reverse=True)
    return [g for g, _ in selected]


def build_subset(
    dataset_dir: Path,
    output_dir: Path,
    num_classes: int,
    min_train_samples: int,
):
    train_df = pd.read_csv(dataset_dir / "train.csv")
    val_df = pd.read_csv(dataset_dir / "val.csv")
    test_df = pd.read_csv(dataset_dir / "test.csv")

    chosen = select_best_variants(train_df, CURATED_CONCEPTS, min_train_samples)
    chosen = chosen[:num_classes]

    if len(chosen) < num_classes:
        print(
            f"\n  Only {len(chosen)} concepts met the cutoff "
            f"(wanted {num_classes}). Lower --min-train-samples or "
            f"extend CURATED_CONCEPTS in this script."
        )

    chosen_set = set(chosen)
    train_sub = train_df[train_df["Gloss"].isin(chosen_set)].copy()
    val_sub = val_df[val_df["Gloss"].isin(chosen_set)].copy()
    test_sub = test_df[test_df["Gloss"].isin(chosen_set)].copy()

    train_counts = Counter(train_sub["Gloss"])
    val_counts = Counter(val_sub["Gloss"])
    test_counts = Counter(test_sub["Gloss"])

    stats = {
        gloss: {
            "train": int(train_counts[gloss]),
            "val": int(val_counts[gloss]),
            "test": int(test_counts[gloss]),
        }
        for gloss in chosen
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    train_sub.to_csv(output_dir / "train.csv", index=False)
    val_sub.to_csv(output_dir / "val.csv", index=False)
    test_sub.to_csv(output_dir / "test.csv", index=False)

    with open(output_dir / "label_map.json", "w") as f:
        json.dump(chosen, f, indent=2)
    with open(output_dir / "stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    print(f"\nSelected {len(chosen)} classes — wrote subset to {output_dir}")
    print(f"  train: {len(train_sub)} samples")
    print(f"  val:   {len(val_sub)} samples")
    print(f"  test:  {len(test_sub)} samples")
    print(f"\nPer-class counts (train / val / test):")
    print(f"  {'gloss':<20} {'train':>6} {'val':>6} {'test':>6}")
    print(f"  {'-' * 20} {'-' * 6} {'-' * 6} {'-' * 6}")
    for gloss in chosen:
        s = stats[gloss]
        print(f"  {gloss:<20} {s['train']:>6} {s['val']:>6} {s['test']:>6}")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--dataset-dir",
        type=Path,
        default=Path("datasets/ASL_Citizen"),
        help="Directory containing train.csv / val.csv / test.csv.",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Where to write the subset (default: <dataset-dir>/subset100).",
    )
    p.add_argument("--num-classes", type=int, default=100)
    p.add_argument(
        "--min-train-samples",
        type=int,
        default=10,
        help="Drop concepts whose best variant has fewer than this many train samples.",
    )
    return p.parse_args()


def main():
    args = parse_args()
    output_dir = args.output_dir or (args.dataset_dir / f"subset{args.num_classes}")
    build_subset(
        dataset_dir=args.dataset_dir,
        output_dir=output_dir,
        num_classes=args.num_classes,
        min_train_samples=args.min_train_samples,
    )


if __name__ == "__main__":
    main()
