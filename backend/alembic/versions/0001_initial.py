"""M1: tabel users & audit_entries

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-08
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("full_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("hashed_password", sa.String(128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("totp_secret", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "audit_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_type", sa.String(16), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("object_type", sa.String(64), nullable=True),
        sa.Column("object_id", sa.String(128), nullable=True),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("entry_hash", sa.String(64), nullable=False),
    )
    op.create_index("ix_audit_entries_ts", "audit_entries", ["ts"])
    op.create_index("ix_audit_entries_action", "audit_entries", ["action"])
    op.create_index(
        "uq_audit_entries_entry_hash", "audit_entries", ["entry_hash"], unique=True
    )


def downgrade() -> None:
    op.drop_table("audit_entries")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
