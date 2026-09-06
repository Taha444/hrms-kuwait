# -*- coding: utf-8 -*-
"""بصمة الطلب — إرسالان متطابقان لا يصيران طلبين.

قِيس على البناء الحالي: ثلاث ضغطات على الزرّ نفسه أنتجت ثلاثة طلبات
حيّة. والسبب المعتاد ليس سوء نية بل ضغطة مزدوجة أو إعادة محاولة بعد
انقطاع شبكة أو تحديث الصفحة بعد الإرسال.

**والقيد جزئي بقصد**: يشمل الطلب المفتوح وحده. فبعد رفضه أو إلغائه
يخرج الصفّ من القيد وتُقبل إعادة التقديم — وهي حالة مشروعة لا تكرار.

**والفحص قبل الإدراج لا يكفي**: طلبان في اللحظة نفسها يجتازانه معًا،
فالقيد هو ما يحسم السباق.

Revision ID: a7b8c9d0e1f
Revises: f6a7b8c9d0e
"""
import hashlib
import json

from alembic import op
import sqlalchemy as sa

revision = "a7b8c9d0e1f"
down_revision = "f6a7b8c9d0e"
branch_labels = None
depends_on = None

INDEX = "uq_request_open_fingerprint"


def _fingerprint(employee_id, type_code, payload) -> str:
    """نسخة مطابقة لـ``workflow.request_fingerprint``.

    ولا تُستورَد منه: الترحيل يجب أن يبقى صالًحا لو تغيّر الكود بعده —
    وهو يصف الحالة عند لحظته لا الحالة الحاليّة.
    """
    if isinstance(payload, str):
        try:
            payload = json.loads(payload or "{}")
        except ValueError:
            payload = {}
    body = json.dumps(payload or {}, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), default=str)
    return hashlib.sha256(
        f"{employee_id}|{type_code}|{body}".encode("utf-8")).hexdigest()


def upgrade():
    op.add_column("requests",
                  sa.Column("dedup_fingerprint", sa.String(64), nullable=True))
    op.create_index("ix_requests_dedup_fingerprint", "requests",
                    ["dedup_fingerprint"])

    # تعبئة الطلبات المفتوحة القائمة: بلا هذا لا يحرسها القيد، فيمكن
    # تكرار طلب مفتوح **موجود اليوم**.
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "SELECT id, employee_id, request_type_code, payload_json "
        "FROM requests WHERE closed_at IS NULL")).fetchall()
    seen: set[str] = set()
    for rid, emp_id, code, payload in rows:
        fp = _fingerprint(emp_id, code, payload)
        # ولا تُوسَم النسخة الثانية من تكرار قائم: القيد سيرفض إنشاءه،
        # والصفّ التاريخي يبقى كما هو — لا نحذف ولا ندمج بأثر رجعي.
        if fp in seen:
            continue
        seen.add(fp)
        conn.execute(sa.text("UPDATE requests SET dedup_fingerprint = :f "
                             "WHERE id = :i"), {"f": fp, "i": rid})

    # قيد فريد **جزئي**: المفتوح وحده. SQLite وPostgres يدعمان ``WHERE``.
    op.execute(sa.text(
        f"CREATE UNIQUE INDEX {INDEX} ON requests (dedup_fingerprint) "
        "WHERE dedup_fingerprint IS NOT NULL AND closed_at IS NULL"))


def downgrade():
    op.execute(sa.text(f"DROP INDEX IF EXISTS {INDEX}"))
    op.drop_index("ix_requests_dedup_fingerprint", table_name="requests")
    op.drop_column("requests", "dedup_fingerprint")
