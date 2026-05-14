from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app import auth
from app.db.models import DiscoveredJob
from app.db.session import get_session, get_sessionmaker
from app.graph.checkpointer import get_checkpointer
from app.graph.runtime import get_context, runnable_config
from app.graph.state import JobSearchState
from app.graph.workflow import build_workflow
from app.llm import prompts
from app.llm.types import LLMRequest, LLMResponse, Message, StreamDelta
from app.llm.usage import CallContext, set_call_context
from app.observability.log import get_logger
from app.profile import load_profile
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


# ---------------------------------------------------------------------------
# Cover letter — SSE generation + save + approve toggle
# ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    force: bool = Field(
        default=False,
        description="Skip the apply-band threshold + approved-letter overwrite checks.",
    )


@router.post("/{job_id}/generate")
async def generate_cover_letter(
    job_id: str,
    force: bool = False,
    _user: auth.SessionUser = Depends(auth.require_session),
) -> EventSourceResponse:
    """Stream a cover-letter draft for an already-scored job.

    Emits SSE events:
      event: meta   data: {model, generations}
      event: delta  data: {text}
      event: final  data: {full_text, cost_eur, prompt_tokens, completion_tokens}
      event: error  data: {detail}

    Persistence on completion: the full text is written to discovered_jobs
    (.cover_letter, .cover_letter_model, .cover_letter_generated_at,
    .cover_letter_generations, .cover_letter_total_cost_eur). `approved` is
    NOT touched by this endpoint — user toggles it via PUT cover-letter.
    """
    # Pre-flight load (separate session from the streaming generator so we
    # don't hold a connection open for the whole stream).
    async with get_sessionmaker()() as session:
        row = await _load_row(session, job_id)
        if not row.parsed_job:
            raise HTTPException(
                status_code=422,
                detail="this job has not been scored yet — click 'Score now' first",
            )
        if not force and row.fit_score is not None and row.fit_score < APPLY_BAND_THRESHOLD:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"fit_score {float(row.fit_score):.0f} is below the apply band "
                    f"({APPLY_BAND_THRESHOLD:.0f}); pass ?force=true to override"
                ),
            )
        if not force and row.cover_letter_approved:
            raise HTTPException(
                status_code=409,
                detail="an approved cover letter already exists; pass ?force=true to overwrite",
            )
        snapshot_id = row.id
        snapshot_workflow_id = str(uuid.uuid4())

    async def event_stream():
        ctx = get_context()
        prompt = prompts.load("generator")
        candidate_profile: dict = {}
        try:
            cv_text = ctx.profile.load_cv_text()
            # Reuse the profile node? Too heavy. Cheap approximation: derive
            # a compact profile from YAML + CV preface; matcher already passed
            # so we trust the cover-letter prompt to ground against the CV.
            candidate_profile = {
                "display_name": ctx.profile.candidate.display_name,
                "headline": ctx.profile.candidate.display_name,
                "work_authorisation": ctx.profile.candidate.work_authorisation,
                "cv_excerpt": cv_text[:6000],
            }
        except Exception as e:  # noqa: BLE001
            yield {"event": "error", "data": json.dumps({"detail": f"profile load failed: {e}"})}
            return

        # Re-load the row inside this generator (in case of edits between
        # pre-flight and stream start).
        async with get_sessionmaker()() as session:
            row = await session.get(DiscoveredJob, snapshot_id)
            if row is None:
                yield {"event": "error", "data": json.dumps({"detail": "job disappeared"})}
                return

            user_content = prompt.render_user(
                parsed_job_json=json.dumps(row.parsed_job or {}),
                candidate_profile_json=json.dumps(candidate_profile),
                company_brief="",
                tone=ctx.profile.cover_letter_tone,
                must_mention=ctx.profile.cover_letter_must_mention,
                forbid_phrases=ctx.profile.cover_letter_forbid_phrases,
            )

            # Resolve the cover_letter task model (db override aware)
            from app.llm.router import _resolve_route

            provider_name, model_name, _, _ = await _resolve_route("cover_letter")
            yield {
                "event": "meta",
                "data": json.dumps(
                    {
                        "model": f"{provider_name}/{model_name}",
                        "generations": row.cover_letter_generations,
                    }
                ),
            }

            set_call_context(
                CallContext(
                    workflow_id=snapshot_workflow_id,
                    node_name="generator_inline",
                    application_id=None,
                    task="cover_letter",
                )
            )

            request = LLMRequest(
                system=prompt.system,
                messages=[Message(role="user", content=user_content)],
                model=model_name,
                temperature=0.4,
                max_tokens=1400,
            )

            from app.llm.json_utils import parse_json

            full_text_parts: list[str] = []
            final_response: LLMResponse | None = None
            try:
                async for event in ctx.router.route_stream("cover_letter", request):
                    if isinstance(event, StreamDelta):
                        full_text_parts.append(event.text)
                        yield {"event": "delta", "data": json.dumps({"text": event.text})}
                        # Cooperative yield so the event loop flushes to the wire.
                        await asyncio.sleep(0)
                    elif isinstance(event, LLMResponse):
                        final_response = event
            except Exception as e:  # noqa: BLE001
                yield {"event": "error", "data": json.dumps({"detail": str(e)})}
                return

            raw_full = "".join(full_text_parts)
            cover_letter_text = raw_full
            bullets: list[str] = []
            try:
                parsed = parse_json(raw_full)
                if isinstance(parsed, dict):
                    cover_letter_text = str(parsed.get("cover_letter") or raw_full)
                    bullets = list(parsed.get("tailored_bullets") or [])
            except Exception:  # noqa: BLE001 — fall back to plain text
                cover_letter_text = raw_full

            now = datetime.now(tz=UTC)
            row.cover_letter = cover_letter_text
            row.cover_letter_bullets = bullets
            row.cover_letter_model = f"{provider_name}/{model_name}"
            row.cover_letter_generated_at = now
            row.cover_letter_generations = (row.cover_letter_generations or 0) + 1
            if final_response is not None:
                row.cover_letter_total_cost_eur = Decimal(
                    str(float(row.cover_letter_total_cost_eur or 0)
                        + float(final_response.estimated_cost_eur))
                )
            row.cover_letter_approved = False
            await session.commit()

            yield {
                "event": "final",
                "data": json.dumps(
                    {
                        "full_text": cover_letter_text,
                        "bullets": bullets,
                        "model": f"{provider_name}/{model_name}",
                        "cost_eur": float(final_response.estimated_cost_eur) if final_response else 0.0,
                        "prompt_tokens": final_response.prompt_tokens if final_response else 0,
                        "completion_tokens": final_response.completion_tokens if final_response else 0,
                        "generations": row.cover_letter_generations,
                        "total_cost_eur": float(row.cover_letter_total_cost_eur or 0),
                    }
                ),
            }

    return EventSourceResponse(event_stream(), media_type="text/event-stream")


class SaveCoverLetterRequest(BaseModel):
    cover_letter: str = Field(..., min_length=1, max_length=20000)
    bullets: list[str] | None = None
    approved: bool = False


class CoverLetterResponse(BaseModel):
    id: str
    cover_letter: str | None
    bullets: list[str]
    model: str | None
    generated_at: str | None
    approved: bool
    generations: int
    total_cost_eur: float


@router.put("/{job_id}/cover-letter", response_model=CoverLetterResponse)
async def save_cover_letter(
    job_id: str,
    req: SaveCoverLetterRequest,
    session: AsyncSession = Depends(get_session),
    _user: auth.SessionUser = Depends(auth.require_session),
) -> CoverLetterResponse:
    """Persist the user-edited cover letter. Use `approved=true` to mark
    the final, ready-to-send version. Future generations on approved rows
    will require ?force=true.
    """
    row = await _load_row(session, job_id)
    row.cover_letter = req.cover_letter
    if req.bullets is not None:
        row.cover_letter_bullets = req.bullets
    row.cover_letter_approved = req.approved
    if row.cover_letter_generated_at is None:
        row.cover_letter_generated_at = datetime.now(tz=UTC)
    await session.commit()
    return _cover_letter_response(row)


@router.post("/{job_id}/cover-letter/approve", response_model=CoverLetterResponse)
async def approve_cover_letter(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    _user: auth.SessionUser = Depends(auth.require_session),
) -> CoverLetterResponse:
    row = await _load_row(session, job_id)
    if not row.cover_letter:
        raise HTTPException(status_code=422, detail="no cover letter saved yet")
    row.cover_letter_approved = True
    await session.commit()
    return _cover_letter_response(row)


@router.post("/{job_id}/cover-letter/unapprove", response_model=CoverLetterResponse)
async def unapprove_cover_letter(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    _user: auth.SessionUser = Depends(auth.require_session),
) -> CoverLetterResponse:
    row = await _load_row(session, job_id)
    row.cover_letter_approved = False
    await session.commit()
    return _cover_letter_response(row)


def _cover_letter_response(row: DiscoveredJob) -> CoverLetterResponse:
    return CoverLetterResponse(
        id=str(row.id),
        cover_letter=row.cover_letter,
        bullets=list(row.cover_letter_bullets or []),
        model=row.cover_letter_model,
        generated_at=(
            row.cover_letter_generated_at.isoformat() if row.cover_letter_generated_at else None
        ),
        approved=bool(row.cover_letter_approved),
        generations=int(row.cover_letter_generations or 0),
        total_cost_eur=float(row.cover_letter_total_cost_eur or 0),
    )


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
