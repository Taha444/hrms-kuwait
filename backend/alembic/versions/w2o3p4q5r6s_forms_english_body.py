# -*- coding: utf-8 -*-
"""FRM-03 — الفقرة الإنجليزية في الصيغ الخمس بأسماء إنجليزية.

كانت تحمل الاسم والمسمّى والشركة بالعربية داخل جملة إنجليزية
(«employed as مدير الشركة since…») — خليط لا يُقرأ في أيٍّ من اللغتين،
في مستند يُقدَّم لبنك أو سفارة.

والاستبدال مقصور على وسم ``<p class='en'>``: استبدال عامّ كان سيغيّر
الفقرة العربية أيًضا فتُطبع بأسماء إنجليزية — عيب مقابل بالضبط.

Revision ID: w2o3p4q5r6s
Revises: v1n2o3p4q5r
"""
import re

import sqlalchemy as sa
from alembic import op

revision = "w2o3p4q5r6s"
down_revision = "v1n2o3p4q5r"
branch_labels = None
depends_on = None

CODES = ["HRMS-PR-001", "HRMS-PR-006", "HRMS-PR-008",
         "HRMS-PR-009", "HRMS-PR-032"]

SWAPS = {
    "{{employee_name}}": "{{employee_name_display_en}}",
    "{{job_title}}": "{{job_title_display_en}}",
    "{{company_name}}": "{{company_name_display_en}}",
}

_EN_P = re.compile(r"(<p class='en'[^>]*>)(.*?)(</p>)", re.S)


def _apply(conn, direction: str) -> int:
    changed = 0
    for code in CODES:
        row = conn.execute(sa.text(
            "SELECT id, body_html FROM document_templates WHERE code = :c"
        ), {"c": code}).fetchone()
        if not row or not row[1]:
            continue

        def swap(m):
            inner = m.group(2)
            for old, new in SWAPS.items():
                a, b = (old, new) if direction == "up" else (new, old)
                inner = inner.replace(a, b)
            return m.group(1) + inner + m.group(3)

        new_html = _EN_P.sub(swap, row[1])
        if new_html != row[1]:
            conn.execute(sa.text(
                "UPDATE document_templates SET body_html = :b WHERE id = :i"
            ), {"b": new_html, "i": row[0]})
            changed += 1
    return changed


def upgrade() -> None:
    n = _apply(op.get_bind(), "up")
    print(f"[migration w2o3p4q5r6s] عُرِّبت الفقرة الإنجليزية في {n} صيغة")


def downgrade() -> None:
    _apply(op.get_bind(), "down")
