"""Offline sanity check for the rPPG estimator (analog of VPG_przyklad_2.m).

Reads a video, forms the rPPG signal the same way the browser will (mean R,G,B
over a face ROI per frame), feeds it to :class:`PulseEstimator`, and prints the
estimated pulse. Use a clip of a fairly still face in decent light.

    uv run scripts/test_pulse_estimator.py --video clip.mp4
    uv run scripts/test_pulse_estimator.py --video clip.mp4 --roi 0.35 0.25 0.30 0.30

``--roi cx_frac cy_frac w_frac h_frac`` places the ROI box (fractions of frame);
default is a central forehead/cheek box, matching the frontend's fixed ROI.
"""

from __future__ import annotations

import argparse

import cv2
import numpy as np

from src.pulse import PulseEstimator


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument(
        "--roi", type=float, nargs=4, default=[0.35, 0.20, 0.30, 0.30],
        metavar=("X", "Y", "W", "H"),
        help="ROI box as fractions of the frame (top-left x, y, width, height)",
    )
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise SystemExit(f"cannot open {args.video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    fx, fy, fw, fh = args.roi

    estimator = PulseEstimator()
    n = 0
    last = None
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        h, w = frame.shape[:2]
        x0, y0 = int(fx * w), int(fy * h)
        x1, y1 = int((fx + fw) * w), int((fy + fh) * h)
        roi = frame[y0:y1, x0:x1]  # BGR
        b, g, r = roi.reshape(-1, 3).mean(axis=0)
        ts = n / fps
        estimator.add_samples([[ts, float(r), float(g), float(b)]])
        n += 1
        if n % int(fps) == 0:  # re-estimate once per simulated second
            last = estimator.estimate()
            if last is not None:
                print(
                    f"t={ts:5.1f}s  bpm={last.bpm:6.1f}  "
                    f"conf={last.confidence:.3f}  fs={last.fs:.1f}  n={last.n_samples}"
                )
    cap.release()

    if last is None:
        print("No estimate — clip too short (need ~6 s) or ROI off the skin.")
    else:
        print(f"\nFinal: {last.bpm:.1f} bpm (confidence {last.confidence:.3f})")


if __name__ == "__main__":
    main()
