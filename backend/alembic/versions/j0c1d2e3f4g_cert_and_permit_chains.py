# -*- coding: utf-8 -*-
"""AC-11/DOC-01/DOC-11 — سلسلة شهادة الراتب وتجديد إذن العمل.

- شهادة الراتب: تُولَّد من بيانات معتمَدة أصًلا، فمرحلة المدير العام شكلية —
  لا يقرّر شيًئا ويؤخّر شهادة يحتاجها الموظف اليوم لبنك أو سفارة. ختم HR وحده.
- تجديد إذن العمل: لا يولّد النظام مستنًدا. الإذن تُصدره الهيئة العامة للقوى
  العاملة، وأي ورقة يولّدها النظام بشكله انتحال صفة جهة حكومية.

catalog_seed يُدرج ولا يُحدِّث، فتصحيح التعريف لا يبلغ قاعدة قائمة.

Revision ID: j0c1d2e3f4g
Revises: i9b0c1d2e3f
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "j0c1d2e3f4g"
down_revision = "i9b0c1d2e3f"
branch_labels = None
depends_on = None

CERT_NEW = [
    {"order": 0, "label": "اعتماد شؤون الموظفين/القانونية", "role": "hr",
     "kind": "approval", "step_type": "DECISION", "produces_document": True},
]
CERT_OLD = [
    {"order": 0, "label": "اعتماد المدير العام", "role": "company_manager",
     "kind": "approval", "step_type": "DECISION", "produces_document": False},
    {"order": 1, "label": "اعتماد شؤون الموظفين/القانونية", "role": "hr",
     "kind": "approval", "step_type": "DECISION", "produces_document": True},
]


def _set_chain(code, chain):
    op.get_bind().execute(
        sa.text("UPDATE request_types SET approval_chain_json = :c "
                "WHERE code = :k AND company_id IS NULL"),
        {"c": json.dumps(chain, ensure_ascii=False), "k": code})


def _wp_chain(last_produces: bool):
    return [
        {"order": 0, "label": "اعتماد شؤون الموظفين/القانونية", "role": "hr",
         "kind": "approval", "step_type": "DECISION", "produces_document": False},
        {"order": 1, "label": "اعتماد المدير العام", "role": "company_manager",
         "kind": "approval", "step_type": "DECISION", "produces_document": False},
        {"order": 2, "label": "اعتماد المندوب", "role": "delegate",
         "kind": "approval", "step_type": "DECISION",
         "produces_document": last_produces},
    ]


def upgrade() -> None:
    _set_chain("REQCERTSAL", CERT_NEW)
    _set_chain("REQWP", _wp_chain(False))
    op.get_bind().execute(sa.text(
        "UPDATE request_types SET produces_document = false "
        "WHERE code = 'REQWP' AND company_id IS NULL"))


def downgrade() -> None:
    _set_chain("REQCERTSAL", CERT_OLD)
    _set_chain("REQWP", _wp_chain(True))
    op.get_bind().execute(sa.text(
        "UPDATE request_types SET produces_document = true "
        "WHERE code = 'REQWP' AND company_id IS NULL"))
