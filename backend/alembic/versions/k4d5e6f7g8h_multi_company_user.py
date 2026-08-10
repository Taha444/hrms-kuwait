# -*- coding: utf-8 -*-
"""Add User.is_cross_company + user_company_links table (multi-company delegates).

Revision ID: k4d5e6f7g8h
Revises: j3c4d5e6f7g
Create Date: 2026-08-10

R9 §16 — دعم المستخدم متعدد الشركات (مثل المندوب محمد فاروق اللي يخدم
شركتين): عند التفعيل، company_id=NULL، والحساب يُربط بشركات متعددة عبر
جدول user_company_links (سطر لكل شركة). عند الدخول → يختار → الـJWT
يحمل active_company_id → السيرفر يحسم company_id + employee_id لكل طلب.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "k4d5e6f7g8h"
down_revision: Union[str, None] = "j3c4d5e6f7g"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) عمود flag على users
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column(
            "is_cross_company", sa.Boolean(), nullable=False, server_default=sa.false()
        ))

    # 2) جدول العضويات
    op.create_table(
        "user_company_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"),
                  nullable=False, index=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("role", sa.String(30), nullable=False, server_default="delegate"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("user_id", "company_id", name="uq_user_company_link"),
    )


def downgrade() -> None:
    op.drop_table("user_company_links")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("is_cross_company")
