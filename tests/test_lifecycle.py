"""Tests for the application-lifecycle status vocabulary + classifications.

End-to-end DB behaviour is covered by the smoke run in CI/curl; these tests
keep the status-set membership stable so the dashboard maths can't silently
drift if someone adds a new status without thinking about pipeline grouping.
"""
from __future__ import annotations

from app.api.lifecycle import (
    ALLOWED_STATUSES,
    APPLIED_STATUSES,
    OPEN_STATUSES,
    RESPONDED_STATUSES,
)


def test_open_pipeline_is_subset_of_applied() -> None:
    # If you're in interview, you obviously applied.
    assert OPEN_STATUSES <= APPLIED_STATUSES


def test_responded_is_subset_of_applied() -> None:
    # Same reasoning: only people who applied can have responded.
    assert RESPONDED_STATUSES <= APPLIED_STATUSES


def test_responded_excludes_self_managed_outcomes() -> None:
    # 'withdrawn' / 'not_applying' / 'bookmarked' are user-driven decisions,
    # not signals that the employer responded.
    assert "withdrawn" not in RESPONDED_STATUSES
    assert "not_applying" not in RESPONDED_STATUSES
    assert "bookmarked" not in RESPONDED_STATUSES


def test_ghosted_counts_as_applied_but_not_responded() -> None:
    assert "ghosted" in APPLIED_STATUSES
    assert "ghosted" not in RESPONDED_STATUSES


def test_allowed_statuses_match_set_membership() -> None:
    # The pipeline buckets must all reference valid statuses.
    for s in OPEN_STATUSES | RESPONDED_STATUSES | APPLIED_STATUSES:
        assert s in ALLOWED_STATUSES
