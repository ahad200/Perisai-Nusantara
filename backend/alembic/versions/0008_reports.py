"""M9: tabel pelaporan — reports, report_schedules

Revision ID: 0008_reports
Revises: 0007_soar
Create Date: 2026-11-09
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0008_reports"
down_revision = "0007_soar"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(200), nullable=False, server_default=""),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("incident_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("summary", sa.String(1024), nullable=False, server_default=""),
        sa.Column("generated_by", sa.String(64), nullable=False, server_default=""),
        sa.Column("approved_by", sa.String(64), nullable=True),
        sa.Column("schedule_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_reports_code", "reports", ["code"], unique=True)
    op.create_index("ix_reports_kind", "reports", ["kind"])
    op.create_index("ix_reports_status", "reports", ["status"])
    op.create_index("ix_reports_incident_id", "reports", ["incident_id"])
    op.create_index("ix_reports_schedule_id", "reports", ["schedule_id"])

    op.create_table(
        "report_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, server_default=""),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("cadence", sa.String(16), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("recipient_role", sa.String(32), nullable=False, server_default="commander"),
        sa.Column("created_by", sa.String(64), nullable=False, server_default=""),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("report_schedules")
    op.drop_index("ix_reports_schedule_id", table_name="reports")
    op.drop_index("ix_reports_incident_id", table_name="reports")
    op.drop_index("ix_reports_status", table_name="reports")
    op.drop_index("ix_reports_kind", table_name="reports")
    op.drop_index("ix_reports_code", table_name="reports")
    op.drop_table("reports")
