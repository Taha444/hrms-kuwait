"""V2.2 §21 — Audit expanded fields (original_actor + UA + correlation + before/after)

Revision ID: 2b1c2d3e4f50
Revises: 1a0b1c2d3e4f
Create Date: 2026-07-22 01:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2b1c2d3e4f50"
down_revision: Union[str, None] = "1a0b1c2d3e4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("audit_log", sa.Column("original_user_id", sa.Integer(), nullable=True))
    op.add_column("audit_log", sa.Column("user_agent", sa.String(length=400), nullable=True))
    op.add_column("audit_log", sa.Column("correlation_id", sa.String(length=80), nullable=True))
    op.add_column("audit_log", sa.Column("before_json", sa.JSON(), nullable=True))
    op.add_column("audit_log", sa.Column("after_json", sa.JSON(), nullable=True))
    op.create_index("ix_audit_log_correlation_id", "audit_log", ["correlation_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_correlation_id", "audit_log")
    for col in ("after_json", "before_json", "correlation_id", "user_agent", "original_user_id"):
        op.drop_column("audit_log", col)
