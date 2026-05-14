from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import applications, captures, discovery, health, metrics
from app.config import get_settings
from app.observability import log

log.configure()


def create_app() -> FastAPI:
    app = FastAPI(title="CareerOS AI", version="0.1.0")

    settings = get_settings()
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    # chrome-extension://* is a literal pattern in browsers; allow via regex too.
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
    return app


app = create_app()
