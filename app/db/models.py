from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary as sa_LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON}


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    company: Mapped[str | None] = mapped_column(String(256))
    role_title: Mapped[str | None] = mapped_column(String(256))
    job_url: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(32), default="paste")  # paste | linkedin | indeed
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    fit_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    decision: Mapped[str | None] = mapped_column(String(16))  # apply | maybe | skip
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    usage_events: Mapped[list[LLMUsageEvent]] = relationship(back_populates="application")


class LLMUsageEvent(Base):
    __tablename__ = "llm_usage_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("applications.id"), index=True
    )
    workflow_id: Mapped[str] = mapped_column(String(64), index=True)
    node_name: Mapped[str] = mapped_column(String(64))
    step_name: Mapped[str | None] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(64))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cached_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_eur: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="ok")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    application: Mapped[Application | None] = relationship(back_populates="usage_events")


class BudgetLimit(Base):
    __tablename__ = "budget_limits"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    monthly_budget_eur: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("15.00"))
    alert_threshold: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("0.70"))


class JobAnalysis(Base):
    __tablename__ = "job_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id"), index=True)
    parsed_job: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    company_brief: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GeneratedArtifact(Base):
    __tablename__ = "generated_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id"), index=True)
    type: Mapped[str] = mapped_column(String(32))  # cover_letter | bullet | brief
    content: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(64))
    eval_scores: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AppSetting(Base):
    """Encrypted key/value store for runtime settings the user can edit via the
    UI: API keys, per-task model overrides, budget caps, the admin password
    hash, etc. Values are AES-GCM encrypted with PII_ENCRYPTION_KEY; nonce is
    stored alongside. The hash for the admin password is also stored here so
    a fresh checkout doesn't ship a default password.
    """

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    encrypted_value: Mapped[bytes] = mapped_column(sa_LargeBinary, nullable=False)
    nonce: Mapped[bytes] = mapped_column(sa_LargeBinary, nullable=False)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DiscoveredJob(Base):
    """A job pulled from an external partner API (Adzuna, Reed). Deduped on
    (source, external_id). Promoted to an Application once the matcher's apply
    band fires; otherwise kept for review or filtered.
    """

    __tablename__ = "discovered_jobs"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_discovered_source_external_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(32), index=True)
    external_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(512))
    company: Mapped[str] = mapped_column(String(256))
    url: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(256))
    country: Mapped[str | None] = mapped_column(String(8))
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    salary_currency: Mapped[str | None] = mapped_column(String(8))
    description: Mapped[str | None] = mapped_column(Text)
    posted_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # Triage state set by the discovery pipeline
    # pending | scored | promoted | filtered | error
    triage_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    fit_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    decision: Mapped[str | None] = mapped_column(String(16))  # apply | maybe | skip
    decision_reason: Mapped[str | None] = mapped_column(Text)
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    parsed_job: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # Human-in-the-loop feedback. Captured via /api/jobs/{id}/feedback.
    # Shape: {thumb: "up"|"down"|null, score_correction: int|null,
    #         decision_override: "apply"|"maybe"|"skip"|null, notes: str,
    #         reviewed_at: iso8601-string|null}
    human_feedback: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    # Application lifecycle tracker — user-set, no automation.
    # Status vocabulary: bookmarked, applied, screening, interview,
    #                    offer, accepted, rejected, ghosted, withdrawn,
    #                    not_applying. NULL = not yet triaged.
    application_status: Mapped[str | None] = mapped_column(String(32), index=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # List of {at, status, note} entries appended on every status change.
    status_history: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)

    application_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("applications.id"), index=True
    )
