"""cover letter draft + approval on discovered_jobs

Revision ID: 0006_cover_letter
Revises: 0005_application_lifecycle
Create Date: 2026-05-14
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0006_cover_letter"
down_revision: str | None = "0005_application_lifecycle"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("discovered_jobs", sa.Column("cover_letter", sa.Text, nullable=True))
    op.add_column(
        "discovered_jobs",
        sa.Column("cover_letter_bullets", JSONB, server_default="[]", nullable=False),
    )
    op.add_column(
        "discovered_jobs", sa.Column("cover_letter_model", sa.String(64), nullable=True)
    )
    op.add_column(
        "discovered_jobs",
        sa.Column("cover_letter_generated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "discovered_jobs",
        sa.Column(
            "cover_letter_approved",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "discovered_jobs",
        sa.Column(
            "cover_letter_generations",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "discovered_jobs",
        sa.Column(
            "cover_letter_total_cost_eur",
            sa.Numeric(10, 6),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("discovered_jobs", "cover_letter_total_cost_eur")
    op.drop_column("discovered_jobs", "cover_letter_generations")
    op.drop_column("discovered_jobs", "cover_letter_approved")
    op.drop_column("discovered_jobs", "cover_letter_generated_at")
    op.drop_column("discovered_jobs", "cover_letter_model")
    op.drop_column("discovered_jobs", "cover_letter_bullets")
    op.drop_column("discovered_jobs", "cover_letter")
