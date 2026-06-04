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
import os
import uuid
from typing import Dict, Optional

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from src.serve import TranslationSession, build_session_from_config

_CONFIG_PATH = os.getenv("PALUSZKI_SERVE_CONFIG", "configs/serve.yaml")

app = FastAPI(title="Paluszki sign-translation service")

# session_id -> session, plus a per-session lock (the session is not safe for
# concurrent frame/tick calls).
_sessions: Dict[str, TranslationSession] = {}
_locks: Dict[str, asyncio.Lock] = {}


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
    return CreateSessionResponse(session_id=session_id)


@app.post("/sessions/{session_id}/frame", response_model=TranslationResponse)
async def push_frame(session_id: str, request: Request) -> TranslationResponse:
    session = _get_session(session_id)
    raw = await request.body()
    bgr = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if bgr is None:
        return TranslationResponse()
    async with _locks[session_id]:
        result = await session.push_frame(bgr)
    return _to_response(result)


@app.post("/sessions/{session_id}/tick", response_model=TranslationResponse)
async def tick(session_id: str) -> TranslationResponse:
    session = _get_session(session_id)
    async with _locks[session_id]:
        result = await session.tick()
    return _to_response(result)


@app.delete("/sessions/{session_id}")
async def close_session(session_id: str) -> dict:
    session = _sessions.pop(session_id, None)
    _locks.pop(session_id, None)
    if session is not None:
        await session.aclose()
    return {"status": "closed"}
