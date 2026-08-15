# -*- coding: utf-8 -*-
"""V2.2 §14 (RW-04) — إجازة داخل الرصيد: مدير واحد ثم تحديث الرصيد.

كانت تمرّ بأربعة معتمِدين — مسؤول الفرع والمدير العام وHR والمندوب — على
يومين إجازة. المدير العام لا يضيف قراًرا فوق قرار المسؤول المباشر: كلاهما
يجيب السؤال نفسه، والثاني يؤخّر إجازة أُقرّت فعًلا. ومراجعة HR تحقّق من الرصيد
والحضور لا قرار عليه، فصارت VALIDATION.

مرحلة المندوب تبقى مشروطة بالسفر كما هي (QA-10).

Revision ID: l2e3f4g5h6i
Revises: k1d2e3f4g5h
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "l2e3f4g5h6i"
down_revision = "k1d2e3f4g5h"
branch_labels = None
depends_on = None

DELEGATE_STAGE = {
    "label": "إجراءات إذن مغادرة البلاد (المندوب)", "role": "delegate",
    "kind": "delegate_exit",
    "when": {"field": "travel_required", "truthy": True},
}

NEW = [
    {"order": 0, "label": "اعتماد مسؤول الفرع", "role": "branch_supervisor",
     "kind": "approval", "step_type": "DECISION"},
    {"order": 1, "label": "تحديث الرصيد والحضور (شؤون الموظفين)", "role": "hr",
     "kind": "hr_review", "step_type": "VALIDATION", "produces_document": True},
    {**DELEGATE_STAGE, "order": 2},
]
OLD = [
    {"order": 0, "label": "اعتماد مسؤول الفرع", "role": "branch_supervisor", "kind": "approval"},
    {"order": 1, "label": "اعتماد المدير العام", "role": "company_manager", "kind": "approval"},
    {"order": 2, "label": "مراجعة شؤون الموظفين وتحديد موعد التوقيع", "role": "hr",
     "kind": "hr_review", "produces_document": True},
    {**DELEGATE_STAGE, "order": 3},
]


def _set(chain):
    op.get_bind().execute(
        sa.text("UPDATE request_types SET approval_chain_json = :c "
                "WHERE code = 'leave' AND company_id IS NULL"),
        {"c": json.dumps(chain, ensure_ascii=False)})


def upgrade() -> None:
    _set(NEW)


def downgrade() -> None:
    _set(OLD)
