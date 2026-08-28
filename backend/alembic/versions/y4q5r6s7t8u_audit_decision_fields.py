# -*- coding: utf-8 -*-
"""BKL-02 — حقول التدقيق المركزي لقرارات المسار.

كل حدث قرار يجب أن يحمل الفاعل والفاعل الأصلي والدور والشركة والفرع
والكيان والفعل والنتيجة وقبل/بعد والسبب والعنوان والمتصفّح ومعرّف الربط
والوقت. وكان أربعة منها غير مُهيكَلة: الدور والفرع يُستنتجان من ملف
المستخدم **اليوم** لا وقت الفعل، والنتيجة والسبب يُدسّان في نصّ حرّ فلا
يُصفّى عليهما ولا يُعدّان.

Revision ID: y4q5r6s7t8u
Revises: x3p4q5r6s7t
"""
import sqlalchemy as sa
from alembic import op

from app.migration_ops import add_column

revision = "y4q5r6s7t8u"
down_revision = "x3p4q5r6s7t"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column("audit_log", sa.Column("actor_role", sa.String(40)))
    add_column("audit_log", sa.Column("branch_id", sa.Integer))
    add_column("audit_log", sa.Column("result", sa.String(12)))
    add_column("audit_log", sa.Column("reason", sa.String(500)))


def downgrade() -> None:
    # لا حذف: الأعمدة تحمل أثر قرارات، وإسقاطها يمحو دليًلا لا يُستعاد.
    pass
