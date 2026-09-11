# -*- coding: utf-8 -*-
"""بدٌل يُعتمد ولا يُصرَف — والرواتب لا تعرف البدلات أصًلا.

**العطل المقيس**: نموذج ``REQALLOW`` يجمع ``allowance_type`` و``amount``
و``effective_from`` و``is_recurring`` — **ولا يقرؤها أحد**. والأبعد من
ذلك: ``gross = earned_basic + overtime_pay`` — فالرواتب **بلا مكوّن
بدلات إطلاًقا**، ولا موضع يهبط فيه البدل لو قُرئ.

فيُعتمد البدل بمرحلتين (مسؤول الفرع ثم المدير) ويُغلَق «مكتمًلا»، ولا
يُصرَف منه فلس. وهو الوجه الموجب للعطل الذي أُصلح في الخصم.

**ولا يمسّ هذا أساًسا قانونًيا**: نهايُة الخدمة تُحسب من ``basic_salary``
صراحًة (``eos.py``)، وأجُر الإضافي من ``basic / divisor``. فكلا الأساسين
على الأساسي لا على الإجمالي، والبدل يدخل أجر الشهر ولا يدخلهما. وهل
**ينبغي** أن يدخلهما سؤاٌل قانوني قائٌم قبل هذا العمل ولم يُحدِثه — وهو
لصاحب القرار.

**وجدوٌل مستقل لا خصٌم بإشارة سالبة**: الحيلة تُغري لأنها توفّر جدوًلا،
وتُفسِد كل تقرير خصومات بعدها — فمن يراجع «كم اقتُطع من فلان» يقرأ رقًما
ناقًصا بقدر بدلاته. والأثر الموجب والسالب معنيان مختلفان لا إشارتان
لمعًنى واحد.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import delete as sa_delete, select

from app import models, payroll
from app.database import SessionLocal
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
SUP = ("100000000005", "sup12345")
MGR = ("100000000001", "manager123")

MONTH = "2034-03"


def _emp_id() -> int:
    db = SessionLocal()
    try:
        return db.scalar(select(models.Employee.id).where(
            models.Employee.civil_id == EMP[0]))
    finally:
        db.close()


def _purge(rid: int) -> None:
    db = SessionLocal()
    try:
        db.execute(sa_delete(models.Allowance).where(
            models.Allowance.request_id == rid))
        for tbl in (models.RequestDocument, models.RequestApproval):
            db.execute(sa_delete(tbl).where(tbl.request_id == rid))
        db.execute(sa_delete(models.Task).where(
            models.Task.related_entity_type == "request",
            models.Task.related_entity_id == rid))
        db.execute(sa_delete(models.Request).where(models.Request.id == rid))
        db.commit()
    finally:
        db.close()


def _grant(client, amount: float, *, recurring: bool = False,
           start: str = f"{MONTH}-01", end: str | None = None) -> int:
    payload = {"allowance_type": "transport", "amount": amount,
               "effective_from": start, "is_recurring": recurring,
               "reason": "قياس أثر البدل"}
    if end:
        payload["effective_to"] = end
    r = client.post("/api/requests", headers=auth_headers(login(client, *EMP)),
                    json={"request_type_code": "REQALLOW", "payload_json": payload})
    assert r.status_code in (200, 201), r.text[:300]
    rid = r.json()["id"]
    for who in (SUP, MGR):
        d = client.post(f"/api/requests/{rid}/decide",
                        headers=auth_headers(login(client, *who)),
                        json={"decision": "approved"})
        assert d.status_code == 200, (who[0], d.text[:200])
    return rid


def _payslip(month: str) -> dict | None:
    """قسيمة هذا الموظف لشهر ``YYYY-MM``."""
    year, mon = (int(x) for x in month.split("-"))
    db = SessionLocal()
    try:
        emp = db.get(models.Employee, _emp_id())
        out = payroll.compute_payroll(db, emp.company_id, year, mon)
        for r in out["payslips"]:
            if r["employee_id"] == emp.id:
                return r
        return None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# الأثر يقع
# ---------------------------------------------------------------------------

def test_an_approved_allowance_is_recorded(client):
    """**جوهر البند**: البدل يُنتج صفَّه، لا حالًة «مكتمل» وحدها."""
    rid = _grant(client, 25.0)
    try:
        db = SessionLocal()
        try:
            row = db.scalar(select(models.Allowance).where(
                models.Allowance.request_id == rid))
        finally:
            db.close()
        assert row is not None, "اعتُمد البدل ولم يُسجَّل"
        assert row.amount == pytest.approx(25.0)
        assert row.effective_from == date.fromisoformat(f"{MONTH}-01")
        assert row.allowance_type == "transport"
    finally:
        _purge(rid)


def test_the_payroll_actually_pays_it(client):
    """**ولا يكفي أن يُسجَّل**: يدخل أجر الشهر فعًلا.

    وكان ``gross`` أساسًيا وإضافًيا فقط — فبدٌل يُسجَّل ولا يُقرأ عطٌل
    كالذي قبله، مقلوًبا.
    """
    before = _payslip(MONTH)
    rid = _grant(client, 25.0)
    try:
        after = _payslip(MONTH)
        assert after is not None
        assert after["allowances"] == pytest.approx(
            (before or {}).get("allowances", 0) + 25.0)
        assert after["gross"] == pytest.approx((before or {})["gross"] + 25.0)
        assert after["net"] == pytest.approx((before or {})["net"] + 25.0)
    finally:
        _purge(rid)


def test_it_touches_no_legal_base(client):
    """**ولا يمسّ أساًسا قانونًيا**: الأساسي كما هو، والإضافي كما هو.

    نهايُة الخدمة تُحسب من ``basic_salary`` وأجُر الإضافي من
    ``basic/divisor`` — فإدخاُل البدل في الإجمالي لا يحرّكهما. وهذا هو ما
    يجعل التغيير آمًنا، فيُقاس لا يُفترَض.
    """
    before = _payslip(MONTH)
    rid = _grant(client, 40.0)
    try:
        after = _payslip(MONTH)
        assert after["basic_salary"] == pytest.approx(before["basic_salary"])
        assert after["earned_basic"] == pytest.approx(before["earned_basic"])
        assert after["overtime_pay"] == pytest.approx(before["overtime_pay"])
    finally:
        _purge(rid)


def test_a_one_off_allowance_is_paid_once(client):
    """وبدٌل لمرٍّة واحدة يُصرَف في شهره ولا يتكرّر بعده."""
    rid = _grant(client, 30.0, recurring=False)
    try:
        this_month = _payslip(MONTH)["allowances"]
        next_month = _payslip("2034-04")["allowances"]
        assert this_month == pytest.approx(30.0), this_month
        assert next_month == pytest.approx(0.0), next_month
    finally:
        _purge(rid)


def test_a_recurring_allowance_repeats_within_its_term(client):
    """والمتكرّر يتكرّر داخل مدّته — ويقف عند نهايتها."""
    rid = _grant(client, 10.0, recurring=True,
                 start=f"{MONTH}-01", end="2034-04-30")
    try:
        assert _payslip(MONTH)["allowances"] == pytest.approx(10.0)
        assert _payslip("2034-04")["allowances"] == pytest.approx(10.0)
        assert _payslip("2034-05")["allowances"] == pytest.approx(0.0)
    finally:
        _purge(rid)


def test_it_is_not_paid_before_it_takes_effect(client):
    """ولا يُصرَف قبل تاريخ نفاذه."""
    rid = _grant(client, 15.0, recurring=True, start=f"{MONTH}-01")
    try:
        assert _payslip("2034-02")["allowances"] == pytest.approx(0.0)
    finally:
        _purge(rid)


# ---------------------------------------------------------------------------
# ولا يُخلَط بالخصم
# ---------------------------------------------------------------------------

def test_an_allowance_is_never_a_negative_deduction(client):
    """**والأثر الموجب والسالب معنيان لا إشارتان.**

    خصٌم بإشارة سالبة يوفّر جدوًلا ويُفسِد كل تقرير خصومات بعده: من يراجع
    «كم اقتُطع من فلان» يقرأ رقًما ناقًصا بقدر بدلاته.
    """
    rid = _grant(client, 20.0)
    try:
        db = SessionLocal()
        try:
            negatives = db.scalars(select(models.Deduction).where(
                models.Deduction.employee_id == _emp_id(),
                models.Deduction.amount < 0)).all()
        finally:
            db.close()
        assert not negatives, "بدٌل كُتب خصًما سالًبا"
        assert _payslip(MONTH)["other_deductions"] >= 0
    finally:
        _purge(rid)


# ---------------------------------------------------------------------------
# والإلغاء يعكس ما لم يُصرَف
# ---------------------------------------------------------------------------

def test_cancelling_before_payment_removes_it(client):
    """بدٌل لم يدخل مسيًَّرا يُحذف بالإلغاء."""
    rid = _grant(client, 18.0)
    try:
        r = client.post(f"/api/requests/{rid}/cancel",
                        headers=auth_headers(login(client, *MGR)),
                        params={"note": "إلغاء قبل الصرف"})
        assert r.status_code == 200, (r.status_code, r.text[:250])
        db = SessionLocal()
        try:
            rows = db.scalars(select(models.Allowance).where(
                models.Allowance.request_id == rid)).all()
        finally:
            db.close()
        assert not rows, "بقي البدل بعد إلغائه"
    finally:
        _purge(rid)


def test_what_was_already_paid_is_not_erased(client):
    """**وما صُرف فعًلا لا يُردّ بحذف صفّ** — سحبُه استرداٌد لا محُو سجل."""
    rid = _grant(client, 22.0)
    db = SessionLocal()
    run_id = None
    try:
        emp = db.get(models.Employee, _emp_id())
        run = models.PayrollRun(company_id=emp.company_id, period=MONTH,
                                status="finalized")
        db.add(run)
        db.commit()
        run_id = run.id
    finally:
        db.close()
    try:
        r = client.post(f"/api/requests/{rid}/cancel",
                        headers=auth_headers(login(client, *MGR)),
                        params={"note": "محاولة إلغاء بعد الصرف"})
        assert r.status_code == 409, (r.status_code, r.text[:250])
        assert "استرداد" in r.text or "استرداٌد" in r.text, r.text[:250]
        db = SessionLocal()
        try:
            rows = db.scalars(select(models.Allowance).where(
                models.Allowance.request_id == rid)).all()
        finally:
            db.close()
        assert len(rows) == 1, "مُحي بدٌل صُرف فعًلا"
    finally:
        _purge(rid)
        db = SessionLocal()
        try:
            db.execute(sa_delete(models.PayrollRun).where(
                models.PayrollRun.id == run_id))
            db.commit()
        finally:
            db.close()


# ---------------------------------------------------------------------------
# والنموذج يفتحه صاحبه — قرار المالك
# ---------------------------------------------------------------------------

def test_the_employee_can_reach_the_allowance_form(client):
    """**نموٌذج بصوت صاحبه لا يفتحه صاحبه.**

    نصُّ النوع الرسمي: «أتقدم بطلب بدل أو ميزة وفق البيانات الموضحة»،
    وسلسلتُه تبدأ من مسؤوله المباشر. وكان محجوًبا عن كتالوجه — وهو العطل
    نفسه الذي ظهر في ``REQWARN`` و``REQVIO``.
    """
    types = client.get("/api/requests/types",
                       headers=auth_headers(login(client, *EMP))).json()
    codes = {t["code"] for t in (types if isinstance(types, list)
                                 else types.get("items") or [])}
    assert "REQALLOW" in codes, f"ليس في كتالوج الموظف: {sorted(codes)}"


def test_and_he_can_actually_submit_it(client):
    """ولا يكفي أن يُعرَض: يُقدَّم فعًلا ويمضي في مساره.

    والحجب كان في الكتالوج وحده — الموظف يحمل ``submit_request`` فالمسار
    يقبله لنفسه. أي أن الحقّ كان قائًما ولا طريق إليه.
    """
    r = client.post("/api/requests", headers=auth_headers(login(client, *EMP)),
                    json={"request_type_code": "REQALLOW",
                          "payload_json": {"allowance_type": "transport",
                                           "amount": 12.0,
                                           "effective_from": f"{MONTH}-01",
                                           "is_recurring": False,
                                           "reason": "بدل مواصلات"}})
    assert r.status_code in (200, 201), r.text[:300]
    rid = r.json()["id"]
    try:
        db = SessionLocal()
        try:
            req = db.get(models.Request, rid)
            assert req.status == "pending", req.status
        finally:
            db.close()
    finally:
        _purge(rid)
