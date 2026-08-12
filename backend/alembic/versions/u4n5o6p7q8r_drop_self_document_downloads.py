# -*- coding: utf-8 -*-
"""إسقاط self_document_downloads — تنزيل مستندات الموظف بلا قيد

الترحيل t3m4n5o6p7q أضاف الجدول ليفرض "تنزيل واحد لكل مستند". هذا عكس المطلوب:
تقرير المراجعة يذكر تقييد التنزيل بمرة واحدة كعطل، والمطلوب إتاحته بلا قيود —
مستند الموظف ملكه ويحتاجه للبنك والسفارة والجهات الحكومية.

نُسقط الجدول بدل تركه معطًلا حتى لا يبقى مخطط ميت يوحي بقاعدة لم تعد قائمة.
تسجيل التنزيلات للتدقيق يبقى في سجل التدقيق العام كما كان.

Revision ID: u4n5o6p7q8r
Revises: t3m4n5o6p7q
"""
import sqlalchemy as sa
from alembic import op

revision = "u4n5o6p7q8r"
down_revision = "t3m4n5o6p7q"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "self_document_downloads" in insp.get_table_names():
        op.drop_table("self_document_downloads")


def downgrade() -> None:
    # لا نُعيد إنشاءه: القاعدة التي كان يفرضها أُلغيت.
    pass
