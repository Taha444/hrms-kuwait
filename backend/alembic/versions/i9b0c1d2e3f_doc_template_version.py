# -*- coding: utf-8 -*-
"""V2.2 §30 (DOC-20) — تثبيت نسخة القالب على المستند الصادر.

القالب يتطوّر والمستند الصادر يبقى، وحُجّيته على نصّه لا على نصّ اليوم. بلا
هذين العمودين يستحيل بعد شهور إثبات بأي نصٍّ صدرت شهادةٌ بعينها.

Revision ID: i9b0c1d2e3f
Revises: h8a9b0c1d2e
"""
from alembic import op
import sqlalchemy as sa

revision = "i9b0c1d2e3f"
down_revision = "h8a9b0c1d2e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("request_documents")}
    if "template_code" not in cols:
        op.add_column("request_documents", sa.Column("template_code", sa.String(50), nullable=True))
    if "template_version" not in cols:
        op.add_column("request_documents", sa.Column("template_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("request_documents")}
    for c in ("template_version", "template_code"):
        if c in cols:
            op.drop_column("request_documents", c)
