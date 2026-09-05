# -*- coding: utf-8 -*-
"""قرار الإجازة يصدر فوًرا — لا انتظار توقيع يدوي.

كان الطلب يقف عند «بانتظار حضور الموظف للتوقيع»، ويُطلَب منه الحضور
ليوقّع باليد **ورقًة تحمل توقيعه مطبوًعا فيها أصًلا**: التوليد يسحب
``signature_path`` من حسابه ويضعه في موضعه.

وبقاؤه لم يكن اختياًرا: كانت الإجازة النوع **الوحيد** الذي يقف للتوقيع
قبل ``f0a1b2c3d4e``، فاستمرّت بحكم الحال لا بقرار.

**والعقود تبقى كما هي** (REQRESIGN · REQEOS · REQCLR).

**والبذر يُدرج ولا يُحدِّث** (درس QA-07): وبلا هذا الترحيل يبقى الصفّ
على الإنتاج مشترًطا للتوقيع، فتظلّ كل إجازة واقفة.

Revision ID: e5f6a7b8c9d
Revises: d4e5f6a7b8c
"""
from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d"
down_revision = "d4e5f6a7b8c"
branch_labels = None
depends_on = None

#: أكواد طلب الإجازة وكنياته التاريخية — الصفّ على الإنتاج قد يحمل أًيا
#: منها، فتحديث كود واحد يترك البقية واقفة.
LEAVE_CODES = ("leave", "REQLV", "annual_leave", "sick_leave")


def upgrade():
    t = sa.table("request_types",
                 sa.column("code", sa.String),
                 sa.column("requires_physical_signature", sa.Boolean))
    op.execute(t.update()
               .where(t.c.code.in_(LEAVE_CODES))
               .values(requires_physical_signature=False))


def downgrade():
    t = sa.table("request_types",
                 sa.column("code", sa.String),
                 sa.column("requires_physical_signature", sa.Boolean))
    op.execute(t.update()
               .where(t.c.code.in_(LEAVE_CODES))
               .values(requires_physical_signature=True))
