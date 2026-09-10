# -*- coding: utf-8 -*-
"""DEC-RACE — عدّاد قرارات على الطلب يمنع سباق الاعتماد والرفض.

كل حرّاس القرار كانت «اقرأ ثم افحص» بلا قفل: طلبا اعتماد ورفض يصلان في
اللحظة نفسها فيقرآن ``pending`` والمرحلة نفسها، فيمرّان كلاهما. والمقيس:
ردّان 200، وخطٌّ زمني فيه اعتماٌد ورفض معًا، وحاٌل نهائية «مكتمل»،
**ومستٌند رسمي يُولَّد رغم وجود رفض**.

والعدّاد يجعل المطالبة ذرّية: من يُحدّث الصفّ بشرط القيمة التي قرأها يفوز،
والثاني يجد شرطه كاذًبا فيُردّ بـ409.

Revision ID: b8c9d0e1f2a
Revises: a7b8c9d0e1f
"""
from alembic import op
import sqlalchemy as sa

revision = "b8c9d0e1f2a"
down_revision = "a7b8c9d0e1f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # الصفوف القائمة تبدأ من صفر — ولا معنى لتاريخ سابق للعدّاد.
    op.add_column("requests", sa.Column(
        "decision_seq", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("requests", "decision_seq")
