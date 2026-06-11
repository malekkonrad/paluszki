import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.config import settings
from app.database import sessionmanager
from app.pulse import pulse_manager
from app.translation import translation_manager

logger = logging.getLogger('uvicorn.error')


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await sessionmanager.init_db()

    if settings.debug:
        logger.critical("DEBUG MODE IS ON")
        logger.critical("Make sure to not use it on production.")
        await sessionmanager.reset_db()

    if os.getenv("PALUSZKI_TRANSLATION_ENABLED") == "1":
        # Real ML pipeline (torch + MediaPipe + Ollama). Imported lazily so
        # the backend still starts without the ML deps when disabled.
        from app.pulse_real import RemotePulseService
        from app.translation_real import SignTranslationService

        translation_manager.set_factory(SignTranslationService)
        pulse_manager.set_factory(RemotePulseService)
        logger.info("[lifespan] Sign-translation + pulse factories enabled (real ML service)")
    else:
        logger.info("[lifespan] ML features disabled — using stubs (set PALUSZKI_TRANSLATION_ENABLED=1 to enable)")

    yield

    await translation_manager.shutdown_all()
    await pulse_manager.shutdown_all()
    if sessionmanager.engine is not None:
        await sessionmanager.close()
