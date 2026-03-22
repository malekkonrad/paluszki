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
    Manages TranslationService instances per meeting.
    Similar pattern to DatabaseSessionManager — one global instance.

    Usage:
        translation_manager.register(meeting_code)    # on meeting create
        service = translation_manager.get(meeting_code)
        result = await service.process_frame(task)
        translation_manager.unregister(meeting_code)   # on meeting end
    """

    def __init__(self):
        self._services: dict[str, TranslationService] = {}
        self._factory: type[TranslationService] = StubTranslationService

    def set_factory(self, factory: type[TranslationService]) -> None:
        """Set the TranslationService class to instantiate for new meetings."""
        self._factory = factory

    async def register(self, meeting_code: str) -> TranslationService:
        """Create and initialize a TranslationService for a meeting."""
        if meeting_code in self._services:
            return self._services[meeting_code]
        service = self._factory()
        await service.initialize()
        self._services[meeting_code] = service
        logger.info(f"[TranslationManager] Registered service for meeting {meeting_code}")
        return service

    def get(self, meeting_code: str) -> TranslationService | None:
        """Get the TranslationService for a meeting, or None if not registered."""
        return self._services.get(meeting_code)

    async def unregister(self, meeting_code: str) -> None:
        """Shut down and remove the TranslationService for a meeting."""
        service = self._services.pop(meeting_code, None)
        if service is not None:
            await service.shutdown()
            logger.info(f"[TranslationManager] Unregistered service for meeting {meeting_code}")

    async def shutdown_all(self) -> None:
        """Shut down all active services. Called during app shutdown."""
        for code in list(self._services.keys()):
            await self.unregister(code)


# Global singleton — same pattern as sessionmanager / connection_manager
translation_manager = TranslationManager()
