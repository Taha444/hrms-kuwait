# -*- coding: utf-8 -*-
"""Add name_en column to branches (schema-only, no data change)

Revision ID: e738495061bc
Revises: d627384950ab
Create Date: 2026-08-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e738495061bc"
down_revision: Union[str, None] = "d627384950ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("branches", sa.Column("name_en", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("branches", "name_en")
