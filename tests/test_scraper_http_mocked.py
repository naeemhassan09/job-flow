from __future__ import annotations

import httpx
import pytest
import respx

from app.profile import SearchLocation, load_profile
from app.scrapers.adzuna import AdzunaScraper
from app.scrapers.reed import ReedScraper


def _profile():
    return load_profile("config/profile.example.yml")


@pytest.mark.asyncio
@respx.mock
async def test_adzuna_search_parses_results() -> None:
    respx.get("https://api.adzuna.com/v1/api/jobs/ie/search/1").mock(
        return_value=httpx.Response(
            200,
            json={
                "count": 1,
                "results": [
                    {
                        "id": "12345",
                        "title": "Senior AI Engineer",
                        "company": {"display_name": "ExampleCo"},
                        "location": {"display_name": "Dublin, Ireland"},
                        "redirect_url": "https://adzuna.example/12345",
                        "description": "Building AI platforms with Python and AWS.",
                        "salary_min": 90000,
                        "salary_max": 120000,
                        "salary_currency": "EUR",
                        "created": "2026-05-10T09:00:00Z",
                    }
                ],
            },
        )
    )

    scraper = AdzunaScraper("id", "key")
    try:
        result = await scraper.search(
            _profile(), SearchLocation(name="Dublin, Ireland", country="ie")
        )
    finally:
        await scraper.close()

    assert result.total_found == 1
    assert len(result.jobs) == 1
    job = result.jobs[0]
    assert job.title == "Senior AI Engineer"
    assert job.company == "ExampleCo"
    assert job.salary_min == 90000
    assert job.country == "ie"
    assert job.posted_date is not None


@pytest.mark.asyncio
@respx.mock
async def test_reed_search_parses_results() -> None:
    respx.get("https://www.reed.co.uk/api/1.0/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "totalResults": 1,
                "results": [
                    {
                        "jobId": 999,
                        "jobTitle": "AI Platform Engineer",
                        "employerName": "Reed Demo",
                        "jobUrl": "https://reed.example/999",
                        "locationName": "Dublin",
                        "minimumSalary": 80000,
                        "maximumSalary": 110000,
                        "currency": "EUR",
                        "jobDescription": "Python, AWS, LangGraph.",
                        "date": "01/05/2026",
                    }
                ],
            },
        )
    )

    scraper = ReedScraper("dummy")
    try:
        result = await scraper.search(
            _profile(), SearchLocation(name="Dublin, Ireland", country="ie")
        )
    finally:
        await scraper.close()

    assert result.total_found == 1
    assert len(result.jobs) == 1
    job = result.jobs[0]
    assert job.title == "AI Platform Engineer"
    assert job.salary_min == 80000
    assert job.source == "reed"


@pytest.mark.asyncio
@respx.mock
async def test_adzuna_red_flag_filter_applied_after_fetch() -> None:
    respx.get("https://api.adzuna.com/v1/api/jobs/ie/search/1").mock(
        return_value=httpx.Response(
            200,
            json={
                "count": 2,
                "results": [
                    {
                        "id": "1",
                        "title": "Senior AI Engineer",
                        "company": {"display_name": "Good"},
                        "redirect_url": "https://x",
                        "description": "Sponsorship available.",
                    },
                    {
                        "id": "2",
                        "title": "Founding Engineer",
                        "company": {"display_name": "Bad"},
                        "redirect_url": "https://y",
                        "description": "Equity only.",
                    },
                ],
            },
        )
    )

    scraper = AdzunaScraper("id", "key")
    try:
        result = await scraper.search(
            _profile(), SearchLocation(name="Dublin, Ireland", country="ie")
        )
    finally:
        await scraper.close()

    assert len(result.jobs) == 1
    assert result.jobs[0].external_id == "1"
