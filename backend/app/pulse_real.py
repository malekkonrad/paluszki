"""HTTP client to the ml/ pulse (rPPG) service.

Thin client owning one remote pulse session per (meeting, user), mirroring
``SignTranslationService``. Points at the same ML service as translation
(``PALUSZKI_ML_SERVICE_URL``); the pulse endpoints live under ``/pulse``.
"""

from __future__ import annotations

import logging
import os

import httpx

from app.pulse import PulseService

logger = logging.getLogger("uvicorn.error")

_SERVICE_URL = os.getenv("PALUSZKI_ML_SERVICE_URL", "http://localhost:8001")
_TIMEOUT = httpx.Timeout(15.0)


class RemotePulseService(PulseService):
    """Thin HTTP client owning one remote pulse estimator session."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(base_url=_SERVICE_URL, timeout=_TIMEOUT)
        self._session_id: str | None = None

    async def initialize(self) -> None:
        try:
            resp = await self._client.post("/pulse/sessions")
            resp.raise_for_status()
            self._session_id = resp.json()["session_id"]
        except Exception as exc:  # noqa: BLE001 — surface a clear failure
            logger.error(f"[Pulse] Cannot reach ML service at {_SERVICE_URL}: {exc}")
            raise RuntimeError(f"ML pulse service unavailable: {exc}") from exc
        logger.info(f"[Pulse] Session {self._session_id} ready via {_SERVICE_URL}")

    async def process_samples(self, samples: list[list[float]]) -> dict | None:
        if self._session_id is None or not samples:
            return None
        try:
            resp = await self._client.post(
                f"/pulse/sessions/{self._session_id}/samples",
                json={"samples": samples},
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            if data.get("bpm") is None:
                return None
            return {"bpm": data["bpm"], "confidence": data.get("confidence", 0.0)}
        except httpx.HTTPError as exc:
            logger.warning(f"[Pulse] samples request failed: {exc}")
            return None

    async def shutdown(self) -> None:
        try:
            if self._session_id is not None:
                await self._client.delete(f"/pulse/sessions/{self._session_id}")
        except httpx.HTTPError:
            pass
        finally:
            await self._client.aclose()
            self._session_id = None
        logger.info("[Pulse] Session closed")
