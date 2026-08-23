# -*- coding: utf-8 -*-
"""RNW-08 — ربط النسخة الموقّعة بالنسخة المولّدة التي وُقّعت بالضبط.

الربط بالمعاملة وحدها لا يكفي: إعادة توليد العقد تُنشئ إصدارًا جديًدا، فلو
أعاد المندوب التوليد بعد إرسال العقد للموظف لم يعد أحد يعرف أي نسخة وقّعها
الموظف فعًلا. والسؤال يُطرح حين تعترض جهة رسمية على المستند — حينها لا تنفع
الذاكرة.

Revision ID: p5h6i7j8k9l
Revises: m3f4g5h6i7j
"""
import sqlalchemy as sa
from alembic import op

revision = "p5h6i7j8k9l"
down_revision = "m3f4g5h6i7j"
branch_labels = None
depends_on = None


def upgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("documents")}
    if "source_document_id" not in cols:
        op.add_column("documents", sa.Column("source_document_id", sa.Integer(), nullable=True))
        op.create_index("ix_documents_source_document_id", "documents", ["source_document_id"])


def downgrade() -> None:
    # لا نُسقط العمود: إسقاطه يفقد رابط الإثبات بين النسخة الموقّعة وأصلها،
    # وهو ما لا يُعاد بناؤه. التراجع يترك العمود فارًغا بلا ضرر.
    pass
