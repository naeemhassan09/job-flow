"""human feedback + parsed_job + decision_reason + score_breakdown on discovered_jobs

Revision ID: 0003_human_feedback
Revises: 0002_discovered_jobs
Create Date: 2026-05-14
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0003_human_feedback"
down_revision: str | None = "0002_discovered_jobs"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "discovered_jobs", sa.Column("decision_reason", sa.Text, nullable=True)
    )
    op.add_column(
        "discovered_jobs",
        sa.Column("score_breakdown", JSONB, server_default="{}", nullable=False),
    )
    op.add_column(
        "discovered_jobs",
        sa.Column("parsed_job", JSONB, server_default="{}", nullable=False),
    )
    op.add_column(
        "discovered_jobs",
        sa.Column("human_feedback", JSONB, server_default="{}", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("discovered_jobs", "human_feedback")
    op.drop_column("discovered_jobs", "parsed_job")
    op.drop_column("discovered_jobs", "score_breakdown")
    op.drop_column("discovered_jobs", "decision_reason")
