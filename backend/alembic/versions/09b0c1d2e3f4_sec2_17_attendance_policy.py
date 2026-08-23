"""SEC2-17 — attendance policy explicit fields (exempt + reason + approver)

Revision ID: 09b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-07-22 00:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
from app.migration_ops import add_column  # يعمل على SQLite وPostgreSQL
import sqlalchemy as sa


revision: str = "09b0c1d2e3f4"
down_revision: Union[str, None] = "f8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    add_column("employees", sa.Column("attendance_exempt", sa.Boolean(),
                                         nullable=False, server_default=sa.false()))
    add_column("employees", sa.Column("attendance_exempt_reason", sa.String(length=200),
                                         nullable=True))
    add_column("employees", sa.Column("attendance_exempt_approved_by", sa.Integer(),
                                         sa.ForeignKey("users.id"), nullable=True))
    add_column("employees", sa.Column("attendance_exempt_approved_at", sa.DateTime(),
                                         nullable=True))


def downgrade() -> None:
    for col in ("attendance_exempt_approved_at", "attendance_exempt_approved_by",
                "attendance_exempt_reason", "attendance_exempt"):
        op.drop_column("employees", col)
