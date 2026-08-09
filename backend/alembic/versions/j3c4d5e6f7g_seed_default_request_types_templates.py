# -*- coding: utf-8 -*-
"""Seed 53 default request types + 42 document templates on any DB missing them.

Revision ID: j3c4d5e6f7g
Revises: i2b3c4d5e6f
Create Date: 2026-08-09

R9 §13 — الحل النهائي لمشكلة "الطلبات والقوالب فاضية في الإنتاج":

المشكلة الجذرية:
- Railway بيشغل alembic upgrade head → يبني Schema فقط
- بعدها bootstrap.py يفحص has_data ولو موجود يخرج بدون بذر
- بعد ما الإدارة أنشأت شركات/مستخدمين يدوي على DB الإنتاج، has_data=True من أول يوم
- النتيجة: جدول request_types و document_templates بقيا فاضيين
- الأثر: صفحة الطلبات فاضية، صفحة القوالب فاضية

الحل هنا:
- نستورد DEFAULT_REQUEST_TYPES من app.workflow (53 نوع طلب)
- نستورد DEFAULT_TEMPLATES من app.seed (42 قالب)
- نُدرج فقط الأكواد المفقودة (INSERT WHERE NOT EXISTS) — لا نمس بيانات موجودة
- Idempotent: آمن للتشغيل مرارًا (تسات + إعادة نشر)

Downgrade: يمسح الأكواد المُدرجة بواسطة هذا الـmigration فقط.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import bindparam, text


revision: str = "j3c4d5e6f7g"
down_revision: Union[str, None] = "i2b3c4d5e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """يحقن أي request types أو document templates ناقصة (company_id=NULL = عامة)."""
    # import مؤجّل — Alembic offline يفضّل top-level خفيفة
    from app.workflow import DEFAULT_REQUEST_TYPES
    from app.seed import DEFAULT_TEMPLATES
    import json

    conn = op.get_bind()

    # ─── Request Types ─────────────────────────────────────────────────
    existing_rt_codes = set(row[0] for row in conn.execute(
        text("SELECT code FROM request_types WHERE company_id IS NULL")
    ).fetchall())

    inserted_rt = 0
    for rt in DEFAULT_REQUEST_TYPES:
        if rt["code"] in existing_rt_codes:
            continue
        # approval_chain_json و template_html قد يكونا list/None
        chain_json = json.dumps(rt.get("approval_chain_json") or [], ensure_ascii=False)
        conn.execute(text("""
            INSERT INTO request_types
                (company_id, code, name, category, requires_physical_signature,
                 produces_document, approval_chain_json, template_html,
                 visible_to_employee, default_template_code, is_active, created_at)
            VALUES
                (NULL, :code, :name, :category, :req_sig, :produces, :chain, :tpl_html,
                 :visible, :default_tpl, TRUE, NOW())
        """), {
            "code": rt["code"],
            "name": rt["name"],
            "category": rt.get("category") or "عام",
            "req_sig": bool(rt.get("requires_physical_signature", False)),
            "produces": bool(rt.get("produces_document", False)),
            "chain": chain_json,
            "tpl_html": rt.get("template_html"),
            "visible": bool(rt.get("visible_to_employee", True)),
            "default_tpl": rt.get("default_template_code"),
        })
        inserted_rt += 1

    # ─── Document Templates ────────────────────────────────────────────
    existing_tpl_codes = set(row[0] for row in conn.execute(
        text("SELECT code FROM document_templates WHERE company_id IS NULL AND code IS NOT NULL")
    ).fetchall())

    inserted_tpl = 0
    for entry in DEFAULT_TEMPLATES:
        # DEFAULT_TEMPLATES = [(code, name, name_en, category, body_html), ...]
        code, name, name_en, category, body = entry
        if code in existing_tpl_codes:
            continue
        conn.execute(text("""
            INSERT INTO document_templates
                (company_id, code, name, name_en, category, body_html,
                 is_active, version, created_at)
            VALUES
                (NULL, :code, :name, :name_en, :category, :body_html,
                 TRUE, 1, NOW())
        """), {"code": code, "name": name, "name_en": name_en,
               "category": category, "body_html": body})
        inserted_tpl += 1

    print(f"[migration j3c4d5e6f7g] inserted {inserted_rt} request types + {inserted_tpl} templates")


def downgrade() -> None:
    """يشيل الأكواد اللي جاءت من DEFAULT_* فقط (يحترم أي قالب يدوي)."""
    from app.workflow import DEFAULT_REQUEST_TYPES
    from app.seed import DEFAULT_TEMPLATES

    conn = op.get_bind()

    rt_codes = [rt["code"] for rt in DEFAULT_REQUEST_TYPES]
    if rt_codes:
        conn.execute(
            text("DELETE FROM request_types "
                 "WHERE company_id IS NULL AND code IN :codes")
                .bindparams(bindparam("codes", expanding=True)),
            {"codes": rt_codes},
        )

    tpl_codes = [e[0] for e in DEFAULT_TEMPLATES]
    if tpl_codes:
        conn.execute(
            text("DELETE FROM document_templates "
                 "WHERE company_id IS NULL AND code IN :codes")
                .bindparams(bindparam("codes", expanding=True)),
            {"codes": tpl_codes},
        )
