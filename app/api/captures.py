from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import DiscoveredJob
from app.db.session import get_session

router = APIRouter(prefix="/api/captures", tags=["captures"])

Source = Literal["linkedin", "indeed"]


class CaptureRequest(BaseModel):
    source: Source
    url: str = Field(min_length=1)
    title: str | None = None
    company: str | None = None
    location: str | None = None
    raw_jd: str = Field(min_length=20, description="Visible JD text extracted from the page DOM")
    captured_at: datetime | None = None


class CaptureResponse(BaseModel):
    discovered_job_id: str
    source: str
    external_id: str
    deduped: bool


@router.post("", response_model=CaptureResponse, status_code=status.HTTP_201_CREATED)
async def create_capture(
    req: CaptureRequest,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> CaptureResponse:
    """Receive a JD captured by the Chrome extension from a tab the user is viewing.

    Stores it in `discovered_jobs` with `triage_status=pending` so it shows up in
    the inbox. Auto-scoring is intentionally NOT triggered here — every capture
    would otherwise burn LLM budget. Score via `POST /api/discover` or a future
    per-job endpoint.
    """
    _check_token(authorization)

    external_id = _external_id_from_url(req.source, req.url)

    existing = await session.execute(
        select(DiscoveredJob).where(
            DiscoveredJob.source == req.source,
            DiscoveredJob.external_id == external_id,
        )
    )
    row = existing.scalar_one_or_none()
    if row:
        # Update raw JD + scraped_at so a re-capture refreshes the text.
        row.description = req.raw_jd
        row.title = req.title or row.title
        row.company = req.company or row.company
        row.location = req.location or row.location
        row.scraped_at = datetime.now(tz=UTC)
        await session.commit()
        return CaptureResponse(
            discovered_job_id=str(row.id),
            source=row.source,
            external_id=row.external_id,
            deduped=True,
        )

    new_id = uuid.uuid4()
    row = DiscoveredJob(
        id=new_id,
        source=req.source,
        external_id=external_id,
        title=req.title or "(unknown title)",
        company=req.company or "(unknown company)",
        url=req.url,
        location=req.location,
        description=req.raw_jd,
        posted_date=req.captured_at,
        scraped_at=datetime.now(tz=UTC),
        raw={"captured_via": "extension", "url": req.url},
        triage_status="pending",
    )
    session.add(row)
    await session.commit()
    return CaptureResponse(
        discovered_job_id=str(new_id),
        source=req.source,
        external_id=external_id,
        deduped=False,
    )


def _check_token(header: str | None) -> None:
    expected = get_settings().extension_api_token
    if not expected:
        return  # open mode for local dev
    if not header or not header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = header.split(" ", 1)[1].strip()
    if token != expected:
        raise HTTPException(status_code=401, detail="invalid bearer token")


_LINKEDIN_ID = re.compile(r"/jobs/view/(\d+)")
_INDEED_ID = re.compile(r"[?&]jk=([a-zA-Z0-9]+)")


def _external_id_from_url(source: str, url: str) -> str:
    """Stable per-source job id derived from the URL.

    - LinkedIn: /jobs/view/{jobId} or /jobs/collections/.../currentJobId=ID
    - Indeed:   ?jk={key}

    Falls back to a sha256 of the URL so dedupe still works on unrecognised URLs.
    """
    if source == "linkedin":
        if m := _LINKEDIN_ID.search(url):
            return m.group(1)
        if m := re.search(r"currentJobId=(\d+)", url):
            return m.group(1)
    if source == "indeed":
        if m := _INDEED_ID.search(url):
            return m.group(1)
    return hashlib.sha256(url.encode()).hexdigest()[:32]
