from __future__ import annotations

import hashlib
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DiscoveredJob, User
from app.db.session import get_session
from app.profile import load_profile
from app.scrapers.pipeline import APPLY_BAND_THRESHOLD, PipelineReport, discover_and_score

router = APIRouter(prefix="/api", tags=["discovery"])


class DiscoverRequest(BaseModel):
    max_results_per_source: int | None = 25  # keep small for ad-hoc runs


class DiscoverResponse(BaseModel):
    fetched: int
    new: int
    duplicates: int
    scored: int
    promoted: int
    filtered: int
    apply_threshold: float
    errors: list[str]


class JobRow(BaseModel):
    id: str
    source: str
    title: str
    company: str
    url: str
    location: str | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    posted_date: str | None
    triage_status: str
    fit_score: float | None
    decision: str | None
    application_status: str | None
    applied_at: str | None
    application_id: str | None


@router.post("/discover", response_model=DiscoverResponse)
async def discover(
    req: DiscoverRequest,
    session: AsyncSession = Depends(get_session),
) -> DiscoverResponse:
    profile = load_profile()
    user_id = await _ensure_user(session, profile.candidate.email)
    report: PipelineReport = await discover_and_score(
        session,
        user_id=user_id,
        profile=profile,
        max_results_per_source=req.max_results_per_source,
    )
    return DiscoverResponse(
        fetched=report.fetched,
        new=report.new,
        duplicates=report.duplicates,
        scored=report.scored,
        promoted=report.promoted,
        filtered=report.filtered,
        apply_threshold=APPLY_BAND_THRESHOLD,
        errors=report.errors,
    )


@router.get("/jobs", response_model=list[JobRow])
async def list_jobs(
    status: Literal["all", "pending", "scored", "promoted", "filtered", "error"] = "all",
    source: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[JobRow]:
    stmt = select(DiscoveredJob).order_by(desc(DiscoveredJob.scraped_at)).limit(limit)
    if status != "all":
        stmt = stmt.where(DiscoveredJob.triage_status == status)
    if source:
        stmt = stmt.where(DiscoveredJob.source == source)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        JobRow(
            id=str(r.id),
            source=r.source,
            title=r.title,
            company=r.company,
            url=r.url,
            location=r.location,
            salary_min=r.salary_min,
            salary_max=r.salary_max,
            salary_currency=r.salary_currency,
            posted_date=r.posted_date.isoformat() if r.posted_date else None,
            triage_status=r.triage_status,
            fit_score=float(r.fit_score) if r.fit_score is not None else None,
            decision=r.decision,
            application_status=r.application_status,
            applied_at=r.applied_at.isoformat() if r.applied_at else None,
            application_id=str(r.application_id) if r.application_id else None,
        )
        for r in rows
    ]


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: str, session: AsyncSession = Depends(get_session)
) -> dict[str, object]:
    try:
        uid = uuid.UUID(job_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="invalid job id") from e

    row = await session.get(DiscoveredJob, uid)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {
        "id": str(row.id),
        "source": row.source,
        "external_id": row.external_id,
        "title": row.title,
        "company": row.company,
        "url": row.url,
        "location": row.location,
        "salary_min": row.salary_min,
        "salary_max": row.salary_max,
        "salary_currency": row.salary_currency,
        "description": row.description,
        "posted_date": row.posted_date.isoformat() if row.posted_date else None,
        "scraped_at": row.scraped_at.isoformat() if row.scraped_at else None,
        "triage_status": row.triage_status,
        "fit_score": float(row.fit_score) if row.fit_score is not None else None,
        "decision": row.decision,
        "decision_reason": row.decision_reason,
        "score_breakdown": row.score_breakdown or {},
        "parsed_job": row.parsed_job or {},
        "human_feedback": row.human_feedback or {},
        "application_status": row.application_status,
        "applied_at": row.applied_at.isoformat() if row.applied_at else None,
        "status_updated_at": (
            row.status_updated_at.isoformat() if row.status_updated_at else None
        ),
        "status_history": row.status_history or [],
        "application_id": str(row.application_id) if row.application_id else None,
    }


async def _ensure_user(session: AsyncSession, email: str) -> uuid.UUID:
    """Single-user mode: lazy-create the User row from the profile email's hash."""
    email_hash = hashlib.sha256(email.lower().encode()).hexdigest()
    existing = await session.execute(select(User).where(User.email_hash == email_hash))
    user = existing.scalar_one_or_none()
    if user:
        return user.id
    user = User(id=uuid.uuid4(), email_hash=email_hash)
    session.add(user)
    await session.commit()
    return user.id
