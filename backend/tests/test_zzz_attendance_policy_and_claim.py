# -*- coding: utf-8 -*-
"""بابان كانا مفتوحَين على الفراغ: سياسة الحضور، والتقاط المهمة.

**١ · سياسة الحضور** — موظف نشط بنمط ``none`` بلا إعفاء موثَّق يوقف
``finalize`` في الوضع الصارم، **ورسالة المنع كانت تسمّي مساًرا خاًما**:
«راجع ``/employees/attendance-policy/pending``» — لا شاشة له. أمٌر بفعل
بلا باب، ونٌص داخلي يتسرّب إلى المستخدم.

وتحته قاعدٌة مكتوبة في موضعين بحكمين متضادّين: ``/attendance-policy``
يرفض ``none`` بلا إعفاء موثَّق، و``/attendance-mode`` **يقبله**. فمن دخل
من الباب الثاني وضع موظًفا في الحال التي بُني عليها المنع، ثم لا يخرج
منها من الباب نفسه.

**٢ · التقاط المهمة** — المهمة الواحدة تُوزَّع على مجموعة أدوار، والالتقاط
بُني ليمنع أن يعملها اثنان. وكان **يُكتَب بالواجهة البرمجية ولا يُقرأ**:
لا القائمة تُظهر من التقطها، ولا زٌر يلتقط. فالتكرار الذي بُني الالتقاط
لمنعه يقع كأنه غير مبنيّ.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import delete as sa_delete, select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")
FRONT = Path(__file__).resolve().parents[2] / "frontend" / "src"


# ---------------------------------------------------------------------------
# سياسة الحضور
# ---------------------------------------------------------------------------

@pytest.fixture
def no_policy_emp():
    """موظف نشط بلا سياسة حضور — الحال التي يمنع بها المسيّر."""
    db = SessionLocal()
    try:
        emp = models.Employee(
            company_id=1, name="موظف بلا سياسة حضور", civil_id="255511220033",
            status="active", basic_salary=350, nationality="مصري",
            attendance_mode="none", attendance_exempt=False)
        db.add(emp)
        db.commit()
        eid = emp.id
    finally:
        db.close()
    yield eid
    db = SessionLocal()
    try:
        db.execute(sa_delete(models.Employee).where(models.Employee.id == eid))
        db.commit()
    finally:
        db.close()


def test_the_gap_is_listed_where_it_can_be_closed(client, no_policy_emp):
    """القائمة تُقرأ، والشاشة التي تقرؤها هي التي تُغلق الشهر."""
    hdr = auth_headers(login(client, *HR))
    r = client.get("/api/employees/attendance-policy/pending", headers=hdr)
    assert r.status_code == 200, r.text
    assert any(x["id"] == no_policy_emp for x in r.json()), "الفجوة لا تُعرَض"

    page = (FRONT / "pages" / "AttendanceReview.tsx").read_text(encoding="utf-8")
    assert "attendance-policy/pending" in page, "الشاشة لا تقرأ القائمة"
    assert "attendance-policy" in page, "ولا تُثبّت سياسة"


def test_the_refusal_no_longer_prints_a_raw_path():
    """**ونٌص داخلي في رسالة للمستخدم عطٌل بذاته** — والمسار لا شاشة له."""
    import inspect

    from app.routers import payroll as P

    src = inspect.getsource(P)
    assert "/employees/attendance-policy/pending" not in src, (
        "الرسالة ما زالت تسمّي مساًرا خاًما"
    )
    assert "مراجعة الحضور" in src, "الرسالة لا تدلّ على شاشة"


def test_setting_a_real_mode_closes_the_gap(client, no_policy_emp):
    """ونمٌط فعليّ يُخرِج الموظف من القائمة — وهو المقصود."""
    hdr = auth_headers(login(client, *HR))
    r = client.post(f"/api/employees/{no_policy_emp}/attendance-policy?mode=qr",
                    headers=hdr)
    assert r.status_code == 200, r.text
    listed = client.get("/api/employees/attendance-policy/pending", headers=hdr).json()
    assert not any(x["id"] == no_policy_emp for x in listed)


def test_exempting_without_a_reason_is_refused(client, no_policy_emp):
    """**والإعفاء بلا سبب هو الحال التي جاء المنع من أجلها.**"""
    hdr = auth_headers(login(client, *HR))
    r = client.post(f"/api/employees/{no_policy_emp}/attendance-policy?mode=none",
                    headers=hdr)
    assert r.status_code == 400, r.text


def test_the_other_door_no_longer_contradicts_the_first(client, no_policy_emp):
    """**قاعدٌة واحدة في موضعين بحكمين متضادّين.**

    ``/attendance-mode`` كان يقبل ``none`` بلا إعفاء ولا سبب — أي يضع
    الموظف في الحال التي يرفضها بابه الآخر، ولا يُخرجه منها.
    """
    hdr = auth_headers(login(client, *HR))
    r = client.post(f"/api/employees/{no_policy_emp}/attendance-mode?mode=none",
                    headers=hdr)
    assert r.status_code == 400, r.text
    assert "سياسة الحضور" in r.json()["detail"], r.json()

    # والنمط الفعليّ يمرّ منه، ويُلغي إعفاًء سابًقا: لا يبصم ويُعدّ معفًى.
    ok = client.post(f"/api/employees/{no_policy_emp}/attendance-mode?mode=qr",
                     headers=hdr)
    assert ok.status_code == 200, ok.text
    db = SessionLocal()
    try:
        emp = db.get(models.Employee, no_policy_emp)
        assert emp.attendance_exempt is False and emp.attendance_exempt_reason is None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# التقاط المهمة
# ---------------------------------------------------------------------------

@pytest.fixture
def a_task():
    """مهمٌة مفتوحة على حساب الموارد البشرية."""
    db = SessionLocal()
    try:
        hr = db.scalar(select(models.User).where(models.User.civil_id == HR[0]))
        t = models.Task(company_id=hr.company_id, assignee_user_id=hr.id,
                        type="config_gap", title="مهمة قياس الالتقاط",
                        status="open", severity="warning")
        db.add(t)
        db.commit()
        made = {"tid": t.id, "uid": hr.id}
    finally:
        db.close()
    yield made
    db = SessionLocal()
    try:
        db.execute(sa_delete(models.Task).where(models.Task.id == made["tid"]))
        db.commit()
    finally:
        db.close()


def test_the_list_says_who_is_working_on_it(client, a_task):
    """**بلا هذا يعملها اثنان** — والالتقاط مبنيّ ولا يُقرأ."""
    hdr = auth_headers(login(client, *HR))
    rows = client.get("/api/tasks/my", headers=hdr).json()
    row = next(x for x in rows if x["id"] == a_task["tid"])
    assert row["claimed_by"] is None and row["can_claim"] is True
    assert row["can_release"] is False

    assert client.post(f"/api/tasks/{a_task['tid']}/claim", headers=hdr).status_code == 200

    rows = client.get("/api/tasks/my", headers=hdr).json()
    row = next(x for x in rows if x["id"] == a_task["tid"])
    assert row["claimed_by"], "التُقطت ولا يُعرَض من التقطها"
    assert row["can_release"] is True


def test_releasing_puts_it_back(client, a_task):
    """وللالتقاط باب خروج: مهمٌة تبقى محجوزة على غائب تقف للأبد."""
    hdr = auth_headers(login(client, *HR))
    client.post(f"/api/tasks/{a_task['tid']}/claim", headers=hdr)
    assert client.post(f"/api/tasks/{a_task['tid']}/release", headers=hdr).status_code == 200
    rows = client.get("/api/tasks/my", headers=hdr).json()
    row = next(x for x in rows if x["id"] == a_task["tid"])
    assert row["claimed_by"] is None and row["can_release"] is False


def test_the_screen_can_claim_and_release():
    """والشاشة تفعلهما — لا الواجهة البرمجية وحدها."""
    page = (FRONT / "pages" / "Tasks.tsx").read_text(encoding="utf-8")
    assert '"claim"' in page and '"release"' in page, "لا طريق إلى الالتقاط"
    assert "claimed_by" in page, "لا تُظهر من يعمل عليها"


def test_claiming_does_not_hide_the_work(client, a_task):
    """**والعمل لا يختفي عند بدئه.**

    ``claim`` يحوّل الحالة إلى ``in_progress``، وكان صندوق «المفتوحة»
    يطابق الحالة حرًفا — فمن التقط مهمة ليقول «هذه معي» أخفاها عن صندوقه
    وعن عدّاده. وهو عكس ما بُني الالتقاط له بالضبط.
    """
    hdr = auth_headers(login(client, *HR))
    before = client.get("/api/tasks/count", headers=hdr).json()["open"]

    assert client.post(f"/api/tasks/{a_task['tid']}/claim", headers=hdr).status_code == 200

    rows = client.get("/api/tasks/my", headers=hdr).json()
    assert any(x["id"] == a_task["tid"] for x in rows), "اختفت من الصندوق بالتقاطها"
    after = client.get("/api/tasks/count", headers=hdr).json()["open"]
    assert after == before, f"العدّاد نقص بالالتقاط: {before} ← {after}"
