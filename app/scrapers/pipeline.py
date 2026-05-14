from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.models import Application, DiscoveredJob
from app.graph.checkpointer import get_checkpointer
from app.graph.runtime import get_context, runnable_config
from app.graph.state import JobSearchState
from app.graph.workflow import build_workflow
from app.observability.log import get_logger
from app.profile import UserProfile, load_profile

from .base import BaseScraper, JobResult
from .registry import build_enabled_scrapers

_log = get_logger(__name__)

APPLY_BAND_THRESHOLD = 70.0


@dataclass
class PipelineReport:
    fetched: int                # raw jobs returned by scrapers (pre-dedupe)
    new: int                    # net new rows inserted into discovered_jobs
    duplicates: int             # already-known (source, external_id)
    scored: int                 # ran through preprocess + matcher
    promoted: int               # fit_score >= APPLY_BAND_THRESHOLD → became applications
    filtered: int               # dropped below threshold or quarantined
    errors: list[str]


async def discover_and_score(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    settings: Settings | None = None,
    profile: UserProfile | None = None,
    max_results_per_source: int | None = None,
) -> PipelineReport:
    """Fan out to every enabled scraper, dedupe into discovered_jobs, then
    auto-score new rows. Promotes only fit_score >= 70 to real applications.
    Cover-letter generation is NOT triggered here — keeps cost predictable.
    """
    settings = settings or get_settings()
    profile = profile or load_profile()

    scrapers = await build_enabled_scrapers(settings, profile)
    if not scrapers:
        return PipelineReport(0, 0, 0, 0, 0, 0, ["no enabled scrapers (missing API credentials?)"])

    try:
        fetched = await _fetch_all(scrapers, profile, max_results_per_source)
    finally:
        for s in scrapers:
            await s.close()

    new_rows, duplicates = await _upsert(session, fetched)
    await session.commit()

    scored = 0
    promoted = 0
    filtered = 0
    errors: list[str] = []
    for row in new_rows:
        scored += 1
        try:
            decision, fit_score, app_id = await _score_and_maybe_promote(
                session, row, user_id=user_id
            )
            if decision == "apply":
                promoted += 1
            else:
                filtered += 1
            row.triage_status = "promoted" if app_id else "filtered"
            row.fit_score = fit_score
            row.decision = decision
            row.application_id = app_id
        except Exception as e:  # noqa: BLE001 — pipeline must not crash on one bad row
            errors.append(f"score {row.source}:{row.external_id} → {e!s}")
            row.triage_status = "error"
            _log.warning("discovery.score_failed", error=str(e), source=row.source)
        await session.commit()

    return PipelineReport(
        fetched=sum(len(fr.jobs) for fr in fetched.values()),
        new=len(new_rows),
        duplicates=duplicates,
        scored=scored,
        promoted=promoted,
        filtered=filtered,
        errors=errors,
    )


async def _fetch_all(
    scrapers: list[BaseScraper],
    profile: UserProfile,
    max_results_per_source: int | None,
) -> dict[str, Any]:
    tasks: list[asyncio.Task] = []
    keys: list[str] = []
    for scraper in scrapers:
        for loc in profile.locations:
            keys.append(f"{scraper.source.value}:{loc.name}")
            tasks.append(
                asyncio.create_task(
                    scraper.search(profile, loc, max_results=max_results_per_source)
                )
            )
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out: dict[str, Any] = {}
    for key, res in zip(keys, results, strict=True):
        if isinstance(res, Exception):
            _log.warning("discovery.scraper_failed", key=key, error=str(res))
            continue
        out[key] = res
    return out


async def _upsert(session: AsyncSession, fetched: dict[str, Any]) -> tuple[list[DiscoveredJob], int]:
    new_rows: list[DiscoveredJob] = []
    duplicates = 0
    seen_in_batch: set[tuple[str, str]] = set()

    for result in fetched.values():
        for job in result.jobs:
            key = (job.source, job.external_id)
            if key in seen_in_batch:
                duplicates += 1
                continue
            seen_in_batch.add(key)

            existing = await session.execute(
                select(DiscoveredJob).where(
                    DiscoveredJob.source == job.source,
                    DiscoveredJob.external_id == job.external_id,
                )
            )
            if existing.scalar_one_or_none():
                duplicates += 1
                continue

            row = DiscoveredJob(
                source=job.source,
                external_id=job.external_id,
                title=job.title,
                company=job.company,
                url=job.url,
                location=job.location,
                country=job.country,
                salary_min=job.salary_min,
                salary_max=job.salary_max,
                salary_currency=job.salary_currency,
                description=job.description,
                posted_date=job.posted_date,
                raw=_serialisable(job.raw),
                triage_status="pending",
            )
            session.add(row)
            new_rows.append(row)
    return new_rows, duplicates


def _serialisable(obj: Any) -> Any:
    """Drop non-JSON-serialisable bits from raw scraper payloads."""
    from datetime import datetime as _dt

    if isinstance(obj, dict):
        return {k: _serialisable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialisable(v) for v in obj]
    if isinstance(obj, _dt):
        return obj.isoformat()
    return obj


async def _score_and_maybe_promote(
    session: AsyncSession, row: DiscoveredJob, *, user_id: uuid.UUID
) -> tuple[str, float, uuid.UUID | None]:
    """Run preprocess + matcher only (no generator/evaluator) on the JD text,
    then if it's an apply, create an Application row that the existing workflow
    API can resume into the generator on user demand.
    """
    jd_text = _compose_jd_text(row)
    workflow_id = str(uuid.uuid4())
    initial: JobSearchState = {
        "workflow_id": workflow_id,
        "raw_jd": jd_text,
        "current_step": "queued",
    }
    async with get_checkpointer() as cp:
        # Halt after the matcher → no generator/evaluator cost on discovered jobs.
        graph = build_workflow(checkpointer=cp, interrupt_after=["matcher"])
        cfg = runnable_config(workflow_id, context=get_context())
        await graph.ainvoke(initial, cfg)
        snapshot = await graph.aget_state(cfg)

    values = snapshot.values or {}
    fit = float(values.get("fit_score") or 0.0)
    decision = str(values.get("decision") or "skip")

    if decision != "apply" or fit < APPLY_BAND_THRESHOLD:
        return decision, fit, None

    application_id = uuid.uuid4()
    app = Application(
        id=application_id,
        user_id=user_id,
        company=row.company,
        role_title=row.title,
        job_url=row.url,
        source=row.source,
        status="discovered_apply",
        fit_score=fit,
        decision=decision,
    )
    session.add(app)
    return decision, fit, application_id


def _compose_jd_text(row: DiscoveredJob) -> str:
    parts = [f"Job title: {row.title}", f"Company: {row.company}"]
    if row.location:
        parts.append(f"Location: {row.location}")
    if row.salary_min or row.salary_max:
        currency = row.salary_currency or ""
        parts.append(f"Salary: {row.salary_min or '?'}-{row.salary_max or '?'} {currency}".strip())
    if row.description:
        parts.append("")
        parts.append(row.description)
    return "\n".join(parts)
