# -*- coding: utf-8 -*-
"""البنود 21 · 30 · 31 — تُقطَع الرحلة في البيئة المعزولة لا تُوصَف.

**لماذا هذا الملف موجود**: البيئة بُنيت لتُجرَّب فيها ثلاث رحلات، ثم لم
تكن تكفي لأيٍّ منها. والفرق بين «بيئة موجودة» و«بيئة تكفي» لا يظهر إلا
حين تُقطَع الرحلة فيها فعًلا — فهذا ما يفعله هذا الملف، خطوة خطوة عبر
نقاط النهاية نفسها التي يستعملها المختبِر، لا عبر دوالّ الداخل.

وما كشفه القياس حين جُرّب أول مرّة:

- **21** المندوب هو من يولّد العقد الحكومي، ولا مندوب في البيئة — فالمسار
  محجوب بالصلاحية. ولا إقامة ولا معاملة تجديد. ولا اسم إنجليزي ولا جواز
  ولا مهنة إنجليزية ولا محافظة على الفرع، والنموذج الرسمي يرفض الناقص.
- **31** الاعتماد يشترط غير من جهّز، و``run_payroll`` لا يحمله من الأدوار
  إلا ``accountant``. فبمحاسب واحد تقف الرحلة عند الاعتماد بـ403 —
  ولا يظهر هذا إلا عند محاولة الاعتماد.

**والحسابات تُغيَّر كلماتها هنا كما يغيّرها المختبِر**: ``must_change``
مفروض على الخادم، فحساب لم تُغيَّر كلمته يُردّ بـ403 عن كل شيء. وبيئة
تُنشأ ولا يُدخَل إليها ليست بيئة.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import models, qa_sandbox
from app.clock import today as kuwait_today
from app.database import SessionLocal
from app.main import app
from tests.conftest import auth_headers, login


def _period() -> str:
    """الشهر المنقضي — مسيٌّر لشهر مستقبلي مرفوض بحق، ولا يُختبَر عليه."""
    first = kuwait_today().replace(day=1)
    prev = first - timedelta(days=1)
    return f"{prev.year}-{prev.month:02d}"


PERIOD = _period()


@pytest.fixture(scope="module")
def sandbox():
    """بيئة نظيفة، وحسابات دخلت وغيّرت كلماتها — أي: صالحة للاستعمال."""
    db = SessionLocal()
    try:
        qa_sandbox.drop(db)
        out = qa_sandbox.create(db)
        qa_sandbox.seed_attendance(db, days=12)
    finally:
        db.close()

    c = TestClient(app)
    creds: dict[str, list[tuple[str, str]]] = {}
    for a in out["accounts"]:
        # كلمة البيئة عشوائية وقد تخلو من رقم؛ والسياسة تشترط حرًفا ورقًما.
        new = a["password"] + "Qa1"
        tok = login(c, a["civil_id"], a["password"])
        r = c.post("/api/auth/change-password", headers=auth_headers(tok),
                   json={"old_password": a["password"], "new_password": new})
        assert r.status_code == 200, (a["role"], r.text)
        creds.setdefault(a["role"], []).append((a["civil_id"], new))

    yield {"company_id": out["company_id"], "renewal_id": out["renewal_id"],
           "creds": creds}

    db = SessionLocal()
    try:
        qa_sandbox.drop(db)
    finally:
        db.close()


def _hdr(client, sandbox, role: str, nth: int = 0):
    civil, pw = sandbox["creds"][role][nth]
    return auth_headers(login(client, civil, pw))


# ---------------------------------------------------------------------------
# البند 21 — توليد العقد الحكومي وتكراره
# ---------------------------------------------------------------------------

def test_21_the_environment_has_something_to_generate_a_contract_for(sandbox):
    """قبل الرحلة: إقامة ومعاملة تجديد. بلاهما لا شيء يُولَّد له عقد."""
    assert sandbox["renewal_id"], "لا معاملة تجديد في البيئة"
    db = SessionLocal()
    try:
        rn = db.get(models.ResidencyRenewal, sandbox["renewal_id"])
        permit = db.get(models.Permit, rn.permit_id)
    finally:
        db.close()
    assert permit is not None and permit.number, "لا رقم إقامة — وهو حقٌّ إلزامي في النموذج"


def test_21_the_delegate_can_actually_generate_it(client, sandbox):
    """**جوهر البند**: الرحلة تبدأ فعًلا — لا تُحجَب بصلاحية ولا ببيانات.

    ورفض النموذج الرسمي يسمّي الناقص، فإن سقط هذا الاختبار قرأتَ من
    رسالته أي حقل غاب عن البيئة.
    """
    r = client.post(f"/api/renewals/{sandbox['renewal_id']}/gov-contract/generate",
                    headers=_hdr(client, sandbox, "delegate"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["document_id"] and body["reference_no"]
    assert body["format"] in ("pdf", "docx"), body["format"]


def test_21_repeating_it_leaves_exactly_one_current_copy(client, sandbox):
    """**والتكرار ليس العطل — تعدّد السارية هو.**

    خمس توليدات لعقد واحد سجّلتها المراجعة. والضرر يقع حين تصير أكثر من
    نسخة «سارية» في وقت واحد: تُقدَّم إحداها للجهة ولا يُعرف أيّها.
    """
    rid = sandbox["renewal_id"]
    hdr = _hdr(client, sandbox, "delegate")
    first = client.post(f"/api/renewals/{rid}/gov-contract/generate", headers=hdr)
    second = client.post(f"/api/renewals/{rid}/gov-contract/generate", headers=hdr)
    assert first.status_code == second.status_code == 200, second.text
    assert first.json()["reference_no"] != second.json()["reference_no"], (
        "توليدان برقم مرجعي واحد — لا يُميَّز أيّهما صدر"
    )

    db = SessionLocal()
    try:
        rn = db.get(models.ResidencyRenewal, rid)
        docs = db.scalars(select(models.Document).where(
            models.Document.entity_type == "employee",
            models.Document.entity_id == rn.employee_id,
            models.Document.document_type_code == f"gov_contract_renewal_{rid}",
        )).all()
    finally:
        db.close()
    assert len(docs) >= 2, f"لم تُحفَظ النسخ: {len(docs)}"
    current = [d for d in docs if d.is_current]
    assert len(current) == 1, f"{len(current)} نسخة سارية في وقت واحد"
    assert current[0].version == max(d.version for d in docs), (
        "السارية ليست الأحدث"
    )


# ---------------------------------------------------------------------------
# البند 31 — مسيّر الرواتب من الرفض إلى القفل
# ---------------------------------------------------------------------------

def test_31_payroll_refuses_an_open_attendance_month_and_says_where_to_go(client, sandbox):
    """البوابة قبل الرحلة: لا مسيّر على حضور لم يُراجَع.

    **والرسالة تدلّ على مخرج**: بوابة تقول «ممنوع» بلا «من أين» هي جدار.
    """
    r = client.post(f"/api/payroll/run?period={PERIOD}",
                    headers=_hdr(client, sandbox, "accountant"))
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert PERIOD in detail and "مراجعة الحضور" in detail, detail


def test_30_hr_closes_the_month_from_the_environment(client, sandbox):
    """البند 30 — الإقفال يقع من داخل البيئة، بحساب يملك مراجعة الحضور."""
    hr = _hdr(client, sandbox, "hr")
    r = client.post(f"/api/attendance/close-month?period={PERIOD}", headers=hr)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "closed"

    st = client.get(f"/api/attendance/close-status?period={PERIOD}", headers=hr)
    assert st.status_code == 200 and st.json()["status"] == "closed", st.text


def test_31_the_run_then_prepares_over_the_whole_environment(client, sandbox):
    """وبعد الإقفال يمرّ المسيّر — على موظفي البيئة وحدهم."""
    r = client.post(f"/api/payroll/run?period={PERIOD}",
                    headers=_hdr(client, sandbox, "accountant"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "prepared" and body["run_id"]
    assert body["employees_count"] == len(qa_sandbox._STAFF), body["employees_count"]
    assert all(p["employee_no"].startswith("QA-") for p in body["payslips"]), (
        "كشف بلا رقم وظيفي منسوب"
    )


def test_31_whoever_prepared_it_cannot_approve_it(client, sandbox):
    """**فصل السلطات مقيس في البيئة لا مفترض فيها.**"""
    acc = _hdr(client, sandbox, "accountant")
    run_id = client.post(f"/api/payroll/run?period={PERIOD}", headers=acc).json()["run_id"]
    r = client.post(f"/api/payroll/runs/{run_id}/approve", headers=acc)
    assert r.status_code == 403, r.text
    assert "جهّزته" in r.json()["detail"], r.json()


def test_31_a_second_accountant_carries_it_to_lock(client, sandbox):
    """**والرحلة تصل إلى آخرها**: اعتماد ← إقفال ← قفل.

    وبمحاسب واحد كانت تقف عند الخطوة الأولى — وهو ما كشفه بناء هذا
    الاختبار، لا وصف البند.
    """
    acc = _hdr(client, sandbox, "accountant")
    run_id = client.post(f"/api/payroll/run?period={PERIOD}", headers=acc).json()["run_id"]

    second = _hdr(client, sandbox, "accountant", nth=1)
    assert client.post(f"/api/payroll/runs/{run_id}/approve",
                       headers=second).status_code == 200
    assert client.post(f"/api/payroll/runs/{run_id}/finalize",
                       headers=second).status_code == 200
    lock = client.post(f"/api/payroll/runs/{run_id}/lock", headers=second)
    assert lock.status_code == 200, lock.text
    assert lock.json()["status"] == "locked"

    again = client.post(f"/api/payroll/run?period={PERIOD}", headers=acc)
    assert again.status_code == 409, "أُعيد التجهيز فوق مسيّر مقفل"


def test_30_reopening_the_month_demands_a_documented_reason(client, sandbox):
    """وإعادة الفتح ليست زًرا: سبٌب موثَّق يبقى في السجلّ."""
    hr = _hdr(client, sandbox, "hr")
    blank = client.post(f"/api/attendance/reopen-month?period={PERIOD}&reason=", headers=hr)
    assert blank.status_code == 400, blank.text

    ok = client.post(f"/api/attendance/reopen-month?period={PERIOD}"
                     "&reason=تصحيح بصمة موظف", headers=hr)
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "reopened"

    db = SessionLocal()
    try:
        row = db.scalar(select(models.AttendanceMonthClose).where(
            models.AttendanceMonthClose.company_id == sandbox["company_id"],
            models.AttendanceMonthClose.period == PERIOD))
    finally:
        db.close()
    assert row.reopen_reason, "أُعيد الفتح بلا سبب محفوظ"


def test_nothing_of_this_journey_left_the_sandbox(sandbox):
    """**وبعد كل هذا لا أثر خارجها** — وهي الشرط الذي بُنيت لأجله."""
    cid = sandbox["company_id"]
    db = SessionLocal()
    try:
        stray_runs = db.scalars(select(models.PayrollRun).where(
            models.PayrollRun.period == PERIOD,
            models.PayrollRun.company_id != cid)).all()
        stray_close = db.scalars(select(models.AttendanceMonthClose).where(
            models.AttendanceMonthClose.period == PERIOD,
            models.AttendanceMonthClose.company_id != cid)).all()
    finally:
        db.close()
    assert not stray_runs, f"مسيّر خارج البيئة: {[r.company_id for r in stray_runs]}"
    assert not stray_close, f"إقفال خارج البيئة: {[c.company_id for c in stray_close]}"
