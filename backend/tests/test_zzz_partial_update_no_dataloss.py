# -*- coding: utf-8 -*-
"""P0 — تعديل جزئي لملف الموظف لا يمحو ما لم يُرسَل.

**العطل**: ``update_employee`` كان يبني حمولته بـ``model_dump()``، وهي
تُنتج **كل** حقول المخطّط — المُرسَل منها والغائب — فيُكتَب الغائب
بقيمته الافتراضية.

فطلب فيه أربعة حقول كان يمحو أحد عشر غيرها. قِستُه على البناء الحالي:

    hire_date:     2024-02-28 → None
    basic_salary:  650.0      → 0.0
    job_title:     'بائع'      → None
    branch_id:     1          → None
    nationality:   'مصري'      → None
    shift_id:      1          → None
    department_id: 1          → None

وهو تدمير بيانات لا نقص ميزة: راتب يصير صفًرا، وتاريخ تعيين يُمحى —
وعليهما يقوم المسيّر ومكافأة نهاية الخدمة. ولم يكن أي اختبار يمسّه.

**والعلاج دمج لا عقد جديد**: ``exclude_unset`` يقصر الكتابة على ما
أرسله العميل. الحقل الذي لم يُذكَر يبقى، والذي أُرسل فارًغا يُفرَّغ
بقصد — فتبقى القدرة على المسح المتعمَّد.
"""
from __future__ import annotations

import inspect
from pathlib import Path

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from app.routers import employees as emp_router
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")
EMP_CIVIL = "100000000101"

#: الحقول التي يقول التقرير إنها فُقدت، ومعها ما بنيناه في هذه الجولة.
WATCHED = ("hire_date", "basic_salary", "job_title", "contract_type",
           "branch_id", "nationality", "shift_id", "department_id",
           "passport_number", "actual_salary", "work_hours_type",
           "attendance_mode", "status")


def _snapshot(eid: int) -> dict:
    db = SessionLocal()
    try:
        e = db.get(models.Employee, eid)
        return {k: getattr(e, k, None) for k in WATCHED}
    finally:
        db.close()


def _seed(eid: int) -> None:
    """يملأ الحقول المرصودة بقيم معلومة — القياس على قيم لا على فراغ."""
    from datetime import date

    db = SessionLocal()
    try:
        e = db.get(models.Employee, eid)
        e.hire_date = date(2024, 2, 28)
        e.basic_salary = 650.0
        e.job_title = "بائع"
        e.nationality = "مصري"
        e.branch_id = e.branch_id or 1
        db.commit()
    finally:
        db.close()


def _emp_id() -> int:
    db = SessionLocal()
    try:
        return db.scalar(select(models.Employee.id).where(
            models.Employee.civil_id == EMP_CIVIL))
    finally:
        db.close()


def test_a_partial_update_touches_only_what_it_sends(client):
    """**جوهر العطل**: أربعة حقول كانت تمحو أحد عشر."""
    eid = _emp_id()
    _seed(eid)
    before = _snapshot(eid)
    assert before["hire_date"] and before["basic_salary"], before

    r = client.put(f"/api/employees/{eid}", headers=auth_headers(login(client, *HR)),
                   json={"name": "أحمد محمود علي", "civil_id": EMP_CIVIL,
                         "phone": "50009999"})
    assert r.status_code == 200, r.text[:250]

    after = _snapshot(eid)
    lost = {k: (before[k], after[k]) for k in WATCHED if before[k] != after[k]}
    assert not lost, f"حقول تغيّرت بلا أن تُرسَل: {lost}"


def test_the_fields_that_are_sent_do_change(client):
    """ولا يُصلَح المحو بتعطيل الكتابة: المُرسَل يُطبَّق."""
    eid = _emp_id()
    r = client.put(f"/api/employees/{eid}", headers=auth_headers(login(client, *HR)),
                   json={"name": "أحمد محمود علي", "civil_id": EMP_CIVIL,
                         "job_title_en": "Salesman", "phone": "50007777"})
    assert r.status_code == 200, r.text[:200]

    db = SessionLocal()
    try:
        e = db.get(models.Employee, eid)
        assert e.job_title_en == "Salesman" and e.phone == "50007777"
    finally:
        db.close()


def test_an_explicit_empty_still_clears(client):
    """والمسح المتعمَّد يبقى ممكًنا: الفرق بين «لم يُرسَل» و«أُرسل فارًغا»."""
    eid = _emp_id()
    hdr = auth_headers(login(client, *HR))
    client.put(f"/api/employees/{eid}", headers=hdr,
               json={"name": "أحمد محمود علي", "civil_id": EMP_CIVIL,
                     "job_title_en": "To be cleared"})
    r = client.put(f"/api/employees/{eid}", headers=hdr,
                   json={"name": "أحمد محمود علي", "civil_id": EMP_CIVIL,
                         "job_title_en": ""})
    assert r.status_code == 200, r.text[:200]

    db = SessionLocal()
    try:
        assert (db.get(models.Employee, eid).job_title_en or "") == ""
    finally:
        db.close()


def test_the_critical_history_does_not_record_phantom_changes(client):
    """ولا يُقيَّد في السجل تغيٌُّر لم يقع.

    كان المحو يمرّ بـ``CRITICAL_FIELDS`` فيكتب «الراتب: 650 ← 0» —
    سجٌّل يوثّق تدميًرا ويجعله يبدو قراًرا.
    """
    eid = _emp_id()
    _seed(eid)
    db = SessionLocal()
    try:
        before_n = db.scalar(select(models.EmployeeFieldChange.id).where(
            models.EmployeeFieldChange.employee_id == eid
        ).order_by(models.EmployeeFieldChange.id.desc())) or 0
    finally:
        db.close()

    client.put(f"/api/employees/{eid}", headers=auth_headers(login(client, *HR)),
               json={"name": "أحمد محمود علي", "civil_id": EMP_CIVIL,
                     "phone": "50008888"})

    db = SessionLocal()
    try:
        rows = db.scalars(select(models.EmployeeFieldChange).where(
            models.EmployeeFieldChange.employee_id == eid,
            models.EmployeeFieldChange.id > before_n)).all()
    finally:
        db.close()
    assert not rows, (
        f"قُيّد تغيير لم يُطلَب: {[(r.field_name, r.old_value, r.new_value) for r in rows]}"
    )


def test_editing_a_name_does_not_demand_attendance_permission(client):
    """وحارس الحضور لا يقع على من لم يمسّه.

    كان يقارن قيمة الموظف بما **لم يُرسَل**، فيرى كل تعديل مسًّا بسياسة
    الحضور ويطلب صلاحية إدارتها ممّن يصحّح اسًما.
    """
    eid = _emp_id()
    r = client.put(f"/api/employees/{eid}", headers=auth_headers(login(client, *HR)),
                   json={"name": "أحمد محمود علي", "civil_id": EMP_CIVIL})
    assert r.status_code == 200, r.text[:200]


def test_the_merge_is_the_mechanism_not_a_field_list():
    """والعلاج عام لا قائمة حقول تُنسى عند إضافة عمود جديد."""
    src = inspect.getsource(emp_router.update_employee)
    assert "exclude_unset=True" in src, (
        "عاد التعديل يكتب كل حقول المخطّط — بما لم يُرسَل"
    )
