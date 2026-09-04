# -*- coding: utf-8 -*-
"""P11-35 — الفعل الذي اتّخذه الإنسان على قرار الطلب.

``decision`` ثلاث قيم يفرّع عليها المحرّك، والأفعال المعروضة تسعة. من
ضغط «البيانات صحيحة» أو «تمّ التنفيذ» أو «علمت» كان يُسجَّل «اعتمد».

Revision ID: e9f0a1b2c3d
Revises: d8e9f0a1b2c
"""
from alembic import op
import sqlalchemy as sa

revision = "e9f0a1b2c3d"
down_revision = "d8e9f0a1b2c"
branch_labels = None
depends_on = None


def upgrade():
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(
        "request_approvals")}
    if "action" not in cols:
        op.add_column("request_approvals",
                      sa.Column("action", sa.String(length=30), nullable=True))


def downgrade():
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(
        "request_approvals")}
    if "action" in cols:
        op.drop_column("request_approvals", "action")
