from __future__ import annotations

import base64
from datetime import datetime
from typing import Any

import httpx

from app.profile import SearchLocation, UserProfile

from .base import BaseScraper, JobResult, ScraperSource, SearchResult

# Reed API docs: https://www.reed.co.uk/developers/jobseeker
_BASE = "https://www.reed.co.uk/api/1.0"


class ReedScraper(BaseScraper):
    source = ScraperSource.REED

    def __init__(self, api_key: str, *, timeout: float = 20.0) -> None:
        if not api_key:
            raise ValueError("ReedScraper requires an api_key")
        # Reed uses HTTP basic auth: api_key as username, empty password.
        auth_b64 = base64.b64encode(f"{api_key}:".encode()).decode()
        self._headers = {"Authorization": f"Basic {auth_b64}", "Accept": "application/json"}
        self._client = httpx.AsyncClient(timeout=timeout, headers=self._headers)

    async def close(self) -> None:
        await self._client.aclose()

    async def test_connection(self) -> bool:
        try:
            r = await self._client.get(f"{_BASE}/search", params={"resultsToTake": 1})
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    async def search(
        self,
        profile: UserProfile,
        location: SearchLocation,
        *,
        max_results: int | None = None,
    ) -> SearchResult:
        cfg = profile.sources.get("reed")
        per_page = cfg.results_per_page if cfg else 100
        max_pages = cfg.max_pages if cfg else 1
        query = self.build_query(profile)

        jobs: list[JobResult] = []
        errors: list[str] = []
        total = 0
        page = 0

        for page in range(max_pages):
            params: dict[str, Any] = {
                "keywords": query,
                "locationName": location.name.split(",")[0].strip(),
                "resultsToTake": per_page,
                "resultsToSkip": page * per_page,
            }
            try:
                r = await self._client.get(f"{_BASE}/search", params=params)
                r.raise_for_status()
            except httpx.HTTPError as e:
                errors.append(f"reed page {page + 1}: {e!s}")
                break

            data = r.json()
            total = int(data.get("totalResults", total))
            results = data.get("results") or []
            for item in results:
                jobs.append(_to_job(item, country=location.country))
            if len(results) < per_page:
                break
            if max_results and len(jobs) >= max_results:
                break

        if max_results:
            jobs = jobs[:max_results]
        jobs = self.filter_red_flags(jobs, profile)
        return SearchResult(jobs=jobs, total_found=total, pages_fetched=page + 1, errors=errors)


def _to_job(item: dict[str, Any], *, country: str) -> JobResult:
    posted = None
    if raw := item.get("date"):
        for fmt in ("%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
            try:
                posted = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue

    return JobResult(
        external_id=str(item["jobId"]),
        source=ScraperSource.REED.value,
        title=str(item.get("jobTitle", "")).strip(),
        company=str(item.get("employerName", "")).strip(),
        url=str(item.get("jobUrl", "")),
        location=item.get("locationName"),
        country=country,
        salary_min=_to_int(item.get("minimumSalary")),
        salary_max=_to_int(item.get("maximumSalary")),
        salary_currency=item.get("currency") or "GBP",
        description=str(item.get("jobDescription") or "").strip(),
        posted_date=posted,
        raw=item,
    )


def _to_int(v: Any) -> int | None:
    if v in (None, ""):
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None
