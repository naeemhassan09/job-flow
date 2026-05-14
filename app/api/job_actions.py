from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DiscoveredJob
from app.db.session import get_session
from app.graph.checkpointer import get_checkpointer
from app.graph.runtime import get_context, runnable_config
from app.graph.state import JobSearchState
from app.graph.workflow import build_workflow
from app.observability.log import get_logger
from app.scrapers.pipeline import APPLY_BAND_THRESHOLD

router = APIRouter(prefix="/api/jobs", tags=["job-actions"])
_log = get_logger(__name__)


class ScoreResponse(BaseModel):
    id: str
    triage_status: str
    fit_score: float | None
    decision: str | None
    decision_reason: str | None
    score_breakdown: dict[str, float] = Field(default_factory=dict)


@router.post("/{job_id}/score", response_model=ScoreResponse)
async def score_job(
    job_id: str, session: AsyncSession = Depends(get_session)
) -> ScoreResponse:
    """Run the score-only workflow (preprocess + profile + matcher, halts after
    matcher) against a single discovered_jobs row. No cover-letter cost.
    """
    row = await _load_row(session, job_id)
    if not row.description or len(row.description) < 50:
        raise HTTPException(
            status_code=422,
            detail="job description is too short to score (re-capture with the extension?)",
        )

    workflow_id = str(uuid.uuid4())
    initial: JobSearchState = {
        "workflow_id": workflow_id,
        "raw_jd": _compose_jd_text(row),
        "current_step": "queued",
    }
    async with get_checkpointer() as cp:
        graph = build_workflow(checkpointer=cp, interrupt_after=["matcher"])
        cfg = runnable_config(workflow_id, context=get_context())
        await graph.ainvoke(initial, cfg)
        snapshot = await graph.aget_state(cfg)

    values = snapshot.values or {}
    fit_value = values.get("fit_score")
    fit = float(fit_value) if fit_value is not None else None
    decision = str(values.get("decision") or "skip")
    decision_reason = str(values.get("decision_reason") or "")
    breakdown = {
        k: float(v) for k, v in (values.get("score_breakdown") or {}).items()
    }

    row.fit_score = Decimal(str(fit)) if fit is not None else None
    row.decision = decision
    row.decision_reason = decision_reason
    row.score_breakdown = breakdown
    row.parsed_job = values.get("parsed_job") or {}
    if values.get("quarantined"):
        row.triage_status = "error"
    elif fit is not None and fit >= APPLY_BAND_THRESHOLD:
        row.triage_status = "promoted" if row.application_id else "scored"
    else:
        row.triage_status = "scored"
    await session.commit()

    return ScoreResponse(
        id=str(row.id),
        triage_status=row.triage_status,
        fit_score=fit,
        decision=decision if fit is not None else None,
        decision_reason=decision_reason or None,
        score_breakdown=breakdown,
    )


class FeedbackRequest(BaseModel):
    thumb: Literal["up", "down"] | None = None
    score_correction: int | None = Field(default=None, ge=0, le=100)
    decision_override: Literal["apply", "maybe", "skip"] | None = None
    notes: str | None = None


class FeedbackResponse(BaseModel):
    id: str
    human_feedback: dict[str, object]


@router.post("/{job_id}/feedback", response_model=FeedbackResponse)
async def record_feedback(
    job_id: str,
    req: FeedbackRequest,
    session: AsyncSession = Depends(get_session),
) -> FeedbackResponse:
    """Append human feedback to a discovered_jobs row. Used as ground truth
    for prompt tuning and (eventually) the eval harness."""
    row = await _load_row(session, job_id)
    existing = dict(row.human_feedback or {})
    update: dict[str, object] = {
        "thumb": req.thumb if req.thumb is not None else existing.get("thumb"),
        "score_correction": (
            req.score_correction
            if req.score_correction is not None
            else existing.get("score_correction")
        ),
        "decision_override": (
            req.decision_override
            if req.decision_override is not None
            else existing.get("decision_override")
        ),
        "notes": req.notes if req.notes is not None else existing.get("notes"),
        "reviewed_at": datetime.now(tz=UTC).isoformat(),
    }
    row.human_feedback = update
    await session.commit()
    return FeedbackResponse(id=str(row.id), human_feedback=update)


async def _load_row(session: AsyncSession, job_id: str) -> DiscoveredJob:
    try:
        uid = uuid.UUID(job_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="invalid job id") from e
    row = await session.get(DiscoveredJob, uid)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    return row


def _compose_jd_text(row: DiscoveredJob) -> str:
    parts = [f"Job title: {row.title}", f"Company: {row.company}"]
    if row.location:
        parts.append(f"Location: {row.location}")
    if row.salary_min or row.salary_max:
        currency = row.salary_currency or ""
        parts.append(
            f"Salary: {row.salary_min or '?'}-{row.salary_max or '?'} {currency}".strip()
        )
    if row.description:
        parts.append("")
        parts.append(row.description)
    return "\n".join(parts)
