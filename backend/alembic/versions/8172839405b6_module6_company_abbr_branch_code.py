"""V2.2 Module 6 — Company.abbreviation + Branch.code for Employee ID format

Revision ID: 8172839405b6
Revises: 7061728394a5
Create Date: 2026-07-24 00:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8172839405b6"
down_revision: Union[str, None] = "7061728394a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("abbreviation", sa.String(length=6), nullable=True))
    op.add_column("branches", sa.Column("code", sa.String(length=6), nullable=True))


def downgrade() -> None:
    op.drop_column("branches", "code")
    op.drop_column("companies", "abbreviation")
