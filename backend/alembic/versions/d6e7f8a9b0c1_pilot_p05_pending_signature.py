"""PILOT-P0-5 — pending_signature_* على users (استبدال التوقيع يحتاج موافقة HR)

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-07-21 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d6e7f8a9b0c1"
down_revision: Union[str, None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("pending_signature_path", sa.String(length=400), nullable=True))
    op.add_column("users", sa.Column("pending_signature_uploaded_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("pending_signature_reason", sa.String(length=300), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "pending_signature_reason")
    op.drop_column("users", "pending_signature_uploaded_at")
    op.drop_column("users", "pending_signature_path")
