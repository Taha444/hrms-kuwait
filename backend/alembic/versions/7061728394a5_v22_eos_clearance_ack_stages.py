"""V2.2 §13 — EOS clearance + acknowledgment stages before execute

Revision ID: 7061728394a5
Revises: 6f5061728394
Create Date: 2026-07-24 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
from app.migration_ops import add_column  # يعمل على SQLite وPostgreSQL
import sqlalchemy as sa


revision: str = "7061728394a5"
down_revision: Union[str, None] = "6f5061728394"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    add_column("employees", sa.Column("pending_termination_cleared_by", sa.Integer(),
                                         sa.ForeignKey("users.id"), nullable=True))
    add_column("employees", sa.Column("pending_termination_cleared_at", sa.DateTime(), nullable=True))
    add_column("employees", sa.Column("pending_termination_clearance_note", sa.Text(), nullable=True))
    add_column("employees", sa.Column("pending_termination_acknowledged_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    for col in ("pending_termination_acknowledged_at",
                "pending_termination_clearance_note",
                "pending_termination_cleared_at",
                "pending_termination_cleared_by"):
        op.drop_column("employees", col)
