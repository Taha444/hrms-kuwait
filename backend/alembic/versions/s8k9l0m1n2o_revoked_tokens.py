# -*- coding: utf-8 -*-
"""جدول الرموز المُبطلة — ليُنهي «الخروج» الجلسة فعًلا.

JWT لا يُسترجع: من حمله ظلّ صالًحا حتى انقضاء مدّته. فكان الخروج يمسح
الرمز من المتصفح ولا يمسّ الرمز نفسه، وكذلك «إنهاء الانتحال». هذا الجدول
هو ما يجعل الزرّين يفعلان ما يقولانه.

Revision ID: s8k9l0m1n2o
Revises: r7j8k9l0m1n
"""
import sqlalchemy as sa
from alembic import op

revision = "s8k9l0m1n2o"
down_revision = "r7j8k9l0m1n"
branch_labels = None
depends_on = None

TABLE = "revoked_tokens"


def upgrade() -> None:
    bind = op.get_bind()
    if TABLE in sa.inspect(bind).get_table_names():
        return                      # قابل لإعادة التشغيل
    op.create_table(
        TABLE,
        sa.Column("jti", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("revoked_at", sa.DateTime, nullable=True),
        sa.Column("reason", sa.String(40), nullable=True),
    )
    # الفهرس على expires_at لأجل التنظيف الدوري وحده — البحث في مسار الطلب
    # يقع على المفتاح الأساسي (jti) فلا يحتاج فهرًسا إضافيًّا.
    op.create_index("ix_revoked_tokens_expires_at", TABLE, ["expires_at"])


def downgrade() -> None:
    bind = op.get_bind()
    if TABLE in sa.inspect(bind).get_table_names():
        op.drop_index("ix_revoked_tokens_expires_at", table_name=TABLE)
        op.drop_table(TABLE)
