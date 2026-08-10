# -*- coding: utf-8 -*-
"""Add User.avatar_path + avatar_updated_at.

Revision ID: l5e6f7g8h9i
Revises: k4d5e6f7g8h
Create Date: 2026-08-10

R9 §17 — صورة البروفايل: كل مستخدم يقدر يرفع صورته لتحل محل الأيقونة الافتراضية
في الـTopBar وأي مكان يظهر فيه اسمه.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "l5e6f7g8h9i"
down_revision: Union[str, None] = "k4d5e6f7g8h"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("avatar_path", sa.String(400), nullable=True))
        batch.add_column(sa.Column("avatar_updated_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("avatar_updated_at")
        batch.drop_column("avatar_path")
