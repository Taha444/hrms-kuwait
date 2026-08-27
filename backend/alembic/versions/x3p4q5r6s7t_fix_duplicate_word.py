# -*- coding: utf-8 -*-
"""BKL-04 — «طلب طلب إجازة» في نصوص الإشعارات.

أربعة وثلاثون من أربعة وخمسين نوع طلب اسمه يبدأ بـ«طلب»، وستّة قوالب
كانت تضيف الكلمة فوقه. فيقرأ الموظف «طلب طلب إجازة» في إشعار يصله على
هاتفه.

والتحديث على المحفوظ في القاعدة: قوالب الإشعارات تُبذَر مرة، وقاعدة عميل
قائمة تبقى فيها الصيغة القديمة إلى الأبد.

Revision ID: x3p4q5r6s7t
Revises: w2o3p4q5r6s
"""
import sqlalchemy as sa
from alembic import op

revision = "x3p4q5r6s7t"
down_revision = "w2o3p4q5r6s"
branch_labels = None
depends_on = None

#: (الكود، النصّ القديم، النصّ الجديد)
BODIES = [
    ("NTF-033",
     "طلب {{request_type}} من {{employee_name}} بانتظار موافقتك.",
     "{{request_type}} من {{employee_name}} بانتظار موافقتك."),
    ("NTF-034",
     "وصل طلبك ({{request_type}}) إلى مرحلة: {{stage_label}}.",
     "وصل «{{request_type}}» إلى مرحلة: {{stage_label}}."),
    ("NTF-035",
     "تم رفض طلبك ({{request_type}}). السبب: {{reason}}.",
     "رُفض «{{request_type}}». السبب: {{reason}}."),
    ("NTF-036",
     "تم إلغاء طلبك ({{request_type}}) من قبل الإدارة.",
     "أُلغي «{{request_type}}» من قبل الإدارة."),
    ("NTF-037",
     "تم إنهاء جميع مراحل طلبك ({{request_type}}) بنجاح.",
     "اكتملت جميع مراحل «{{request_type}}» بنجاح."),
    ("NTF-039",
     "طلبك ({{request_type}}) جاهز للاستلام من شؤون الموظفين.",
     "«{{request_type}}» جاهز للاستلام من شؤون الموظفين."),
]

TABLE_CANDIDATES = ("notification_templates", "notification_template")


def _table(conn) -> str | None:
    names = sa.inspect(conn).get_table_names()
    for t in TABLE_CANDIDATES:
        if t in names:
            return t
    return None


def _apply(conn, direction: str) -> int:
    table = _table(conn)
    if not table:
        return 0
    cols = {c["name"] for c in sa.inspect(conn).get_columns(table)}
    body_col = "body_text" if "body_text" in cols else (
        "body" if "body" in cols else None)
    if not body_col:
        return 0
    changed = 0
    for code, old, new in BODIES:
        a, b = (old, new) if direction == "up" else (new, old)
        row = conn.execute(sa.text(
            f"SELECT id, {body_col} FROM {table} WHERE code = :c"
        ), {"c": code}).fetchone()
        if not row or not row[1] or a not in row[1]:
            continue
        conn.execute(sa.text(
            f"UPDATE {table} SET {body_col} = :b WHERE id = :i"
        ), {"b": row[1].replace(a, b), "i": row[0]})
        changed += 1
    return changed


def upgrade() -> None:
    n = _apply(op.get_bind(), "up")
    print(f"[migration x3p4q5r6s7t] أُصلح تكرار «طلب» في {n} إشعاًرا")


def downgrade() -> None:
    _apply(op.get_bind(), "down")
