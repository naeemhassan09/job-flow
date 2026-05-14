"""research loop output on discovered_jobs

Revision ID: 0007_research
Revises: 0006_cover_letter
Create Date: 2026-05-14
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0007_research"
down_revision: str | None = "0006_cover_letter"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "discovered_jobs",
        sa.Column("company_brief", JSONB, server_default="{}", nullable=False),
    )
    op.add_column(
        "discovered_jobs",
        sa.Column("research_trace", JSONB, server_default="[]", nullable=False),
    )
    op.add_column(
        "discovered_jobs",
        sa.Column("research_iterations", sa.Integer, server_default="0", nullable=False),
    )
    op.add_column(
        "discovered_jobs",
        sa.Column("research_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "discovered_jobs",
        sa.Column(
            "research_total_cost_eur",
            sa.Numeric(10, 6),
            server_default="0",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("discovered_jobs", "research_total_cost_eur")
    op.drop_column("discovered_jobs", "research_at")
    op.drop_column("discovered_jobs", "research_iterations")
    op.drop_column("discovered_jobs", "research_trace")
    op.drop_column("discovered_jobs", "company_brief")
