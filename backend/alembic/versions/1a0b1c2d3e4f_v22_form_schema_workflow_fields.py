"""V2.2 — form_schema_json + workflow needs_info/cancel fields

Revision ID: 1a0b1c2d3e4f
Revises: 09b0c1d2e3f4
Create Date: 2026-07-22 00:45:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1a0b1c2d3e4f"
down_revision: Union[str, None] = "09b0c1d2e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("request_types", sa.Column("form_schema_json", sa.JSON(), nullable=True))
    op.add_column("requests", sa.Column("needs_info_note", sa.Text(), nullable=True))
    op.add_column("requests", sa.Column("cancelled_by_user_id", sa.Integer(),
                                        sa.ForeignKey("users.id"), nullable=True))
    op.add_column("requests", sa.Column("cancelled_at", sa.DateTime(), nullable=True))
    op.add_column("requests", sa.Column("cancel_reason", sa.String(length=300), nullable=True))


def downgrade() -> None:
    for col in ("cancel_reason", "cancelled_at", "cancelled_by_user_id", "needs_info_note"):
        op.drop_column("requests", col)
    op.drop_column("request_types", "form_schema_json")
