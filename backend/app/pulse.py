"""Pulse (rPPG) service interface + per-(meeting, user) manager.

Mirrors the translation layer but lighter: there's no model and no per-frame
work — the browser forms the ROI mean-color signal and we relay batches of
samples to the ML service, which runs the frequency-domain estimation. Kept as
a separate manager so pulse works independently of the translation toggle.
"""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger("uvicorn.error")


class PulseService(ABC):
    """Abstract interface for a per-signer pulse estimator session."""

    @abstractmethod
    async def process_samples(self, samples: list[list[float]]) -> dict | None:
        """Push ROI mean-color samples; return ``{bpm, confidence}`` or ``None``."""
        ...

    @abstractmethod
    async def initialize(self) -> None:
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        ...


class StubPulseService(PulseService):
    """No-op used when the ML service is disabled."""

    async def process_samples(self, samples: list[list[float]]) -> dict | None:
        return None

    async def initialize(self) -> None:
        logger.info("[PulseStub] Initialized (stub — no ML service)")

    async def shutdown(self) -> None:
        logger.info("[PulseStub] Shut down")


class PulseManager:
    """Manages PulseService instances per (meeting, user). One global instance."""

    def __init__(self):
        self._services: dict[tuple[str, int], PulseService] = {}
        self._factory: type[PulseService] = StubPulseService

    def set_factory(self, factory: type[PulseService]) -> None:
        self._factory = factory

    async def register(self, meeting_code: str, user_id: int) -> PulseService:
        key = (meeting_code, user_id)
        if key in self._services:
            return self._services[key]
        service = self._factory()
        await service.initialize()
        self._services[key] = service
        logger.info(f"[PulseManager] Registered service for {key}")
        return service

    async def get_or_register(self, meeting_code: str, user_id: int) -> PulseService:
        existing = self.get(meeting_code, user_id)
        if existing is not None:
            return existing
        return await self.register(meeting_code, user_id)

    def get(self, meeting_code: str, user_id: int) -> PulseService | None:
        return self._services.get((meeting_code, user_id))

    async def unregister(self, meeting_code: str, user_id: int) -> None:
        service = self._services.pop((meeting_code, user_id), None)
        if service is not None:
            await service.shutdown()
            logger.info(f"[PulseManager] Unregistered service for {(meeting_code, user_id)}")

    async def unregister_meeting(self, meeting_code: str) -> None:
        for code, user_id in [k for k in self._services if k[0] == meeting_code]:
            await self.unregister(code, user_id)

    async def shutdown_all(self) -> None:
        for code, user_id in list(self._services.keys()):
            await self.unregister(code, user_id)


# Global singleton — same pattern as translation_manager / connection_manager
pulse_manager = PulseManager()
