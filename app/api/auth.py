from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app import auth as auth_lib

router = APIRouter(prefix="/api/auth", tags=["auth"])


class InitRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=256)


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=256)


@router.get("/status")
async def status_() -> dict[str, bool]:
    """Tells the login UI whether to show the initial-setup form or the
    standard login form. No auth required."""
    return {"initialised": await auth_lib.is_initialised()}


@router.post("/init")
async def init(req: InitRequest, response: Response) -> dict[str, str]:
    """First-run admin setup. Fails 409 if an admin already exists."""
    await auth_lib.init_admin(req.username, req.password)
    token = await auth_lib.issue_session(req.username)
    response.set_cookie(auth_lib.SESSION_COOKIE, token, **auth_lib.cookie_kwargs())
    return {"username": req.username, "status": "initialised"}


@router.post("/login")
async def login(req: LoginRequest, response: Response) -> dict[str, str]:
    if not await auth_lib.is_initialised():
        raise HTTPException(status_code=409, detail="admin not initialised; POST /api/auth/init")
    if not await auth_lib.verify_credentials(req.username, req.password):
        raise HTTPException(status_code=401, detail="invalid username or password")
    token = await auth_lib.issue_session(req.username)
    response.set_cookie(auth_lib.SESSION_COOKIE, token, **auth_lib.cookie_kwargs())
    return {"username": req.username, "status": "logged_in"}


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(auth_lib.SESSION_COOKIE, path="/")
    return {"status": "logged_out"}


@router.get("/me")
async def me(user: auth_lib.SessionUser = Depends(auth_lib.require_session)) -> dict[str, str]:
    return {"username": user.username}


@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    user: auth_lib.SessionUser = Depends(auth_lib.require_session),
) -> dict[str, str]:
    await auth_lib.change_password(user.username, req.old_password, req.new_password)
    return {"status": "password_changed"}
