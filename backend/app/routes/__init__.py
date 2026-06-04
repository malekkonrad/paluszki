from fastapi import APIRouter

from app.routes.auth import router as auth_router
from app.routes.meeting import router as meeting_router
from app.routes.ws import router as ws_router

router = APIRouter()

# HTTP API lives under /api (the frontend's NEXT_PUBLIC_API_BASE_URL default
# is http://localhost:8000/api). The WebSocket route keeps its own /ws path
# (frontend NEXT_PUBLIC_WS_BASE_URL default is ws://localhost:8000/ws).
router.include_router(auth_router, prefix="/api")
router.include_router(meeting_router, prefix="/api")
router.include_router(ws_router)
