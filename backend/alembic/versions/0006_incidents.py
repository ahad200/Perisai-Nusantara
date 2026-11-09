"""M7: tabel incidents & incident_notes + alerts.incident_id

Revision ID: 0006_incidents
Revises: 0005_alert_anomaly
Create Date: 2026-11-08
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_incidents"
down_revision = "0005_alert_anomaly"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("incident_code", sa.String(16), nullable=False),
        sa.Column("correlation_key", sa.String(160), nullable=False),
        sa.Column("title", sa.String(256), nullable=False, server_default=""),
        sa.Column("summary", sa.String(1024), nullable=False, server_default=""),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("assignee", sa.String(64), nullable=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("host", sa.String(128), nullable=True),
        sa.Column("techniques", sa.JSON(), nullable=False),
        sa.Column("alert_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_event_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_event_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_incidents_incident_code", "incidents", ["incident_code"], unique=True)
    op.create_index("ix_incidents_correlation_key", "incidents", ["correlation_key"], unique=True)
    op.create_index("ix_incidents_severity", "incidents", ["severity"])
    op.create_index("ix_incidents_status", "incidents", ["status"])
    op.create_index("ix_incidents_assignee", "incidents", ["assignee"])
    op.create_index("ix_incidents_asset_id", "incidents", ["asset_id"])

    op.create_table(
        "incident_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("incident_id", sa.Integer(), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False, server_default="note"),
        sa.Column("body", sa.String(2048), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_incident_notes_incident_id", "incident_notes", ["incident_id"])

    # Batch mode: SQLite tak mendukung ALTER untuk menambah constraint FK.
    with op.batch_alter_table("alerts") as batch:
        batch.add_column(sa.Column("incident_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_alerts_incident_id", "incidents", ["incident_id"], ["id"], ondelete="SET NULL"
        )
    op.create_index("ix_alerts_incident_id", "alerts", ["incident_id"])


def downgrade() -> None:
    op.drop_index("ix_alerts_incident_id", table_name="alerts")
    with op.batch_alter_table("alerts") as batch:
        batch.drop_constraint("fk_alerts_incident_id", type_="foreignkey")
        batch.drop_column("incident_id")
    op.drop_index("ix_incident_notes_incident_id", table_name="incident_notes")
    op.drop_table("incident_notes")
    op.drop_index("ix_incidents_asset_id", table_name="incidents")
    op.drop_index("ix_incidents_assignee", table_name="incidents")
    op.drop_index("ix_incidents_status", table_name="incidents")
    op.drop_index("ix_incidents_severity", table_name="incidents")
    op.drop_index("ix_incidents_correlation_key", table_name="incidents")
    op.drop_index("ix_incidents_incident_code", table_name="incidents")
    op.drop_table("incidents")
