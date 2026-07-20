"""SIG-01 — User.signature_path + signature_updated_at

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-07-19 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("signature_path", sa.String(length=400), nullable=True))
    op.add_column("users", sa.Column("signature_updated_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "signature_updated_at")
    op.drop_column("users", "signature_path")
