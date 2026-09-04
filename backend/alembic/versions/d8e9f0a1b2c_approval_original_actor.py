# -*- coding: utf-8 -*-
"""P11-36 — الفاعل الحقيقي على قرار الطلب.

القرار كان يُنسَب إلى المنتحَل وحده. سجلّ التدقيق يحمل
``original_user_id``، لكن من يقرأ الطلب لا يقرأ التدقيق — ويرى اسًما
لم يتّخذ القرار.

Revision ID: d8e9f0a1b2c
Revises: c7d8e9f0a1b
"""
from alembic import op
import sqlalchemy as sa

revision = "d8e9f0a1b2c"
down_revision = "c7d8e9f0a1b"
branch_labels = None
depends_on = None


def upgrade():
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(
        "request_approvals")}
    if "original_user_id" not in cols:
        op.add_column("request_approvals",
                      sa.Column("original_user_id", sa.Integer(), nullable=True))


def downgrade():
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(
        "request_approvals")}
    if "original_user_id" in cols:
        op.drop_column("request_approvals", "original_user_id")
