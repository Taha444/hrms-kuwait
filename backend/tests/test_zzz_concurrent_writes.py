# -*- coding: utf-8 -*-
"""قراءٌة ثم كتابٌة بال قيد — وطلبان في اللحظة نفسها يمرّان.

**القياس**: قيوُد التفريد في القاعدة مقابل الفحوص التي تسبق الكتابة.
وثالُث حااٍلت:

1. **قراُر الطلب — محمٌّي أصًلا**: ``claim_decision`` تحديٌث مشروط على
   ``decision_seq``، فيفوز واحٌد ويُردّ اآلخُر بـ409. وشرحُها يقول لماذا
   ال ``FOR UPDATE``: «SQLite تتجاهله، فتعمل الحمايُة في اإلنتاج وتغيب عن
   القياس» — وهو الصنُف الذي كُنس اليوم بتمامه.

2. **الحضوُر — كان مكشوًفا**: ``check_in`` يقرأ «ال سجّل مفتوح» ثم يكتب.
   فنقرتان في اللحظة نفسها تُنشئان اثنين، ثم يأخذ ``_finalize_out``
   أحدهما (``order_by(check_in_at.desc())``) **ويبقى اآلخُر مفتوًحا إلى
   األبد** — فيمنع كلَّ حضوٍر الحق (الفحُص نفسه يردّ 409)، وتُحتسب دقائُق
   عمٍل مرتين أو تُفقَد، ويُبنى كشُف راتٍب على أياٍم لم تقع.

   فالقيُد في القاعدة: فهٌرس فريٌد **مشروٌط** بـ``check_out_at IS NULL``
   (ترحيل ``f4a5b6c7d8e``) — يعبّر عن الشرط بحرفه، فالسجالُت المنصرفة ال
   يحدّها شيء.

3. **املسيَّر — يُقال وال يُمَسّ**: ال مطالبَة ذرّية له، فتشغيالن متزامنان
   يُنشئان مسيَّرين للشهر نفسه. وال يُضاف قيٌد: ``adjustment_run`` **حالٌة**
   ال جدوٌل آخر، فمسيُّر التسوية يشارك الفترَة نفسها — فقيٌد ساذٌج على
   ``(company_id, period)`` **يمنع تسويًة مشروعة**. والقاعدة 20 تمنع
   تغييَر الرواتب بال إذٍن، فيُقال الفرُق ويُترَك لصاحبه.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timezone

from sqlalchemy import delete as sa_delete, func, select, text
from sqlalchemy.exc import IntegrityError

from app import models
from app.database import SessionLocal


def test_a_second_open_attendance_record_is_refused_by_the_database():
    """**جوهر البند**: القيُد في القاعدة ال في الفحص."""
    db = SessionLocal()
    made = []
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1))
        if emp is None:
            import pytest
            pytest.skip("ال موظَف في هذه القاعدة")
        now = datetime.now(timezone.utc)
        first = models.AttendanceRecord(company_id=1, employee_id=emp.id,
                                        check_in_at=now, status="present")
        db.add(first)
        db.commit()
        made.append(first.id)

        second = models.AttendanceRecord(company_id=1, employee_id=emp.id,
                                         check_in_at=now, status="present")
        db.add(second)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
        else:
            made.append(second.id)
            raise AssertionError("أُدخِل سجٌّل مفتوٌح ثاٍن — القيُد ال يعمل")
    finally:
        if made:
            db.execute(sa_delete(models.AttendanceRecord).where(
                models.AttendanceRecord.id.in_(made)))
            db.commit()
        db.close()


def test_a_closed_record_does_not_block_a_new_one():
    """**والقيُد مشروٌط ال مطلق**: من انصرف يبصم غًدا.

    ولو كان التفرُّد على ``employee_id`` وحده لمنع كلَّ حضوٍر ثاٍن في
    عمر الموظف — وذلك عطٌل أوسُع من الذي يُصلحه.
    """
    db = SessionLocal()
    made = []
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1))
        now = datetime.now(timezone.utc)
        closed = models.AttendanceRecord(
            company_id=1, employee_id=emp.id, check_in_at=now,
            check_out_at=now, worked_minutes=0, status="present")
        db.add(closed)
        db.commit()
        made.append(closed.id)

        fresh = models.AttendanceRecord(company_id=1, employee_id=emp.id,
                                        check_in_at=now, status="present")
        db.add(fresh)
        db.commit()
        made.append(fresh.id)
    finally:
        if made:
            db.execute(sa_delete(models.AttendanceRecord).where(
                models.AttendanceRecord.id.in_(made)))
            db.commit()
        db.close()


def test_the_constraint_speaks_the_same_message_as_the_check():
    """**وقيٌد يردّ خمسمئة بادَل تسابًقا بانهيار.**

    فالمستخدُم ال يفهم أيَّهما، والرسالُة المفهومة موجودٌة أصًلا في الفحص
    السابق — فتُقال هي نفسها عند القيد.
    """
    from app.routers import attendance as A

    src = inspect.getsource(A.check_in)
    assert "IntegrityError" in src, "القيُد يردّ خمسمئة"
    assert "لديك تسجيل حضور مفتوح" in src, "رسالٌة ثانية لقاعدٍة واحدة"
    assert src.count("لديك تسجيل حضور مفتوح") >= 2, \
        "الفحُص والقيُد يقوالن نًصّا واحًدا — يُقاس أنهما اثنان في الشيفرة"


def test_the_migration_measures_before_it_enforces():
    """**وترحيٌل يسقط على قاعدة العميل أسوأ من العطل الذي يُصلحه.**

    فقاعدٌة فيها نسخٌة قائمة يسقط عليها إنشاُء الفهرس فتفشل النشرُة كلُّها.
    فيُقاس أوًّلا، ويُبقى األحدُث ويُغلق ما قبله — **وال يُحذَف**: سجلُّ
    حضوٍر دليٌل ال يُمحى.
    """
    import pathlib

    mig = (pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions"
           / "f4a5b6c7d8e_one_open_attendance.py").read_text(encoding="utf-8")
    assert "HAVING COUNT(*) > 1" in mig, "ال يُقاس قبل الفرض"
    assert "UPDATE attendance_records" in mig, "ال يُعالَج التكراُر القائم"
    assert "DELETE" not in mig.upper(), "يحذف سجلَّ حضور"
    assert "auto_closed" in mig, "ال يُعرَف أن اإلغالَق من الترحيل"


def test_the_index_is_partial_not_total():
    """والشرُط في الفهرس نفسه — ال في الشيفرة التي تقرؤه."""
    db = SessionLocal()
    try:
        sql = db.scalar(text(
            "SELECT sql FROM sqlite_master WHERE type='index' "
            "AND name='ux_attendance_one_open_per_employee'"))
    finally:
        db.close()
    if sql is None:
        import pytest
        pytest.skip("القاعدُة ليست SQLite")
    assert "WHERE" in sql.upper(), sql
    assert "CHECK_OUT_AT IS NULL" in sql.upper().replace('"', ""), sql


def test_the_payroll_race_is_reported_not_silently_constrained():
    """**ومسيُّر التسوية يشارك الفترَة نفسها** — فقيٌد ساذٌج يمنع مشروًعا.

    ``adjustment_run`` حالٌة ال جدوٌل آخر (``STATUS_ORDER`` يضعها بجانب
    ``locked``). فلو أُضيف تفرٌُّد على ``(company_id, period)`` لمُنِعت كلُّ
    تسويٍة بعد القفل. والقاعدة 20 تمنع تغييَر الرواتب بال إذن — فيُقاس
    الفرُق ويُقال، وال يُفرَض قيٌد بحسن نيّة.
    """
    from app.routers import payroll as P

    assert "adjustment_run" in P.STATUS_ORDER, P.STATUS_ORDER
    # وال قيَد على الفترة — يُقاس ليُعرَف أن الحالَة كما وُصفت.
    cols = {c.name for c in models.PayrollRun.__table__.columns}
    assert {"company_id", "period", "status"} <= cols
    uniq = [
        "+".join(col.name for col in c.columns)
        for c in models.PayrollRun.__table__.constraints
        if type(c).__name__ == "UniqueConstraint"
    ]
    assert "company_id+period" not in uniq, (
        "أُضيف تفرٌُّد على الفترة — يمنع تسويًة مشروعة، ويُراجَع هذا الملف")
