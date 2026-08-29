# -*- coding: utf-8 -*-
"""IMP-01/IMP-02 — الخمول يُقاس على الجلسة لا على المستخدم

كان ``users.last_activity_at`` هو مصدر الخمول الوحيد، فجلسة الانتحال
ترث خمول من انتُحلت شخصيته وتُرفض بـ401 وهي وليدة، وجلستان لمستخدم
واحد في متصفّحين تتصارعان على صفّ واحد.

الجدول هنا يفصل النشاط لكل رمز على حدة (``jti``).

Revision ID: a5b6c7d8e9f
Revises: y4q5r6s7t8u
"""
from alembic import op
import sqlalchemy as sa

revision = "a5b6c7d8e9f"
down_revision = "y4q5r6s7t8u"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "session_activity",
        sa.Column("jti", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"),
                  nullable=True),
        sa.Column("last_activity_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("impersonated", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
    )
    op.create_index("ix_session_activity_user_id", "session_activity",
                    ["user_id"])
    op.create_index("ix_session_activity_expires_at", "session_activity",
                    ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_session_activity_expires_at",
                  table_name="session_activity")
    op.drop_index("ix_session_activity_user_id", table_name="session_activity")
    op.drop_table("session_activity")
