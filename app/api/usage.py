from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import LLMUsageEvent
from app.db.session import get_session

router = APIRouter(prefix="/api/usage", tags=["usage"])


def _start_of_month() -> datetime:
    now = datetime.now(tz=UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


@router.get("/monthly")
async def monthly_summary(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    settings = get_settings()
    start = _start_of_month()
    stmt = select(
        func.coalesce(func.sum(LLMUsageEvent.estimated_cost_eur), 0),
        func.coalesce(func.sum(LLMUsageEvent.total_tokens), 0),
        func.coalesce(func.sum(LLMUsageEvent.cached_tokens), 0),
        func.count(LLMUsageEvent.id),
    ).where(LLMUsageEvent.created_at >= start)
    row = (await session.execute(stmt)).one()
    spend, tokens, cached, calls = row
    cap = Decimal(settings.monthly_budget_eur)
    spend_dec = Decimal(spend)
    pct = float(spend_dec / cap * 100) if cap > 0 else 0.0
    return {
        "month_start": start.isoformat(),
        "spend_eur": float(spend_dec),
        "monthly_cap_eur": float(cap),
        "spent_pct": round(pct, 2),
        "total_tokens": int(tokens),
        "cached_tokens": int(cached),
        "cache_hit_rate": round(int(cached) / int(tokens), 4) if int(tokens) else 0.0,
        "calls": int(calls),
    }


@router.get("/by-model")
async def by_model(
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    start = _start_of_month()
    stmt = (
        select(
            LLMUsageEvent.provider,
            LLMUsageEvent.model,
            func.count(LLMUsageEvent.id).label("calls"),
            func.coalesce(func.sum(LLMUsageEvent.total_tokens), 0).label("tokens"),
            func.coalesce(func.sum(LLMUsageEvent.estimated_cost_eur), 0).label("spend"),
        )
        .where(LLMUsageEvent.created_at >= start)
        .group_by(LLMUsageEvent.provider, LLMUsageEvent.model)
        .order_by(desc("spend"))
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "provider": r.provider,
            "model": r.model,
            "calls": int(r.calls),
            "tokens": int(r.tokens),
            "spend_eur": float(r.spend),
        }
        for r in rows
    ]


@router.get("/by-node")
async def by_node(
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    start = _start_of_month()
    stmt = (
        select(
            LLMUsageEvent.node_name,
            func.count(LLMUsageEvent.id).label("calls"),
            func.coalesce(func.sum(LLMUsageEvent.total_tokens), 0).label("tokens"),
            func.coalesce(func.sum(LLMUsageEvent.estimated_cost_eur), 0).label("spend"),
            func.coalesce(func.avg(LLMUsageEvent.latency_ms), 0).label("avg_latency_ms"),
        )
        .where(LLMUsageEvent.created_at >= start)
        .group_by(LLMUsageEvent.node_name)
        .order_by(desc("spend"))
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "node": r.node_name,
            "calls": int(r.calls),
            "tokens": int(r.tokens),
            "spend_eur": float(r.spend),
            "avg_latency_ms": int(r.avg_latency_ms or 0),
        }
        for r in rows
    ]


@router.get("/recent")
async def recent(
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    stmt = (
        select(LLMUsageEvent).order_by(desc(LLMUsageEvent.created_at)).limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": str(r.id),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "workflow_id": r.workflow_id,
            "application_id": str(r.application_id) if r.application_id else None,
            "node": r.node_name,
            "provider": r.provider,
            "model": r.model,
            "prompt_tokens": r.prompt_tokens,
            "completion_tokens": r.completion_tokens,
            "cached_tokens": r.cached_tokens,
            "total_tokens": r.total_tokens,
            "cost_eur": float(r.estimated_cost_eur),
            "latency_ms": r.latency_ms,
            "status": r.status,
        }
        for r in rows
    ]
