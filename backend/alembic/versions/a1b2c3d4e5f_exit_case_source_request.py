# -*- coding: utf-8 -*-
"""P6-27 — الرابط بين طلب الخروج وحالة نهاية الخدمة.

قرار المالك: حالة نهاية الخدمة هي المرجع. وهذا العمود هو **الرابط**
الذي يطلبه البند: من يقرأ الحالة يعرف من أين جاءت، ومن يقرأ الطلب يصل
إلى ما ترتّب عليه.

Revision ID: a1b2c3d4e5f
Revises: f0a1b2c3d4e
"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f"
down_revision = "f0a1b2c3d4e"
branch_labels = None
depends_on = None


def upgrade():
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("eos_cases")}
    if "source_request_id" not in cols:
        # بلا قيد مفتاح أجنبي في الترحيل: SQLite لا تضيفه بـALTER، والقيد
        # معلَن في النموذج فيُنشأ مع أي قاعدة جديدة. والعمود نفسه هو ما
        # يحمل الرابط.
        op.add_column("eos_cases",
                      sa.Column("source_request_id", sa.Integer(), nullable=True))
        op.create_index("ix_eos_cases_source_request_id", "eos_cases",
                        ["source_request_id"])


def downgrade():
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("eos_cases")}
    if "source_request_id" in cols:
        op.drop_index("ix_eos_cases_source_request_id", table_name="eos_cases")
        op.drop_column("eos_cases", "source_request_id")
