# -*- coding: utf-8 -*-
"""بدلُ الإنذار وأساسُ المكافأة — قرارا المالك (2026-09-17) مُثبَّتَين.

كان ``eos.notice_pay`` وسياسةُ ``eos.notice_days`` قائمَين **بلا مناد**،
والتسويةُ ``indemnity + leave_payout`` وحدهما، ولا حقلَ يسجّل هل أُبلغ
الإنذار. فالفصلُ غير التأديبي بلا إنذار كان يُسوّى **بلا بدله** (المادة 44).

**والقرار**: يُربط البدلُ بحقل «أُبلغ الإنذار؟» وتاريخه:

- فصلٌ غير تأديبي بلا إنذار ← مدةُ الإنذار كاملة (أيامٌ تقويمية، أجرُها
  بالشهر ÷30: تسعون يومًا = ثلاثة رواتب أساسية).
- أُبلغ قبل الإنهاء بمدة ← ما بقي منها وحده.
- الفصلُ التأديبي (م41) والاستقالة ← لا بدل.
- لم يُسجَّل الجواب في فصلٍ غير تأديبي ← **يُرفض الحساب** لا يُفترض.

**وأساسُ المكافأة الراتبُ الأساسي وحده** — البدلات لا تدخل.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import delete as sa_delete, select

from app import eos as E, models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")
ACC = ("100000000007", "account123")
TERM = "2027-06-01"


# ---------------------------------------------------------------------------
# المحرّك
# ---------------------------------------------------------------------------

def _calc(reason="termination", owed=0.0, basic=900):
    return E.calculate_eos(basic, "2020-01-01", TERM, reason=reason,
                           day_divisor=26, notice_days_owed=owed)


def test_unserved_notice_pays_three_basic_salaries():
    base, full = _calc(owed=0), _calc(owed=90)
    assert full["notice_payout"] == pytest.approx(2700.0)
    assert full["total_settlement"] == pytest.approx(base["total_settlement"] + 2700.0)


@pytest.mark.parametrize("served_date, owed", [
    ("2027-05-02", 60.0),       # أُبلغ قبل ثلاثين يومًا
    ("2027-03-03", 0.0),        # أُبلغ قبل تسعين يومًا
    ("2026-01-01", 0.0),        # أكثر من المدة — لا سالب
])
def test_partial_notice_pays_only_what_is_left(served_date, owed):
    got = E.notice_owed_days("termination", 90, True, date.fromisoformat(served_date),
                             date.fromisoformat(TERM))
    assert got == owed


@pytest.mark.parametrize("reason", ["misconduct", "resignation", "contract_expiry",
                                    "death", "disability", "marriage"])
def test_no_notice_pay_outside_non_disciplinary_termination(reason):
    assert E.notice_owed_days(reason, 90, False, None, date.fromisoformat(TERM)) == 0.0
    assert E.notice_owed_days(reason, 90, None, None, date.fromisoformat(TERM)) == 0.0


def test_an_unanswered_or_undated_notice_is_not_assumed():
    t = date.fromisoformat(TERM)
    assert E.notice_owed_days("termination", 90, None, None, t) is None
    assert E.notice_owed_days("termination", 90, True, None, t) is None


def test_the_indemnity_basis_is_basic_salary_only():
    """أساسُ المكافأة: لا مُدخَل للبدلات في المحرّك، والمساراتُ تمرّر الأساسي."""
    import inspect

    from app.routers import employees as RE, eos as RO

    params = inspect.signature(E.calculate_eos).parameters
    assert not [p for p in params if "allow" in p or "gross" in p or "total_salary" in p]
    for fn in (RO.calculate_case, RO.for_employee, RE.prepare_termination):
        src = inspect.getsource(fn)
        assert "basic_salary=emp.basic_salary" in src, fn.__name__
    # والرقم نفسه: الراتبُ اليومي من الأساسي وحده.
    assert _calc(basic=780)["daily_wage"] == pytest.approx(30.0)


# ---------------------------------------------------------------------------
# المسار الكامل
# ---------------------------------------------------------------------------

@pytest.fixture
def emp_id():
    db = SessionLocal()
    try:
        hr = db.scalar(select(models.User).where(models.User.civil_id == HR[0]))
        eid = db.scalar(select(models.Employee.id).where(
            models.Employee.company_id == hr.company_id,
            models.Employee.status == "active",
            models.Employee.basic_salary.isnot(None),
            models.Employee.hire_date.isnot(None),
            models.Employee.non_payroll.is_(False)).order_by(models.Employee.id.desc()))
        db.execute(sa_delete(models.EosCase).where(models.EosCase.employee_id == eid))
        db.commit()
        yield eid
        db.execute(sa_delete(models.EosCase).where(models.EosCase.employee_id == eid))
        db.commit()
    finally:
        db.close()


def _open(client, eid, **extra):
    r = client.post("/api/eos/cases", headers=auth_headers(login(client, *HR)),
                    params={"employee_id": eid, "termination_date": TERM,
                            "reason": "termination", **extra})
    assert r.status_code == 201, r.text[:200]
    return r.json()


def _calculate(client, cid):
    return client.post(f"/api/eos/cases/{cid}/calculate",
                       headers=auth_headers(login(client, *ACC)),
                       params={"used_leave_days": 0})


def test_a_case_without_the_answer_cannot_be_calculated(client, emp_id):
    case = _open(client, emp_id)
    r = _calculate(client, case["id"])
    assert r.status_code == 409, (r.status_code, r.text[:200])
    assert "الإنذار" in r.json()["detail"]


def test_an_unserved_case_carries_the_notice_payout(client, emp_id):
    case = _open(client, emp_id, notice_served="false")
    assert case["notice_served"] is False
    r = _calculate(client, case["id"])
    assert r.status_code == 200, r.text[:200]
    s = r.json()["settlement"]
    db = SessionLocal()
    try:
        basic = float(db.get(models.Employee, emp_id).basic_salary)
    finally:
        db.close()
    assert s["notice"]["owed_days"] == 90
    assert s["notice_payout"] == pytest.approx(round(basic * 3, 3))
    assert s["total_settlement"] == pytest.approx(
        round(s["indemnity"] + s["leave_payout"] + s["notice_payout"], 3), abs=0.002)


def test_recording_a_served_notice_reduces_it_and_is_audited(client, emp_id):
    case = _open(client, emp_id)
    hr = auth_headers(login(client, *HR))
    bad = client.post(f"/api/eos/cases/{case['id']}/notice", headers=hr,
                      params={"served": "true"})
    assert bad.status_code == 400
    late = client.post(f"/api/eos/cases/{case['id']}/notice", headers=hr,
                       params={"served": "true", "served_date": "2027-07-01"})
    assert late.status_code == 400
    ok = client.post(f"/api/eos/cases/{case['id']}/notice", headers=hr,
                     params={"served": "true", "served_date": "2027-05-02"})
    assert ok.status_code == 200, ok.text[:200]
    assert ok.json()["notice_served_date"] == "2027-05-02"
    s = _calculate(client, case["id"]).json()["settlement"]
    assert s["notice"]["owed_days"] == 60
    db = SessionLocal()
    try:
        assert db.scalar(select(models.AuditLog).where(
            models.AuditLog.action == "eos_notice_recorded",
            models.AuditLog.entity_id == case["id"]))
    finally:
        db.close()
    # وبعد الحساب لا يُعدَّل جانبيًّا.
    after = client.post(f"/api/eos/cases/{case['id']}/notice", headers=hr,
                        params={"served": "false"})
    assert after.status_code == 409


def test_the_termination_draft_obeys_the_same_rule(client, emp_id):
    hr = auth_headers(login(client, *HR))
    url = f"/api/employees/{emp_id}/terminate"
    try:
        missing = client.post(url, headers=hr, params={"end_date": TERM, "reason": "termination"})
        assert missing.status_code == 409, missing.text[:200]
        ok = client.post(url, headers=hr, params={"end_date": TERM, "reason": "termination",
                                                  "notice_served": "false"})
        assert ok.status_code == 200, ok.text[:200]
        assert ok.json()["settlement"]["notice"]["owed_days"] == 90
    finally:
        client.post(f"{url}/cancel", headers=hr)


def test_misconduct_needs_no_answer_and_pays_no_notice(client, emp_id):
    r = client.post("/api/eos/cases", headers=auth_headers(login(client, *HR)),
                    params={"employee_id": emp_id, "termination_date": TERM,
                            "reason": "misconduct"})
    calc = _calculate(client, r.json()["id"])
    assert calc.status_code == 200, calc.text[:200]
    assert calc.json()["settlement"]["notice_payout"] == 0
