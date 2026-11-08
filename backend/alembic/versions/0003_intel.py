"""M4: tabel iocs & enrichment_mirror

Revision ID: 0003_intel
Revises: 0002_assets_events
Create Date: 2026-11-08
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_intel"
down_revision = "0002_assets_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "iocs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("value", sa.String(512), nullable=False),
        sa.Column("source", sa.String(128), nullable=False, server_default=""),
        sa.Column("tlp", sa.String(8), nullable=False, server_default="AMBER"),
        sa.Column("confidence", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("first_seen", sa.DateTime(), nullable=False),
        sa.Column("last_seen", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("description", sa.String(512), nullable=False, server_default=""),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("stix_id", sa.String(128), nullable=True),
        sa.UniqueConstraint("type", "value", name="uq_iocs_type_value"),
    )
    op.create_index("ix_iocs_type", "iocs", ["type"])
    op.create_index("ix_iocs_value", "iocs", ["value"])
    op.create_index("ix_iocs_status", "iocs", ["status"])
    op.create_index("ix_iocs_stix_id", "iocs", ["stix_id"])

    op.create_table(
        "enrichment_mirror",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(512), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("source", sa.String(128), nullable=False, server_default=""),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("mirror_updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_enrichment_key_kind", "enrichment_mirror", ["key", "kind"])


def downgrade() -> None:
    op.drop_table("enrichment_mirror")
    op.drop_index("ix_iocs_stix_id", table_name="iocs")
    op.drop_index("ix_iocs_status", table_name="iocs")
    op.drop_index("ix_iocs_value", table_name="iocs")
    op.drop_index("ix_iocs_type", table_name="iocs")
    op.drop_table("iocs")
