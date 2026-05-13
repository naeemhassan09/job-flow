"""baseline schema

Revision ID: 0001_baseline
Revises:
Create Date: 2026-05-14

Creates the six application tables defined in spec §13. LangGraph's Postgres
checkpointer manages its own schema (installed lazily by ``AsyncPostgresSaver.setup()``).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email_hash", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("email_hash", name="uq_users_email_hash"),
    )
    op.create_index("ix_users_email_hash", "users", ["email_hash"])

    op.create_table(
        "applications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("company", sa.String(256)),
        sa.Column("role_title", sa.String(256)),
        sa.Column("job_url", sa.Text),
        sa.Column("source", sa.String(32), nullable=False, server_default="paste"),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("fit_score", sa.Numeric(5, 2)),
        sa.Column("decision", sa.String(16)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("applied_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_applications_user_id", "applications", ["user_id"])
    op.create_index("ix_applications_status", "applications", ["status"])

    op.create_table(
        "job_analyses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id"), nullable=False
        ),
        sa.Column("parsed_job", JSONB, server_default="{}"),
        sa.Column("score_breakdown", JSONB, server_default="{}"),
        sa.Column("company_brief", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_job_analyses_application_id", "job_analyses", ["application_id"])

    op.create_table(
        "generated_artifacts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id"), nullable=False
        ),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("eval_scores", JSONB, server_default="{}"),
        sa.Column("approved", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_generated_artifacts_application_id", "generated_artifacts", ["application_id"]
    )

    op.create_table(
        "llm_usage_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id")),
        sa.Column("workflow_id", sa.String(64), nullable=False),
        sa.Column("node_name", sa.String(64), nullable=False),
        sa.Column("step_name", sa.String(64)),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("prompt_tokens", sa.Integer, server_default="0"),
        sa.Column("completion_tokens", sa.Integer, server_default="0"),
        sa.Column("cached_tokens", sa.Integer, server_default="0"),
        sa.Column("total_tokens", sa.Integer, server_default="0"),
        sa.Column("estimated_cost_eur", sa.Numeric(10, 6), server_default="0"),
        sa.Column("latency_ms", sa.Integer, server_default="0"),
        sa.Column("cache_hit", sa.Boolean, server_default=sa.text("false")),
        sa.Column("retry_count", sa.Integer, server_default="0"),
        sa.Column("status", sa.String(16), server_default="ok"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_llm_usage_events_application_id", "llm_usage_events", ["application_id"])
    op.create_index("ix_llm_usage_events_workflow_id", "llm_usage_events", ["workflow_id"])
    op.create_index("ix_llm_usage_events_created_at", "llm_usage_events", ["created_at"])

    op.create_table(
        "budget_limits",
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("monthly_budget_eur", sa.Numeric(10, 2), server_default="15.00"),
        sa.Column("alert_threshold", sa.Numeric(3, 2), server_default="0.70"),
    )


def downgrade() -> None:
    op.drop_table("budget_limits")
    op.drop_table("llm_usage_events")
    op.drop_table("generated_artifacts")
    op.drop_table("job_analyses")
    op.drop_table("applications")
    op.drop_table("users")
