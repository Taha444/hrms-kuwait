# -*- coding: utf-8 -*-
"""QA-07 — REQSIG مرئي للموظف.

طلب تغيير التوقيع خدمة ذاتية: الموظف صاحبه الوحيد. لكنه سُجّل في
DEFAULT_REQUEST_TYPES بلا visible_to_employee فورث الافتراضي False المخصّص
لإجراءات ADM* الداخلية — فاختفى من شاشة "طلب جديد" عنده.

تصحيح التعريف وحده لا يكفي: catalog_seed يُدرج ولا يُحدِّث
(``if rt["code"] in existing_rt: continue``)، فالصف موجود في الإنتاج بقيمته
الخاطئة ولن يمسّه البذر أبًدا. هذا الترحيل هو ما يوصل التصحيح فعًلا.

يقتصر على الصفوف العامة (company_id IS NULL) وعلى الكود REQSIG وحده حتى لا
يدهس أي تخصيص أجرته شركة على أنواعها.

Revision ID: y8r9s0t1u2v
Revises: x7q8r9s0t1u
"""
from alembic import op
import sqlalchemy as sa

revision = "y8r9s0t1u2v"
down_revision = "x7q8r9s0t1u"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(
        "UPDATE request_types SET visible_to_employee = true "
        "WHERE code = 'REQSIG' AND company_id IS NULL"
    ))


def downgrade() -> None:
    op.execute(sa.text(
        "UPDATE request_types SET visible_to_employee = false "
        "WHERE code = 'REQSIG' AND company_id IS NULL"
    ))
