"""Top-K buffer holding the signs of the sentence being built.

The session translates the buffer's *snapshot* after every accepted sign
(incremental sentence updates), so the buffer is not cleared per flush —
it represents "the current sentence so far". It is cleared when:
- ``max_segments`` is reached (sentence committed, next sign starts fresh), or
- ``flush_pause_ms`` milliseconds pass with no new sign (signer went idle;
  the session's ``tick()`` polls ``should_reset(now)`` for this).
"""

from __future__ import annotations

from typing import List

from src.serve.schemas import ClassifierOutput


class TopKBuffer:
    def __init__(self, max_segments: int = 8, flush_pause_ms: int = 15000):
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

    def snapshot(self) -> List[ClassifierOutput]:
        """Current sentence contents, without clearing."""
        return list(self._entries)

    def is_full(self) -> bool:
        return len(self._entries) >= self.max_segments

    def should_reset(self, now: float) -> bool:
        """True when the signer has been idle long enough to close the
        sentence — the next sign starts a fresh one."""
        if not self._entries:
            return False
        elapsed_ms = (now - self._last_push_ts) * 1000.0
        return elapsed_ms >= self.flush_pause_ms

    def flush(self) -> List[ClassifierOutput]:
        out = self._entries
        self._entries = []
        return out
