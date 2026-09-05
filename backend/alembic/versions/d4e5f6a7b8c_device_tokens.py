# -*- coding: utf-8 -*-
"""أجهزة المستخدمين لاستقبال الإشعارات الفورية (FCM).

**جهاز لا مستخدم**: الموظف الواحد قد يفتح النظام على هاتفه وحاسبه،
ولكلٍّ رمزه. وصفّ واحد لكل مستخدم يجعل آخر جهاز يُسجَّل يُلغي ما قبله
بصمت.

و``token`` فريد **عالمًيا** لا لكل مستخدم: Firebase قد يعيد الرمز نفسه
لجهاز انتقل بين حسابين على المتصفّح ذاته — فالقيد يمنع أن يصل إشعار
زيد إلى جهاز يستعمله عمرو.

Revision ID: d4e5f6a7b8c
Revises: c3d4e5f6a7b
"""
from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c"
down_revision = "c3d4e5f6a7b"
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    if "device_tokens" in insp.get_table_names():
        return
    op.create_table(
        "device_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"),
                  nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=False,
                  server_default="web"),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_reason", sa.String(length=60), nullable=True),
        sa.UniqueConstraint("token", name="uq_device_token"),
    )
    op.create_index("ix_device_tokens_user_id", "device_tokens", ["user_id"])


def downgrade():
    insp = sa.inspect(op.get_bind())
    if "device_tokens" not in insp.get_table_names():
        return
    op.drop_index("ix_device_tokens_user_id", table_name="device_tokens")
    op.drop_table("device_tokens")
