# -*- coding: utf-8 -*-
"""V2.2 §13.10 (AC-10) + RW-14 — إخلاء الطرف بمهام متوازية.

كان سلسلة متتابعة (المحاسب ثم HR)، فتنتظر جهةٌ دورَ أخرى وإن لم تكن بينهما
علاقة. الجهات مستقلة بطبعها: كل واحدة تعرف عهدتها ولا تعرف عهدة غيرها.

الترحيل لازم لأن catalog_seed يُدرج ولا يُحدِّث: تصحيح السلسلة في seed لا يبلغ
أي قاعدة قائمة. ولا يُمسّ صف خصّصته شركة (company_id غير فارغ).

Revision ID: e5x6y7z8a9b
Revises: d4w5x6y7z8a
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "e5x6y7z8a9b"
down_revision = "d4w5x6y7z8a"
branch_labels = None
depends_on = None

NEW_CHAIN = [
    {"order": 0, "kind": "parallel", "label": "إقرارات الجهات",
     "step_type": "VALIDATION", "produces_document": False,
     "parties": [
         {"role": "accountant", "label": "المالية — العهد والالتزامات"},
         {"role": "branch_supervisor", "label": "الفرع — عهدة الموقع"},
         {"role": "delegate", "label": "المندوب — الوثائق الحكومية",
          "when": {"field": "has_gov_documents", "truthy": True}},
     ]},
    {"order": 1, "label": "اعتماد شؤون الموظفين/القانونية", "role": "hr",
     "kind": "approval", "step_type": "DECISION", "produces_document": True},
]


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("UPDATE request_types SET approval_chain_json = :c "
                "WHERE code = 'REQCLR' AND company_id IS NULL"),
        {"c": json.dumps(NEW_CHAIN, ensure_ascii=False)},
    )


def downgrade() -> None:
    old = [
        {"order": 0, "label": "اعتماد المحاسب", "role": "accountant",
         "kind": "approval", "step_type": "DECISION", "produces_document": False},
        {"order": 1, "label": "اعتماد شؤون الموظفين/القانونية", "role": "hr",
         "kind": "approval", "step_type": "DECISION", "produces_document": True},
    ]
    op.get_bind().execute(
        sa.text("UPDATE request_types SET approval_chain_json = :c "
                "WHERE code = 'REQCLR' AND company_id IS NULL"),
        {"c": json.dumps(old, ensure_ascii=False)},
    )
