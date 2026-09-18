# -*- coding: utf-8 -*-
"""من لن يصدر له عقدٌ حكومي — يُعرف مقدًَّما، وبقاعدة المولِّد نفسها.

العقدُ يوقف إصداره حقٌل ناقص ويسمّيه (قرار المالك 2026-09-17). فبلا هذه
القائمة يكتشف HR النقَص موظًفا موظًفا عند الضغط، ونقٌص في الشركة يوقف
عقوَد الجميع دفعًة واحدة. **والقائمُة والمولُِّد لا يختلفان**: موظٌف تقول
القائمُة إنه جاهز يصدر عقُده، ومن تقول إنه ناقص يُرفض بالسبب نفسه.
"""
from __future__ import annotations

from sqlalchemy import select

from app import gov_contract_data, gov_contract_form, models
from app.database import SessionLocal
from app.gov_contract_readiness import COMPANY_LEVEL, readiness
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")


def test_the_list_and_the_generator_agree_for_every_employee():
    from app.routers.templates import _resolve_authoritative_data

    db = SessionLocal()
    try:
        r = readiness(db, 1)
        blocked = {e["employee_id"]: set(e["missing"]) for e in r["employees"]}
        company = db.get(models.Company, 1)
        emps = db.scalars(select(models.Employee).where(
            models.Employee.company_id == 1)).all()
        for emp in emps:
            if emp.status in ("archived", "terminated", "resigned", "retired") or emp.non_payroll:
                continue
            ctx = _resolve_authoritative_data(db, emp, extras={})
            ctx.update(gov_contract_data.contract_context(db, emp, company))
            *_, missing, _ = gov_contract_form.generate(ctx)
            own = {m for m in missing
                   if m not in {gov_contract_form.REQUIRED[k] for k in COMPANY_LEVEL}}
            assert own == blocked.get(emp.id, set()), (emp.name, own, blocked.get(emp.id))
    finally:
        db.close()


def test_a_company_level_gap_is_reported_once_not_per_employee():
    db = SessionLocal()
    try:
        c = db.get(models.Company, 1)
        snap = c.representative_name
        c.representative_name = None
        db.flush()
        r = readiness(db, 1)
        assert gov_contract_form.REQUIRED["company_rep_name"] in r["company_missing"]
        for e in r["employees"]:
            assert gov_contract_form.REQUIRED["company_rep_name"] not in e["missing"]
    finally:
        db.rollback()
        db.close()


def test_the_pro_sees_it_in_the_operations_centre(client):
    """مركُز العمليات للمندوب — وهو من يُصدر عقَد التجديد."""
    r = client.get("/api/operations",
                   headers=auth_headers(login(client, "100000000003", "deleg123")))
    assert r.status_code == 200, r.text[:200]
    assert "gov_contract_readiness" in r.json()


def test_hr_sees_it_where_hr_issues_the_hire_contract(client):
    """ومركُز العمليات مغلٌق أمام الموارد البشرية — وهي من يُصدر عقَد التعيين.
    فالقائمُة تُعرض في شاشة الموظفين أيًضا، بصلاحية الإصدار نفسها."""
    r = client.get("/api/employees/gov-contract-readiness",
                   headers=auth_headers(login(client, *HR)))
    assert r.status_code == 200, r.text[:200]
    body = r.json()
    assert "company_missing" in body and "employees" in body
    import pathlib
    src = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages"
    assert "gov-contract-readiness" in (src / "Employees.tsx").read_text(encoding="utf-8")
    assert "gov_contract_readiness" in (src / "Operations.tsx").read_text(encoding="utf-8")
