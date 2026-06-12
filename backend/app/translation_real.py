"""HTTP client to the ml/ sign-translation service.

The heavy pipeline (torch + MediaPipe + the classifier) runs as a separate
service — ``ml/src/serve/http_app.py`` — so the backend just *queries* it
instead of importing torch in-process. This keeps the backend light and lets
the model restart / move to a GPU box independently (same pattern as Ollama).

The translation pipeline is stateful per signer, so we create one remote
session per ``SignTranslationService`` instance (i.e. per meeting+user) and
address it by id.

Enable with ``PALUSZKI_TRANSLATION_ENABLED=1`` (see app/lifespan.py).
Point at the service with ``PALUSZKI_ML_SERVICE_URL`` (default
``http://localhost:8001``).
"""

from __future__ import annotations

import logging
import os

import httpx

from app.schemas.translation import TranslationResult, TranslationTask
from app.translation import TranslationService

logger = logging.getLogger("uvicorn.error")

_SERVICE_URL = os.getenv("PALUSZKI_ML_SERVICE_URL", "http://localhost:8001")
# Generous: creating a session loads the model, and an LLM flush (Gemma on
# CPU) can take a few seconds.
_TIMEOUT = httpx.Timeout(120.0)


class SignTranslationService(TranslationService):
    """Thin HTTP client owning one remote pipeline session."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(base_url=_SERVICE_URL, timeout=_TIMEOUT)
        self._session_id: str | None = None

    async def initialize(self) -> None:
        try:
            # speaker_name is set by the TranslationManager before initialize;
            # the ML service feeds it to the LLM prompt for gender agreement.
            payload = {"speaker_name": getattr(self, "speaker_name", None)}
            resp = await self._client.post("/sessions", json=payload)
            resp.raise_for_status()
            self._session_id = resp.json()["session_id"]
        except Exception as exc:  # noqa: BLE001 — surface a clear failure
            logger.error(
                f"[SignTranslation] Cannot reach ML service at {_SERVICE_URL}: {exc}"
            )
            raise RuntimeError(f"ML translation service unavailable: {exc}") from exc
        logger.info(
            f"[SignTranslation] Session {self._session_id} ready via {_SERVICE_URL}"
        )

    async def process_frame(self, task: TranslationTask) -> TranslationResult:
        if self._session_id is None:
            return self._empty(task)
        try:
            resp = await self._client.post(
                f"/sessions/{self._session_id}/frame",
                content=task.frame_data,
                headers={"content-type": "application/octet-stream"},
            )
            if resp.status_code != 200:
                return self._empty(task)
            return self._map(task, resp.json())
        except httpx.HTTPError as exc:
            logger.warning(f"[SignTranslation] frame request failed: {exc}")
            return self._empty(task)

    async def tick(self, task: TranslationTask) -> TranslationResult:
        if self._session_id is None:
            return self._empty(task)
        try:
            resp = await self._client.post(f"/sessions/{self._session_id}/tick")
            if resp.status_code != 200:
                return self._empty(task)
            return self._map(task, resp.json())
        except httpx.HTTPError as exc:
            logger.warning(f"[SignTranslation] tick request failed: {exc}")
            return self._empty(task)

    async def shutdown(self) -> None:
        try:
            if self._session_id is not None:
                await self._client.delete(f"/sessions/{self._session_id}")
        except httpx.HTTPError:
            pass
        finally:
            await self._client.aclose()
            self._session_id = None
        logger.info("[SignTranslation] Session closed")

    @staticmethod
    def _empty(task: TranslationTask) -> TranslationResult:
        return TranslationResult(
            meeting_code=task.meeting_code, user_id=task.user_id, text=None
        )

    @staticmethod
    def _map(task: TranslationTask, data: dict) -> TranslationResult:
        return TranslationResult(
            meeting_code=task.meeting_code,
            user_id=task.user_id,
            gesture_label=data.get("gestureLabel"),
            confidence=data.get("confidence") or 0.0,
            gesture_accepted=data.get("gestureAccepted"),
            text=data.get("text"),
        )
