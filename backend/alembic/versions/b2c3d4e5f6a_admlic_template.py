# -*- coding: utf-8 -*-
"""ADMLIC — إزالة تصنيف تأديبي عن تجديد ترخيص شركة.

كان ``default_template_code = "HRMS-PR-022"`` وهو **«إنذار موظف»**،
فئته «الإجراءات التأديبية». والقالب لا يُرسَم منه جسم المستند، لكنه
يُشتقّ منه ``od_code`` ويُختَم ``template_code`` على الأثر — فأثرُ
تجديد ترخيص شركة كان يُحفَظ ويُصنَّف تحت فئة تأديبية.

**ولم يُستبدَل بتخمين**: لا قالب لتجديد مستند شركة في الكتالوج، ومحرّك
العرض كلّه موجَّه للموظف (يطلب ``employee_id``، ويغلّف بشبكة بيانات
موظف، ويحفظ ``entity_type="employee"``). فبلا تصنيف أصدق من تصنيف
كاذب.

**والبذر يُدرج ولا يُحدِّث** (درس QA-07): فبلا هذا الترحيل يبقى الصفّ
على الإنتاج بقيمته الخاطئة، ويستمرّ التصنيف التأديبي على كل أثر جديد.

Revision ID: b2c3d4e5f6a
Revises: a1b2c3d4e5f
"""
from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a"
down_revision = "a1b2c3d4e5f"
branch_labels = None
depends_on = None


def upgrade():
    t = sa.table("request_types",
                 sa.column("code", sa.String),
                 sa.column("default_template_code", sa.String))
    # مشروط بالقيمة الخاطئة: لو كان أحدهم قد صحّحه يدًوا فلا يُمسّ.
    op.execute(t.update()
               .where(t.c.code == "ADMLIC")
               .where(t.c.default_template_code == "HRMS-PR-022")
               .values(default_template_code=None))


def downgrade():
    t = sa.table("request_types",
                 sa.column("code", sa.String),
                 sa.column("default_template_code", sa.String))
    op.execute(t.update()
               .where(t.c.code == "ADMLIC")
               .where(t.c.default_template_code.is_(None))
               .values(default_template_code="HRMS-PR-022"))
