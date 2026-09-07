# -*- coding: utf-8 -*-
"""شركة اختبار معزولة — لتجربة ما لا يُجرَّب على بيانات حقيقية.

**لماذا**: ثلاثة بنود في تقرير المراجعة (21 · 30 · 31) ليست أعطاًلا بل
**فجوات تغطية**: تكرار توليد العقد، ومسار الحضور كامًلا، ومسيّر الرواتب
من التشغيل إلى القفل. وكلّها تحتاج بيانات يجوز إفسادها.

وبلا هذه البيئة يكون أمام المختبِر خياران كلاهما رديء: ألّا يختبر،
أو يشغّل مسيّر رواتب على موظفين حقيقيين ويأمل.

**والعزل بالبناء لا بالانتباه**:

- شركة مستقلّة برقم تجاري خاص، وكل موظفيها ومستنداتها داخلها.
- أرقام مدنية في نطاق ``9990…`` لا يتقاطع مع البذرة ولا مع الواقع.
- كلمات مرور تُولَّد عشوائًيا وتُطبع مرًة واحدة — لا كلمة موحّدة، ولا
  حساب مشترك.
- ``QA`` في الاسم والاختصار، فمن يفتح الشاشة يعرف أنه ليس في الإنتاج.

**وبيئة لا تكفي للرحلة ليست بيئة.** بُنيت أول مرة بستّة حسابات وشركة
وفرع، فبقيت الرحلات الثلاث متعذّرة عليها رغم أنها بُنيت لها:

- **العقد (21)** يوّلده المندوب أو صاحبه، ولا مندوب فيها — فالمسار مقفل
  بالصلاحية قبل أن يُقاس. ثم لا إقامة ولا معاملة تجديد يُولَّد لها عقد.
  ثم النموذج الرسمي يرفض الناقص بالاسم: لا اسم إنجليزي ولا جواز ولا
  مهنة إنجليزية ولا إدارة عمل على الفرع.
- **الرواتب (31)** تفصل المُجهِّز عن المعتمِد، وصاحب ``run_payroll``
  فيها كان واحًدا — فالرحلة تقف عند الاعتماد بـ403.

فأُكملت البيئة حتى تُقطَع الرحلات الثلاث فيها من طرف إلى طرف، لا حتى
تبدأ.

**وحذفها ممكن**: ``--drop`` يزيلها وحدها بمعرّفها، فلا تتراكم بيئات.

الاستعمال::

    python -m app.qa_sandbox                 # تقرير: هل هي موجودة؟
    python -m app.qa_sandbox --create        # يُنشئها ويطبع الحسابات
    python -m app.qa_sandbox --attendance    # يزرع سجلات حضور
    python -m app.qa_sandbox --drop          # يحذفها هي وحدها
"""
from __future__ import annotations

import argparse
import secrets
from datetime import datetime, timedelta

from sqlalchemy import delete as sa_delete, or_ as sa_or, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models
from . import renewal as R
from .security import hash_password
from .clock import today as kuwait_today
from .database import SessionLocal

#: علامة البيئة — تُقرأ ولا تُخمَّن.
QA_REG = "QA-SANDBOX-0001"
QA_NAME = "شركة الاختبار (QA)"
QA_ABBR = "QA"

#: نطاق أرقام مدنية لا يتقاطع مع البذرة (1…/2…) ولا مع أرقام حقيقية.
_CIVIL_BASE = "999000000"

#: أدوار البيئة: ما يكفي لقطع رحلات الحضور والرواتب والعقد كاملة.
#:
#: (الاسم، الدور، الرقم، الاسم بالإنجليزية، المهنة، المهنة بالإنجليزية)
#:
#: والمندوب والمحاسب الثاني ليسا زينة: بلا الأول لا يُولَّد عقد حكومي
#: (الصلاحية تحجب المسار قبل أن يُقاس)، وبلا الثاني لا يُعتمَد مسيّر —
#: فصل السلطات يمنع من جهّزه أن يعتمده، و``run_payroll`` لا يحمله من
#: الأدوار إلا ``accountant``. فشركة بمحاسب واحد لا تصل بمسيّرها إلى
#: الاعتماد أصًلا، وهو ما كان يقع في هذه البيئة.
_STAFF = [
    ("مدير الاختبار", "company_manager", 1, "QA Manager", "مدير عام", "General Manager"),
    ("موارد بشرية (اختبار)", "hr", 2, "QA HR", "أخصائي موارد بشرية", "HR Specialist"),
    ("محاسب (اختبار)", "accountant", 3, "QA Accountant", "محاسب", "Accountant"),
    ("مسؤول فرع (اختبار)", "branch_supervisor", 4, "QA Supervisor", "مشرف", "Supervisor"),
    ("موظف اختبار أول", "employee", 5, "QA Employee One", "بائع", "Salesman"),
    ("موظف اختبار ثانٍ", "employee", 6, "QA Employee Two", "بائع", "Salesman"),
    ("مندوب (اختبار)", "delegate", 7, "QA Delegate", "مندوب", "Government Liaison"),
    ("محاسب ثانٍ (اختبار)", "accountant", 8, "QA Accountant Two", "محاسب", "Accountant"),
]

#: صاحب معاملة التجديد في البيئة — موظف عادي لا صاحب صلاحية.
_RENEWAL_STAFF_IDX = 5


def find(db: Session) -> models.Company | None:
    return db.scalar(select(models.Company).where(
        models.Company.commercial_reg == QA_REG))


def _civil(n: int) -> str:
    return f"{_CIVIL_BASE}{n:03d}"


def _password() -> str:
    """كلمة مرور عشوائية لكل حساب — لا موحّدة ولا مشتقّة من الاسم."""
    return secrets.token_urlsafe(9)


def renewal_id(db: Session, company_id: int) -> int | None:
    """معاملة التجديد التي يُولَّد لها العقد في هذه البيئة."""
    rn = db.scalar(select(models.ResidencyRenewal).where(
        models.ResidencyRenewal.company_id == company_id
    ).order_by(models.ResidencyRenewal.id))
    return rn.id if rn else None


def create(db: Session) -> dict:
    """يُنشئ البيئة إن لم تكن موجودة. يعيد الحسابات وكلماتها **مرة واحدة**."""
    existing = find(db)
    if existing is not None:
        return {"created": False, "company_id": existing.id, "accounts": [],
                "renewal_id": renewal_id(db, existing.id)}

    company = models.Company(
        name=QA_NAME, name_en="QA Sandbox Co.", commercial_reg=QA_REG,
        abbreviation=QA_ABBR, entity_type="company",
        eos_day_divisor=26, eos_max_months=18, alert_lead_days=60,
        representative_name="ممثّل الاختبار",
        representative_name_en="QA Representative",
        representative_civil_id=_civil(999))
    db.add(company)
    db.flush()

    # المحافظة ليست تزيًينا: العقد الحكومي تُطبع فيه إدارة العمل المختصّة،
    # وتُشتقّ من محافظة الفرع. وفرع بلا محافظة يوقف التوليد بـ400.
    branch = models.Branch(company_id=company.id, name="فرع الاختبار",
                           code="QAB", latitude=29.3759, longitude=47.9774,
                           geofence_radius_m=120,
                           governorate="العاصمة", governorate_en="Al Asima",
                           # سرٌّ خاصٌّ بالبيئة — لا يُشارك مع فرع حقيقي.
                           qr_secret=secrets.token_hex(16),
                           kiosk_key=secrets.token_hex(16))
    db.add(branch)
    db.flush()
    dept = models.Department(company_id=company.id, branch_id=branch.id,
                             name="قسم الاختبار")
    db.add(dept)
    # وردية صريحة: بلا وردية يُوسَم الجميع «حاضر» دائًما فلا يُختبر التأخير.
    shift = models.Shift(company_id=company.id, name="دوام الاختبار",
                         start_time=datetime(2000, 1, 1, 8, 0).time(),
                         end_time=datetime(2000, 1, 1, 17, 0).time(),
                         work_days="0,1,2,3,4", grace_minutes=15)
    db.add(shift)
    db.flush()

    accounts = []
    renewal_owner = None
    for name, role, idx, name_en, job_ar, job_en in _STAFF:
        civil = _civil(idx)
        emp = models.Employee(
            company_id=company.id, name=name, name_en=name_en, civil_id=civil,
            branch_id=branch.id, department_id=dept.id, shift_id=shift.id,
            hire_date=kuwait_today() - timedelta(days=400),
            basic_salary=400.0 + idx * 10, status="active",
            nationality="مصري", nationality_en="Egyptian",
            job_title=job_ar, job_title_en=job_en,
            # النموذج الرسمي يرفض الناقص بالاسم، فتُملأ حقوله كاملة هنا —
            # وإلا كانت البيئة تُنشَأ ثم يقف التوليد فيها عند أول محاولة.
            passport_number=f"QA{idx:06d}",
            contract_type="definite",
            attendance_mode="qr")
        db.add(emp)
        db.flush()
        if idx == _RENEWAL_STAFF_IDX:
            renewal_owner = emp

        pw = _password()
        db.add(models.User(
            company_id=company.id, employee_id=emp.id, civil_id=civil,
            full_name=name, role=role, is_active=True,
            password_hash=hash_password(pw),
            # كل حساب لشخص واحد، ويُجبَر على تغيير كلمته عند أول دخول.
            must_change_password=True))
        accounts.append({"name": name, "role": role,
                         "civil_id": civil, "password": pw})

    # إقامة قاربت على الانتهاء ومعاملة تجديد مفتوحة عليها: بلا هاتين لا
    # شيء يُولَّد له عقد أصًلا، ورقم الإقامة نفسه حقٌّ إلزامي في النموذج.
    permit = models.Permit(
        company_id=company.id, employee_id=renewal_owner.id, kind="residency",
        number=f"QA-RES-{renewal_owner.id}",
        start_date=kuwait_today() - timedelta(days=345),
        expiry_date=kuwait_today() + timedelta(days=20), status="active")
    db.add(permit)
    db.flush()
    renewal = models.ResidencyRenewal(
        company_id=company.id, employee_id=renewal_owner.id,
        permit_id=permit.id, renewal_type="normal",
        status=R.AWAITING_CONTRACTS, days_left_at_request=20,
        notes="معاملة بيئة الاختبار — لتجربة توليد العقد وتكراره.")
    db.add(renewal)
    db.flush()

    # أرقام وظيفية: بيئة يُختبَر فيها الكشف يجب أن تحمل ما يُنسَب إليه.
    from . import employee_no as _en

    _en.backfill_missing(db, company_id=company.id)
    rid = renewal.id
    db.commit()
    return {"created": True, "company_id": company.id, "accounts": accounts,
            "renewal_id": rid}


def seed_attendance(db: Session, *, days: int = 10, late_days: int = 2) -> int:
    """سجلات حضور صالحة للاختبار — بعضها متأخّر ليُقاس التأخير.

    **ولا تمسّ حضوًرا حقيقًيا**: مقصورة على موظفي البيئة وحدها.
    """
    company = find(db)
    if company is None:
        return 0
    emps = db.scalars(select(models.Employee).where(
        models.Employee.company_id == company.id)).all()
    branch = db.scalar(select(models.Branch).where(
        models.Branch.company_id == company.id))

    added = 0
    for emp in emps:
        made, back = 0, 1
        while made < days and back < 40:
            day = kuwait_today() - timedelta(days=back)
            back += 1
            if (day.weekday() + 1) % 7 > 4:      # الجمعة والسبت
                continue
            exists = db.scalar(select(models.AttendanceRecord.id).where(
                models.AttendanceRecord.employee_id == emp.id,
                models.AttendanceRecord.check_in_at >= datetime(
                    day.year, day.month, day.day),
                models.AttendanceRecord.check_in_at < datetime(
                    day.year, day.month, day.day) + timedelta(days=1)))
            if exists:
                made += 1
                continue
            late = made < late_days
            ci = datetime(day.year, day.month, day.day, 8, 45 if late else 5)
            co = datetime(day.year, day.month, day.day, 17, 10)
            worked = int((co - ci).total_seconds() // 60)
            db.add(models.AttendanceRecord(
                company_id=company.id, employee_id=emp.id,
                branch_id=branch.id if branch else None,
                check_in_at=ci, check_out_at=co, method="qr",
                status="late" if late else "present",
                worked_minutes=worked, overtime_minutes=max(worked - 540, 0),
                selfie_in_path="(اختبار)", selfie_out_path="(اختبار)"))
            made += 1
            added += 1
    db.commit()
    return added


def _tables_pointing_at(target: str):
    """الجداول التي تشير إلى ``target`` ولا تحمل رقم شركة.

    وهي التي لا يطالها الحذف بالشركة: جلسات، ورموز أجهزة، وتفضيلات
    إشعارات — يخلّفها **مجرّد تسجيل الدخول**.
    """
    for table in models.Base.metadata.tables.values():
        if table.name == target or "company_id" in table.c:
            continue
        cols = [c for c in table.columns
                if any(fk.column.table.name == target for fk in c.foreign_keys)]
        if cols:
            yield table, cols


def drop(db: Session) -> dict:
    """يحذف البيئة وحدها بمعرّفها.

    **والحذف بالمعرّف لا بالاسم**: اسٌم مشابه لشركة حقيقية لا يُصيبها.

    **والترتيب مشتقٌّ من المخطّط لا مكتوب بيد.** كانت هنا قائمة جداول
    مسرودة، فسقطت مرّتين: مرة حين أُضيفت الإقامة ومعاملة التجديد، ومرة
    حين تبيّن أن **تسجيل الدخول وحده** يخلّف صفوًفا في جداول لا تحمل رقم
    شركة (جلسات ورموز). وحذٌف ناقص يترك صًفا معلًَّقا يُفشل إنشاء البيئة
    في المرّة التالية — فتصير بيئة تُنشأ مرّة واحدة، وهو ضدّ الغرض منها.

    فبدل القائمة: كل ما يشير إلى مستخدميها وموظفيها يُمسح أوًلا، ثم كل
    جدول يحمل رقمها بتمريرات متتالية — كل تمريرة تحذف ما زال معلًَّقا
    منها، حتى لا يبقى شيء. وأي جدول يُضاف للنظام غًدا يدخل الحساب وحده.
    """
    company = find(db)
    if company is None:
        return {"dropped": False}
    cid = company.id

    user_ids = set(db.scalars(select(models.User.id).where(
        models.User.company_id == cid)))
    emp_ids = set(db.scalars(select(models.Employee.id).where(
        models.Employee.company_id == cid)))
    for target, ids in (("users", user_ids), ("employees", emp_ids)):
        if not ids:
            continue
        for table, cols in _tables_pointing_at(target):
            db.execute(sa_delete(table).where(
                sa_or(*[c.in_(ids) for c in cols])))

    pending = [t for t in models.Base.metadata.tables.values()
               if "company_id" in t.c and t.name != "companies"]
    while pending:
        stuck = []
        for table in pending:
            try:
                with db.begin_nested():
                    db.execute(sa_delete(table).where(table.c.company_id == cid))
            except IntegrityError:
                stuck.append(table)
        if len(stuck) == len(pending):
            raise RuntimeError(
                "تعذّر حذف بيئة الاختبار — مراجع متبادلة في: "
                + "، ".join(t.name for t in stuck))
        pending = stuck

    db.execute(sa_delete(models.Company).where(models.Company.id == cid))
    db.commit()
    return {"dropped": True, "company_id": cid}


def main() -> None:
    p = argparse.ArgumentParser(description="بيئة اختبار معزولة")
    p.add_argument("--create", action="store_true")
    p.add_argument("--attendance", action="store_true",
                   help="يزرع سجلات حضور للبيئة")
    p.add_argument("--drop", action="store_true")
    args = p.parse_args()

    db = SessionLocal()
    try:
        if args.drop:
            print(drop(db))
            return
        if args.create:
            out = create(db)
            if not out["created"]:
                print(f"البيئة موجودة (شركة #{out['company_id']}) — لا يُعاد إنشاؤها.")
            else:
                print(f"أُنشئت البيئة: شركة #{out['company_id']}")
                print("الحسابات — تُطبَع مرّة واحدة فقط:")
                print("")
                for a in out["accounts"]:
                    print(f"  {a['civil_id']}  {a['password']:<16} {a['role']:<18} {a['name']}")
                print("")
                print("كل حساب مُجبَر على تغيير كلمته عند أول دخول.")
            if out.get("renewal_id"):
                print(f"معاملة التجديد للعقد الحكومي: #{out['renewal_id']}")
        if args.attendance:
            print("سجلات حضور مُضافة:", seed_attendance(db))
        if not (args.create or args.attendance or args.drop):
            c = find(db)
            print("البيئة موجودة، شركة #%d" % c.id if c else "البيئة غير موجودة.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
