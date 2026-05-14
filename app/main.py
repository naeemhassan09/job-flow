from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import auth as auth_lib
from app.api import (
    applications,
    auth as auth_api,
    captures,
    discovery,
    health,
    job_actions,
    metrics,
    settings as settings_api,
    usage,
)
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
        allow_credentials=True,  # cookies for session auth
    )

    @app.middleware("http")
    async def session_gate(request: Request, call_next):
        """Session-cookie gate for /ui and /api.

        Whitelist: healthz, metrics, captures (bearer-token auth),
        auth API, login page, OpenAPI docs.
        """
        path = request.url.path
        if any(path.startswith(p) for p in auth_lib.WHITELIST_PREFIXES):
            return await call_next(request)
        # Static asset bundles for the login page need to load before auth.
        if path.startswith("/ui/") and any(
            path.endswith(s) for s in ("login.css", "login.js", "styles.css")
        ):
            return await call_next(request)

        if not (path.startswith("/api/") or path.startswith("/ui/") or path == "/"):
            return await call_next(request)

        token = request.cookies.get(auth_lib.SESSION_COOKIE)
        user = await auth_lib.verify_session(token) if token else None
        if user is not None:
            return await call_next(request)

        # Unauthed UI requests → redirect to login.
        if path == "/" or path.startswith("/ui/"):
            next_url = request.url.path
            if request.url.query:
                next_url += f"?{request.url.query}"
            return RedirectResponse(url=f"/ui/login.html?next={next_url}", status_code=302)

        # Unauthed API requests → 401 JSON.
        return JSONResponse(
            status_code=401,
            content={"detail": "not authenticated"},
        )

    app.include_router(health.router)
    app.include_router(metrics.router)
    app.include_router(auth_api.router)
    app.include_router(applications.router)
    app.include_router(discovery.router)
    app.include_router(captures.router)
    app.include_router(job_actions.router)
    app.include_router(usage.router)
    app.include_router(settings_api.router)

    app.mount("/ui", StaticFiles(directory=STATIC_DIR, html=True), name="ui")

    @app.get("/")
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/ui/")

    return app


app = create_app()
