"""M3: tabel assets & events

Revision ID: 0002_assets_events
Revises: 0001_initial
Create Date: 2026-11-08
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_assets_events"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hostname", sa.String(128), nullable=False),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("segment", sa.String(64), nullable=False, server_default=""),
        sa.Column("owner", sa.String(128), nullable=False, server_default=""),
        sa.Column("criticality", sa.String(2), nullable=False, server_default="K1"),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_assets_hostname", "assets", ["hostname"], unique=True)
    op.create_index("ix_assets_segment", "assets", ["segment"])
    op.create_index("ix_assets_criticality", "assets", ["criticality"])

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("host", sa.String(128), nullable=True),
        sa.Column(
            "asset_id", sa.Integer(),
            sa.ForeignKey("assets.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("user", sa.String(128), nullable=True),
        sa.Column("src_ip", sa.String(45), nullable=True),
        sa.Column("dst_ip", sa.String(45), nullable=True),
        sa.Column("dst_port", sa.Integer(), nullable=True),
        sa.Column("bytes_out", sa.Integer(), nullable=True),
        sa.Column("message", sa.String(512), nullable=False, server_default=""),
        sa.Column("scenario", sa.String(32), nullable=True),
        sa.Column("raw", sa.JSON(), nullable=False),
    )
    op.create_index("ix_events_ts", "events", ["ts"])
    op.create_index("ix_events_source_type", "events", ["source_type"])
    op.create_index("ix_events_host", "events", ["host"])
    op.create_index("ix_events_asset_id", "events", ["asset_id"])
    op.create_index("ix_events_category", "events", ["category"])
    op.create_index("ix_events_scenario", "events", ["scenario"])


def downgrade() -> None:
    op.drop_table("events")
    op.drop_index("ix_assets_criticality", table_name="assets")
    op.drop_index("ix_assets_segment", table_name="assets")
    op.drop_index("ix_assets_hostname", table_name="assets")
    op.drop_table("assets")
