"""V2.2 §9 — TOTP 2FA columns on users

Revision ID: 5e4f50617283
Revises: 4d3e4f506172
Create Date: 2026-07-22 01:45:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5e4f50617283"
down_revision: Union[str, None] = "4d3e4f506172"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("totp_secret", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("totp_confirmed", sa.Boolean(), nullable=False,
                                     server_default=sa.false()))
    op.add_column("users", sa.Column("totp_last_used_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    for col in ("totp_last_used_at", "totp_confirmed", "totp_secret"):
        op.drop_column("users", col)
