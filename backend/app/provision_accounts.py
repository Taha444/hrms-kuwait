# -*- coding: utf-8 -*-
"""BKL-07 (الخطوة الأولى) — تجهيز حسابات الأدوار لاختبار المسار الكامل.

مسار تجديد الإقامة لا يُختبر بحساب واحد: يحتاج **المندوب** الذي يفتح
المعاملة ويولّد العقد، و**الموظف** الذي يوقّعه ويرفعه، و**مسؤول الفرع**
و**HR**. وبيئة الإنتاج تُنشئ الإدارة العليا والمالك فقط، فيتوقّف الاختبار
قبل أن يبدأ — وهذا سبب بقاء البند مفتوًحا.

**القواعد التي تحكم هذه الأداة، وكلها ملزِمة:**

- **لا يُنشأ موظف وهمي.** الأداة تربط حساًبا بموظف **قائم** في ملف الشركة.
  موظف مخترع يدخل التقارير والمسيّر والإحصاءات، ويبقى بعد الاختبار.
- **كلمة مرور عشوائية مختلفة لكل شخص**، تُطبع مرة واحدة ولا تُحفظ في أي
  سجلّ. لا كلمة موحّدة ولا مشتركة.
- **``must_change_password``** مرفوع دائًما: الكلمة المطبوعة للتسليم لا
  للاستعمال الدائم.
- **حساب لكل شخص.** لا حساب مشترك بدور، ولا إعادة استعمال حساب قائم
  لشخص آخر.
- **لا تُنشئ الأداة إدارة عليا** بحال.
- **الربط ذرّيّ**: الحساب ورابطه بالموظف يُكتبان في معاملة واحدة، فلا
  يبقى حساب معلَّق بلا موظف إن فشل الشوط.

التشغيل::

    python -m app.provision_accounts --company 1              # فحص فقط
    python -m app.provision_accounts --company 1 --apply
    python -m app.provision_accounts --company 1 --apply --roles delegate,employee
"""
from __future__ import annotations

import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .database import SessionLocal
from .security import generate_temp_password, hash_password

#: الأدوار التي يحتاجها اختبار المسار الكامل. «الإدارة العليا» ليست منها
#: عمًدا: أداة تُنشئ صلاحية مطلقة ليست أداة تجهيز اختبار.
TEST_ROLES = ["delegate", "employee", "branch_supervisor", "hr"]

FORBIDDEN_ROLES = {"super_admin", "company_owner"}


def _has_account(db: Session, employee_id: int) -> models.User | None:
    return db.scalar(select(models.User).where(
        models.User.employee_id == employee_id))


def _pick_employee(db: Session, company_id: int,
                   taken: set[int]) -> models.Employee | None:
    """موظف قائم نشط بلا حساب — لا يُخترع أحد.

    الأولوية لمن له بيانات أكمل: العقد الحكومي يتوقّف عند أول حقل ناقص،
    فاختيار موظف ناقص البيانات يوقف الاختبار في منتصفه لسبب لا علاقة له
    بالمسار.
    """
    rows = db.scalars(select(models.Employee).where(
        models.Employee.company_id == company_id,
        models.Employee.status == "active",
    )).all()
    candidates = [e for e in rows
                  if e.id not in taken and _has_account(db, e.id) is None]
    if not candidates:
        return None

    def completeness(e: models.Employee) -> int:
        return sum(1 for v in (e.name, e.name_en, e.civil_id, e.passport_number,
                               e.job_title, e.job_title_en, e.branch_id,
                               e.basic_salary) if v)

    return max(candidates, key=completeness)


def provision(db: Session, company_id: int, roles: list[str],
              apply_changes: bool) -> list[dict]:
    """يجهّز حساًبا لكل دور مطلوب. يعيد وصف ما تمّ (أو ما سيتمّ)."""
    bad = set(roles) & FORBIDDEN_ROLES
    if bad:
        raise SystemExit(f"✘ ممنوع تجهيز هذه الأدوار بهذه الأداة: {sorted(bad)}")

    company = db.get(models.Company, company_id)
    if not company:
        raise SystemExit(f"✘ لا شركة برقم {company_id}")

    out: list[dict] = []
    taken: set[int] = set()
    for role in roles:
        existing = db.scalar(select(models.User).where(
            models.User.role == role,
            models.User.company_id == company_id,
            models.User.is_active == True,          # noqa: E712
            models.User.employee_id.isnot(None),
        ))
        if existing:
            out.append({"role": role, "action": "موجود",
                        "civil_id": existing.civil_id, "password": None})
            continue

        emp = _pick_employee(db, company_id, taken)
        if emp is None:
            out.append({"role": role, "action": "تعذّر — لا موظف نشط بلا حساب",
                        "civil_id": None, "password": None})
            continue
        taken.add(emp.id)

        if not apply_changes:
            out.append({"role": role, "action": "سيُنشأ",
                        "civil_id": emp.civil_id, "password": None,
                        "employee": emp.name})
            continue

        pw = generate_temp_password()
        # الربط ذرّيّ: الحساب ورابطه في معاملة واحدة. الفشل بينهما يترك
        # حساًبا بلا موظف — وهو أسوأ من ألّا يُنشأ.
        try:
            user = models.User(
                civil_id=emp.civil_id, full_name=emp.name, role=role,
                company_id=company_id, employee_id=emp.id,
                password_hash=hash_password(pw),
                must_change_password=True, is_active=True,
            )
            db.add(user)
            db.commit()
        except Exception:
            db.rollback()
            raise
        out.append({"role": role, "action": "أُنشئ", "civil_id": emp.civil_id,
                    "password": pw, "employee": emp.name})
    return out


def main() -> int:
    args = sys.argv[1:]

    def arg(name: str, default=None):
        if name in args:
            i = args.index(name)
            if i + 1 < len(args):
                return args[i + 1]
        return default

    company_id = int(arg("--company", "0") or 0)
    if not company_id:
        print(__doc__)
        return 1
    apply_changes = "--apply" in args
    roles = [r.strip() for r in (arg("--roles") or ",".join(TEST_ROLES)).split(",")
             if r.strip()]

    db = SessionLocal()
    try:
        rows = provision(db, company_id, roles, apply_changes)
    finally:
        db.close()

    print("=" * 66)
    for r in rows:
        line = f"  {r['role']:<20}{r['action']:<12}{r.get('civil_id') or '—'}"
        if r.get("employee"):
            line += f"   ({r['employee']})"
        print(line)
    print("=" * 66)

    made = [r for r in rows if r.get("password")]
    if made:
        print("\n كلمات المرور — تُعرض مرة واحدة، سلّمها لأصحابها مباشرة:")
        for r in made:
            print(f"   {r['civil_id']:<16}{r['password']}")
        print("\n كلٌّ مختلفة، ويُطلب تغييرها عند أول دخول.")
        print(" لا تُرسل في جروب ولا ملف ولا تقرير.")
    elif not apply_changes:
        print("\nفحص فقط — لم يتغيّر شيء. أعد التشغيل مع --apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
