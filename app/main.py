from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api import applications, captures, discovery, health, job_actions, metrics, usage
from app.config import get_settings
from app.observability import log

log.configure()

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(title="CareerOS AI", version="0.1.0")

    settings = get_settings()
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=r"^chrome-extension://[a-z]+$",
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        allow_credentials=False,
    )

    app.include_router(health.router)
    app.include_router(metrics.router)
    app.include_router(applications.router)
    app.include_router(discovery.router)
    app.include_router(captures.router)
    app.include_router(job_actions.router)
    app.include_router(usage.router)

    # Inbox UI — single-page HTML served from /ui.
    app.mount("/ui", StaticFiles(directory=STATIC_DIR, html=True), name="ui")

    @app.get("/")
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/ui/")

    return app


app = create_app()
