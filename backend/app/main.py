import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse

from app.docs import tags_metadata
from app.lifespan import lifespan
from app.routes import router

description = f'''
**Build from:** {os.getenv('BUILD_TIME', "unknown")} rev. {os.getenv("CI_COMMIT_SHORT_SHA", "unknown")}.
'''

app = FastAPI(
    lifespan=lifespan,
    title="MeetFlow backend",
    openapi_tags=tags_metadata,
    description=description,
)

# CORS — allow frontend dev server (localhost + any device on the LAN).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "https://paluszki-front.ivk.pl",
    ],
    # Private-network origins (other computers/phones on the same Wi-Fi) on the
    # frontend dev ports, so they can reach this backend.
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+):(3000|5173|5174)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root():
    response = RedirectResponse(url="/docs")
    return response


@app.get("/healthz", tags=["Health"])
async def healthz():
    return {"status": "ok"}
