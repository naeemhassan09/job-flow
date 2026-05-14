"""application lifecycle tracker on discovered_jobs

Revision ID: 0005_application_lifecycle
Revises: 0004_app_settings
Create Date: 2026-05-14
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0005_application_lifecycle"
down_revision: str | None = "0004_app_settings"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "discovered_jobs", sa.Column("application_status", sa.String(32), nullable=True)
    )
    op.add_column(
        "discovered_jobs", sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "discovered_jobs",
        sa.Column("status_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "discovered_jobs",
        sa.Column("status_history", JSONB, server_default="[]", nullable=False),
    )
    op.create_index(
        "ix_discovered_jobs_application_status",
        "discovered_jobs",
        ["application_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_discovered_jobs_application_status", table_name="discovered_jobs")
    op.drop_column("discovered_jobs", "status_history")
    op.drop_column("discovered_jobs", "status_updated_at")
    op.drop_column("discovered_jobs", "applied_at")
    op.drop_column("discovered_jobs", "application_status")
