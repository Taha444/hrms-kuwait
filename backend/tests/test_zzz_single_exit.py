# -*- coding: utf-8 -*-
"""P6-27 — خروج واحد للموظف في وقت واحد.

**ما ظهر بالقياس، وهو أسوأ مما يصفه البند:**

فتحتُ للموظف نفسه ثلاثة مسارات خروج في دقيقة واحدة، وقُبلت كلها:

* ``EosCase`` بتاريخ إنهاء **2026-10-01**
* مسودة إنهاء على ملفه بتاريخ **2026-11-15** — و**بتسوية محسوبة كاملة**
* طلب ``REQEOS`` بآخر يوم عمل **2026-12-01**

ثلاثة تواريخ لمغادرة واحدة، وحسابان مستقلّان للمستحقّات. وأيُّ مسار
يبلغ نهايته أوًلا يكتب ``terminated`` و``eos_settlement_json`` **فوق**
ما كتبه الآخر، بلا تعارض ظاهر — فيُدفع رقم ويبقى في السجلّ رقم آخر.

**وكل باب كان يحرس نفسه ويجهل الآخرَين**: مسار المسودة يرفض مسودتين
(``if emp.pending_termination_json``) ولا يرى حالة نهاية الخدمة ولا
الطلب. ثلاثة حرّاس، كلٌّ يرى مساره نظيًفا.

**وأيُّ وحدة هي المرجع سؤال عمل** — يبقى مفتوًحا. أما «خروجان مفتوحان
مًعا» فليس سؤاًلا: لا سياسة تقصده.
"""
from __future__ import annotations

import pytest
from sqlalchemy import delete as sa_delete, select

from app import exit_guard, models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")

RESIGN = {"submitted_at": "2026-12-15", "proposed_last_day": "2027-01-15",
          "notice_period_days": 30, "reason": "ظروف شخصية"}
EOS_REQ = {"last_working_day": "2026-12-01", "reason": "استقالة",
           "notes": "طلب تسوية"}


@pytest.fixture
def leaver():
    """موظف من شركة HR يصلح لفتح خروج — يُنشأ ويُنظَّف."""
    db = SessionLocal()
    made = None
    try:
        hr = db.scalar(select(models.User).where(
            models.User.civil_id == HR[0]))
        emp = models.Employee(
            company_id=hr.company_id, name="موظف مغادر", civil_id="288800110077",
            job_title="فني", basic_salary=600, status="active",
            nationality="مصري", hire_date=__import__("datetime").date(2022, 1, 1),
            non_payroll=False)
        db.add(emp)
        db.commit()
        made = emp.id
        yield emp.id
    finally:
        if made:
            reqs = [r for (r,) in db.execute(select(models.Request.id).where(
                models.Request.employee_id == made)).all()]
            if reqs:
                db.execute(sa_delete(models.Task).where(
                    models.Task.related_entity_type == "request",
                    models.Task.related_entity_id.in_(reqs)))
            db.execute(sa_delete(models.Request).where(
                models.Request.employee_id == made))
            db.execute(sa_delete(models.EosCase).where(
                models.EosCase.employee_id == made))
            db.execute(sa_delete(models.Employee).where(
                models.Employee.id == made))
            db.commit()
        db.close()


def _open_case(client, eid: int):
    return client.post("/api/eos/cases", headers=auth_headers(login(client, *HR)),
                       params={"employee_id": eid,
                               "termination_date": "2026-10-01",
                               "reason": "resignation"})


def _open_draft(client, eid: int):
    return client.post(f"/api/employees/{eid}/terminate",
                       headers=auth_headers(login(client, *HR)),
                       params={"end_date": "2026-11-15", "reason": "termination"})


def _open_request(client, eid: int, code: str, payload: dict):
    return client.post("/api/requests", headers=auth_headers(login(client, *HR)),
                       json={"employee_id": eid, "request_type_code": code,
                             "payload_json": payload})


def test_the_first_exit_opens_normally(client, leaver):
    """خطّ الأساس: بلا خروج أول يكون منع الثاني قياًسا على فراغ."""
    r = _open_case(client, leaver)
    assert r.status_code == 201, r.text[:200]


def test_a_draft_cannot_sit_beside_an_eos_case(client, leaver):
    """**جوهر البند**: تاريخان لمغادرة واحدة، وحسابان للمستحقّات."""
    assert _open_case(client, leaver).status_code == 201
    r = _open_draft(client, leaver)
    assert r.status_code == 409, (
        f"فُتحت مسودة بجانب حالة نهاية خدمة: {r.status_code} {r.text[:200]}"
    )
    detail = r.json()["detail"]
    assert detail["code"] == "EXIT_ALREADY_OPEN", detail
    assert detail["where"], "رفض بلا وجهة — أين الخروج المفتوح؟"


def test_an_eos_case_cannot_sit_beside_a_draft(client, leaver):
    """والعكس كذلك: المنع لا يتبع ترتيب الفتح."""
    assert _open_draft(client, leaver).status_code == 200
    r = _open_case(client, leaver)
    assert r.status_code == 409, (
        f"فُتحت حالة نهاية خدمة بجانب مسودة: {r.status_code} {r.text[:200]}"
    )


def test_an_exit_request_cannot_sit_beside_a_case(client, leaver):
    """وطلب الخروج ليس باًبا ثالًثا مفتوًحا."""
    assert _open_case(client, leaver).status_code == 201
    r = _open_request(client, leaver, "REQEOS", EOS_REQ)
    assert r.status_code == 409, (
        f"فُتح طلب خروج بجانب حالة قائمة: {r.status_code} {r.text[:200]}"
    )


def test_two_exit_requests_cannot_coexist(client, leaver):
    """**والعطل الذي أحدثتُه ثم أصلحتُه**: طلبان من النوع نفسه.

    كتبتُ أوًلا مرشًِّحا يُسقط ما يطابق نوع الفاتح، ظًنا أنه يمنع تعارض
    الباب مع نفسه. وأثره الوحيد أن يمرّ ``REQRESIGN`` بجانب ``REQEOS``
    لأن كليهما ``request`` — أي أن الحارس يفتح الثغرة التي بُني لسدّها.
    """
    first = _open_request(client, leaver, "REQEOS", EOS_REQ)
    assert first.status_code == 201, first.text[:250]
    second = _open_request(client, leaver, "REQRESIGN", RESIGN)
    assert second.status_code == 409, (
        f"فُتح طلب خروج ثانٍ: {second.status_code} {second.text[:200]}"
    )


def test_clearance_is_still_allowed_during_an_exit(client, leaver):
    """وإخلاء الطرف **خطوة داخل** الخروج لا خروج مستقلّ.

    منعُه يمنع إجراًء مشروًعا أثناء خروج قائم — وحالة نهاية الخدمة
    نفسها فيها مرحلة ``clearance``.
    """
    assert "REQCLR" not in exit_guard.EXIT_REQUEST_TYPES, (
        "صار إخلاء الطرف يُعدّ خروًجا مستقًلا — فيُمنع أثناء الخروج الذي "
        "هو جزء منه"
    )


def test_the_guard_names_what_is_open_and_where(client, leaver):
    """ومن يُمنع يحتاج أن يعرف أين الباب الأول ليغلقه."""
    assert _open_case(client, leaver).status_code == 201
    r = _open_draft(client, leaver)
    detail = r.json()["detail"]
    opens = detail["open_exits"]
    assert opens, detail
    assert opens[0]["kind"] == "eos_case", opens
    assert opens[0]["date"] == "2026-10-01", opens
    # الرقم المرجعي أنفع من اسم الشاشة: به يصل القارئ إلى الحالة نفسها.
    assert opens[0]["label"].split()[-1] in detail["message"], detail["message"]
    assert "EOS/" in detail["message"], detail["message"]


def test_a_finished_exit_does_not_block_a_new_one(client, leaver):
    """وخروج انتهى لا يمنع غيره: الحارس على المفتوح لا على التاريخ.

    وإلا لاستحال إعادة توظيف من غادر ثم عاد.
    """
    r = _open_case(client, leaver)
    assert r.status_code == 201
    cid = r.json()["id"]

    db = SessionLocal()
    try:
        case = db.get(models.EosCase, cid)
        case.status = "settled"          # بلغ نهايته
        db.commit()
        assert exit_guard.open_exits(db, leaver) == [], (
            "خروج مصروف ما زال يُعدّ مفتوًحا"
        )
    finally:
        db.close()

    assert _open_draft(client, leaver).status_code == 200


def test_all_three_doors_read_the_same_source():
    """**الحارس الجامع**: باب رابع يُضاف غًدا لا يُنسى.

    ثلاثة حرّاس كلٌّ يرى مساره نظيًفا هو أصل العطل. والقاعدة الآن في
    موضع واحد، وطلبات الخروج تمرّ بنقطة الاختناق ``create_request``
    لا بالراوتر — فلا يبقى منفذ إنشاء بلا فحص.
    """
    import inspect

    from app import workflow
    from app.routers import employees, eos

    for mod in (employees, eos, workflow):
        src = inspect.getsource(mod)
        assert "assert_single_exit" in src, (
            f"{mod.__name__} يفتح خروًجا بلا قراءة المصدر الواحد"
        )
    assert "assert_single_exit" in inspect.getsource(workflow.create_request), (
        "فحص طلبات الخروج خارج نقطة الاختناق — منفذ إنشاء آخر يتجاوزه"
    )
