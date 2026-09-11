# -*- coding: utf-8 -*-
"""قراُر خصٍم يُعتمد ولا يُخصَم — وجدوٌل يُقرأ ولا يُكتب.

**العطل المقيس**: ``ADMDED`` يمرّ بثلاث مراحل (شؤون الموظفين ← المحاسب ←
المدير) ويُغلَق «مكتمًلا». وجدول ``deductions`` **تقرؤه** الرواتب سطًرا
سطًرا وتجمعه في ``other_deductions`` — **ولا سطَر في النظام كلّه يُنشئ
صًفا فيه**. فالمجموع صفٌر دائًما مهما اعتُمد من قرارات.

ومفهومان متوازيان يتقاسمان المعنى:

===========================================  ==========  ==============
المفهوم                                      يُكتَب      تقرؤه الرواتب
===========================================  ==========  ==============
``EmployeeEvent(kind="penalty", amount=…)``  يدوًيا      **لا**
``Deduction``                                **لا شيء**  نعم
===========================================  ==========  ==============

فالذي يُكتب لا يُقرأ، والذي يُقرأ لا يُكتب.

**وازداد الأمر خطًرا بعمل هذه الجولة نفسها**: صار ``ADMDED`` يُصدر «قرار
خصم» موقًَّعا (``OD-008``). فلولا هذا الأثر لصارت **ورقٌة تشهد بخصٍم لم
يقع** — وهي أسوأ من غياب الورقة.

**وبإذٍن صريح من المالك** (القاعدة 20 من قواعد الحماية: لا مساس
بالرواتب إلا بـFinding مثبت وموافقة).
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import delete as sa_delete, select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
HR = ("100000000002", "hr12345")
ACC = ("100000000007", "account123")
MGR = ("100000000001", "manager123")

MONTH = "2031-04"
AMOUNT = 12.5


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
        db.execute(sa_delete(models.Deduction).where(
            models.Deduction.request_id == rid))
        for tbl in (models.RequestDocument, models.RequestApproval):
            db.execute(sa_delete(tbl).where(tbl.request_id == rid))
        db.execute(sa_delete(models.Task).where(
            models.Task.related_entity_type == "request",
            models.Task.related_entity_id == rid))
        db.execute(sa_delete(models.Request).where(models.Request.id == rid))
        db.commit()
    finally:
        db.close()


def _issue(client, **overrides) -> int:
    payload = {"deduction_amount": AMOUNT, "reason": "غراماُت تأخير موثَّقة",
               "payroll_month": MONTH}
    payload.update(overrides)
    r = client.post("/api/requests", headers=auth_headers(login(client, *HR)),
                    json={"request_type_code": "ADMDED",
                          "employee_id": _emp_id(), "payload_json": payload})
    assert r.status_code in (200, 201), r.text[:300]
    return r.json()["id"]


def _approve_all(client, rid: int):
    last = None
    for who in (HR, ACC, MGR):
        last = client.post(f"/api/requests/{rid}/decide",
                           headers=auth_headers(login(client, *who)),
                           json={"decision": "approved"})
        assert last.status_code == 200, (who[0], last.text[:200])
    return last


@pytest.fixture
def applied(client):
    """قراُر خصٍم معتمٌَد بالمراحل الثلاث."""
    rid = _issue(client)
    _approve_all(client, rid)
    yield rid
    _purge(rid)


# ---------------------------------------------------------------------------
# الأثر يقع
# ---------------------------------------------------------------------------

def test_an_approved_deduction_actually_writes_a_deduction(client, applied):
    """**جوهر البند**: القرار يُنتج مدخَل الرواتب، لا حالًة «مكتمل» وحدها."""
    db = SessionLocal()
    try:
        row = db.scalar(select(models.Deduction).where(
            models.Deduction.request_id == applied))
        got = (row.amount, str(row.date), row.employee_id) if row else None
    finally:
        db.close()
    assert row is not None, "اعتُمد القرار ولم يُكتب خصٌم"
    assert got[0] == pytest.approx(AMOUNT)
    assert got[1] == f"{MONTH}-01", got[1]


def test_the_payroll_actually_sees_it(client, applied):
    """**ولا يكفي أن يُكتَب**: الرواتب تقرأ بالتاريخ داخل حدود الشهر.

    فصفٌّ بتاريخ خارج الشهر يُكتب ولا يُقرأ — وهو العطل نفسه مقلوًبا.
    """
    db = SessionLocal()
    try:
        row = db.scalar(select(models.Deduction).where(
            models.Deduction.request_id == applied))
        first = date.fromisoformat(f"{MONTH}-01")
        nxt = date(first.year + (first.month == 12), (first.month % 12) + 1, 1)
        inside = first <= row.date < nxt
    finally:
        db.close()
    assert inside, f"تاريخ الخصم {row.date} خارج حدود {MONTH}"


def test_the_deduction_names_its_decision(client, applied):
    """**وخصٌم بلا مصدر رقٌم بلا تفسير** — من يقرأ الكشف يبلغ قراره."""
    db = SessionLocal()
    try:
        row = db.scalar(select(models.Deduction).where(
            models.Deduction.request_id == applied))
        assert row.request_id == applied
        assert (row.reason or "").strip(), "خصٌم بلا سبب مكتوب"
    finally:
        db.close()


def test_one_decision_never_becomes_two_deductions(client, applied):
    """وقراٌر واحٌد لا يُنتج خصمين — ولو أُعيد تطبيق الأثر."""
    from app import workflow

    db = SessionLocal()
    try:
        req = db.get(models.Request, applied)
        ok, note = workflow._apply_deduction(db, req)
        db.commit()
        count = len(db.scalars(select(models.Deduction).where(
            models.Deduction.request_id == applied)).all())
    finally:
        db.close()
    assert ok, note
    assert count == 1, f"تكرّر الخصم: {count}"


# ---------------------------------------------------------------------------
# ولا يقع حيث لا يُقرأ
# ---------------------------------------------------------------------------

def test_a_closed_payroll_month_refuses_the_deduction(client):
    """**أثٌر يُعلَن واقًعا ولا يقع** — وهو العطل نفسه مقلوًبا.

    الرواتب تقرأ الخصومات داخل حدود الشهر، فصفٌّ يُكتب في شهٍر اكتمل
    مسيّره لا يقرؤه أحٌد أبًدا. فيُردّ الطلب ``apply_failed`` بسببه
    مكتوًبا بدل أن يُختم «مكتمًلا» بلا أثر.
    """
    closed = "2031-05"
    db = SessionLocal()
    try:
        emp = db.get(models.Employee, _emp_id())
        run = models.PayrollRun(company_id=emp.company_id, period=closed,
                                status="locked")
        db.add(run)
        db.commit()
        run_id = run.id
    finally:
        db.close()

    rid = _issue(client, payroll_month=closed)
    try:
        _approve_all(client, rid)
        db = SessionLocal()
        try:
            req = db.get(models.Request, rid)
            # سبُب الفشل يُكتب صفَّ قراٍر باسم النظام — لا عموًدا على الطلب.
            fail = db.scalar(select(models.RequestApproval).where(
                models.RequestApproval.request_id == rid,
                models.RequestApproval.decision == "apply_failed",
            ).order_by(models.RequestApproval.id.desc()))
            status, note = req.status, (getattr(fail, "note", "") or "")
            rows = db.scalars(select(models.Deduction).where(
                models.Deduction.request_id == rid)).all()
        finally:
            db.close()
        assert status == "apply_failed", status
        assert not rows, "كُتب خصٌم في شهٍر مقفل"
        assert closed in note or "أُقفل" in note, note
    finally:
        _purge(rid)
        db = SessionLocal()
        try:
            db.execute(sa_delete(models.PayrollRun).where(
                models.PayrollRun.id == run_id))
            db.commit()
        finally:
            db.close()


def test_a_missing_amount_is_refused_at_the_door(client):
    """ومبلٌغ ناقص يُردّ عند التقديم لا عند التطبيق."""
    r = client.post("/api/requests", headers=auth_headers(login(client, *HR)),
                    json={"request_type_code": "ADMDED",
                          "employee_id": _emp_id(),
                          "payload_json": {"reason": "بلا مبلغ",
                                           "payroll_month": MONTH}})
    assert r.status_code == 400, r.status_code
    assert "deduction_amount" in r.text, r.text[:250]


# ---------------------------------------------------------------------------
# وأثٌر وقع لا يُلغى بتغيير حالة
# ---------------------------------------------------------------------------

def test_cancelling_an_applied_request_is_refused(client, applied):
    """**والإلغاء لا يعكس الأثر.**

    ``cancel`` تكتب «ملغى» ولا تعكس شيًئا، والمسار لا يفحص الحالة. فطلٌب
    مكتمٌل وقع أثره كان يُلغى ويبقى أثره: خصٌم اقتُطع من الأجر والطلب
    يقول «ملغى» — والسجلّ يشهد بغير ما وقع.

    وهو تضييٌق لا توسيع: من كان يلغي فيظنّ أنه يعكس، صار يعرف أنه لم يكن
    يعكس شيًئا.
    """
    r = client.post(f"/api/requests/{applied}/cancel",
                    headers=auth_headers(login(client, *MGR)),
                    params={"note": "محاولة إلغاء بعد وقوع الأثر"})
    assert r.status_code == 409, (r.status_code, r.text[:250])

    db = SessionLocal()
    try:
        req = db.get(models.Request, applied)
        rows = db.scalars(select(models.Deduction).where(
            models.Deduction.request_id == applied)).all()
    finally:
        db.close()
    assert req.status != "cancelled", req.status
    assert len(rows) == 1, "اختفى الخصم أو تكرّر"
