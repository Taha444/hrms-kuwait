"""V1.5 Phase 3 — task claim/SLA fields + approval_delegations table

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-07-12 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) توسيع جدول tasks بحقول claim + SLA
    op.add_column("tasks", sa.Column("claimed_by_user_id", sa.Integer(),
                                     sa.ForeignKey("users.id"), nullable=True))
    op.add_column("tasks", sa.Column("claimed_at", sa.DateTime(), nullable=True))
    op.add_column("tasks", sa.Column("sla_due_at", sa.DateTime(), nullable=True))
    op.add_column("tasks", sa.Column("escalated_at", sa.DateTime(), nullable=True))
    op.add_column("tasks", sa.Column("escalation_task_id", sa.Integer(),
                                     sa.ForeignKey("tasks.id"), nullable=True))
    op.create_index("ix_tasks_claimed_by_user_id", "tasks", ["claimed_by_user_id"])
    op.create_index("ix_tasks_sla_due_at", "tasks", ["sla_due_at"])

    # 2) جدول approval_delegations (تفويض مؤقت لصلاحية الاعتماد)
    op.create_table(
        "approval_delegations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("delegator_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("delegate_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.String(length=250), nullable=True),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False, server_default="all"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_approval_delegations_company_id", "approval_delegations", ["company_id"])
    op.create_index("ix_approval_delegations_delegator_user_id", "approval_delegations", ["delegator_user_id"])
    op.create_index("ix_approval_delegations_delegate_user_id", "approval_delegations", ["delegate_user_id"])


def downgrade() -> None:
    op.drop_index("ix_approval_delegations_delegate_user_id", "approval_delegations")
    op.drop_index("ix_approval_delegations_delegator_user_id", "approval_delegations")
    op.drop_index("ix_approval_delegations_company_id", "approval_delegations")
    op.drop_table("approval_delegations")
    op.drop_index("ix_tasks_sla_due_at", "tasks")
    op.drop_index("ix_tasks_claimed_by_user_id", "tasks")
    op.drop_column("tasks", "escalation_task_id")
    op.drop_column("tasks", "escalated_at")
    op.drop_column("tasks", "sla_due_at")
    op.drop_column("tasks", "claimed_at")
    op.drop_column("tasks", "claimed_by_user_id")
