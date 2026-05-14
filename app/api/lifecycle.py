"""Application lifecycle tracking — manual status updates + dashboard stats.

Mirrors the spec §25.6 amendment: every entry is user-set, no automation.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import auth
from app.db.models import DiscoveredJob
from app.db.session import get_session

router = APIRouter(tags=["lifecycle"])

# Canonical status vocabulary. Keep aligned with the UI dropdown options.
ALLOWED_STATUSES = (
    "bookmarked",
    "applied",
    "screening",
    "interview",
    "offer",
    "accepted",
    "rejected",
    "ghosted",
    "withdrawn",
    "not_applying",
)

# Statuses that count as "in the pipeline" (you've engaged but it's not closed).
OPEN_STATUSES = {"applied", "screening", "interview", "offer"}

# Statuses that mean "I got a real response" (used to compute response rate).
RESPONDED_STATUSES = {"screening", "interview", "offer", "accepted", "rejected"}

# Statuses that count as "applied" (i.e. you put yourself forward).
APPLIED_STATUSES = {
    "applied",
    "screening",
    "interview",
    "offer",
    "accepted",
    "rejected",
    "ghosted",
}


StatusLiteral = Literal[
    "bookmarked",
    "applied",
    "screening",
    "interview",
    "offer",
    "accepted",
    "rejected",
    "ghosted",
    "withdrawn",
    "not_applying",
]


class StatusRequest(BaseModel):
    status: StatusLiteral
    applied_at: datetime | None = None  # auto-filled to now() when applicable
    note: str | None = Field(default=None, max_length=1000)


class StatusResponse(BaseModel):
    id: str
    application_status: str
    applied_at: str | None
    status_updated_at: str
    status_history: list[dict[str, Any]]


@router.post("/api/jobs/{job_id}/status", response_model=StatusResponse)
async def update_status(
    job_id: str,
    req: StatusRequest,
    session: AsyncSession = Depends(get_session),
    _user: auth.SessionUser = Depends(auth.require_session),
) -> StatusResponse:
    try:
        uid = uuid.UUID(job_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="invalid job id") from e

    row = await session.get(DiscoveredJob, uid)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")

    now = datetime.now(tz=UTC)
    row.application_status = req.status
    row.status_updated_at = now

    # Set applied_at the first time the user enters an applied-shaped status,
    # unless they explicitly provided a date.
    if req.applied_at is not None:
        row.applied_at = req.applied_at
    elif req.status in APPLIED_STATUSES and row.applied_at is None:
        row.applied_at = now

    history = list(row.status_history or [])
    history.append(
        {
            "at": now.isoformat(),
            "status": req.status,
            "note": req.note,
        }
    )
    row.status_history = history

    await session.commit()
    return StatusResponse(
        id=str(row.id),
        application_status=row.application_status,
        applied_at=row.applied_at.isoformat() if row.applied_at else None,
        status_updated_at=row.status_updated_at.isoformat(),
        status_history=history,
    )


# ---------------------------------------------------------------------------
# Dashboard stats
# ---------------------------------------------------------------------------


@router.get("/api/stats/dashboard")
async def dashboard(
    session: AsyncSession = Depends(get_session),
    _user: auth.SessionUser = Depends(auth.require_session),
) -> dict[str, Any]:
    # Total + by-status (NULL → "untriaged" bucket for the donut).
    total = (await session.execute(select(func.count(DiscoveredJob.id)))).scalar_one()
    status_stmt = (
        select(
            func.coalesce(DiscoveredJob.application_status, "untriaged"),
            func.count(DiscoveredJob.id),
        )
        .group_by(DiscoveredJob.application_status)
    )
    by_status = {row[0]: int(row[1]) for row in (await session.execute(status_stmt)).all()}

    # Open pipeline = engaged but not closed.
    open_count = sum(by_status.get(s, 0) for s in OPEN_STATUSES)

    # Response rate = responded / applied. Defined when applied > 0.
    applied_n = sum(by_status.get(s, 0) for s in APPLIED_STATUSES)
    responded_n = sum(by_status.get(s, 0) for s in RESPONDED_STATUSES)
    response_rate = (responded_n / applied_n) if applied_n else None

    # Average fit score on applications you actually sent (applied or further).
    avg_fit_stmt = select(func.avg(DiscoveredJob.fit_score)).where(
        DiscoveredJob.application_status.in_(APPLIED_STATUSES)
    )
    avg_fit = (await session.execute(avg_fit_stmt)).scalar()

    # Applied per week, last 12 weeks.
    weekly_stmt = (
        select(
            func.date_trunc("week", DiscoveredJob.applied_at).label("week"),
            func.count(DiscoveredJob.id).label("n"),
        )
        .where(DiscoveredJob.applied_at.is_not(None))
        .group_by("week")
        .order_by(desc("week"))
        .limit(12)
    )
    weekly_rows = (await session.execute(weekly_stmt)).all()
    applied_per_week = [
        {"week_start": r.week.isoformat() if r.week else None, "count": int(r.n)}
        for r in reversed(weekly_rows)
    ]

    # Top companies you've applied to, top 8.
    top_co_stmt = (
        select(DiscoveredJob.company, func.count(DiscoveredJob.id).label("n"))
        .where(DiscoveredJob.application_status.in_(APPLIED_STATUSES))
        .group_by(DiscoveredJob.company)
        .order_by(desc("n"))
        .limit(8)
    )
    top_companies = [
        {"company": r[0], "count": int(r[1])}
        for r in (await session.execute(top_co_stmt)).all()
    ]

    # Stale applications: still in "applied" or "screening" and not updated in 14d.
    fortnight_ago = datetime.now(tz=UTC).timestamp() - 14 * 24 * 3600
    stale_stmt = (
        select(
            DiscoveredJob.id,
            DiscoveredJob.title,
            DiscoveredJob.company,
            DiscoveredJob.applied_at,
            DiscoveredJob.status_updated_at,
            DiscoveredJob.application_status,
        )
        .where(
            DiscoveredJob.application_status.in_({"applied", "screening"}),
            DiscoveredJob.status_updated_at < datetime.fromtimestamp(fortnight_ago, tz=UTC),
        )
        .order_by(DiscoveredJob.status_updated_at)
        .limit(20)
    )
    stale_rows = (await session.execute(stale_stmt)).all()
    stale = [
        {
            "id": str(r.id),
            "title": r.title,
            "company": r.company,
            "status": r.application_status,
            "applied_at": r.applied_at.isoformat() if r.applied_at else None,
            "status_updated_at": (
                r.status_updated_at.isoformat() if r.status_updated_at else None
            ),
        }
        for r in stale_rows
    ]

    return {
        "total_jobs": int(total),
        "by_status": by_status,
        "open_pipeline": open_count,
        "applied_total": applied_n,
        "responded_total": responded_n,
        "response_rate": response_rate,
        "avg_fit_applied": float(avg_fit) if avg_fit is not None else None,
        "applied_per_week": applied_per_week,
        "top_companies_applied": top_companies,
        "stale_followups": stale,
        "allowed_statuses": list(ALLOWED_STATUSES),
    }
