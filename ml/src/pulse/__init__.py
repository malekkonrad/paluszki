"""Remote photoplethysmography (rPPG) — contact-free pulse estimation.

The browser forms the raw signal (per-frame mean R,G,B over a face ROI) at
the camera's native frame rate and streams compact ``(ts, r, g, b)`` samples;
this package does the actual estimation (the algorithm from the PULS lab:
detrend → projection/bandpass → FFT → peak → bpm). Pure numpy, no torch /
MediaPipe — a pulse session is cheap.
"""

from src.pulse.estimator import PulseEstimator, PulseResult

__all__ = ["PulseEstimator", "PulseResult"]
