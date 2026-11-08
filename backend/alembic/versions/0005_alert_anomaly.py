"""M6: kolom anomali ELANG-1 pada alerts (anomaly_score, features)

Revision ID: 0005_alert_anomaly
Revises: 0004_detection_alerts
Create Date: 2026-11-08
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_alert_anomaly"
down_revision = "0004_detection_alerts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("alerts", sa.Column("anomaly_score", sa.Float(), nullable=True))
    op.add_column("alerts", sa.Column("features", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("alerts", "features")
    op.drop_column("alerts", "anomaly_score")
