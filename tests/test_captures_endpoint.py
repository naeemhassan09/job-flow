from __future__ import annotations

from app.api.captures import _external_id_from_url


def test_linkedin_view_url_id_extracted() -> None:
    url = "https://www.linkedin.com/jobs/view/4123456789/?refId=abc"
    assert _external_id_from_url("linkedin", url) == "4123456789"


def test_linkedin_collections_url_id_extracted() -> None:
    url = (
        "https://www.linkedin.com/jobs/collections/recommended/"
        "?currentJobId=4987654321&trackingId=xyz"
    )
    assert _external_id_from_url("linkedin", url) == "4987654321"


def test_indeed_jk_extracted() -> None:
    url = "https://ie.indeed.com/viewjob?jk=abc123def456&from=serp"
    assert _external_id_from_url("indeed", url) == "abc123def456"


def test_unrecognised_url_falls_back_to_sha_prefix() -> None:
    url = "https://www.linkedin.com/some-weird-url"
    out = _external_id_from_url("linkedin", url)
    assert len(out) == 32
    assert all(c in "0123456789abcdef" for c in out)
