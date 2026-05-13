from __future__ import annotations

import pytest

from app.llm import prompts


@pytest.mark.parametrize(
    "name,expected_task",
    [
        ("extract", "jd_parsing"),
        ("profile", "cv_profile_compress"),
        ("matcher", "matcher"),
        ("generator", "cover_letter"),
        ("evaluator", "evaluator"),
    ],
)
def test_prompts_load_with_headers(name: str, expected_task: str) -> None:
    p = prompts.load(name)
    assert p.task == expected_task
    assert p.version >= 1
    assert p.system.strip()
    assert p.user_template.strip()


def test_extract_renders_with_redacted_jd() -> None:
    rendered = prompts.load("extract").render_user(redacted_jd="Senior AI Engineer in Dublin")
    assert "<jd>" in rendered
    assert "Senior AI Engineer" in rendered


def test_generator_renders_with_lists() -> None:
    rendered = prompts.load("generator").render_user(
        parsed_job_json="{}",
        candidate_profile_json="{}",
        company_brief="",
        tone="concise",
        must_mention=["Stamp 1G"],
        forbid_phrases=["synergy"],
    )
    assert "Stamp 1G" in rendered
    assert "synergy" in rendered
