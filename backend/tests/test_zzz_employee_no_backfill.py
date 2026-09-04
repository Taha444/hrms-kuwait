# -*- coding: utf-8 -*-
"""P7-29 — تعبئة الأرقام الوظيفية: فحص قبل الكتابة، وبقواعد التوليد نفسها.

المنطق كان موجوًدا (``employee_no.backfill_missing``) والناقص الطريق
إليه: دالة يناديها من يعرفها ليست أداة تشغيل، ومن يحتاجها على بيئة
عميل لا يفتح مفسّر بايثون ليكتب استدعاًء.

**والفحص قبل الكتابة ليس تزيًُّنا**: الرقم الوظيفي يدخل العقود والمسيّر
والمراسلات. توليده لعشرات الموظفين بأمر واحد بلا أن يرى أحد ما سيُكتب
هو ما يجعل التراجع صعًبا.

**والمعاينة تُري ما سيقع فعًلا**: تُولَّد الأرقام ثم يُتراجَع عنها، لا
تُقرَّب بقاعدة ثانية. وقاعدة تختلف بين المعاينة والتطبيق تجعل المعاينة
بلا قيمة.
"""
from __future__ import annotations

import pytest
from sqlalchemy import delete as sa_delete, func, select

from app import models
from app.backfill_employee_no import preview
from app.database import SessionLocal
from app.employee_no import backfill_missing


@pytest.fixture
def employees_without_numbers():
    """ثلاثة موظفين بلا رقم — تُبنى وتُحذف."""
    db = SessionLocal()
    made = []
    try:
        cid = db.scalar(select(models.Company.id).order_by(models.Company.id))
        for i in range(3):
            emp = models.Employee(
                company_id=cid, name=f"موظف بلا رقم {i}",
                name_en=f"Unnumbered {i}", civil_id=f"2777001100{i:02d}",
                job_title="فني", basic_salary=300, status="active",
                nationality="مصري", employee_no=None)
            db.add(emp)
            db.flush()
            made.append(emp.id)
        db.commit()
        yield made
    finally:
        db.execute(sa_delete(models.Employee).where(
            models.Employee.id.in_(made)))
        db.commit()
        db.close()


def test_the_fixture_really_creates_unnumbered_employees(
        employees_without_numbers):
    """ادّعاء على موظفين مرقَّمين لا يقيس شيًئا."""
    db = SessionLocal()
    try:
        rows = db.scalars(select(models.Employee).where(
            models.Employee.id.in_(employees_without_numbers))).all()
    finally:
        db.close()
    assert rows and all(r.employee_no is None for r in rows)


def test_preview_lists_them_without_writing(employees_without_numbers):
    """**جوهر الأمان**: المعاينة تعرض ولا تكتب."""
    db = SessionLocal()
    try:
        rows = preview(db)
        ids = {r["id"] for r in rows}
    finally:
        db.close()
    assert set(employees_without_numbers) <= ids, (
        f"المعاينة لم تشمل من بلا رقم: {set(employees_without_numbers) - ids}"
    )

    db = SessionLocal()
    try:
        still_none = db.scalar(select(func.count()).select_from(
            models.Employee).where(
                models.Employee.id.in_(employees_without_numbers),
                models.Employee.employee_no.is_(None)))
    finally:
        db.close()
    assert still_none == len(employees_without_numbers), (
        "المعاينة كتبت أرقاًما — والتشغيل الافتراضي يجب أن يقرأ فقط"
    )


def test_preview_shows_a_real_number_not_a_placeholder(
        employees_without_numbers):
    """وما تعرضه رقم حقيقي بقاعدة التوليد نفسها."""
    db = SessionLocal()
    try:
        rows = [r for r in preview(db) if r["id"] in employees_without_numbers]
    finally:
        db.close()
    assert rows
    for r in rows:
        code = r["employee_no"]
        assert code and len(code) >= 3, f"رقم غير صالح: {code}"
        assert not code.startswith("?"), code


def test_applying_writes_exactly_what_was_previewed(employees_without_numbers):
    """والمعاينة تُري ما سيقع: التطبيق يكتب ما عُرض بالضبط.

    ولو اختلفا لصارت المعاينة طمأنينة كاذبة — يُراجَع رقم ويُكتب غيره.
    """
    db = SessionLocal()
    try:
        planned = {r["id"]: r["employee_no"]
                   for r in preview(db) if r["id"] in employees_without_numbers}
        made = backfill_missing(db)
    finally:
        db.close()
    assert made >= len(employees_without_numbers)

    db = SessionLocal()
    try:
        actual = {e.id: e.employee_no for e in db.scalars(select(
            models.Employee).where(
                models.Employee.id.in_(employees_without_numbers))).all()}
    finally:
        db.close()
    assert all(actual[i] for i in actual), "بقي موظف بلا رقم بعد التطبيق"
    assert actual == planned, (
        f"كُتب غير ما عُرض:\n  عُرض: {planned}\n  كُتب: {actual}"
    )


def test_numbers_are_unique_after_backfill(employees_without_numbers):
    """ولا يتكرّر رقم: العمود فريد، والتعبئة الدفعية أكثر ما يكسره."""
    db = SessionLocal()
    try:
        backfill_missing(db)
        codes = [c for (c,) in db.execute(select(
            models.Employee.employee_no).where(
                models.Employee.employee_no.isnot(None))).all()]
    finally:
        db.close()
    assert len(codes) == len(set(codes)), (
        f"أرقام مكرَّرة بعد التعبئة: {len(codes) - len(set(codes))}"
    )


def test_running_backfill_twice_changes_nothing_more(employees_without_numbers):
    """والتشغيل الثاني لا يُعيد الترقيم: من له رقم يبقى برقمه."""
    db = SessionLocal()
    try:
        backfill_missing(db)
        first = {e.id: e.employee_no for e in db.scalars(select(
            models.Employee).where(
                models.Employee.id.in_(employees_without_numbers))).all()}
        again = backfill_missing(db)
        second = {e.id: e.employee_no for e in db.scalars(select(
            models.Employee).where(
                models.Employee.id.in_(employees_without_numbers))).all()}
    finally:
        db.close()
    assert again == 0, f"التشغيل الثاني عبّأ {again} — إعادة ترقيم"
    assert first == second, "تغيّرت أرقام بعد التشغيل الثاني"
