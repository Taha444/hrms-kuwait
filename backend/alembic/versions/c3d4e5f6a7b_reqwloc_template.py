# -*- coding: utf-8 -*-
"""REQWLOC — قالب التكليف بموقع يبلغ القواعد القائمة.

كان النوع يُنتج مستنًدا **بلا قالب إطلاًقا**: فأثره يخرج بلا صنف
(``od_code = None``) ولا نصّ مثبَّت (``template_version``). ومساره
``WF-018`` يعلن ``OD-005`` — فالسجلّ يقول أيّ **مستند** ولا يقول أيّ
**قالب** من ثمانية تشير إليه.

وحسمه المالك: ``HRMS-PR-017`` «قرار تكليف بفرع أو موقع عمل». والاختيار
موافق للسجلّ لا للاسم وحده — ``PR-017 → OD-005`` وهو ما يعلنه المسار.

**والبذر يُدرج ولا يُحدِّث** (درس QA-07): فبلا هذا الترحيل يبقى الصفّ
على الإنتاج بلا قالب، ويستمرّ كل أثر جديد بلا صنف.

Revision ID: c3d4e5f6a7b
Revises: b2c3d4e5f6a
"""
from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b"
down_revision = "b2c3d4e5f6a"
branch_labels = None
depends_on = None

CODE = "HRMS-PR-017"


def upgrade():
    bind = op.get_bind()
    # لا يُربَط النوع بقالب غير موجود: ربط بلا قالب يترك الأثر بلا صنف،
    # وهو الحال الذي نُصلحه — فلا يُستبدَل بحال مثله.
    exists = bind.execute(sa.text(
        "SELECT 1 FROM document_templates WHERE code = :c LIMIT 1"
    ), {"c": CODE}).first()
    if not exists:
        return

    t = sa.table("request_types",
                 sa.column("code", sa.String),
                 sa.column("default_template_code", sa.String))
    # مشروط بالفراغ: لو أُسنِد قالب يدًوا فلا يُمسّ.
    op.execute(t.update()
               .where(t.c.code == "REQWLOC")
               .where(t.c.default_template_code.is_(None))
               .values(default_template_code=CODE))


def downgrade():
    t = sa.table("request_types",
                 sa.column("code", sa.String),
                 sa.column("default_template_code", sa.String))
    op.execute(t.update()
               .where(t.c.code == "REQWLOC")
               .where(t.c.default_template_code == CODE)
               .values(default_template_code=None))
