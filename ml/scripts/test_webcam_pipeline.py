"""Webcam smoke test for the live translation pipeline.

Opens the default camera, pushes frames into a ``TranslationSession``, and
draws a debug overlay so you can:

- calibrate ``segmenter.motion_threshold`` (live velocity number visible),
- see when a sign gets segmented (state IDLE/SIGNING/PAUSED + last top-1),
- inspect what the LLM produces from a buffer of multiple signs.

Defaults to ``--llm-type mock`` so it runs offline. Pass ``--llm-type
anthropic`` (with ``ANTHROPIC_API_KEY``) for a real end-to-end test.

Keys (window must be focused):
    q   quit
    f   force-flush whatever's in the buffer through the LLM
    r   reset segmenter + clear buffer (use after a botched attempt)

Examples:
    uv run scripts/test_webcam_pipeline.py
    uv run scripts/test_webcam_pipeline.py --llm-type anthropic --mirror
    uv run scripts/test_webcam_pipeline.py --camera 2 --width 1280 --height 720
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

# Allow ``uv run scripts/test_webcam_pipeline.py`` from the ml/ root —
# without this, sys.path[0] is scripts/ and ``src`` is not importable.
_ML_ROOT = Path(__file__).resolve().parent.parent
if str(_ML_ROOT) not in sys.path:
    sys.path.insert(0, str(_ML_ROOT))

import cv2

from src.serve import build_session_from_config


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/serve.yaml")
    p.add_argument("--camera", type=int, default=0)
    p.add_argument(
        "--llm-type", default=None,
        help="Override llm.type from the config. Omit to use the config's "
             "llm (currently Ollama). Pass 'mock' for an offline run.",
    )
    p.add_argument("--llm-model", default=None)
    p.add_argument(
        "--mirror", action="store_true",
        help="Flip the preview horizontally (selfie view). Does not affect "
             "the keypoint stream — MediaPipe is symmetric enough.",
    )
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--height", type=int, default=480)
    return p.parse_args()


STATE_COLOR = {
    "IDLE":    (180, 180, 180),
    "SIGNING": (60, 220, 60),
    "PAUSED":  (60, 200, 220),
}


def _wrap(text: str, max_chars: int) -> list[str]:
    words = text.split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def draw_overlay(
    frame,
    *,
    state: str,
    velocity: float,
    motion_threshold: float,
    pause_count: int,
    buf_len: int,
    tick_ms: float,
    last_top1: str | None,
    last_conf: float,
    last_result: str | None,
) -> None:
    h, w = frame.shape[:2]

    # Top status strip.
    bar = frame.copy()
    cv2.rectangle(bar, (0, 0), (w, 96), (0, 0, 0), -1)
    cv2.addWeighted(bar, 0.55, frame, 0.45, 0, frame)

    cv2.putText(frame, state, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75,
                STATE_COLOR.get(state, (255, 255, 255)), 2)

    vel_col = (60, 220, 60) if velocity > motion_threshold else (80, 140, 220)
    cv2.putText(frame, f"vel {velocity:.4f} / th {motion_threshold:.4f}",
                (135, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.55, vel_col, 1)
    cv2.putText(frame, f"pause {pause_count}", (420, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 230), 1)
    cv2.putText(frame, f"buf {buf_len}", (540, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 230), 1)

    cv2.putText(frame, f"frame {tick_ms:5.0f}ms", (10, 56),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    if last_top1 is not None:
        cv2.putText(frame, f"last sign: {last_top1}  ({last_conf:.2f})",
                    (10, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (255, 255, 255), 1)

    # Bottom: LLM result + help line.
    help_y = h - 8
    cv2.putText(frame, "q quit  f flush  r reset", (10, help_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

    if last_result:
        max_chars = max(20, w // 14)
        lines = _wrap(last_result, max_chars)[-3:]
        block_h = 26 * len(lines) + 14
        bar = frame.copy()
        cv2.rectangle(bar, (0, h - block_h - 22), (w, h - 18), (0, 0, 0), -1)
        cv2.addWeighted(bar, 0.6, frame, 0.4, 0, frame)
        for i, line in enumerate(lines):
            y = h - block_h - 22 + 24 * (i + 1)
            cv2.putText(frame, line, (10, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (80, 230, 120), 2)


async def run(args) -> None:
    llm_override: dict = {}
    if args.llm_type is not None:
        llm_override["type"] = args.llm_type
    if args.llm_model is not None:
        llm_override["model"] = args.llm_model

    session = build_session_from_config(
        args.config, llm_override=llm_override or None,
    )

    cap = cv2.VideoCapture(args.camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera index {args.camera}")

    last_top1: str | None = None
    last_conf: float = 0.0
    last_result: str | None = None
    prev_buf_len = 0
    motion_threshold = session.segmenter.motion_threshold

    llm = session.postprocessor.llm
    llm_desc = f"{type(llm).__name__}({getattr(llm, 'model', '?')})"
    print(f"camera {args.camera} open. llm={llm_desc}. "
          f"window: q quit / f flush / r reset")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            t0 = time.monotonic()
            ts = time.time()
            result = await session.push_frame(frame, ts=ts)
            tick_ms = (time.monotonic() - t0) * 1000.0

            if result is not None:
                if result.source_signs:
                    last_top1 = result.source_signs[-1].top_k[0][0]
                    last_conf = result.source_signs[-1].top_k[0][1]
                last_result = result.text
                prev_buf_len = 0
                tops = " | ".join(s.top_k[0][0] for s in result.source_signs)
                print(f"[{result.started_at:6.2f}s -> {result.ended_at:6.2f}s] "
                      f"signs: {tops}")
                print(f"   ->  {result.text}")
            else:
                cur = len(session.buffer)
                if cur > prev_buf_len:
                    # A new sign just landed in the buffer.
                    latest = session.buffer._entries[-1]  # debug-only peek
                    last_top1 = latest.top_k[0][0]
                    last_conf = latest.top_k[0][1]
                    print(f"[t={ts:.2f}] sign: {last_top1}  ({last_conf:.2f})")
                prev_buf_len = cur

            # Read segmenter internals for the overlay. Private attrs but
            # we accept that for a debug/calibration script.
            seg = session.segmenter
            display = cv2.flip(frame, 1) if args.mirror else frame
            draw_overlay(
                display,
                state=seg._state,
                velocity=seg._smoothed_vel,
                motion_threshold=motion_threshold,
                pause_count=seg._pause_count,
                buf_len=len(session.buffer),
                tick_ms=tick_ms,
                last_top1=last_top1,
                last_conf=last_conf,
                last_result=last_result,
            )
            cv2.imshow("paluszki -- live", display)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("f"):
                forced = await session.flush()
                if forced is not None:
                    last_result = forced.text
                    prev_buf_len = 0
                    if forced.source_signs:
                        last_top1 = forced.source_signs[-1].top_k[0][0]
                        last_conf = forced.source_signs[-1].top_k[0][1]
                    print(f"[forced flush] -> {forced.text}")
                else:
                    print("[forced flush] buffer empty")
            elif key == ord("r"):
                session.segmenter.reset()
                session.buffer.flush()
                prev_buf_len = 0
                last_top1 = None
                last_result = None
                print("[reset]")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        await session.aclose()


def main() -> None:
    asyncio.run(run(parse_args()))


if __name__ == "__main__":
    main()
