# -*- coding: utf-8 -*-
"""حقول التوظيف والعقد الناقصة في شاشة الموظف

مراجعة العميل (الصفحة ٣) رصدت نقص حقول في تبويب "التوظيف والعقد":
الوظيفة الفعلية، ساعات الدوام (محددة/غير محددة + الرسمية/الفعلية)، وتاريخ
انتهاء الإقامة.

- actual_job_title: يكمل ثنائية (رسمي/فعلي) القائمة أصلًا في الراتب والفرع
  والترخيص — مهنة إذن العمل قد تختلف عمّا يؤديه الموظف فعلًا.
- work_hours_type + official/actual_work_hours: الرقمان يخصّان حالة "محددة"
  فقط؛ "غير محددة" تعني طبيعة عمل بلا ساعات ثابتة.
- job_title_en / nationality_en: يحتاجهما العقد الحكومي ثنائي اللغة وكان
  يطبعهما فارغين.

تاريخ انتهاء الإقامة لا يحتاج عمودًا: موجود في permits(kind='residency').
يُعرَض في واجهة الموظف من هناك.

Revision ID: w6p7q8r9s0t
Revises: v5o6p7q8r9s
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "w6p7q8r9s0t"
down_revision: Union[str, None] = "v5o6p7q8r9s"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLS = [
    ("actual_job_title", sa.String(length=150)),
    ("job_title_en", sa.String(length=150)),
    ("nationality_en", sa.String(length=80)),
    ("work_hours_type", sa.String(length=20)),
    ("official_work_hours", sa.Float()),
    ("actual_work_hours", sa.Float()),
]


def upgrade() -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("employees")}
    for name, type_ in _COLS:
        if name not in existing:
            op.add_column("employees", sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("employees")}
    for name, _ in reversed(_COLS):
        if name in existing:
            op.drop_column("employees", name)
