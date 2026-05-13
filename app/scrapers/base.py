from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from app.profile import SearchLocation, UserProfile


class ScraperSource(str, Enum):
    """Job-source identifiers. Only official-API sources are allowed in V1.

    LINKEDIN and INDEED intentionally have no implementations — they violate ToS
    when scraped. JDs from those sites enter via the Chrome extension companion
    (week 5), which POSTs the visible JD text from a tab the user is viewing.
    """

    ADZUNA = "adzuna"
    REED = "reed"


@dataclass(frozen=True)
class JobResult:
    """A single job discovered by a scraper. Maps 1:1 to discovered_jobs rows."""

    external_id: str
    source: str
    title: str
    company: str
    url: str
    location: str | None = None
    country: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    description: str | None = None
    posted_date: datetime | None = None
    scraped_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    jobs: list[JobResult]
    total_found: int
    pages_fetched: int
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return not self.errors or bool(self.jobs)


class BaseScraper(ABC):
    """Async scraper interface. One instance per source per process is fine."""

    source: ScraperSource

    @abstractmethod
    async def search(
        self,
        profile: UserProfile,
        location: SearchLocation,
        *,
        max_results: int | None = None,
    ) -> SearchResult: ...

    @abstractmethod
    async def test_connection(self) -> bool: ...

    async def close(self) -> None:
        """Override if the scraper holds open resources (httpx clients, etc.)."""

    # -- helpers shared across implementations --

    def build_query(self, profile: UserProfile) -> str:
        """Construct a free-text query from primary titles + must-have keywords.

        Most boards (Adzuna, Reed) treat the query as full-text with implicit
        AND between tokens. We OR the titles so any one matches, then AND the
        must-have keywords.
        """
        titles = profile.target_titles.primary[:3]
        must = profile.keywords.must_have[:3]
        title_clause = " OR ".join(f'"{t}"' for t in titles) if titles else ""
        must_clause = " ".join(must)
        if title_clause and must_clause:
            return f"({title_clause}) {must_clause}"
        return title_clause or must_clause

    def filter_red_flags(self, jobs: list[JobResult], profile: UserProfile) -> list[JobResult]:
        return [
            j for j in jobs if not profile.has_red_flag(f"{j.title} {j.description or ''}")
        ]
