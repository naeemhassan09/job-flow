from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import get_engine

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        db = "ok"
    except Exception:
        db = "down"
    return {"status": "ok", "db": db}
