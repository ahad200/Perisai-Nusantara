"""M8: tabel SOAR — playbooks, playbook_runs, action_executions, approvals,
notifications, break_glass

Revision ID: 0007_soar
Revises: 0006_incidents
Create Date: 2026-11-09
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007_soar"
down_revision = "0006_incidents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "playbooks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("trigger_technique", sa.String(16), nullable=True),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("owner", sa.String(64), nullable=False, server_default=""),
        sa.Column("description", sa.String(512), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_playbooks_code", "playbooks", ["code"], unique=True)
    op.create_index("ix_playbooks_trigger_technique", "playbooks", ["trigger_technique"])

    op.create_table(
        "playbook_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("playbook_id", sa.Integer(), sa.ForeignKey("playbooks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("playbook_code", sa.String(32), nullable=False, server_default=""),
        sa.Column("incident_id", sa.Integer(), sa.ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("mode", sa.String(16), nullable=False, server_default="auto"),
        sa.Column("status", sa.String(24), nullable=False, server_default="running"),
        sa.Column("severity", sa.String(16), nullable=False, server_default=""),
        sa.Column("criticality", sa.String(2), nullable=False, server_default=""),
        sa.Column("host", sa.String(128), nullable=True),
        sa.Column("actor", sa.String(64), nullable=False, server_default=""),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_playbook_runs_playbook_id", "playbook_runs", ["playbook_id"])
    op.create_index("ix_playbook_runs_incident_id", "playbook_runs", ["incident_id"])
    op.create_index("ix_playbook_runs_status", "playbook_runs", ["status"])

    op.create_table(
        "action_executions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("playbook_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=True),
        sa.Column("step_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("disruptive", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("pre_approved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reversible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("decision_mode", sa.String(16), nullable=False, server_default=""),
        sa.Column("decision_reason", sa.String(512), nullable=False, server_default=""),
        sa.Column("status", sa.String(24), nullable=False, server_default="skipped"),
        sa.Column("rolled_back", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("approval_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_action_executions_run_id", "action_executions", ["run_id"])

    op.create_table(
        "approvals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("action_execution_id", sa.Integer(), sa.ForeignKey("action_executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(32), nullable=False, server_default=""),
        sa.Column("severity", sa.String(16), nullable=False, server_default=""),
        sa.Column("criticality", sa.String(2), nullable=False, server_default=""),
        sa.Column("required_tier", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("on_timeout", sa.String(16), nullable=False, server_default="escalate"),
        sa.Column("approver", sa.String(64), nullable=True),
        sa.Column("note", sa.String(512), nullable=False, server_default=""),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_approvals_action_execution_id", "approvals", ["action_execution_id"])
    op.create_index("ix_approvals_run_id", "approvals", ["run_id"])
    op.create_index("ix_approvals_status", "approvals", ["status"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipient_role", sa.String(32), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False, server_default="info"),
        sa.Column("title", sa.String(160), nullable=False, server_default=""),
        sa.Column("body", sa.String(512), nullable=False, server_default=""),
        sa.Column("ref_type", sa.String(32), nullable=True),
        sa.Column("ref_id", sa.Integer(), nullable=True),
        sa.Column("read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notifications_recipient_role", "notifications", ["recipient_role"])
    op.create_index("ix_notifications_read", "notifications", ["read"])

    op.create_table(
        "break_glass",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("activated_by", sa.String(64), nullable=False),
        sa.Column("reason", sa.String(512), nullable=False, server_default=""),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("break_glass")
    op.drop_index("ix_notifications_read", table_name="notifications")
    op.drop_index("ix_notifications_recipient_role", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_approvals_status", table_name="approvals")
    op.drop_index("ix_approvals_run_id", table_name="approvals")
    op.drop_index("ix_approvals_action_execution_id", table_name="approvals")
    op.drop_table("approvals")
    op.drop_index("ix_action_executions_run_id", table_name="action_executions")
    op.drop_table("action_executions")
    op.drop_index("ix_playbook_runs_status", table_name="playbook_runs")
    op.drop_index("ix_playbook_runs_incident_id", table_name="playbook_runs")
    op.drop_index("ix_playbook_runs_playbook_id", table_name="playbook_runs")
    op.drop_table("playbook_runs")
    op.drop_index("ix_playbooks_trigger_technique", table_name="playbooks")
    op.drop_index("ix_playbooks_code", table_name="playbooks")
    op.drop_table("playbooks")
