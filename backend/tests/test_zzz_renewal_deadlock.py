# -*- coding: utf-8 -*-
"""RNW-D1 — لا حالة بلا مخرج.

**العطل**: رفع البطاقة المدنية كان ينقل المعاملة إلى ``pending_hr_verify``
بلا فحص. فإن لم يكن المندوب قد أدخل بيانات الحكومة بعد، وقعت المعاملة في
حالة **مقفولة من الناحيتين**:

- ``finalize`` يردّ 409 — المرحلة الحالية ليست ضمن ما يسمح بالإدخال
- تحقّق HR يرفض الإغلاق — البيانات ناقصة

ولا طريق للأمام ولا للخلف. والاختبار القائم لم يكشفها لأنه يمشي بالترتيب
السليم وحده: يُدخل البيانات ثم يرفع البطاقة. والعطل في الترتيب المعكوس —
وهو ترتيب مشروع تماًما: الموظف لا ينتظر المندوب ليرفع بطاقته.

القاعدة المحروسة: **ممنوع أن تصل المعاملة إلى حالة لا يوجد منها طريق
للاستمرار.**
"""
from __future__ import annotations

import io
from datetime import date, timedelta

import pytest
from sqlalchemy import and_ as sa_and, delete as sa_delete, or_ as sa_or, select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

PRO = ("100000000003", "deleg123")
HR = ("100000000002", "hr12345")

GOV_DATA = {
    "gov_reference_no": "GOV-2026-DEADLOCK",
    "fees_amount": "150.500",
    "fees_receipt_no": "R-DL-01",
    "new_permit_number": "RES-DL-77001",
}


def _f():
    return {"file": ("doc.pdf", io.BytesIO(b"content"), "application/pdf")}


@pytest.fixture
def new_case(client):
    """يبني موظًفا وإقامة تنتهي قريًبا ويفتح له معاملة — ثم ينظّف.

    البذرة تحمل موظفَين فقط ضمن مهلة الثلاثين يوًما، فاختباران يستهلكانها
    ويسقط الباقي لسبب لا علاقة له بالمُختبَر. وبناء الحالة هنا يجعل كل
    اختبار مستقًلا عن ترتيب تشغيله وعن غيره.
    """
    created = []

    def _make():
        db = SessionLocal()
        try:
            pro_user = db.scalar(select(models.User).where(
                models.User.civil_id == PRO[0]))
            n = len(created)
            emp = models.Employee(
                company_id=pro_user.company_id,
                name=f"موظف قفلة {n}", name_en=f"Deadlock Employee {n}",
                civil_id=f"29900{id(created) % 10000:04d}{n:02d}",
                job_title="فني", job_title_en="Technician",
                basic_salary=350, passport_number=f"PDL{n:05d}",
                status="active", nationality="مصري")
            db.add(emp)
            db.flush()
            permit = models.Permit(
                company_id=emp.company_id, employee_id=emp.id,
                kind="residency", number=f"RES-DL-{emp.id}",
                start_date=date.today() - timedelta(days=345),
                expiry_date=date.today() + timedelta(days=20),
                status="active")
            db.add(permit)
            db.commit()
            eid = emp.id
        finally:
            db.close()

        pro = auth_headers(login(client, *PRO))
        r = client.post("/api/renewals", headers=pro, data={"employee_id": eid})
        assert r.status_code == 201, r.text
        rid = r.json()["id"]
        created.append((eid, rid))
        return pro, rid

    yield _make

    db = SessionLocal()
    try:
        for eid, rid in created:
            db.execute(sa_delete(models.Document).where(
                sa_or(sa_and(models.Document.entity_type == "renewal",
                             models.Document.entity_id == rid),
                      sa_and(models.Document.entity_type == "employee",
                             models.Document.entity_id == eid))))
            db.execute(sa_delete(models.Task).where(
                sa_or(sa_and(models.Task.related_entity_type == "renewal",
                             models.Task.related_entity_id == rid),
                      sa_and(models.Task.related_entity_type == "employee",
                             models.Task.related_entity_id == eid))))
            db.execute(sa_delete(models.ResidencyRenewal).where(
                models.ResidencyRenewal.id == rid))
            db.execute(sa_delete(models.Permit).where(
                models.Permit.employee_id == eid))
            db.execute(sa_delete(models.Employee).where(
                models.Employee.id == eid))
        db.commit()
    finally:
        db.close()


def _reach_awaiting_civil_card(client, pro_h, rid: int) -> None:
    """يمضي بالمعاملة إلى «بانتظار البطاقة المدنية» بلا إدخال بيانات حكومة."""
    client.post(f"/api/renewals/{rid}/upload", headers=pro_h,
                data={"doc_type": "renewal_contract_gov"}, files=_f())
    client.post(f"/api/renewals/{rid}/upload", headers=pro_h,
                data={"doc_type": "renewal_signed_gov"}, files=_f())
    client.post(f"/api/renewals/{rid}/renewing", headers=pro_h)
    client.post(f"/api/renewals/{rid}/upload", headers=pro_h,
                data={"doc_type": "work_permit"}, files=_f())
    st = client.get(f"/api/renewals/{rid}", headers=pro_h).json()["status"]
    assert st == "awaiting_civil_card", f"لم نصل للمرحلة المطلوبة: {st}"


def test_civil_card_without_gov_data_does_not_enter_verify(client, new_case):
    """**هذا هو العطل**: البطاقة وحدها لا تنقل المعاملة.

    قبل الإصلاح كانت تنقلها إلى ``pending_hr_verify`` فتُقفل.
    """
    pro, rid = new_case()
    _reach_awaiting_civil_card(client, pro, rid)

    client.post(f"/api/renewals/{rid}/upload", headers=pro,
                data={"doc_type": "civil_id"}, files=_f())
    st = client.get(f"/api/renewals/{rid}", headers=pro).json()["status"]
    assert st == "awaiting_civil_card", (
        f"انتقلت إلى «{st}» بلا بيانات حكومة — وهذه هي القفلة"
    )


def test_the_document_is_kept_even_though_the_stage_did_not_move(client, new_case):
    """الموظف رفع ما عليه: لا يُعاقَب بضياع رفعه لتأخّر المندوب."""
    pro, rid = new_case()
    _reach_awaiting_civil_card(client, pro, rid)

    r = client.post(f"/api/renewals/{rid}/upload", headers=pro,
                    data={"doc_type": "civil_id"}, files=_f())
    assert r.status_code == 200, r.text


def test_finalizing_after_the_card_completes_the_move(client, new_case):
    """**الطرف الثاني للبوّابة** — وبدونه ينتقل العطل ولا يزول.

    لو فُحص الشرط عند رفع البطاقة وحده، لبقيت المعاملة ساكنة إلى الأبد
    بعد إدخال البيانات: لا حدث يعيد تقييم الانتقال. قفلة في موضع جديد.
    """
    pro, rid = new_case()
    _reach_awaiting_civil_card(client, pro, rid)

    client.post(f"/api/renewals/{rid}/upload", headers=pro,
                data={"doc_type": "civil_id"}, files=_f())
    fin = client.post(f"/api/renewals/{rid}/finalize", headers=pro, data={
        **GOV_DATA,
        "new_expiry_date": (date.today() + timedelta(days=730)).isoformat(),
    })
    assert fin.status_code == 200, fin.text
    st = client.get(f"/api/renewals/{rid}", headers=pro).json()["status"]
    assert st == "pending_hr_verify", (
        f"البيانات اكتملت والبطاقة مرفوعة ومع ذلك بقيت في «{st}» — ساكنة بلا مخرج"
    )


def test_gov_data_before_the_card_still_waits_for_it(client, new_case):
    """الاتجاه المعاكس: البيانات وحدها لا تكفي — البطاقة شرط أيًضا."""
    pro, rid = new_case()
    _reach_awaiting_civil_card(client, pro, rid)

    fin = client.post(f"/api/renewals/{rid}/finalize", headers=pro, data={
        **GOV_DATA,
        "new_expiry_date": (date.today() + timedelta(days=730)).isoformat(),
    })
    assert fin.status_code == 200, fin.text
    st = client.get(f"/api/renewals/{rid}", headers=pro).json()["status"]
    assert st == "awaiting_civil_card", f"انتقلت بلا بطاقة: {st}"


def test_a_case_that_reached_verify_can_always_be_closed(client, new_case):
    """**الادّعاء الحاكم**: كل معاملة تصل إلى تحقّق HR لها مخرج.

    لا يكفي أن يُمنع الدخول الخاطئ؛ المطلوب أن يكون كل من دخل قادًرا على
    الخروج. فيُقاس المخرج نفسه لا البوّابة وحدها.
    """
    pro, rid = new_case()
    _reach_awaiting_civil_card(client, pro, rid)
    client.post(f"/api/renewals/{rid}/upload", headers=pro,
                data={"doc_type": "civil_id"}, files=_f())
    client.post(f"/api/renewals/{rid}/finalize", headers=pro, data={
        **GOV_DATA,
        "new_expiry_date": (date.today() + timedelta(days=730)).isoformat(),
    })
    assert client.get(f"/api/renewals/{rid}",
                      headers=pro).json()["status"] == "pending_hr_verify"

    hr = auth_headers(login(client, *HR))
    done = client.post(f"/api/renewals/{rid}/hr-verify", headers=hr,
                       data={"note": "تحقّق"})
    assert done.status_code == 200, (
        f"دخلت تحقّق HR ولا تستطيع الخروج — قفلة: {done.text}"
    )
    assert client.get(f"/api/renewals/{rid}",
                      headers=pro).json()["status"] == "completed"


# ==========================================================================
# RNW-D2 — الإنقاذ: المنع لا يحرّر ما هو عالق بالفعل
# ==========================================================================
def _strand(rid: int) -> None:
    """يضع المعاملة في القفلة كما تبدو في البيانات القديمة.

    الالتفاف على الواجهة مقصود: البوّابة الجديدة تمنع الوصول إلى هذه
    الحالة، والمطلوب اختبار **الخروج** منها لا الدخول إليها. ولو بُني
    الاختبار عبر الواجهة لما أمكن إنتاج الحالة أصًلا، ولمرّ اختبار الإنقاذ
    وهو لم يختبر إنقاًذا.
    """
    db = SessionLocal()
    try:
        rn = db.get(models.ResidencyRenewal, rid)
        rn.status = "pending_hr_verify"
        rn.new_expiry_date = None
        rn.new_permit_number = None
        rn.gov_reference_no = None
        db.commit()
    finally:
        db.close()


def test_a_stranded_case_can_be_completed_in_place(client, new_case):
    """**الإنقاذ**: معاملة عالقة تُستكمل من مرحلتها وتُغلق."""
    pro, rid = new_case()
    _reach_awaiting_civil_card(client, pro, rid)
    client.post(f"/api/renewals/{rid}/upload", headers=pro,
                data={"doc_type": "civil_id"}, files=_f())
    _strand(rid)

    fin = client.post(f"/api/renewals/{rid}/finalize", headers=pro, data={
        **GOV_DATA,
        "new_expiry_date": (date.today() + timedelta(days=730)).isoformat(),
    })
    assert fin.status_code == 200, (
        f"المعاملة العالقة ما زالت ترفض الاستكمال: {fin.text}"
    )

    hr = auth_headers(login(client, *HR))
    done = client.post(f"/api/renewals/{rid}/hr-verify", headers=hr,
                       data={"note": "أُنقذت"})
    assert done.status_code == 200, done.text
    assert client.get(f"/api/renewals/{rid}",
                      headers=pro).json()["status"] == "completed"


def test_stranded_cases_are_listed_before_anything_is_changed(client, new_case):
    """الحصر قبل التعديل: الأداة تسمّي المعاملة وما ينقصها."""
    from app.stuck_renewals import find_stuck

    pro, rid = new_case()
    _reach_awaiting_civil_card(client, pro, rid)
    client.post(f"/api/renewals/{rid}/upload", headers=pro,
                data={"doc_type": "civil_id"}, files=_f())
    _strand(rid)

    db = SessionLocal()
    try:
        rows = {r["id"]: r for r in find_stuck(db)}
    finally:
        db.close()
    assert rid in rows, "المعاملة العالقة لم تظهر في الحصر"
    assert len(rows[rid]["missing"]) == 3


def test_healthy_cases_awaiting_hr_are_not_reported_as_stuck(client, new_case):
    """معاملة كاملة تنتظر HR ليست عالقة — عدّها عالقة يُغرق القائمة."""
    from app.stuck_renewals import find_stuck

    pro, rid = new_case()
    _reach_awaiting_civil_card(client, pro, rid)
    client.post(f"/api/renewals/{rid}/upload", headers=pro,
                data={"doc_type": "civil_id"}, files=_f())
    client.post(f"/api/renewals/{rid}/finalize", headers=pro, data={
        **GOV_DATA,
        "new_expiry_date": (date.today() + timedelta(days=730)).isoformat(),
    })
    assert client.get(f"/api/renewals/{rid}",
                      headers=pro).json()["status"] == "pending_hr_verify"

    db = SessionLocal()
    try:
        ids = [r["id"] for r in find_stuck(db)]
    finally:
        db.close()
    assert rid not in ids, "معاملة مكتملة عُدّت عالقة"


def test_a_closed_case_still_refuses_gov_data(client, new_case):
    """الإنقاذ لم يفتح الباب على مصراعيه: المكتملة لا تُعدَّل."""
    pro, rid = new_case()
    _reach_awaiting_civil_card(client, pro, rid)
    client.post(f"/api/renewals/{rid}/upload", headers=pro,
                data={"doc_type": "civil_id"}, files=_f())
    client.post(f"/api/renewals/{rid}/finalize", headers=pro, data={
        **GOV_DATA,
        "new_expiry_date": (date.today() + timedelta(days=730)).isoformat(),
    })
    hr = auth_headers(login(client, *HR))
    client.post(f"/api/renewals/{rid}/hr-verify", headers=hr, data={"note": "تم"})

    again = client.post(f"/api/renewals/{rid}/finalize", headers=pro, data={
        **GOV_DATA, "gov_reference_no": "GOV-TAMPER",
        "new_expiry_date": (date.today() + timedelta(days=900)).isoformat(),
    })
    assert again.status_code == 409, (
        "معاملة مغلقة قبلت تعديل بياناتها الحكومية"
    )
