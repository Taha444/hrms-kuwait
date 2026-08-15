# -*- coding: utf-8 -*-
"""RW-11 — تغيير الحساب البنكي: تحقّق HR من الهوية قبل المراجع المالي.

كانت السلسلة تبدأ بالمحاسب مباشرة بلا تثبّت من أن طالب التغيير هو صاحب الحساب
فعًلا — وهذا أشيع مسار احتيال داخلي في أنظمة الرواتب: رسالة "غيّروا حسابي"
تمرّ بلا تحقّق من هوية مرسلها.

catalog_seed يُدرج ولا يُحدِّث، فتصحيح التعريف لا يبلغ قاعدة قائمة.

Revision ID: h8a9b0c1d2e
Revises: g7z8a9b0c1d
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "h8a9b0c1d2e"
down_revision = "g7z8a9b0c1d"
branch_labels = None
depends_on = None

NEW = [
    {"order": 0, "label": "تحقّق شؤون الموظفين/القانونية", "role": "hr",
     "kind": "approval", "step_type": "VALIDATION", "produces_document": False},
    {"order": 1, "label": "اعتماد المحاسب", "role": "accountant",
     "kind": "approval", "step_type": "DECISION", "produces_document": False},
    {"order": 2, "label": "اعتماد المدير العام", "role": "company_manager",
     "kind": "approval", "step_type": "DECISION", "produces_document": False},
]
OLD = [
    {"order": 0, "label": "اعتماد المحاسب", "role": "accountant",
     "kind": "approval", "step_type": "DECISION", "produces_document": False},
    {"order": 1, "label": "اعتماد المدير العام", "role": "company_manager",
     "kind": "approval", "step_type": "DECISION", "produces_document": False},
]


def _set(chain):
    op.get_bind().execute(
        sa.text("UPDATE request_types SET approval_chain_json = :c "
                "WHERE code = 'REQBANK' AND company_id IS NULL"),
        {"c": json.dumps(chain, ensure_ascii=False)})


def upgrade() -> None:
    _set(NEW)


def downgrade() -> None:
    _set(OLD)
