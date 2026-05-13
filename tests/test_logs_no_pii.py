from __future__ import annotations

from app.observability.scrub import scrub_pii


def test_scrub_email_from_string() -> None:
    assert scrub_pii("contact jhonattan@example.com please") == "contact [EMAIL] please"


def test_scrub_phone_from_string() -> None:
    out = scrub_pii("ring +353 87 123 4567")
    assert "[PHONE]" in out
    assert "+353" not in out


def test_scrub_walks_dict() -> None:
    payload = {
        "user": "jhonattan@example.com",
        "nested": {"phone": "+353 87 123 4567"},
        "items": ["jhonattan@example.com"],
        "count": 3,
    }
    out = scrub_pii(payload)
    assert out["user"] == "[EMAIL]"
    assert out["nested"]["phone"] == "[PHONE]"
    assert out["items"][0] == "[EMAIL]"
    assert out["count"] == 3


def test_scrub_preserves_non_pii_strings() -> None:
    assert scrub_pii("FastAPI + LangGraph + Postgres") == "FastAPI + LangGraph + Postgres"
