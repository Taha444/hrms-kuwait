# -*- coding: utf-8 -*-
"""كتابٌة أو قراءٌة تعبُر الشركات — كنٌس دائم لصنٍف عطٍل تكرّر ثلاث مرات.

**لماذا هذا الكنس**: وُجد في ``POST /documents`` تحديٌث جماعي::

    update(Task).where(related_entity_type == "document",
                       type == "doc_expiring",
                       status.in_(["open", "in_progress"]))
         .values(status="done", ...)

بلا قيٍد على مستنٍد ولا على شركة. فرفُع جواٍز لموظٍف واحد كان يُغلق كلَّ
مهمة انتهاء مستند مفتوحة **في قاعدة البيانات بأسرها** — كلُّ موظف، في كل
شركة. والدالُة الصحيحة المقيَّدة بمستندها تقع اثنَي عشر سطًرا فوقه.

وهذا الشكُل لا يُمسَك باختبار وظيفي: تركيُب حالٍة تُثبته يعني إفساد بيانات
السويت كلّها. فيُمسَك بقراءة الشيفرة.

**ويميّز الكنُس بين أمرين**:

- ``كتابة`` — ``update``/``delete`` جماعية لا تسمّي صًفّا ولا شركة. وهذه
  تكاد لا تكون مشروعًة إلا في جداول لا تحمل شركًة أصًلا (الرموز المنتهية،
  سجلّ تشغيل المهام).
- ``قراءة`` — دالُة مسار تستعلم نموًذجا يحمل ``company_id`` بلا قيٍد ولا
  حارس. وهذه **كثيرُة الإنذار الكاذب**: النطاق يأتي غالًبا من حارٍس
  بالواسطة (``_get_emp`` · ``_get_renewal``)، فتُقرأ يدوًيا لا تُعَدّ عطًلا.

الاستخدام::

    .venv/Scripts/python.exe scripts/unscoped_writes.py

يُخرج ``2`` إن وُجدت كتابٌة جماعية بلا نطاق، و``0`` غير ذلك. والقراءاُت
تُطبَع للمراجعة ولا تُغيّر رمز الخروج.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

#: ما يجعل جملًة مقيَّدًة بصٍّف أو بشركة.
ROW_SCOPES = ("company_id", ".id ==", ".id.in_", "_id ==", "_id.in_")

#: جداٌل عامّة لا تحمل شركًة — الحذف الدوري فيها مشروع.
GLOBAL_TABLES = ("JobRun", "ConsumedToken", "RevokedToken")

#: حرّاس النطاق، مباشرًة أو بالواسطة.
GUARDS = ("company_id", "scope_company_id", "assert_same_company",
          "require_super_admin", "_company(", "visible_", "same_company",
          "_get_emp(", "_get_renewal(", "_get_request(")


def _statement_text(lines: list[str], node: ast.AST) -> str:
    lo = node.lineno
    hi = min(getattr(node, "end_lineno", lo) + 6, len(lines))
    return "\n".join(lines[lo - 1:hi])


def bulk_writes() -> list[tuple[str, int, str]]:
    """``update``/``delete`` جماعية لا تسمّي صًفّا ولا شركة."""
    out = []
    for path in sorted((ROOT / "app").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        for node in ast.walk(ast.parse(text)):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if name not in ("update", "delete"):
                continue
            stmt = _statement_text(lines, node)
            if "where" not in stmt:
                continue
            if any(t in stmt for t in GLOBAL_TABLES):
                continue
            if any(s in stmt for s in ROW_SCOPES):
                continue
            out.append((str(path.relative_to(ROOT)), node.lineno, stmt.strip()))
    return out


def unscoped_reads() -> list[tuple[str, int, str, list[str]]]:
    """دواُل مسار تستعلم نماذَج الشركة بلا قيٍد ولا حارس — للمراجعة."""
    from app import models

    scoped = {m.class_.__name__ for m in models.Base.registry.mappers
              if "company_id" in {c.name for c in m.local_table.columns}}
    out = []
    for path in sorted((ROOT / "app" / "routers").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        for fn in ast.walk(ast.parse(text)):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body = "\n".join(lines[fn.lineno - 1:
                                   getattr(fn, "end_lineno", fn.lineno)])
            if "select(models." not in body or any(g in body for g in GUARDS):
                continue
            used = sorted(m for m in scoped
                          if f"select(models.{m})" in body
                          or f"select(models.{m}." in body)
            if used:
                out.append((str(path.relative_to(ROOT)), fn.lineno, fn.name, used))
    return out


def main() -> int:
    writes = bulk_writes()
    reads = unscoped_reads()

    print(f"كتابٌة جماعية بلا نطاق: {len(writes)}")
    for path, line, stmt in writes:
        print(f"\n  {path}:{line}")
        for one in stmt.splitlines()[:6]:
            print("     ", one.strip())

    print(f"\nقراءاٌت للمراجعة اليدوية (قد يأتي نطاقها بالواسطة): {len(reads)}")
    for path, line, name, used in reads:
        print(f"  {path}:{line}  {name}()  →  {used}")

    if writes:
        print("\nكتابٌة جماعية بلا نطاق — تُقرأ وتُقيَّد أو تُحذف.")
        return 2
    print("\nلا كتابَة جماعية بلا نطاق.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
