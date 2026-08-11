# -*- coding: utf-8 -*-
"""Immutable signature version history table.

Revision ID: q0j1k2l3m4n
Revises: p9i0j1k2l3m
Create Date: 2026-08-10

QA §12 — سجل نسخ التوقيع: صف لكل نسخة معتمَدة، لا يُحدَّث ولا يُحذَف.
يحمل سياق الفاعل (دور/شركة/فرع) وسياق الاعتماد (المُعتمِد/السبب/المرحلة)
والـcorrelation_id ورقم مرجعي فريد لكل نسخة.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "q0j1k2l3m4n"
down_revision: Union[str, None] = "p9i0j1k2l3m"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_signature_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(400), nullable=True),
        sa.Column("checksum_sha256", sa.String(64), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("actor_role", sa.String(30), nullable=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"),
                  nullable=True, index=True),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("stage", sa.String(30), nullable=False, server_default="approved"),
        sa.Column("reason", sa.String(300), nullable=True),
        sa.Column("approved_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approver_role", sa.String(30), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("correlation_id", sa.String(80), nullable=True, index=True),
        sa.Column("reference_no", sa.String(60), nullable=True, unique=True, index=True),
        sa.Column("before_json", sa.JSON(), nullable=True),
        sa.Column("after_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "version", name="uq_user_signature_version"),
    )


def downgrade() -> None:
    op.drop_table("user_signature_versions")
