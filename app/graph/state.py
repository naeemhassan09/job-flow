from __future__ import annotations

from typing import Any, Literal, TypedDict

Decision = Literal["apply", "maybe", "skip"]


class PiiFindingDict(TypedDict, total=False):
    kind: str
    placeholder: str


class JobSearchState(TypedDict, total=False):
    # Identity
    user_id: str
    application_id: str
    workflow_id: str

    # Inputs
    raw_jd: str
    raw_cv_text: str

    # Security outputs (populated by preprocess node)
    redacted_jd: str
    redacted_cv: str
    pii_findings: list[PiiFindingDict]
    injection_flags: list[str]
    quarantined: bool

    # Parsed (populated by preprocess + profile)
    parsed_job: dict[str, Any]
    candidate_profile: dict[str, Any]

    # Research loop (week 3)
    research_iterations: int
    research_notes: list[dict[str, Any]]
    company_brief: str | None

    # Matching
    fit_score: float
    score_breakdown: dict[str, float]
    decision: Decision
    decision_reason: str

    # Generation
    tailored_bullets: list[str]
    cover_letter: str | None

    # Evaluation
    eval_scores: dict[str, float]
    quality_gate_passed: bool

    # System
    current_step: str
    errors: list[str]
    retry_count: int
    awaiting_approval: bool

    # Cost telemetry (denormalised for quick reads)
    total_tokens: int
    total_cost_eur: float
