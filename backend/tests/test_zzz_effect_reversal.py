# -*- coding: utf-8 -*-
"""إلغاٌء يعكس أثره — أو يقول لماذا لا يعكسه.

**العطل الأصلي**: ``cancel`` تكتب «ملغى» و**لا تعكس شيًئا**، والمسار لا
يفحص الحالة أصًلا. فطلٌب مكتمٌل وقع أثره يُلغى ويبقى أثره: تُلغى الإجازة
ويبقى رصيُدها منقوًصا، والسجلّ يشهد بغير ما وقع.

**وعطٌل أحدثتُه أنا في الجولة نفسها**: سددتُ الباب (409) لئلا يُقتطع خصٌم
والطلب يقول «ملغى» — فصار الباب مغلًقا **بلا مفتاح**، ورسالُة الردّ تأمر
بـ«قرار معاكس أو تسوية» وليس لهما وجود. وأمٌر بما لا يستطيعه النظام أسوأ
من صمت.

فصار الإلغاء يعكس حيث للعكس معًنى، ويُردّ حيث لا معنى له — **ويفرّق بين
الحالين في الرسالة**:

- إجازٌة لم تبدأ → يُردّ رصيُدها ويُقيَّد في الدفتر.
- إجازٌة بدأت → **لا يُعاد رصيُد يوٍم غاب فيه الموظف**. والرجل لم يكن على
  رأس العمل، فردُّ الرصيد يمنحه أياًما استهلكها.
- خصٌم لم يحتسبه مسيّر → يُحذف قبل أن يُقتطع.
- خصٌم اكتمل مسيّر شهره → **المال خرج**، وردُّه تسويٌة مالية لا محُو سجل.
- نوٌع لا مفتاح له → يُردّ ويُقال إنه لا يُعكَس تلقائًيا.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import delete as sa_delete, select

from app import models
from app.clock import today as kuwait_today
from app.database import SessionLocal
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
SUP = ("100000000005", "sup12345")
HR = ("100000000002", "hr12345")
ACC = ("100000000007", "account123")
MGR = ("100000000001", "manager123")


def _emp_id() -> int:
    db = SessionLocal()
    try:
        return db.scalar(select(models.Employee.id).where(
            models.Employee.civil_id == EMP[0]))
    finally:
        db.close()


def _balance() -> float:
    db = SessionLocal()
    try:
        return float(db.get(models.Employee, _emp_id()).annual_leave_balance or 0)
    finally:
        db.close()


def _purge(rid: int) -> None:
    db = SessionLocal()
    try:
        db.execute(sa_delete(models.LeaveLedger).where(
            models.LeaveLedger.request_id == rid))
        db.execute(sa_delete(models.Leave).where(models.Leave.request_id == rid))
        db.execute(sa_delete(models.Deduction).where(
            models.Deduction.request_id == rid))
        for tbl in (models.RequestDocument, models.RequestApproval,
                    models.Appointment):
            db.execute(sa_delete(tbl).where(tbl.request_id == rid))
        db.execute(sa_delete(models.Task).where(
            models.Task.related_entity_type == "request",
            models.Task.related_entity_id == rid))
        db.execute(sa_delete(models.Request).where(models.Request.id == rid))
        db.commit()
    finally:
        db.close()


def _annual_leave(client, start_offset: int, days: int = 2) -> int:
    """إجازٌة سنوية معتمَدة — تخصم من الرصيد فعًلا."""
    start = kuwait_today() + timedelta(days=start_offset)
    r = client.post("/api/requests", headers=auth_headers(login(client, *EMP)),
                    json={"request_type_code": "leave",
                          "payload_json": {
                              "leave_type": "annual", "days": days,
                              "start_date": start.isoformat(),
                              "end_date": (start + timedelta(days=days - 1)).isoformat(),
                              "reason": "قياس عكس الأثر"}})
    assert r.status_code in (200, 201), r.text[:300]
    rid = r.json()["id"]
    for who in (SUP, HR):
        d = client.post(f"/api/requests/{rid}/decide",
                        headers=auth_headers(login(client, *who)),
                        json={"decision": "approved"})
        assert d.status_code == 200, (who[0], d.text[:200])
    return rid


# ---------------------------------------------------------------------------
# إجازٌة لم تبدأ: تُعكَس ويُردّ رصيُدها
# ---------------------------------------------------------------------------

def test_cancelling_a_future_leave_returns_its_balance(client):
    """**جوهر البند**: الإلغاء يعكس الأثر لا يكتب حالًة فوقه."""
    before = _balance()
    rid = _annual_leave(client, start_offset=30, days=2)
    try:
        during = _balance()
        assert during == pytest.approx(before - 2), (before, during)

        r = client.post(f"/api/requests/{rid}/cancel",
                        headers=auth_headers(login(client, *MGR)),
                        params={"note": "إلغاء قبل البدء"})
        assert r.status_code == 200, (r.status_code, r.text[:250])
        assert _balance() == pytest.approx(before), (before, _balance())

        db = SessionLocal()
        try:
            leave = db.scalar(select(models.Leave).where(
                models.Leave.request_id == rid))
            rev = db.scalar(select(models.LeaveLedger).where(
                models.LeaveLedger.request_id == rid,
                models.LeaveLedger.kind == "reversal"))
        finally:
            db.close()
        assert leave.status == "cancelled", leave.status
        assert rev is not None, "رُدّ الرصيد بلا قيٍد في الدفتر"
        assert rev.balance_after == pytest.approx(before), rev.balance_after
    finally:
        _purge(rid)
        db = SessionLocal()
        try:
            db.get(models.Employee, _emp_id()).annual_leave_balance = before
            db.commit()
        finally:
            db.close()


def test_the_cancellation_record_says_what_was_returned(client):
    """**وعكُس الأثر يُكتب مع الإلغاء لا يُفصَل عنه.**

    من يقرأ «ملغى» بعد سنة يحتاج أن يعرف ماذا رُدّ.
    """
    before = _balance()
    rid = _annual_leave(client, start_offset=40, days=1)
    try:
        client.post(f"/api/requests/{rid}/cancel",
                    headers=auth_headers(login(client, *MGR)),
                    params={"note": "سبٌب إداري"})
        db = SessionLocal()
        try:
            row = db.scalar(select(models.RequestApproval).where(
                models.RequestApproval.request_id == rid,
                models.RequestApproval.stage_label == "إلغاء المدير العام"))
            note = (row.note or "") if row else ""
        finally:
            db.close()
        assert "الرصيد" in note or "رُدّ" in note, note
    finally:
        _purge(rid)
        db = SessionLocal()
        try:
            db.get(models.Employee, _emp_id()).annual_leave_balance = before
            db.commit()
        finally:
            db.close()


# ---------------------------------------------------------------------------
# وإجازٌة بدأت: لا يُعاد رصيُد يوٍم غاب فيه
# ---------------------------------------------------------------------------

def test_a_leave_already_begun_is_not_un_taken(client):
    """**ولا يُعاد رصيُد يوٍم غاب فيه الموظف.**

    والرجل لم يكن على رأس العمل، فردُّ الرصيد يمنحه أياًما استهلكها — وهو
    خطٌأ في المال لا في السجلّ وحده.
    """
    before = _balance()
    rid = _annual_leave(client, start_offset=-1, days=2)
    try:
        during = _balance()
        r = client.post(f"/api/requests/{rid}/cancel",
                        headers=auth_headers(login(client, *MGR)),
                        params={"note": "محاولة إلغاء بعد البدء"})
        assert r.status_code == 409, (r.status_code, r.text[:250])
        assert "بدأت" in r.text, r.text[:250]
        assert _balance() == pytest.approx(during), "رُدّ رصيُد أياٍم استُهلكت"

        db = SessionLocal()
        try:
            assert db.get(models.Request, rid).status != "cancelled"
        finally:
            db.close()
    finally:
        _purge(rid)
        db = SessionLocal()
        try:
            db.get(models.Employee, _emp_id()).annual_leave_balance = before
            db.commit()
        finally:
            db.close()


# ---------------------------------------------------------------------------
# والخصم: يُحذف قبل احتسابه، ولا يُمحى بعده
# ---------------------------------------------------------------------------

def _deduction(client, month: str) -> int:
    r = client.post("/api/requests", headers=auth_headers(login(client, *HR)),
                    json={"request_type_code": "ADMDED",
                          "employee_id": _emp_id(),
                          "payload_json": {"deduction_amount": 5.0,
                                           "reason": "قياس عكس الخصم",
                                           "payroll_month": month}})
    assert r.status_code in (200, 201), r.text[:300]
    rid = r.json()["id"]
    for who in (HR, ACC, MGR):
        d = client.post(f"/api/requests/{rid}/decide",
                        headers=auth_headers(login(client, *who)),
                        json={"decision": "approved"})
        assert d.status_code == 200, (who[0], d.text[:200])
    return rid


def test_an_uncounted_deduction_is_removed_on_cancel(client):
    """خصٌم لم يحتسبه مسيّر يُحذف قبل أن يُقتطع."""
    rid = _deduction(client, "2032-01")
    try:
        r = client.post(f"/api/requests/{rid}/cancel",
                        headers=auth_headers(login(client, *MGR)),
                        params={"note": "إلغاء قبل الاحتساب"})
        assert r.status_code == 200, (r.status_code, r.text[:250])
        db = SessionLocal()
        try:
            rows = db.scalars(select(models.Deduction).where(
                models.Deduction.request_id == rid)).all()
        finally:
            db.close()
        assert not rows, "بقي الخصم بعد إلغائه"
    finally:
        _purge(rid)


def test_a_deduction_inside_a_closed_month_is_not_erased(client):
    """**وما اقتُطع فعًلا لا يُردّ بحذف صفّ** — ردُّه تسويٌة مالية."""
    month = "2032-02"
    rid = _deduction(client, month)
    db = SessionLocal()
    run_id = None
    try:
        emp = db.get(models.Employee, _emp_id())
        run = models.PayrollRun(company_id=emp.company_id, period=month,
                                status="finalized")
        db.add(run)
        db.commit()
        run_id = run.id
    finally:
        db.close()

    try:
        r = client.post(f"/api/requests/{rid}/cancel",
                        headers=auth_headers(login(client, *MGR)),
                        params={"note": "محاولة إلغاء بعد الاحتساب"})
        assert r.status_code == 409, (r.status_code, r.text[:250])
        assert "تسوي" in r.text, r.text[:250]
        db = SessionLocal()
        try:
            rows = db.scalars(select(models.Deduction).where(
                models.Deduction.request_id == rid)).all()
        finally:
            db.close()
        assert len(rows) == 1, "مُحي خصٌم اقتُطع فعًلا"
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
# ونوٌع لا مفتاح له يُردّ ويقول ذلك
# ---------------------------------------------------------------------------

def test_a_type_with_no_reverser_says_so(client):
    """**باٌب مغلٌق يقول لماذا خيٌر من باب يُفتَح بلا مفتاح.**

    ولا يُدَّعى عكٌس لا يقع: الرسالة تفرّق بين «لا يُعكَس هذا النوع» و«لا
    يُعكَس في هذه الحال».
    """
    import inspect

    from app import workflow

    src = inspect.getsource(workflow.cancel)
    assert "_REVERSAL" in src, "الإلغاء لا يعرف كيف يعكس"
    assert "لا يُعكَس أثر هذا النوع تلقائًيا" in src, "لا تفريق في الرسالة"
    # وكل مفتاح في السجلّ دالٌة فعلية لا اسٌم معلَّق.
    for code, fn in workflow._REVERSAL.items():
        assert callable(fn), code
