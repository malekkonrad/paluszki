"""rPPG pulse estimation from a stream of ROI mean-color samples.

Implements the pipeline from the PULS / videoplethysmography lab, adapted for
a live stream where the *signal forming* step (averaging skin pixels in a face
ROI) happens client-side and we receive ``(ts, r, g, b)`` samples:

    samples → uniform resample → POS projection → detrend → windowed FFT
            → peak in the 48-180 bpm band → bpm + SNR confidence

Why POS (Wang et al. 2017, *Algorithmic Principles of Remote PPG*) rather than
the plain green channel from the lab's first part: in a video call the head
moves, and POS is markedly more motion-robust than a single channel while
staying a few lines of numpy (no training, no extra deps).

The estimate is windowed: with no signal yet it returns ``None``; a stable read
needs ~6 s of samples (the lab uses ≥1024 samples ≈ 17 s @ 60 Hz). This is
inherent to frequency-domain HR estimation, not a tunable we can shortcut.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass
class PulseResult:
    bpm: float
    confidence: float  # peak power / in-band power, in (0, 1]; higher = cleaner
    fs: float          # effective sampling rate of the analysed window (Hz)
    n_samples: int


class PulseEstimator:
    """Rolling-window rPPG estimator fed by ``(ts, r, g, b)`` samples.

    Stateful per signer (one instance per session). Thread-unsafe; the HTTP
    layer serializes access with a per-session lock.
    """

    def __init__(
        self,
        window_s: float = 12.0,
        min_window_s: float = 6.0,
        min_samples: int = 96,
        min_bpm: float = 48.0,
        max_bpm: float = 180.0,
    ) -> None:
        self.window_s = window_s
        self.min_window_s = min_window_s
        self.min_samples = min_samples
        self.min_hz = min_bpm / 60.0
        self.max_hz = max_bpm / 60.0
        self._ts: deque[float] = deque()
        self._rgb: deque[tuple[float, float, float]] = deque()

    def add_samples(self, samples) -> None:
        """Append ``[(ts, r, g, b), ...]`` and drop anything older than the window."""
        for s in samples:
            ts, r, g, b = float(s[0]), float(s[1]), float(s[2]), float(s[3])
            self._ts.append(ts)
            self._rgb.append((r, g, b))
        self._trim()

    def _trim(self) -> None:
        if not self._ts:
            return
        cutoff = self._ts[-1] - self.window_s
        while len(self._ts) > 1 and self._ts[0] < cutoff:
            self._ts.popleft()
            self._rgb.popleft()

    def estimate(self) -> PulseResult | None:
        n = len(self._ts)
        if n < self.min_samples:
            return None
        ts = np.asarray(self._ts, dtype=np.float64)
        span = ts[-1] - ts[0]
        if span < self.min_window_s:
            return None

        rgb = np.asarray(self._rgb, dtype=np.float64)  # (N, 3)

        # Correct frame-timing jitter: resample onto a uniform grid. The
        # browser's setInterval is not metronome-accurate and the DSP below
        # assumes a constant Fs.
        fs = (n - 1) / span
        t_uniform = np.linspace(ts[0], ts[-1], n)
        rgb_u = np.stack(
            [np.interp(t_uniform, ts, rgb[:, c]) for c in range(3)], axis=1
        )

        sig = self._pos(rgb_u)
        sig = _detrend_linear(sig)
        sig = sig - sig.mean()
        if not np.any(sig):
            return None
        sig = sig * np.hanning(n)

        spec = np.abs(np.fft.rfft(sig)) ** 2
        freqs = np.fft.rfftfreq(n, d=1.0 / fs)
        band = (freqs >= self.min_hz) & (freqs <= self.max_hz)
        if not band.any():
            return None  # Fs too low to even cover the pulse band (Nyquist)

        band_spec = spec[band]
        band_freqs = freqs[band]
        peak = int(np.argmax(band_spec))
        bpm = float(band_freqs[peak] * 60.0)

        total = float(band_spec.sum())
        confidence = float(band_spec[peak] / total) if total > 0 else 0.0
        return PulseResult(bpm=bpm, confidence=confidence, fs=float(fs), n_samples=n)

    @staticmethod
    def _pos(rgb: np.ndarray) -> np.ndarray:
        """POS (plane-orthogonal-to-skin) projection → 1-D pulse signal."""
        mean = rgb.mean(axis=0)
        mean[mean == 0] = 1.0
        cn = rgb / mean  # temporal normalization per channel
        # Projection plane orthogonal to the skin-tone direction.
        s1 = cn[:, 1] - cn[:, 2]                    # G - B
        s2 = -2.0 * cn[:, 0] + cn[:, 1] + cn[:, 2]  # -2R + G + B
        std2 = s2.std()
        alpha = s1.std() / std2 if std2 > 1e-9 else 0.0
        return s1 + alpha * s2


def _detrend_linear(x: np.ndarray) -> np.ndarray:
    """Remove a least-squares linear trend (slow lighting/exposure drift)."""
    n = x.shape[0]
    t = np.arange(n, dtype=np.float64)
    a, b = np.polyfit(t, x, 1)
    return x - (a * t + b)
