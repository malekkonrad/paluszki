import logging
from abc import ABC, abstractmethod

from app.schemas.translation import TranslationTask, TranslationResult

logger = logging.getLogger("uvicorn.error")


class TranslationService(ABC):
    """
    Abstract interface for sign language translation.
    Implement this class with your actual model (e.g. MediaPipe, custom CNN).
    """

    @abstractmethod
    async def process_frame(self, task: TranslationTask) -> TranslationResult:
        """Process a single video frame and return the translation result."""
        ...

    async def tick(self, task: TranslationTask) -> TranslationResult:
        """Periodic poke with no new frame, so pause-based flushing can fire.

        Default: no-op (returns an empty result). Stateful services override."""
        return TranslationResult(
            meeting_code=task.meeting_code, user_id=task.user_id, text=None
        )

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the model (load weights, etc.)"""
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Clean up resources."""
        ...


class StubTranslationService(TranslationService):
    """
    Stub implementation that returns empty results.
    Replace with actual model implementation.
    """

    async def process_frame(self, task: TranslationTask) -> TranslationResult:
        logger.debug(f"[TranslationStub] Processing frame for user {task.user_id} in meeting {task.meeting_code}")
        return TranslationResult(
            meeting_code=task.meeting_code,
            user_id=task.user_id,
            gesture_label=None,
            confidence=0.0,
            text=None,
            overlay_frame=None,
        )

    async def initialize(self) -> None:
        logger.info("[TranslationStub] Initialized (stub — no real model loaded)")

    async def shutdown(self) -> None:
        logger.info("[TranslationStub] Shut down")


class TranslationManager:
    """
    Manages TranslationService instances per (meeting, user) — each user
    streams their own video, so each gets an independent stateful pipeline.
    Similar pattern to DatabaseSessionManager — one global instance.

    Usage:
        service = await translation_manager.get_or_register(meeting_code, user_id)
        result = await service.process_frame(task)
        await translation_manager.unregister(meeting_code, user_id)   # on leave
        await translation_manager.unregister_meeting(meeting_code)    # on end
    """

    def __init__(self):
        self._services: dict[tuple[str, int], TranslationService] = {}
        self._factory: type[TranslationService] = StubTranslationService

    def set_factory(self, factory: type[TranslationService]) -> None:
        """Set the TranslationService class to instantiate for new sessions."""
        self._factory = factory

    async def register(
        self, meeting_code: str, user_id: int, speaker_name: str | None = None
    ) -> TranslationService:
        """Create and initialize a TranslationService for a (meeting, user)."""
        key = (meeting_code, user_id)
        if key in self._services:
            return self._services[key]
        service = self._factory()
        # Forwarded to the ML session's LLM prompt (gender agreement);
        # the stub implementation simply ignores it.
        service.speaker_name = speaker_name
        await service.initialize()
        self._services[key] = service
        logger.info(f"[TranslationManager] Registered service for {key}")
        return service

    async def get_or_register(
        self, meeting_code: str, user_id: int, speaker_name: str | None = None
    ) -> TranslationService:
        """Return the existing service or create one if absent."""
        existing = self.get(meeting_code, user_id)
        if existing is not None:
            return existing
        return await self.register(meeting_code, user_id, speaker_name)

    def get(self, meeting_code: str, user_id: int) -> TranslationService | None:
        """Get the service for a (meeting, user), or None if not registered."""
        return self._services.get((meeting_code, user_id))

    async def unregister(self, meeting_code: str, user_id: int) -> None:
        """Shut down and remove the service for a (meeting, user)."""
        service = self._services.pop((meeting_code, user_id), None)
        if service is not None:
            await service.shutdown()
            logger.info(f"[TranslationManager] Unregistered service for {(meeting_code, user_id)}")

    async def unregister_meeting(self, meeting_code: str) -> None:
        """Shut down all sessions belonging to a meeting (last user left)."""
        for code, user_id in [k for k in self._services if k[0] == meeting_code]:
            await self.unregister(code, user_id)

    async def shutdown_all(self) -> None:
        """Shut down all active services. Called during app shutdown."""
        for code, user_id in list(self._services.keys()):
            await self.unregister(code, user_id)


# Global singleton — same pattern as sessionmanager / connection_manager
translation_manager = TranslationManager()
