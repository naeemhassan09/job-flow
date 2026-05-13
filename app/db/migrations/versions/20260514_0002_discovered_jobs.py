"""discovered_jobs table

Revision ID: 0002_discovered_jobs
Revises: 0001_baseline
Create Date: 2026-05-14
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0002_discovered_jobs"
down_revision: str | None = "0001_baseline"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "discovered_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("company", sa.String(256), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("location", sa.String(256)),
        sa.Column("country", sa.String(8)),
        sa.Column("salary_min", sa.Integer),
        sa.Column("salary_max", sa.Integer),
        sa.Column("salary_currency", sa.String(8)),
        sa.Column("description", sa.Text),
        sa.Column("posted_date", sa.DateTime(timezone=True)),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("raw", JSONB, server_default="{}"),
        sa.Column("triage_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("fit_score", sa.Numeric(5, 2)),
        sa.Column("decision", sa.String(16)),
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id")),
        sa.UniqueConstraint("source", "external_id", name="uq_discovered_source_external_id"),
    )
    op.create_index("ix_discovered_jobs_source", "discovered_jobs", ["source"])
    op.create_index("ix_discovered_jobs_external_id", "discovered_jobs", ["external_id"])
    op.create_index("ix_discovered_jobs_scraped_at", "discovered_jobs", ["scraped_at"])
    op.create_index("ix_discovered_jobs_triage_status", "discovered_jobs", ["triage_status"])
    op.create_index("ix_discovered_jobs_application_id", "discovered_jobs", ["application_id"])


def downgrade() -> None:
    op.drop_table("discovered_jobs")
