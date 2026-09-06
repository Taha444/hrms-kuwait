# -*- coding: utf-8 -*-
"""بيئة اختبار معزولة — البنود 21 و30 و31.

**وهذه فجوة تغطية لا عطل**: تكرار توليد العقد، ومسار الحضور كامًلا،
ومسيّر الرواتب من التشغيل إلى القفل — ثلاثتها تحتاج بيانات **يجوز
إفسادها**. وبلا بيئة كهذه يكون أمام المختبِر خياران رديئان: ألّا
يختبر، أو يشغّل مسيّر رواتب على موظفين حقيقيين ويأمل.

**والعزل بالبناء لا بالانتباه**: شركة مستقلّة، وأرقام مدنية في نطاق
``999…``، وكلمات مرور عشوائية لكل حساب تُطبَع مرّة واحدة، و``QA`` في
الاسم والرقم الوظيفي — فمن يفتح الشاشة يعرف أنه ليس في الإنتاج.
"""
from __future__ import annotations

from sqlalchemy import func, select

from app import models, payroll, qa_sandbox
from app.database import SessionLocal


def _fresh():
    """بيئة نظيفة لكل قياس: تُحذف ثم تُنشأ."""
    db = SessionLocal()
    try:
        qa_sandbox.drop(db)
        out = qa_sandbox.create(db)
        return out
    finally:
        db.close()


def test_it_creates_a_self_contained_company():
    """**جوهرها**: شركة قائمة بذاتها لا صفوف مبعثرة."""
    out = _fresh()
    assert out["created"] and out["company_id"]

    db = SessionLocal()
    try:
        qa = qa_sandbox.find(db)
        assert qa is not None and qa.commercial_reg == qa_sandbox.QA_REG
        emps = db.scalars(select(models.Employee).where(
            models.Employee.company_id == qa.id)).all()
        assert len(emps) == len(qa_sandbox._STAFF), len(emps)
        # ولكلٍّ وردية: بلا وردية يُوسَم الجميع «حاضر» فلا يُختبر التأخير.
        assert all(e.shift_id for e in emps), "موظف بلا وردية"
        assert all(e.employee_no for e in emps), "موظف بلا رقم وظيفي"
    finally:
        db.close()


def test_nothing_leaks_outside_the_sandbox():
    """**والعزل مقيس لا مُدَّعى**: لا رقم من نطاقها خارجها."""
    _fresh()
    db = SessionLocal()
    try:
        qa = qa_sandbox.find(db)
        leak = db.scalar(select(func.count()).select_from(models.Employee).where(
            models.Employee.civil_id.like("999%"),
            models.Employee.company_id != qa.id))
    finally:
        db.close()
    assert leak == 0, f"{leak} سجًلا بأرقام البيئة خارجها"


def test_each_account_has_its_own_random_password():
    """ولا كلمة موحّدة ولا حساب مشترك — وكلٌّ يُجبَر على تغييرها."""
    out = _fresh()
    pw = [a["password"] for a in out["accounts"]]
    assert len(set(pw)) == len(pw), "كلمات مكرَّرة"
    assert all(len(p) >= 8 for p in pw), pw

    db = SessionLocal()
    try:
        qa = qa_sandbox.find(db)
        users = db.scalars(select(models.User).where(
            models.User.company_id == qa.id)).all()
        assert all(u.must_change_password for u in users), (
            "حساب لا يُجبَر على تغيير كلمته"
        )
        assert len({u.civil_id for u in users}) == len(users)
    finally:
        db.close()


def test_the_passwords_are_returned_once_not_stored_plainly():
    """وتُطبَع مرّة: إعادة الإنشاء لا تُعيدها، والمحفوظ بصمة لا كلمة."""
    _fresh()
    db = SessionLocal()
    try:
        again = qa_sandbox.create(db)
        qa = qa_sandbox.find(db)
        user = db.scalar(select(models.User).where(
            models.User.company_id == qa.id))
    finally:
        db.close()
    assert again["created"] is False and again["accounts"] == []
    assert user.password_hash and len(user.password_hash) > 20


def test_attendance_can_be_seeded_and_stays_inside():
    """**مسار الحضور صار قابًلا للاختبار** — وسجلاته لا تخرج عنها."""
    _fresh()
    db = SessionLocal()
    try:
        added = qa_sandbox.seed_attendance(db, days=5, late_days=2)
        qa = qa_sandbox.find(db)
        inside = db.scalar(select(func.count()).select_from(
            models.AttendanceRecord).where(
            models.AttendanceRecord.company_id == qa.id))
        late = db.scalar(select(func.count()).select_from(
            models.AttendanceRecord).where(
            models.AttendanceRecord.company_id == qa.id,
            models.AttendanceRecord.status == "late"))
    finally:
        db.close()
    assert added > 0 and inside == added
    assert late > 0, "لا سجل متأخّر — لا يُقاس التأخير"


def test_seeding_twice_does_not_double_the_records():
    """وقابلة لإعادة التشغيل: لا يوم بسجلّين."""
    _fresh()
    db = SessionLocal()
    try:
        first = qa_sandbox.seed_attendance(db, days=5)
        second = qa_sandbox.seed_attendance(db, days=5)
    finally:
        db.close()
    assert first > 0 and second == 0, (first, second)


def test_payroll_runs_on_the_sandbox_alone():
    """**ومسيّر الرواتب يُجرَّب بلا مساس بأحد.**"""
    _fresh()
    db = SessionLocal()
    try:
        qa = qa_sandbox.find(db)
        qa_sandbox.seed_attendance(db, days=5)
        res = payroll.compute_payroll(db, qa.id, 2026, 9)
    finally:
        db.close()
    assert res["employees_count"] == len(qa_sandbox._STAFF), res["employees_count"]
    row = res["payslips"][0]
    assert row["employee_no"] and row["employee_no"].startswith("QA-"), row
    assert res["totals"]["gross"] > 0


def test_dropping_removes_it_and_only_it():
    """**والحذف بالمعرّف**: بيئات لا تتراكم، وشركة حقيقية لا تُصاب."""
    _fresh()
    db = SessionLocal()
    try:
        before_others = db.scalar(select(func.count()).select_from(
            models.Company).where(
            models.Company.commercial_reg != qa_sandbox.QA_REG))
        out = qa_sandbox.drop(db)
        gone = qa_sandbox.find(db)
        after_others = db.scalar(select(func.count()).select_from(
            models.Company).where(
            models.Company.commercial_reg != qa_sandbox.QA_REG))
    finally:
        db.close()
    assert out["dropped"] and gone is None
    assert after_others == before_others, "مسّ الحذف شركة أخرى"


def test_it_is_named_so_nobody_mistakes_it_for_production():
    """ومن يفتح الشاشة يعرف أنه ليس في الإنتاج — الاسم والرقم يقولانها."""
    _fresh()
    db = SessionLocal()
    try:
        qa = qa_sandbox.find(db)
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == qa.id))
    finally:
        db.close()
    assert "QA" in qa.name or "اختبار" in qa.name, qa.name
    assert qa.abbreviation == "QA"
    assert emp.employee_no.startswith("QA-"), emp.employee_no
