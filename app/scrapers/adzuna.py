from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.profile import SearchLocation, UserProfile

from .base import BaseScraper, JobResult, ScraperSource, SearchResult

# Adzuna docs: https://developer.adzuna.com/docs/search
_BASE = "https://api.adzuna.com/v1/api/jobs"


class AdzunaScraper(BaseScraper):
    source = ScraperSource.ADZUNA

    def __init__(self, app_id: str, app_key: str, *, timeout: float = 20.0) -> None:
        if not app_id or not app_key:
            raise ValueError("AdzunaScraper requires both app_id and app_key")
        self._app_id = app_id
        self._app_key = app_key
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        await self._client.aclose()

    async def test_connection(self) -> bool:
        try:
            r = await self._client.get(
                f"{_BASE}/ie/categories",
                params={"app_id": self._app_id, "app_key": self._app_key},
            )
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
        cfg = profile.sources.get("adzuna")
        per_page = cfg.results_per_page if cfg else 50
        max_pages = cfg.max_pages if cfg else 1
        max_age_days = cfg.max_age_days if cfg else 14
        query = self.build_query(profile)

        jobs: list[JobResult] = []
        errors: list[str] = []
        total = 0

        for page in range(1, max_pages + 1):
            url = f"{_BASE}/{location.country}/search/{page}"
            params: dict[str, Any] = {
                "app_id": self._app_id,
                "app_key": self._app_key,
                "results_per_page": per_page,
                "what": query,
                "where": location.name,
                "max_days_old": max_age_days,
                "content-type": "application/json",
            }
            try:
                r = await self._client.get(url, params=params)
                r.raise_for_status()
            except httpx.HTTPError as e:
                errors.append(f"adzuna page {page}: {e!s}")
                break

            data = r.json()
            total = int(data.get("count", total))
            for item in data.get("results", []):
                jobs.append(_to_job(item, country=location.country))
            if len(data.get("results", [])) < per_page:
                # last page reached
                break
            if max_results and len(jobs) >= max_results:
                break

        if max_results:
            jobs = jobs[:max_results]
        jobs = self.filter_red_flags(jobs, profile)
        return SearchResult(jobs=jobs, total_found=total, pages_fetched=page, errors=errors)


def _to_job(item: dict[str, Any], *, country: str) -> JobResult:
    posted = None
    if raw := item.get("created"):
        try:
            posted = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            posted = None

    salary_currency = None
    if item.get("salary_min") or item.get("salary_max"):
        salary_currency = item.get("salary_currency") or _currency_for(country)

    return JobResult(
        external_id=str(item["id"]),
        source=ScraperSource.ADZUNA.value,
        title=str(item.get("title", "")).strip(),
        company=str((item.get("company") or {}).get("display_name", "")).strip(),
        url=str(item.get("redirect_url") or item.get("url", "")),
        location=(item.get("location") or {}).get("display_name"),
        country=country,
        salary_min=_to_int(item.get("salary_min")),
        salary_max=_to_int(item.get("salary_max")),
        salary_currency=salary_currency,
        description=str(item.get("description") or "").strip(),
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


def _currency_for(country: str) -> str:
    return {"ie": "EUR", "gb": "GBP", "us": "USD", "de": "EUR", "fr": "EUR"}.get(country, "EUR")
