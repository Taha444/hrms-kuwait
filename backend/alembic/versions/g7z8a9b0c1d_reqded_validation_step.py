# -*- coding: utf-8 -*-
"""V2.2 §13.3 (AC-03) — خطوة HR في اعتراض الخصم تحقّق لا قرار مالي.

كل خطوة في السلسلة كانت "اعتماًدا"، فمن يتحقّق من صحة بيانات الخصم يحتاج
صلاحية القرار المالي نفسها التي يحتاجها من يقرّر صرفه — ومتى مُنحت له لأجل
خطوته صار يملك القرار في كل الطلبات المالية.

catalog_seed يُدرج ولا يُحدِّث، فتصحيح التعريف لا يبلغ قاعدة قائمة.

Revision ID: g7z8a9b0c1d
Revises: f6y7z8a9b0c
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "g7z8a9b0c1d"
down_revision = "f6y7z8a9b0c"
branch_labels = None
depends_on = None


def _rewrite(bind, hr_step_type: str, hr_label: str):
    row = bind.execute(sa.text(
        "SELECT approval_chain_json FROM request_types "
        "WHERE code = 'REQDED' AND company_id IS NULL")).first()
    if not row or not row[0]:
        return
    chain = row[0] if isinstance(row[0], list) else json.loads(row[0])
    for s in chain:
        if s.get("role") == "hr":
            s["step_type"] = hr_step_type
            s["label"] = hr_label
    bind.execute(sa.text(
        "UPDATE request_types SET approval_chain_json = :c "
        "WHERE code = 'REQDED' AND company_id IS NULL"),
        {"c": json.dumps(chain, ensure_ascii=False)})


def upgrade() -> None:
    _rewrite(op.get_bind(), "VALIDATION", "تحقّق شؤون الموظفين/القانونية")


def downgrade() -> None:
    _rewrite(op.get_bind(), "DECISION", "اعتماد شؤون الموظفين/القانونية")
