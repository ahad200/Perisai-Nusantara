"""M5: tabel detection_rules & alerts

Revision ID: 0004_detection_alerts
Revises: 0003_intel
Create Date: 2026-11-08
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_detection_alerts"
down_revision = "0003_intel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "detection_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rule_code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("type", sa.String(16), nullable=False, server_default="sigma"),
        sa.Column("severity", sa.String(16), nullable=False, server_default="medium"),
        sa.Column("technique", sa.String(16), nullable=True),
        sa.Column("technique_name", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="enabled"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.String(512), nullable=False, server_default=""),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_detection_rules_rule_code", "detection_rules", ["rule_code"], unique=True)

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("detection_rules.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rule_code", sa.String(32), nullable=False, server_default=""),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("technique", sa.String(16), nullable=True),
        sa.Column("technique_name", sa.String(64), nullable=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("host", sa.String(128), nullable=True),
        sa.Column("title", sa.String(256), nullable=False, server_default=""),
        sa.Column("explanation", sa.String(1024), nullable=False, server_default=""),
        sa.Column("event_ids", sa.JSON(), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="new"),
        sa.Column("assignee", sa.String(64), nullable=True),
        sa.Column("dedup_key", sa.String(256), nullable=False),
        sa.Column("first_event_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_event_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_alerts_dedup_key", "alerts", ["dedup_key"], unique=True)
    op.create_index("ix_alerts_severity", "alerts", ["severity"])
    op.create_index("ix_alerts_status", "alerts", ["status"])
    op.create_index("ix_alerts_technique", "alerts", ["technique"])
    op.create_index("ix_alerts_assignee", "alerts", ["assignee"])
    op.create_index("ix_alerts_asset_id", "alerts", ["asset_id"])
    op.create_index("ix_alerts_rule_id", "alerts", ["rule_id"])


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_index("ix_detection_rules_rule_code", table_name="detection_rules")
    op.drop_table("detection_rules")
