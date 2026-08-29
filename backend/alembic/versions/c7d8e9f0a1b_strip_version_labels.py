# -*- coding: utf-8 -*-
"""LBL-01 — إزالة وسم الإصدار الداخلي من أسماء الكتالوج

«طلب شهادة راتب (V1.3)» — رقم إصدار داخلي ظهر للمستخدم في كتالوج
الطلبات. لا يعني له شيًئا، ويوحي بأن ثمّة نسخة أخرى من الطلب عليه أن
يختار بينها.

وإصلاح النصّ في الشيفرة لا يكفي: الكتالوج **مخزَّن في القاعدة**، والصفوف
القائمة تحمل الاسم القديم. فمن يقرأ الشيفرة يراها نظيفة ومن يفتح الشاشة
يرى الوسم.

والتنظيف بنمط لا باسم واحد: أي «(V1.3)» أو «(V2.2)» يُزال أينما كان،
فلا يعود الوسم بصيغة أخرى في صفّ لم نره.

Revision ID: c7d8e9f0a1b
Revises: b6c7d8e9f0a
"""
import re

from alembic import op
import sqlalchemy as sa

revision = "c7d8e9f0a1b"
down_revision = "b6c7d8e9f0a"
branch_labels = None
depends_on = None

_MARKER = re.compile(r"\s*\(\s*[Vv]\d+(?:\.\d+)*\s*\)")

_TARGETS = (
    ("request_types", ("name", "name_en")),
    ("document_templates", ("name", "name_en")),
)


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    tables = set(insp.get_table_names())
    fixed = 0

    for table, fields in _TARGETS:
        if table not in tables:
            continue
        cols = {c["name"] for c in insp.get_columns(table)}
        present = [f for f in fields if f in cols]
        if not present:
            continue
        sel = ", ".join(["id"] + present)
        for row in conn.execute(sa.text(f"SELECT {sel} FROM {table}")):
            data = row._mapping
            updates = {}
            for f in present:
                value = data.get(f)
                if not value:
                    continue
                cleaned = _MARKER.sub("", value).strip()
                if cleaned != value:
                    updates[f] = cleaned
            if updates:
                assigns = ", ".join(f"{k} = :{k}" for k in updates)
                conn.execute(sa.text(f"UPDATE {table} SET {assigns} WHERE id = :id"),
                             {**updates, "id": data["id"]})
                fixed += 1

    print(f"[migration {revision}] نُظّف وسم الإصدار من {fixed} صًفا")


def downgrade() -> None:
    # لا رجعة: الوسم عيب لا ميزة، وإعادته تُفسد ما أُصلح.
    pass
