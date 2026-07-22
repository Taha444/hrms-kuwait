"""V2.2 §9 — Session revocation via tokens_valid_after

Revision ID: 4d3e4f506172
Revises: 3c2d3e4f5061
Create Date: 2026-07-22 01:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4d3e4f506172"
down_revision: Union[str, None] = "3c2d3e4f5061"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("tokens_valid_after", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "tokens_valid_after")
