# -*- coding: utf-8 -*-
"""GC-03 — حقول يطلبها نموذج العقد الحكومي ولم يكن لها مصدر.

النموذج الرسمي يطلب في خانة «الطرف الأول» اسمَ ممثّل الشركة ورقمَه المدني،
وفي الترويسة إدارةَ العمل المختصّة. ولم يوجد لهذه الثلاثة عمود في النظام:
فكان العقد يطبع اسم الشركة في خانة اسم الممثّل، والبطاقة المدنية فارغة،
وإدارة العمل قيمة عيّنة من عقد منشأة أخرى.

ولا تُشتقّ من شيء: من يوقّع عن الشركة قرار إداري، والمحافظة قائمة مغلقة
لا تُستخرج من عنوان نصّي حر.

Revision ID: u0m1n2o3p4q
Revises: t9l0m1n2o3p
"""
import sqlalchemy as sa
from alembic import op

from app.migration_ops import add_column

revision = "u0m1n2o3p4q"
down_revision = "t9l0m1n2o3p"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column("companies", sa.Column("representative_name", sa.String(160)))
    add_column("companies", sa.Column("representative_name_en", sa.String(160)))
    add_column("companies", sa.Column("representative_civil_id", sa.String(20)))
    add_column("branches", sa.Column("governorate", sa.String(40)))
    add_column("branches", sa.Column("governorate_en", sa.String(40)))


def downgrade() -> None:
    # لا حذف: الأعمدة تحمل بيانات أدخلها العميل، وإسقاطها يفقدها بلا رجعة.
    pass
