"""M10: tabel attribution_hypotheses (hipotesis atribusi ELANG-3)

Revision ID: 0009_attribution
Revises: 0008_reports
Create Date: 2026-11-09
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0009_attribution"
down_revision = "0008_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attribution_hypotheses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("incident_id", sa.Integer(), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor", sa.String(160), nullable=False, server_default=""),
        sa.Column("confidence", sa.String(8), nullable=False, server_default="low"),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("alternatives", sa.JSON(), nullable=False),
        sa.Column("rationale", sa.String(1024), nullable=False, server_default=""),
        sa.Column("injection_flags", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="proposed"),
        sa.Column("created_by", sa.String(64), nullable=False, server_default="ELANG-3"),
        sa.Column("model_name", sa.String(64), nullable=False, server_default=""),
        sa.Column("validator", sa.String(64), nullable=True),
        sa.Column("validator_note", sa.String(512), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_attribution_hypotheses_incident_id", "attribution_hypotheses", ["incident_id"])
    op.create_index("ix_attribution_hypotheses_status", "attribution_hypotheses", ["status"])


def downgrade() -> None:
    op.drop_index("ix_attribution_hypotheses_status", table_name="attribution_hypotheses")
    op.drop_index("ix_attribution_hypotheses_incident_id", table_name="attribution_hypotheses")
    op.drop_table("attribution_hypotheses")
