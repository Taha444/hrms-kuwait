# -*- coding: utf-8 -*-
"""V2.2 §13.5 (AC-05) — جدول break_glass_sessions.

super_admin كان يملك override_approval في كل لحظة (has_permission تعيد له True
مطلًقا)، فيعتمد أي مرحلة عمل بلا طلب ولا انتباه. صار التجاوز يحتاج نافذة
موقّتة بسبب مكتوب.

Revision ID: f6y7z8a9b0c
Revises: e5x6y7z8a9b
"""
from alembic import op
import sqlalchemy as sa

revision = "f6y7z8a9b0c"
down_revision = "e5x6y7z8a9b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "break_glass_sessions" in insp.get_table_names():
        return
    op.create_table(
        "break_glass_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), index=True),
        sa.Column("reason", sa.String(400), nullable=False),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime()),
        sa.Column("uses", sa.Integer(), server_default="0"),
    )


def downgrade() -> None:
    if "break_glass_sessions" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("break_glass_sessions")
