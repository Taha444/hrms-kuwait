# -*- coding: utf-8 -*-
"""V2.2 §30 (DOC-10) — إلغاء المستند بلا حذف الملف.

مستند صدر ووصل جهة خارجية لا يُمحى من الوجود بضغطة؛ محوُه يُفقد القدرة على
إثبات ما صدر ولمن. يُوسَم ملغى، ورمز التحقق يُعلن ذلك لمن يفحصه.

Revision ID: k1d2e3f4g5h
Revises: j0c1d2e3f4g
"""
from alembic import op
from app.migration_ops import add_column  # يعمل على SQLite وPostgreSQL
import sqlalchemy as sa

revision = "k1d2e3f4g5h"
down_revision = "j0c1d2e3f4g"
branch_labels = None
depends_on = None

COLS = [
    ("revoked_at", lambda: sa.Column("revoked_at", sa.DateTime(), nullable=True)),
    ("revoked_by_user_id", lambda: sa.Column("revoked_by_user_id", sa.Integer(),
                                             sa.ForeignKey("users.id"), nullable=True)),
    ("revocation_reason", lambda: sa.Column("revocation_reason", sa.String(300), nullable=True)),
]


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("request_documents")}
    for name, factory in COLS:
        if name not in have:
            add_column("request_documents", factory())


def downgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("request_documents")}
    for name, _ in reversed(COLS):
        if name in have:
            op.drop_column("request_documents", name)
