import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.config import settings
from app.database import sessionmanager
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
        from app.translation_real import SignTranslationService

        translation_manager.set_factory(SignTranslationService)
        logger.info("[lifespan] Sign-translation factory enabled (real pipeline)")
    else:
        logger.info("[lifespan] Translation disabled — using stub (set PALUSZKI_TRANSLATION_ENABLED=1 to enable)")

    yield

    await translation_manager.shutdown_all()
    if sessionmanager.engine is not None:
        await sessionmanager.close()
