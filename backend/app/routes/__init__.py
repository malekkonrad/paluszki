from fastapi import APIRouter

from app.routes.auth import router as auth_router
from app.routes.meeting import router as meeting_router
from app.routes.ws import router as ws_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(meeting_router)
router.include_router(ws_router)
