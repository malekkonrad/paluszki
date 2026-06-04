"""Top-K buffer accumulating classified segments until a flush trigger fires.

Flush triggers:
- buffer reaches ``max_segments`` entries, or
- ``flush_pause_ms`` milliseconds elapse with no new push.

The pause-based trigger needs the caller to periodically call
``should_flush(now)``; the session does this on every incoming frame and
on explicit ``tick()`` calls.
"""

from __future__ import annotations

from typing import List

from src.serve.schemas import ClassifierOutput


class TopKBuffer:
    def __init__(self, max_segments: int = 8, flush_pause_ms: int = 1500):
        self.max_segments = max_segments
        self.flush_pause_ms = flush_pause_ms
        self._entries: List[ClassifierOutput] = []
        self._last_push_ts: float = 0.0

    def push(self, sign: ClassifierOutput, ts: float) -> None:
        self._entries.append(sign)
        self._last_push_ts = ts

    def __len__(self) -> int:
        return len(self._entries)

    def is_empty(self) -> bool:
        return not self._entries

    def should_flush(self, now: float) -> bool:
        if not self._entries:
            return False
        if len(self._entries) >= self.max_segments:
            return True
        elapsed_ms = (now - self._last_push_ts) * 1000.0
        return elapsed_ms >= self.flush_pause_ms

    def flush(self) -> List[ClassifierOutput]:
        out = self._entries
        self._entries = []
        return out
