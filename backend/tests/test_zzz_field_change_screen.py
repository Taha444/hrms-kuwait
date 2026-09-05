# -*- coding: utf-8 -*-
"""R7-G — تغيير الحقول الحرجة: صار له مدخل، وبلاغ لمن يعتمده.

**العطل**: المسار مبنيّ كامًلا على الخادم — يُقترَح ولا يُطبَّق حتى
يعتمده **غيرُ مقترِحه**، ثم يُطبَّق ويُقيَّد في ``EmployeeFieldChange``.
ولا مدخل من الواجهة أصًلا: فلا أحد يقترح تغيير راتب، ولا أحد يعتمده.

**وقياس ثانٍ كشف ما هو أسوأ من غياب الشاشة**: الاقتراح كان يُسجَّل
ويُدقَّق **ثم يصمت** — لا بلاغ ولا طابور، والقائمة الوحيدة داخل ملف
الموظف. فلا يعلم المعتمِد إلا إن فتح ذلك الملف مصادفًة، وراتب ينتظر
اعتماًدا لا يجده أحد يبقى معلًَّقا إلى الأبد.

وهو النمط الذي تكرّر في هذه الجولة بصيغ: بوابة بلا مخرج، ونقطة بلا
طريق، وسجلٌّ لا يقرؤه أحد. وهنا: **عمل يُنشأ ولا يُبلَّغ به**.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")        # يملك edit_employee — يقترح
MGR = ("100000000001", "manager123")    # يعتمد
EMP = ("100000000101", "emp12345")

FRONT = Path(__file__).resolve().parents[2] / "frontend"
PAGE = FRONT / "src" / "pages" / "EmployeeProfile.tsx"


def _emp_id() -> int:
    db = SessionLocal()
    try:
        return db.scalar(select(models.Employee.id).where(
            models.Employee.civil_id == EMP[0]))
    finally:
        db.close()


def _propose(client, hdr, value: str, field: str = "basic_salary") -> int:
    r = client.post(f"/api/employees/{_emp_id()}/salary-change-request",
                    headers=hdr, params={
                        "field_name": field, "new_value": value,
                        "effective_date": (date.today()
                                           + timedelta(days=30)).isoformat(),
                        "reason": "علاوة سنوية"})
    assert r.status_code == 201, r.text[:250]
    return r.json()["request_id"]


def test_the_proposal_reaches_whoever_may_approve_it(client):
    """**جوهر الإصلاح**: اقتراح لا يعلم به أحد ورقة في درج."""
    made = _propose(client, auth_headers(login(client, *HR)), "555")

    db = SessionLocal()
    try:
        tasks = db.scalars(select(models.Task).where(
            models.Task.dedup_key == f"salary_change:{made}")).all()
        approvers = {u.id for u in db.scalars(select(models.User).where(
            models.User.role.in_(("company_manager", "company_owner"))))}
    finally:
        db.close()
    assert tasks, "الاقتراح صامت — لا يعلم به من يعتمده"
    assert all(t.assignee_user_id in approvers for t in tasks), (
        "بلاغ لمن لا يملك القرار خبر لا عمل"
    )


def test_the_proposer_is_not_told_to_approve_their_own(client):
    """ولا يُبلَّغ المقترِح ليعتمد اقتراحه — الخادم سيرفضه.

    بلاغ يدعو إلى فعل ممنوع يُعلّم قارئه أن الصندوق يكذب.
    """
    hdr = auth_headers(login(client, *MGR))
    made = _propose(client, hdr, "556")
    db = SessionLocal()
    try:
        mgr_id = db.scalar(select(models.User.id).where(
            models.User.civil_id == MGR[0]))
        mine = db.scalars(select(models.Task).where(
            models.Task.dedup_key == f"salary_change:{made}",
            models.Task.assignee_user_id == mgr_id)).all()
    finally:
        db.close()
    assert not mine, "أُبلغ المقترِح ليعتمد اقتراحه"


def test_the_queue_gathers_what_awaits_the_approver(client):
    """والطابور يقول **ما ينتظر** مجموًعا — لا يفتح المعتمِد الملفات ملًفا ملًفا."""
    made = _propose(client, auth_headers(login(client, *HR)), "557")
    r = client.get("/api/employees/salary-change-requests/pending",
                   headers=auth_headers(login(client, *MGR)))
    assert r.status_code == 200, r.text[:200]
    row = next((x for x in r.json() if x["id"] == made), None)
    assert row, "الاقتراح غائب عن الطابور"
    assert row["employee_name"] and row["proposed_by_name"], row


def test_approving_applies_the_change_and_closes_the_task(client):
    """**والاعتماد يُطبّق فعًلا**: القيمة تتغيّر، ويُقيَّد الأثر، ويُغلق البلاغ.

    ومهمة تبقى مفتوحة بعد انتهاء عملها تُعلّم قارئها أن الصندوق يكذب.
    """
    made = _propose(client, auth_headers(login(client, *HR)), "777")
    r = client.post(f"/api/employees/salary-change-requests/{made}/decide",
                    headers=auth_headers(login(client, *MGR)),
                    params={"decision": "approved"})
    assert r.status_code == 200, r.text[:250]

    db = SessionLocal()
    try:
        emp = db.get(models.Employee, _emp_id())
        change = db.scalar(select(models.EmployeeFieldChange).where(
            models.EmployeeFieldChange.employee_id == emp.id,
            models.EmployeeFieldChange.new_value == "777"))
        tasks = db.scalars(select(models.Task).where(
            models.Task.dedup_key == f"salary_change:{made}")).all()
    finally:
        db.close()
    assert float(emp.basic_salary) == 777.0, emp.basic_salary
    assert change is not None, "طُبِّق التغيير بلا قيد في السجل"
    assert all(t.status == "done" for t in tasks), (
        f"بقي البلاغ مفتوًحا بعد القرار: {[t.status for t in tasks]}"
    )


def test_rejecting_changes_nothing_and_closes_the_task(client):
    """والرفض لا يمسّ الملف — ويُغلق بلاغه أيًضا."""
    db = SessionLocal()
    try:
        before = float(db.get(models.Employee, _emp_id()).basic_salary or 0)
    finally:
        db.close()

    made = _propose(client, auth_headers(login(client, *HR)), "999")
    r = client.post(f"/api/employees/salary-change-requests/{made}/decide",
                    headers=auth_headers(login(client, *MGR)),
                    params={"decision": "rejected", "note": "خارج الميزانية"})
    assert r.status_code == 200, r.text[:200]

    db = SessionLocal()
    try:
        after = float(db.get(models.Employee, _emp_id()).basic_salary or 0)
        tasks = db.scalars(select(models.Task).where(
            models.Task.dedup_key == f"salary_change:{made}")).all()
    finally:
        db.close()
    assert after == before, f"الرفض غيّر القيمة: {before} → {after}"
    assert all(t.status == "done" for t in tasks)


def test_nobody_approves_their_own_proposal(client):
    """**فصل الواجبات مقيس لا مفترَض**: من اقترح لا يعتمد."""
    hdr = auth_headers(login(client, *MGR))
    made = _propose(client, hdr, "888")
    r = client.post(f"/api/employees/salary-change-requests/{made}/decide",
                    headers=hdr, params={"decision": "approved"})
    assert r.status_code == 403, r.status_code


def test_the_screen_offers_the_path_and_hides_what_would_be_refused():
    """والشاشة تتبع الخادم: لا زرّ لمن سيُرفض طلبه."""
    page = PAGE.read_text(encoding="utf-8")
    assert "salary-change-request" in page, "لا مدخل للاقتراح"
    assert "salary-change-requests/${reqId}/decide" in page, "لا قرار من الشاشة"
    assert 'r.proposed_by !== user?.id' in page, (
        "زرّ الاعتماد يظهر للمقترِح — يردّ 403"
    )
    assert '"company_manager", "company_owner", "super_admin"' in page, (
        "زرّ القرار غير محصور بمن يملكه"
    )


def test_the_screen_asks_for_the_reason_the_server_requires():
    """والسبب إلزامي على الخادم — يُطلَب في الشاشة لا يُردّ الطلب."""
    page = PAGE.read_text(encoding="utf-8")
    assert "سبب التغيير إلزامي" in page, "الشاشة ترسل ما تعرف أنه سيُرفض"
