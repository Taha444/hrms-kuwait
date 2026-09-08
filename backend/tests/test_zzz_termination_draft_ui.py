# -*- coding: utf-8 -*-
"""إنهاء الخدمة: الشاشة تقول «تمّ» والخادم يقول «مسودة».

**العطلان المقيسان**، وكلاهما في الطريق لا في القاعدة:

1. **جملٌة تصف ما لم يقع.** ``POST /terminate`` يحسب التسوية ويحفظها
   **مسودة**، والحالة تبقى ``active``. وكانت الشاشة تُظهر بعده «تم إنهاء
   الخدمة» — فيصدّق المستخدم أن الخدمة انتهت وهي قائمة، ويمضي.

2. **خمس نقاط بلا طريق**: الاعتماد وإخلاء الطرف والإقرار والتنفيذ
   والإلغاء. فالمسودة تُحضَّر ثم لا تتقدّم خطوة ولا تُلغى. **ووجودها
   يمنع تحضير غيرها** بـ409 يقول «الغِها أوًلا» — ولا زرّ يلغيها.
   طريٌق مسدود بقفل: لا الموظف تنتهي خدمته، ولا يُعاد المحاولة.

ولم تكن المسودة تُقرأ من أي نقطة أصًلا، فلا تعرف الواجهة بوجودها ولا في
أي مرحلة وقفت — ولذلك أُضيف ``GET /employees/{id}/termination``.

**والدورة نفسها لم تُمسّ**: توحيد مسارات الخروج الثلاثة (P6-27) قراٌر
للمالك لا يُتّخذ من هنا. هذا يصل ما هو قائم بالشاشة، ويصحّح ما تقوله.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import delete as sa_delete, select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")
ACCOUNTANT = ("100000000007", "account123")

FRONT = Path(__file__).resolve().parents[2] / "frontend" / "src"
PAGE = FRONT / "pages" / "EmployeeProfile.tsx"
I18N = FRONT / "i18n.tsx"


@pytest.fixture
def emp_id(client):
    """موظف نشط تُحضَّر له مسودة — وتُلغى بعد القياس مهما جرى."""
    db = SessionLocal()
    try:
        e = db.scalars(select(models.Employee).where(
            models.Employee.status == "active",
            models.Employee.hire_date.isnot(None),
            models.Employee.basic_salary > 0,
            models.Employee.pending_termination_json.is_(None)).limit(1)).first()
        assert e is not None, "لا موظف صالح للقياس"
        eid = e.id
    finally:
        db.close()

    yield eid

    db = SessionLocal()
    try:
        e = db.get(models.Employee, eid)
        e.pending_termination_json = None
        e.pending_termination_prepared_by = None
        e.pending_termination_prepared_at = None
        e.pending_termination_approved_by = None
        e.pending_termination_approved_at = None
        e.pending_termination_cleared_by = None
        e.pending_termination_cleared_at = None
        e.pending_termination_clearance_note = None
        e.pending_termination_acknowledged_at = None
        db.commit()
    finally:
        db.close()


def _prepare(client, hdr, eid):
    end = (date.today() + timedelta(days=15)).isoformat()
    return client.post(f"/api/employees/{eid}/terminate"
                       f"?end_date={end}&reason=termination&used_leave_days=0",
                       headers=hdr)


# ---------------------------------------------------------------------------
# الخادم: المسودة صارت تُقرأ
# ---------------------------------------------------------------------------

def test_preparing_does_not_end_anyones_service(client, emp_id):
    """**جوهر الكذبة**: التحضير لا يُنهي خدمة أحد — والحالة تشهد."""
    hdr = auth_headers(login(client, *HR))
    r = _prepare(client, hdr, emp_id)
    assert r.status_code == 200, r.text
    assert r.json()["stage"] == "prepared"
    assert r.json()["status"] != "terminated", "انتهت الخدمة عند التحضير"


def test_the_draft_can_be_read_at_all(client, emp_id):
    """ولم تكن تُقرأ: لا نقطة تُظهرها، فلا واجهة تعرف بوجودها."""
    hdr = auth_headers(login(client, *HR))
    empty = client.get(f"/api/employees/{emp_id}/termination", headers=hdr)
    assert empty.status_code == 200 and empty.json()["exists"] is False

    _prepare(client, hdr, emp_id)
    got = client.get(f"/api/employees/{emp_id}/termination", headers=hdr).json()
    assert got["exists"] is True and got["stage"] == "prepared"
    assert got["prepared_by"], "المسودة بلا اسم من حضّرها"
    assert got["settlement"]["total_settlement"] is not None


def test_the_flags_agree_with_what_the_server_enforces(client, emp_id):
    """**زٌر يظهر ثم يفشل أسوأ من زرّ غائب** — والأعلام من شرط المنع نفسه."""
    hdr = auth_headers(login(client, *HR))
    _prepare(client, hdr, emp_id)
    view = client.get(f"/api/employees/{emp_id}/termination", headers=hdr).json()

    # لم تُعتمد بعد: لا إخلاء طرف ولا تنفيذ.
    assert view["can_clear"] is False and view["can_execute"] is False
    refused = client.post(f"/api/employees/{emp_id}/terminate/clearance", headers=hdr)
    assert refused.status_code == 409, refused.text

    # وإلغاؤها متاح دائًما — وإلا بقي الموظف محبوًسا.
    assert view["can_cancel"] is True


def test_whoever_prepared_it_is_told_why_they_cannot_approve(client, emp_id):
    """وفصل السلطات يُشرَح لا يُترَك صمًتا أمام صفّ بلا زرّ."""
    hdr = auth_headers(login(client, *HR))
    _prepare(client, hdr, emp_id)
    # المحاسب هو صاحب ``approve_termination``؛ ونقيس على من حضّر:
    view = client.get(f"/api/employees/{emp_id}/termination", headers=hdr).json()
    assert view["can_approve"] is False
    acc = auth_headers(login(client, *ACCOUNTANT))
    other = client.get(f"/api/employees/{emp_id}/termination", headers=acc).json()
    assert other["can_approve"] is True, "المعتمِد لا يرى الاعتماد"
    assert other["blocked_reason"] is None

    # ونصّ المنع واحٌد يقرؤه الاثنان — نصّان لقاعدة واحدة ينحرفان.
    db = SessionLocal()
    try:
        emp = db.get(models.Employee, emp_id)
        acc_user = db.scalar(select(models.User).where(
            models.User.civil_id == ACCOUNTANT[0]))
        emp.pending_termination_prepared_by = acc_user.id   # كأنه حضّرها
        db.commit()
    finally:
        db.close()
    seen = client.get(f"/api/employees/{emp_id}/termination", headers=acc).json()
    refused = client.post(f"/api/employees/{emp_id}/terminate/approve", headers=acc)
    assert refused.status_code == 403, refused.text
    assert refused.json()["detail"] == seen["blocked_reason"], (
        "رسالتان لقاعدة واحدة"
    )


def test_the_whole_cycle_completes_and_the_status_changes(client, emp_id):
    """**والدورة تُقطَع إلى آخرها**: اعتماد ← إخلاء ← إقرار ← تنفيذ."""
    hr = auth_headers(login(client, *HR))
    acc = auth_headers(login(client, *ACCOUNTANT))
    _prepare(client, hr, emp_id)

    assert client.post(f"/api/employees/{emp_id}/terminate/approve", headers=acc).status_code == 200
    assert client.post(f"/api/employees/{emp_id}/terminate/clearance"
                       "?clearance_note=سلّم العهدة", headers=hr).status_code == 200
    assert client.post(f"/api/employees/{emp_id}/terminate/acknowledge", headers=hr).status_code == 200

    ready = client.get(f"/api/employees/{emp_id}/termination", headers=hr).json()
    assert ready["stage"] == "acknowledged" and ready["can_execute"] is True

    assert client.post(f"/api/employees/{emp_id}/terminate/execute", headers=hr).status_code == 200

    db = SessionLocal()
    try:
        emp = db.get(models.Employee, emp_id)
        status, pending = emp.status, emp.pending_termination_json
        # إعادته إلى حاله: القياس لا يترك موظًفا منتهي الخدمة في البذرة.
        # **وحالة الخروج تُزال معه**: التنفيذ يفتح حالة نهاية خدمة، وحارس
        # «خروج واحد» يمنع بعدها أي تحضير — فيسقط القياس التالي بسبب أثر
        # هذا القياس لا بسبب عطل.
        emp.status = "active"
        emp.termination_date = None
        emp.termination_reason = None
        emp.eos_settlement_json = None
        db.execute(sa_delete(models.EosCase).where(
            models.EosCase.employee_id == emp_id))
        db.commit()
    finally:
        db.close()
    assert status == "terminated", "نُفِّذت الدورة والحالة لم تتغيّر"
    assert pending is None, "بقيت المسودة بعد التنفيذ"


def test_cancelling_frees_the_employee_for_another_attempt(client, emp_id):
    """**ولا طريق مسدود بقفل**: مسودٌة لا تُلغى تمنع تحضير غيرها للأبد."""
    hdr = auth_headers(login(client, *HR))
    assert _prepare(client, hdr, emp_id).status_code == 200
    blocked = _prepare(client, hdr, emp_id)
    assert blocked.status_code == 409, "المسودة الثانية مرّت"

    assert client.post(f"/api/employees/{emp_id}/terminate/cancel", headers=hdr).status_code == 200
    assert _prepare(client, hdr, emp_id).status_code == 200, "بقي محبوًسا بعد الإلغاء"


# ---------------------------------------------------------------------------
# الشاشة: تقول ما وقع، وتتقدّم بما بقي
# ---------------------------------------------------------------------------

def test_the_screen_no_longer_claims_the_service_ended():
    """**جملٌة تصف ما لم يقع** هي العطل، لا الزرّ."""
    i18n = I18N.read_text(encoding="utf-8")
    assert "epf_terminated_msg" not in i18n, "الجملة الكاذبة ما زالت"
    assert "epf_term_drafted" in i18n
    page = PAGE.read_text(encoding="utf-8")
    assert "epf_term_drafted" in page


def test_the_screen_can_advance_the_draft_and_cancel_it():
    """وخمس نقاط بلا طريق صار لها طريق واحد ظاهر."""
    page = PAGE.read_text(encoding="utf-8")
    for step in ("approve", "clearance", "acknowledge", "execute", "cancel"):
        assert re.search(rf'["\'`]{step}["\'`]', page), f"لا طريق إلى {step}"
    assert "/termination" in page, "الشاشة لا تقرأ حال المسودة"
