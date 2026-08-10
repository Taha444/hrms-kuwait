# -*- coding: utf-8 -*-
"""Add User.signature_version counter.

Revision ID: o8h9i0j1k2l
Revises: n7g8h9i0j1k
Create Date: 2026-08-10

P1-#15 — عدّاد نسخة التوقيع: يبدأ من 0 (بلا توقيع)، يُبدَّل مع كل approve
لاستبدال التوقيع. يظهر في audit trail وفي كل مستند مُصدَر (signature_version).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "o8h9i0j1k2l"
down_revision: Union[str, None] = "n7g8h9i0j1k"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column(
            "signature_version", sa.Integer(), nullable=False, server_default="0"
        ))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("signature_version")
