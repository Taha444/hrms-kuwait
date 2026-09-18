# -*- coding: utf-8 -*-
"""مخطط قاعدة البيانات (DLV-44) — يُولَّد من النماذج، لا يُكتب باليد.

كلُّ جدوٍل بأعمدته وأنواعها وقيودها وعلاقاته، ووصفُه من السطر الأول لشرح
نموذجه — فالوصُف والجدول مصدٌر واحد. ويحرسه
``tests/test_zzz_db_schema_doc.py``: من يضيف عمودًا يُعيد التوليد.

يُشغَّل::

    backend/.venv/Scripts/python.exe backend/scripts/db_schema_doc.py
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

OUT = ROOT / "docs" / "DATABASE_SCHEMA.md"


def _first_line(cls) -> str:
    # شرُح النموذج نفسه لا الموروث: ``inspect.getdoc`` يصعد إلى ``Base``
    # فيصف كلَّ جدوٍل بلا شرٍح بـ«القاعدة المشتركة لكل النماذج».
    doc = inspect.cleandoc(cls.__dict__.get("__doc__") or "")
    line = doc.strip().splitlines()[0] if doc.strip() else ""
    return line.replace("|", "/")


def render() -> str:
    from app import models
    from app.database import Base

    by_table = {}
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        by_table[cls.__table__.name] = cls

    L = ["# مخطط قاعدة البيانات (DLV-44)", "",
         "> **مولَّد من النماذج** بـ`backend/scripts/db_schema_doc.py` — لا يُحرَّر باليد.",
         "> والترحيلات في `backend/alembic/versions`؛ الإنتاج على PostgreSQL والاختبار على SQLite.", "",
         f"عدد الجداول: **{len(Base.metadata.tables)}**.", "",
         "## الفهرس", ""]
    tables = sorted(Base.metadata.tables.values(), key=lambda t: t.name)
    for t in tables:
        cls = by_table.get(t.name)
        L.append(f"- [`{t.name}`](#{t.name.replace('_', '-')})"
                 + (f" — {_first_line(cls)}" if cls is not None and _first_line(cls) else ""))
    L.append("")
    for t in tables:
        cls = by_table.get(t.name)
        L.append(f"## {t.name}")
        L.append("")
        if cls is not None:
            L.append(f"النموذج: `models.{cls.__name__}`" + (f" — {_first_line(cls)}" if _first_line(cls) else ""))
            L.append("")
        L.append("| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |")
        L.append("|---|---|:-:|:-:|---|")
        for c in t.columns:
            fks = ", ".join(f"`{fk.target_fullname}`" for fk in c.foreign_keys)
            try:
                typ = str(c.type)
            except Exception:  # noqa: BLE001 — نوٌع لا يُطبَع بلا لهجة
                typ = type(c.type).__name__
            L.append(f"| `{c.name}` | {typ} | {'✓' if c.nullable else ''} | "
                     f"{'PK' if c.primary_key else ''} | {fks} |")
        uniq = [con for con in t.constraints
                if con.__class__.__name__ == "UniqueConstraint" and con.columns]
        if uniq:
            L.append("")
            L.append("قيود التفرّد: " + "؛ ".join(
                "(" + ", ".join(f"`{c.name}`" for c in con.columns) + ")" for con in uniq))
        L.append("")
    return "\n".join(L).rstrip() + "\n"


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        cur = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        print("ok" if cur == text else "DATABASE_SCHEMA.md لا يطابق النماذج")
        return 0 if cur == text else 1
    OUT.write_text(text, encoding="utf-8")
    print(f"كُتب {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
