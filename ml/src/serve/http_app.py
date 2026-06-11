"""HTTP wrapper around the sign-translation pipeline.

Runs the heavyweight :mod:`src.serve` ``TranslationSession`` behind a small
FastAPI service so consumers (the backend) can *query* translations over HTTP
instead of importing torch + MediaPipe in-process. Mirrors how the LLM
(Ollama) is already a separate, queried service.

The pipeline is stateful per signer (the segmenter and buffer carry state
across frames), so sessions are created explicitly and addressed by id.

Run from the ``ml/`` root so ``serve.yaml``'s relative paths resolve::

    uv run uvicorn src.serve.http_app:app --port 8001

Config: ``PALUSZKI_SERVE_CONFIG`` (default ``configs/serve.yaml``).
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Dict, Optional

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from src.pulse import PulseEstimator
from src.serve import TranslationSession, build_session_from_config

_CONFIG_PATH = os.getenv("PALUSZKI_SERVE_CONFIG", "configs/serve.yaml")

# Dedicated "paluszki" logger → stderr, so pipeline events (sign accepted /
# dropped, LLM calls + timing, results) show in this service's console.
# Verbosity via PALUSZKI_LOG_LEVEL (INFO default; DEBUG also logs every frame).
_root_logger = logging.getLogger("paluszki")
if not _root_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter("%(asctime)s [%(name)s] %(levelname)s %(message)s", "%H:%M:%S")
    )
    _root_logger.addHandler(_handler)
    _root_logger.propagate = False
_root_logger.setLevel(os.getenv("PALUSZKI_LOG_LEVEL", "INFO").upper())

logger = logging.getLogger("paluszki.serve.http")

app = FastAPI(title="Paluszki sign-translation service")

# session_id -> session, plus a per-session lock (the session is not safe for
# concurrent frame/tick calls).
_sessions: Dict[str, TranslationSession] = {}
_locks: Dict[str, asyncio.Lock] = {}

# Pulse (rPPG) sessions are independent and cheap (pure-numpy DSP, no model),
# so they get their own registry. The browser streams ROI mean-color samples;
# we just do the frequency-domain estimation.
_pulse: Dict[str, PulseEstimator] = {}
_pulse_locks: Dict[str, asyncio.Lock] = {}


class CreateSessionResponse(BaseModel):
    session_id: str


class TranslationResponse(BaseModel):
    text: Optional[str] = None
    gestureLabel: Optional[str] = None
    confidence: float = 0.0


def _to_response(result) -> TranslationResponse:
    if result is None:
        return TranslationResponse()
    gesture_label = None
    confidence = 0.0
    if result.source_signs:
        last = result.source_signs[-1]
        gesture_label = last.top_k[0][0] if last.top_k else None
        confidence = float(last.raw_argmax_conf)
    return TranslationResponse(
        text=result.text, gestureLabel=gesture_label, confidence=confidence
    )


def _get_session(session_id: str) -> TranslationSession:
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return session


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok", "sessions": len(_sessions)}


@app.post("/sessions", response_model=CreateSessionResponse)
async def create_session() -> CreateSessionResponse:
    # Blocking: loads the checkpoint + spins up MediaPipe. Off the event loop.
    session = await asyncio.to_thread(build_session_from_config, _CONFIG_PATH)
    session_id = uuid.uuid4().hex
    _sessions[session_id] = session
    _locks[session_id] = asyncio.Lock()
    logger.info("session created: %s (active=%d)", session_id[:8], len(_sessions))
    return CreateSessionResponse(session_id=session_id)


@app.post("/sessions/{session_id}/frame", response_model=TranslationResponse)
async def push_frame(session_id: str, request: Request) -> TranslationResponse:
    session = _get_session(session_id)
    raw = await request.body()
    logger.debug("[%s] frame %d bytes", session_id[:8], len(raw))
    bgr = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if bgr is None:
        return TranslationResponse()
    async with _locks[session_id]:
        result = await session.push_frame(bgr)
    return _log_result(session_id, _to_response(result))


@app.post("/sessions/{session_id}/tick", response_model=TranslationResponse)
async def tick(session_id: str) -> TranslationResponse:
    session = _get_session(session_id)
    async with _locks[session_id]:
        result = await session.tick()
    return _log_result(session_id, _to_response(result))


def _log_result(session_id: str, resp: TranslationResponse) -> TranslationResponse:
    if resp.text:
        logger.info("[%s] sentence -> %r", session_id[:8], resp.text)
    return resp


@app.delete("/sessions/{session_id}")
async def close_session(session_id: str) -> dict:
    session = _sessions.pop(session_id, None)
    _locks.pop(session_id, None)
    if session is not None:
        await session.aclose()
    logger.info("session closed: %s (active=%d)", session_id[:8], len(_sessions))
    return {"status": "closed"}


# ── Pulse (rPPG) ──────────────────────────────────────────────────────────


class PulseSamplesRequest(BaseModel):
    # Each sample is [ts_seconds, mean_r, mean_g, mean_b] for the face ROI.
    samples: list[list[float]]


class PulseResponse(BaseModel):
    bpm: Optional[float] = None
    confidence: float = 0.0
    fs: float = 0.0


@app.post("/pulse/sessions", response_model=CreateSessionResponse)
async def create_pulse_session() -> CreateSessionResponse:
    session_id = uuid.uuid4().hex
    _pulse[session_id] = PulseEstimator()
    _pulse_locks[session_id] = asyncio.Lock()
    logger.info("pulse session created: %s (active=%d)", session_id[:8], len(_pulse))
    return CreateSessionResponse(session_id=session_id)


@app.post("/pulse/sessions/{session_id}/samples", response_model=PulseResponse)
async def push_pulse_samples(session_id: str, req: PulseSamplesRequest) -> PulseResponse:
    estimator = _pulse.get(session_id)
    if estimator is None:
        raise HTTPException(status_code=404, detail="pulse session not found")
    async with _pulse_locks[session_id]:
        estimator.add_samples(req.samples)
        result = estimator.estimate()
    if result is None:
        return PulseResponse()
    return PulseResponse(bpm=result.bpm, confidence=result.confidence, fs=result.fs)


@app.delete("/pulse/sessions/{session_id}")
async def close_pulse_session(session_id: str) -> dict:
    _pulse.pop(session_id, None)
    _pulse_locks.pop(session_id, None)
    logger.info("pulse session closed: %s (active=%d)", session_id[:8], len(_pulse))
    return {"status": "closed"}
