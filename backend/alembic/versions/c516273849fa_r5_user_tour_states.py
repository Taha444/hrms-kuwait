# -*- coding: utf-8 -*-
"""R5 §3 — UserTourState table

Revision ID: c516273849fa
Revises: b405162738e9
Create Date: 2026-08-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c516273849fa"
down_revision: Union[str, None] = "b405162738e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_tour_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("tour_key", sa.String(60), nullable=False, index=True),
        sa.Column("completed_at", sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("skipped", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("step_reached", sa.Integer(), nullable=True),
        sa.UniqueConstraint("user_id", "tour_key", name="uq_tour_user_key"),
    )


def downgrade() -> None:
    op.drop_table("user_tour_states")
