"""Smoke test: feed a video through TranslationSession and print results.

Simulates a frontend that streams BGR frames at native FPS. Useful for:
- verifying the full pipeline works end-to-end without writing a frontend,
- measuring per-stage latency,
- regressing on motion-segmenter / classifier behavior changes.

Examples:
    # offline (no API calls):
    uv run scripts/test_translation_pipeline.py \\
        --video datasets/ASL_Citizen/videos/9527729417030506-LEARN.mp4 \\
        --llm-type mock

    # against Anthropic (requires ANTHROPIC_API_KEY):
    uv run scripts/test_translation_pipeline.py \\
        --video datasets/ASL_Citizen/videos/9527729417030506-LEARN.mp4

    # multiple clips concatenated (mimics a phrase):
    uv run scripts/test_translation_pipeline.py \\
        --video clip1.mp4 clip2.mp4 clip3.mp4 --llm-type mock
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

# Allow ``uv run scripts/test_translation_pipeline.py`` from the ml/ root —
# without this, sys.path[0] is scripts/ and ``src`` is not importable.
_ML_ROOT = Path(__file__).resolve().parent.parent
if str(_ML_ROOT) not in sys.path:
    sys.path.insert(0, str(_ML_ROOT))

import cv2

from src.serve import build_session_from_config


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/serve.yaml")
    p.add_argument(
        "--video", nargs="+", required=True,
        help="One or more video files; played sequentially as one stream.",
    )
    p.add_argument(
        "--llm-type", default=None,
        help="Override llm.type from the config (e.g. 'mock' for offline run).",
    )
    p.add_argument(
        "--llm-model", default=None,
        help="Override llm.model from the config.",
    )
    p.add_argument(
        "--realtime", action="store_true",
        help="Sleep between frames to mimic real-time stream "
             "(otherwise pushes frames as fast as possible).",
    )
    return p.parse_args()


async def stream_video(session, video_path: str, ts_offset: float, realtime: bool) -> float:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_dt = 1.0 / fps
    print(f"--- {Path(video_path).name}  ({fps:.1f} fps) ---")

    frame_idx = 0
    last_wall = time.monotonic()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            ts = ts_offset + frame_idx * frame_dt

            t0 = time.monotonic()
            result = await session.push_frame(frame, ts=ts)
            stage_ms = (time.monotonic() - t0) * 1000.0

            if result is not None:
                _print_result(result, stage_ms)

            if realtime:
                wait = (last_wall + frame_dt) - time.monotonic()
                if wait > 0:
                    await asyncio.sleep(wait)
                last_wall = time.monotonic()

            frame_idx += 1
    finally:
        cap.release()

    return ts_offset + frame_idx * frame_dt


def _print_result(result, stage_ms: float):
    tops = " | ".join(s.top_k[0][0] for s in result.source_signs)
    confs = " | ".join(f"{s.top_k[0][1]:.2f}" for s in result.source_signs)
    print(
        f"[{result.started_at:6.2f}s → {result.ended_at:6.2f}s] "
        f"({stage_ms:5.0f}ms) "
        f"signs: {tops}\n"
        f"   conf: {confs}\n"
        f"   →  {result.text}"
    )


async def main():
    args = parse_args()

    llm_override = {}
    if args.llm_type is not None:
        llm_override["type"] = args.llm_type
    if args.llm_model is not None:
        llm_override["model"] = args.llm_model

    session = build_session_from_config(
        args.config,
        llm_override=llm_override or None,
    )

    try:
        ts = 0.0
        for path in args.video:
            ts = await stream_video(session, path, ts, args.realtime)
            # 0.5s gap between clips so the segmenter sees a clear pause.
            ts += 0.5

        # Pause-flush is wall-clock based; for an instant simulation we
        # fast-forward by passing a future timestamp to the session tick.
        future_ts = ts + 5.0
        result = await session.tick(ts=future_ts)
        if result is not None:
            print("--- final flush ---")
            _print_result(result, 0.0)
        else:
            # tick() bails if buffer empty; force-flush in case of leftovers.
            result = await session.flush()
            if result is not None:
                print("--- forced final flush ---")
                _print_result(result, 0.0)
    finally:
        await session.aclose()


if __name__ == "__main__":
    asyncio.run(main())
