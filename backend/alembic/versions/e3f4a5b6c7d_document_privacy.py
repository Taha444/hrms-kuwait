"""مستٌند سرٌّي في ملٍّف مفتوح ليس سرًّا.

Revision ID: e3f4a5b6c7d
Revises: d2e3f4a5b6c

الأرشيف لم يكن يعرف السرّية: من يحمل ``view_documents`` يقرأ كل ما في ملف
الموظف. وأربعُة مستنداٍت سرّية تُصدَر اليوم — قرار إنذار، قرار خصم،
اتفاقية قرض، تسوية نهاية خدمة.

و``source_request_id`` به تُقرأ قاعدُة الرؤية من الطلب نفسه لا من نسخٍة
ثانية لها.
"""
from alembic import op
import sqlalchemy as sa

revision = "e3f4a5b6c7d"
down_revision = "d2e3f4a5b6c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        batch.add_column(sa.Column("is_confidential", sa.Boolean(),
                                   nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("source_request_id", sa.Integer(), nullable=True))
        # ``SET NULL``: ورقٌة رسمية صدرت لا تُمحى بمحو طلبها — تفقد
        # مصدَرها لا وجودَها، والسرّي بلا مصدٍر يُحجَب.
        batch.create_foreign_key("fk_documents_source_request", "requests",
                                 ["source_request_id"], ["id"],
                                 ondelete="SET NULL")
    op.create_index("ix_documents_source_request_id", "documents",
                    ["source_request_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_source_request_id", table_name="documents")
    with op.batch_alter_table("documents") as batch:
        batch.drop_constraint("fk_documents_source_request", type_="foreignkey")
        batch.drop_column("source_request_id")
        batch.drop_column("is_confidential")
