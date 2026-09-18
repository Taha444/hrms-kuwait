# -*- coding: utf-8 -*-
"""تعديُل الراتب يصدر بقرار، والنوع الأجوف يخرج من القائمة — قرار المالك (2026-09-18).

- ``ADMACTUAL`` «تعديل الراتب الفعلي أو مكان العمل الفعلي»: لا نموذج له ولا
  أثر — اعتماده لا يغيّر شيئًا. فيُرفع من قائمة الإنشاء ويُرفض إنشاؤه، وما
  قُدِّم منه قبلُ يبقى يُقرأ ويُبَتّ فيه.
- والراتب يتغيّر فعلًا من «اقتراح تعديل» في ملف الموظف (اقتراح ← اعتماد
  غيره) — وكان بلا ورقة. فاعتماُده يُصدر «قرار تعديل راتب» (``HRMS-PR-019``)
  بالقديم والجديد، مستندًا مُصدَرًا في ملف الموظف برقٍم مرجعي وبصمة.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")
MGR = ("100000000001", "manager123")


def _pick_employee():
    db = SessionLocal()
    try:
        mine = [u.employee_id for u in db.scalars(select(models.User).where(
            models.User.civil_id.in_([HR[0], MGR[0]]))).all() if u.employee_id]
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.status == "active",
            models.Employee.id.notin_(mine or [-1])))
        return emp.id, emp.basic_salary, emp.actual_salary
    finally:
        db.close()


def _restore(emp_id, basic, actual):
    db = SessionLocal()
    try:
        e = db.get(models.Employee, emp_id)
        e.basic_salary, e.actual_salary = basic, actual
        db.commit()
    finally:
        db.close()


def _decisions(emp_id):
    db = SessionLocal()
    try:
        return db.scalars(select(models.Document).where(
            models.Document.entity_type == "employee",
            models.Document.entity_id == emp_id,
            models.Document.document_type_code == "form_HRMS-PR-019")).all()
    finally:
        db.close()


def test_an_approved_salary_change_issues_its_decision(client):
    emp_id, basic, actual = _pick_employee()
    before = len(_decisions(emp_id))
    try:
        r = client.post(f"/api/employees/{emp_id}/salary-change-request",
                        headers=auth_headers(login(client, *HR)),
                        params={"field_name": "basic_salary", "new_value": "1234.5",
                                "effective_date": (date.today() + timedelta(days=5)).isoformat(),
                                "reason": "مراجعة سنوية"})
        assert r.status_code == 201, r.text[:200]
        ok = client.post(f"/api/employees/salary-change-requests/{r.json()['request_id']}/decide",
                         headers=auth_headers(login(client, *MGR)),
                         params={"decision": "approved"})
        assert ok.status_code == 200, ok.text[:200]
        assert ok.json().get("document_id"), ok.json()
        docs = _decisions(emp_id)
        assert len(docs) == before + 1, "اعتُمد تعديل الراتب بلا قرار"
        doc = docs[-1]
        assert doc.is_issued and doc.reference_no and doc.checksum_sha256
    finally:
        _restore(emp_id, basic, actual)


def test_a_non_salary_change_issues_no_salary_decision(client):
    emp_id, basic, actual = _pick_employee()
    before = len(_decisions(emp_id))
    db = SessionLocal()
    try:
        old_title = db.get(models.Employee, emp_id).job_title
    finally:
        db.close()
    try:
        r = client.post(f"/api/employees/{emp_id}/salary-change-request",
                        headers=auth_headers(login(client, *HR)),
                        params={"field_name": "job_title", "new_value": "مسمى اختبار",
                                "effective_date": date.today().isoformat(),
                                "reason": "تصحيح"})
        assert r.status_code == 201, r.text[:200]
        ok = client.post(f"/api/employees/salary-change-requests/{r.json()['request_id']}/decide",
                         headers=auth_headers(login(client, *MGR)),
                         params={"decision": "approved"})
        assert ok.status_code == 200, ok.text[:200]
        assert len(_decisions(emp_id)) == before
    finally:
        db = SessionLocal()
        try:
            db.get(models.Employee, emp_id).job_title = old_title
            db.commit()
        finally:
            db.close()


def test_the_hollow_type_is_gone_from_the_list_and_refused(client):
    h = auth_headers(login(client, *HR))
    types = client.get("/api/requests/types", headers=h, params={"creatable_only": True})
    assert types.status_code == 200, types.text[:200]
    assert "ADMACTUAL" not in {t["code"] for t in types.json()}
    emp_id, _b, _a = _pick_employee()
    r = client.post("/api/requests", headers=h, json={
        "request_type_code": "ADMACTUAL", "employee_id": emp_id, "payload_json": {}})
    assert r.status_code in (400, 409, 410), (r.status_code, r.text[:200])
    assert "اقتراح" in r.text or "الراتب" in r.text
