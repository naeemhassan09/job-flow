"""Local single-user auth.

- Password is bcrypt-hashed; the hash lives in app_settings (encrypted
  alongside everything else).
- A signed cookie session is issued on successful login.
- Endpoints under /api and /ui are gated except for an explicit whitelist
  (health, metrics, captures via bearer token, login/logout/init, and the
  login UI page itself).

Bootstrap: if no admin hash exists, the only allowed flow is
POST /api/auth/init {username, password} which sets the credentials.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Final

import bcrypt
from fastapi import HTTPException, Request, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app import settings_store
from app.config import get_settings
from app.observability.log import get_logger

_log = get_logger(__name__)

SESSION_COOKIE: Final = "careeros_session"
SESSION_TTL_SECONDS: Final = 60 * 60 * 24 * 7  # 7 days
_SALT: Final = "careeros.auth.session"

# Setting keys
_KEY_USERNAME = "auth.admin_username"
_KEY_HASH = "auth.admin_password_hash"
_KEY_SESSION_SECRET = "auth.session_secret"


@dataclass(frozen=True)
class SessionUser:
    username: str


async def _session_serializer() -> URLSafeTimedSerializer:
    """Long-lived signing key for session cookies. Stored encrypted alongside
    everything else so containers and local runs share it."""
    secret = await settings_store.get(_KEY_SESSION_SECRET)
    if not secret:
        secret = secrets.token_urlsafe(48)
        await settings_store.put(_KEY_SESSION_SECRET, secret, is_secret=True)
    return URLSafeTimedSerializer(secret, salt=_SALT)


async def is_initialised() -> bool:
    """True once an admin password hash exists in app_settings."""
    return bool(await settings_store.get(_KEY_HASH))


async def init_admin(username: str, password: str) -> None:
    if await is_initialised():
        raise HTTPException(status_code=409, detail="admin already initialised")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="password must be at least 8 characters")
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode("utf-8")
    await settings_store.put(_KEY_USERNAME, username, is_secret=False)
    await settings_store.put(_KEY_HASH, hashed, is_secret=True)


async def change_password(username: str, old_password: str, new_password: str) -> None:
    if not await verify_credentials(username, old_password):
        raise HTTPException(status_code=401, detail="invalid current password")
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="new password must be at least 8 characters")
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt(rounds=12)).decode("utf-8")
    await settings_store.put(_KEY_HASH, hashed, is_secret=True)


async def verify_credentials(username: str, password: str) -> bool:
    stored_user = await settings_store.get(_KEY_USERNAME)
    stored_hash = await settings_store.get(_KEY_HASH)
    if not stored_user or not stored_hash:
        return False
    if not secrets.compare_digest(stored_user, username):
        return False
    try:
        return bcrypt.checkpw(password.encode(), stored_hash.encode())
    except (ValueError, TypeError):
        return False


async def issue_session(username: str) -> str:
    s = await _session_serializer()
    return s.dumps({"u": username})


async def verify_session(token: str) -> SessionUser | None:
    s = await _session_serializer()
    try:
        data = s.loads(token, max_age=SESSION_TTL_SECONDS)
    except SignatureExpired:
        return None
    except BadSignature:
        return None
    if not isinstance(data, dict) or "u" not in data:
        return None
    return SessionUser(username=str(data["u"]))


# -- middleware-style dependency ----------------------------------------------

# Paths that bypass session auth. The bearer-token-protected /api/captures and
# the public /healthz / /metrics are here. The login UI and auth API are also
# whitelisted so a user can log in.
WHITELIST_PREFIXES: Final = (
    "/healthz",
    "/metrics",
    "/api/captures",
    "/api/auth/",
    "/ui/login",
    "/docs",
    "/openapi.json",
    "/redoc",
)


async def require_session(request: Request) -> SessionUser:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")
    user = await verify_session(token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="session expired")
    return user


def cookie_kwargs() -> dict[str, object]:
    """Cookie attributes shared by /login and /logout. SameSite=lax so the
    Chrome extension's cross-origin POST to /api/captures keeps working
    independently via bearer token."""
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": get_settings().app_env == "prod",
        "max_age": SESSION_TTL_SECONDS,
        "path": "/",
    }
