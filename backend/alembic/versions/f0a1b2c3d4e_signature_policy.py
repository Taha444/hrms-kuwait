# -*- coding: utf-8 -*-
"""P5-23 — سياسة التوقيع المادّي تبلغ القواعد القائمة.

قرار المالك: **الاستقالة وتسوية نهاية الخدمة وإخلاء الطرف تُوقَّع**،
وتُرفَع الراية عن الباقي.

**ولماذا ترحيل لا تعديل تعريف وحده**: البذر يُدرج ولا يُحدِّث (الدرس
الموثَّق في QA-07 مع ``REQSIG``). فصفّ ``request_types`` على الإنتاج
يبقى على قيمته القديمة، ويمرّ اختبار التعريف كذًبا لأنه يعمل على قاعدة
مبذورة من الصفر.

وبعد أن صار المحرّك يقرأ هذه الراية (لا بنية السلسلة)، فإن بقاءها
مرفوعة على أحد عشر نوًعا يعني توقّف طلباتها عند ``awaiting_signature``
انتظاًرا لتوقيع لم يقرّره أحد — أي أن إهمال الترحيل يُعطّل الأنواع
الأحد عشر على الإنتاج، لا يترك عيًبا صامًتا فحسب.

Revision ID: f0a1b2c3d4e
Revises: e9f0a1b2c3d
"""
from alembic import op
import sqlalchemy as sa

revision = "f0a1b2c3d4e"
down_revision = "e9f0a1b2c3d"
branch_labels = None
depends_on = None

#: تُوقَّع: قرار المالك صراحًة. و``leave`` كانت تعمل أصًلا.
SIGNED = ("leave", "REQRESIGN", "REQEOS", "REQCLR")

#: تُرفَع عنها الراية — كانت تُعلن توقيًعا ولا تطلبه أبًدا.
LIFTED = ("REQWLOC", "REQMIS", "REQRESE", "REQRESN", "REQWP", "REQTRFLIC",
          "REQTRF", "REQPROMO", "REQCON", "ADMWARN", "ADMLIC")


def _set(codes, value: bool) -> None:
    if not codes:
        return
    t = sa.table("request_types",
                 sa.column("code", sa.String),
                 sa.column("requires_physical_signature", sa.Boolean))
    op.execute(t.update()
               .where(t.c.code.in_(codes))
               .values(requires_physical_signature=value))


def upgrade():
    _set(LIFTED, False)
    _set(SIGNED, True)


def downgrade():
    # الرجوع يُعيد الحال السابق: الأحد عشر كانت تُعلن توقيًعا.
    _set(LIFTED, True)
