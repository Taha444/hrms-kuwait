# -*- coding: utf-8 -*-
"""Enable V1.5 canonical flags globally (company_id=NULL rows).

Revision ID: m6f7g8h9i0j
Revises: l5e6f7g8h9i
Create Date: 2026-08-10

P0-#5 — على الإنتاج نفعّل V15_LEGACY_CATALOG_HIDDEN + V15_CANONICAL_DISPLAY
عالميًا بحيث:
- /requests/types (dropdown في UI) يعرض canonical فقط (يخفي legacy)
- الأكواد المعروضة هي canonical (WF-*/REQ-*) بدل leave/salary_certificate
- Backend يرفض تلقائيًا POST بكود legacy (كود موجود في requests.py::submit_request)

الـcode default لا يزال False (لعدم كسر التسات)، لكن السجلات المُدرَجة هنا
تعلو على default الكود. الإدارة تقدر تعيدها False لأي شركة عبر /feature-flags.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = "m6f7g8h9i0j"
down_revision: Union[str, None] = "l5e6f7g8h9i"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_FLAGS_TO_ENABLE = [
    "v15_canonical_display",
    "v15_legacy_catalog_hidden",
    "v15_status_labels",
    "v15_document_lifecycle",
    "v15_step_type_actions",
]


def upgrade() -> None:
    conn = op.get_bind()
    for key in _FLAGS_TO_ENABLE:
        exists = conn.execute(
            text("SELECT id FROM feature_flags WHERE key = :k AND company_id IS NULL LIMIT 1"),
            {"k": key},
        ).first()
        if exists:
            # لو موجود بالفعل بأي قيمة، ما نتلاعب — تحكم الإدارة
            continue
        conn.execute(
            text("""
                INSERT INTO feature_flags (key, company_id, value, updated_at)
                VALUES (:k, NULL, 'on', NOW())
            """),
            {"k": key},
        )


def downgrade() -> None:
    conn = op.get_bind()
    from sqlalchemy import bindparam
    conn.execute(
        text("DELETE FROM feature_flags "
             "WHERE company_id IS NULL AND value = 'on' AND key IN :keys")
            .bindparams(bindparam("keys", expanding=True)),
        {"keys": _FLAGS_TO_ENABLE},
    )
