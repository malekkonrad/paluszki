"""Bidirectional mapping between gloss strings and integer class IDs."""

import json
from pathlib import Path


class GlossLabelMap:
    """Maps sign-language glosses to integer labels and back.

    Build once from the WLASL JSON (using the first *num_classes* entries)
    and pass the same instance to train / val / test datasets so the mapping
    is consistent.
    """

    def __init__(self, glosses: list[str]):
        self.glosses = list(glosses)
        self.gloss_to_id: dict[str, int] = {g: i for i, g in enumerate(self.glosses)}
        self.id_to_gloss: dict[int, str] = {i: g for i, g in enumerate(self.glosses)}

    # ── Constructors ─────────────────────────────────────────────────

    @classmethod
    def from_wlasl_json(cls, json_path: str | Path, num_classes: int = 100) -> "GlossLabelMap":
        with open(json_path) as f:
            data = json.load(f)
        glosses = [entry["gloss"] for entry in data[:num_classes]]
        return cls(glosses)

    @classmethod
    def load(cls, path: str | Path) -> "GlossLabelMap":
        with open(path) as f:
            glosses = json.load(f)
        return cls(glosses)

    # ── Persistence ──────────────────────────────────────────────────

    def save(self, path: str | Path):
        with open(path, "w") as f:
            json.dump(self.glosses, f)

    # ── Encode / Decode ──────────────────────────────────────────────

    def encode(self, gloss: str) -> int:
        return self.gloss_to_id[gloss]

    def decode(self, label_id: int) -> str:
        return self.id_to_gloss[label_id]

    def __len__(self) -> int:
        return len(self.glosses)

    def __contains__(self, gloss: str) -> bool:
        return gloss in self.gloss_to_id
