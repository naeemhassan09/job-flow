from __future__ import annotations

from fastapi import FastAPI

from app.api import applications, health, metrics
from app.observability import log

log.configure()


def create_app() -> FastAPI:
    app = FastAPI(title="CareerOS AI", version="0.1.0")
    app.include_router(health.router)
    app.include_router(metrics.router)
    app.include_router(applications.router)
    return app


app = create_app()
