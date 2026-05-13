from __future__ import annotations

from datetime import datetime

from app.profile import load_profile
from app.scrapers.adzuna import AdzunaScraper
from app.scrapers.base import JobResult, ScraperSource
from app.scrapers.reed import ReedScraper


def _profile():
    return load_profile("config/profile.example.yml")


def test_build_query_combines_titles_and_must_have() -> None:
    scraper = AdzunaScraper("dummy_id", "dummy_key")
    try:
        q = scraper.build_query(_profile())
    finally:
        # AdzunaScraper holds an httpx client; in sync test context we don't await close()
        pass
    assert "AI Engineer" in q or "ML Engineer" in q
    assert "Python" in q


def test_filter_red_flags_drops_offending_jobs() -> None:
    profile = _profile()
    scraper = AdzunaScraper("x", "y")
    jobs = [
        JobResult(
            external_id="1",
            source=ScraperSource.ADZUNA.value,
            title="Senior AI Engineer",
            company="X",
            url="https://x",
            description="Great role with sponsorship support.",
        ),
        JobResult(
            external_id="2",
            source=ScraperSource.ADZUNA.value,
            title="AI Engineer (unpaid internship)",
            company="Y",
            url="https://y",
            description="Equity only, no salary.",
        ),
    ]
    filtered = scraper.filter_red_flags(jobs, profile)
    assert [j.external_id for j in filtered] == ["1"]


def test_scrapers_require_credentials() -> None:
    import pytest

    with pytest.raises(ValueError):
        AdzunaScraper("", "")
    with pytest.raises(ValueError):
        ReedScraper("")


def test_job_result_carries_metadata() -> None:
    j = JobResult(
        external_id="abc",
        source="adzuna",
        title="t",
        company="c",
        url="https://u",
        posted_date=datetime(2026, 5, 14),
    )
    assert j.scraped_at  # default factory ran
    assert j.posted_date.year == 2026
