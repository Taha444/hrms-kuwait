# -*- coding: utf-8 -*-
"""البند 5 — الشكوى السرّية تُحجَب عن المشكو منه.

**العطل المقيس**: نموذج الشكوى يسأل صراحًة «المُشتكى منه (اختياري)» ويخزّن
``against_user_id``. **والكلمة تظهر في الشيفرة كلّها مرًّة واحدة: في
النموذج الذي يجمعها.** لا سطَر يقرؤها.

وهذا ليس حقًلا مهمًلا بل **وعٌد لا يُوفى**. من يكتب اسم من يشكو منه يفهم
أنه بذلك يحتجب عنه؛ والنظام لا يفعل شيًئا بالاسم.

**وأثره ينقلب على الغرض**: سلسلة ``REQGRV`` مرحلٌة واحدة دورها ``hr``،
و``resolve_stage_approvers`` تعيد **كل** من يحمل الدور. فإن كان المشكو منه
من شؤون الموظفين:

- يصله الطلب في صندوقه،
- و``_get_req`` تأذن له لأنه **معتمِد المرحلة**،
- ويقرّره: يعتمد أو يرفض الشكوى المرفوعة ضدّه.

وحارس الاعتماد الذاتي لا يمنعه: ``can_decide`` يقيس
``req.employee_id == user.employee_id`` — أي **مقدّم** الشكوى لا المشكو
منه. فالقاعدة موجودة وتقيس الطرف الآخر.

**والنصّ الرسمي للنوع يقول**: «وأطلب التعامل معها بسرية وبما يمنع تضارب
المصالح. إذا كان المسؤول المباشر طرًفا لا يطلع عليها تلقائًيا.» فالسياسة
مكتوبة في النصّ ولم تُكتب في الشيفرة.
"""
from __future__ import annotations

import pytest
from sqlalchemy import delete as sa_delete, select

from app import models, workflow
from app.database import SessionLocal
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
HR = ("100000000002", "hr12345")
MGR = ("100000000001", "manager123")


def _user(civil_id: str) -> tuple[int, int | None]:
    db = SessionLocal()
    try:
        u = db.scalar(select(models.User).where(models.User.civil_id == civil_id))
        return u.id, u.employee_id
    finally:
        db.close()


@pytest.fixture
def grievance_against_hr(client):
    """شكوى مقدَّمة، والمشكو منه **من شؤون الموظفين** — وهو معتمِد المرحلة."""
    _hr_uid, hr_emp = _user(HR[0])
    assert hr_emp, "حساب شؤون الموظفين في البذرة بلا ملف موظف — لا يُقاس التعارض"

    r = client.post("/api/requests", headers=auth_headers(login(client, *EMP)),
                    json={"request_type_code": "REQGRV",
                          "payload_json": {
                              "subject": "قياس تضارب المصالح",
                              "category": "management",
                              "against_user_id": hr_emp,
                              "details": "الشكوى مرفوعة على من يعتمد المرحلة.",
                              "confidential": True}})
    assert r.status_code in (200, 201), r.text[:300]
    rid = r.json()["id"]
    yield rid

    db = SessionLocal()
    try:
        for tbl in (models.RequestDocument, models.RequestApproval):
            db.execute(sa_delete(tbl).where(tbl.request_id == rid))
        db.execute(sa_delete(models.Task).where(
            models.Task.related_entity_type == "request",
            models.Task.related_entity_id == rid))
        db.execute(sa_delete(models.Request).where(models.Request.id == rid))
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# الحقل يُقرأ
# ---------------------------------------------------------------------------

def test_the_accused_field_is_read_somewhere(client):
    """**حقٌل يُجمَع ولا يُقرأ وعٌد لا يُوفى.**

    وكانت الكلمة تظهر في الشيفرة مرًّة واحدة: في النموذج الذي يجمعها.
    """
    import inspect

    src = inspect.getsource(workflow)
    assert "against_user_id" in src, \
        "المشكو منه يُجمَع في النموذج ولا يقرؤه المحرّك"


# ---------------------------------------------------------------------------
# ولا يقرّر المشكو منه شكوى نفسه
# ---------------------------------------------------------------------------

def test_the_accused_is_not_an_approver_of_the_complaint(grievance_against_hr):
    """**جوهر البند**: من شُكي منه ليس معتمًِدا للشكوى ضدّه.

    وسلسلة ``REQGRV`` دورها ``hr`` و``resolve_stage_approvers`` تعيد كل من
    يحمله — فكان المشكو منه فيهم بحكم دوره.
    """
    _uid, hr_emp = _user(HR[0])
    db = SessionLocal()
    try:
        req = db.get(models.Request, grievance_against_hr)
        rt = workflow.get_request_type(db, req.company_id, req.request_type_code)
        stage = workflow._chain(rt, req)[req.current_stage]
        approvers = workflow.resolve_stage_approvers(db, req, stage)
        emp_ids = [u.employee_id for u in approvers]
    finally:
        db.close()
    assert hr_emp not in emp_ids, \
        f"المشكو منه من معتمِدي المرحلة: {emp_ids}"


def test_the_accused_cannot_decide_it(client, grievance_against_hr):
    """ولا يقبل المسار قراره — لا عرًضا ولا نداًء."""
    hdr = auth_headers(login(client, *HR))
    r = client.post(f"/api/requests/{grievance_against_hr}/decide",
                    headers=hdr, json={"decision": "rejected", "note": "لا"})
    assert r.status_code in (403, 404), r.text[:250]

    db = SessionLocal()
    try:
        req = db.get(models.Request, grievance_against_hr)
        assert req.status == "pending", req.status
    finally:
        db.close()


def test_the_accused_cannot_read_it(client, grievance_against_hr):
    """**ولا يطّلع عليها** — والاطلاع وحده ضٌرر ولو لم يقرّر.

    ويُردّ بـ404 لا 403: أن الطلب موجوٌد ومحجوٌب عنك خبٌر في نفسه.
    """
    r = client.get(f"/api/requests/{grievance_against_hr}",
                   headers=auth_headers(login(client, *HR)))
    assert r.status_code == 404, r.status_code


def test_the_accused_does_not_see_it_in_his_inbox(client, grievance_against_hr):
    """ولا تظهر في صندوقه — والصندوق باٌب كالتفصيل."""
    inbox = client.get("/api/requests/inbox",
                       headers=auth_headers(login(client, *HR))).json()
    ids = [x["id"] for x in inbox]
    assert grievance_against_hr not in ids, ids


def test_the_accused_gets_no_task_about_it(client, grievance_against_hr):
    """ولا مهمٌة ولا إخطار — فعنواٌن في الصندوق يكشف وجودها."""
    hr_uid, _emp = _user(HR[0])
    db = SessionLocal()
    try:
        rows = db.scalars(select(models.Task).where(
            models.Task.related_entity_type == "request",
            models.Task.related_entity_id == grievance_against_hr,
            models.Task.assignee_user_id == hr_uid,
        )).all()
        titles = [t.title for t in rows]
    finally:
        db.close()
    assert not titles, f"أُخطِر المشكو منه بالشكوى ضدّه: {titles}"


# ---------------------------------------------------------------------------
# والحجب لا يُنتج بابًا مغلًقا
# ---------------------------------------------------------------------------

def test_excluding_the_accused_still_leaves_someone_to_decide(grievance_against_hr):
    """**وحجٌب يُفرِغ المرحلة يوقف الشكوى** — وهو ضٌرر آخر بالمشتكي.

    فلو كان المشكو منه وحده حامَل الدور، لصارت الشكوى بلا معتمِد ووقفت
    إلى الأبد. والتصعيد يبقى داخل من يملك ``approve_grievance`` أصًلا
    (``company_manager``) — فلا سلطٌة جديدة تُمنَح.
    """
    db = SessionLocal()
    try:
        req = db.get(models.Request, grievance_against_hr)
        rt = workflow.get_request_type(db, req.company_id, req.request_type_code)
        stage = workflow._chain(rt, req)[req.current_stage]
        approvers = workflow.resolve_stage_approvers(db, req, stage)
        roles = sorted({u.role for u in approvers})
    finally:
        db.close()
    assert approvers, "الشكوى بلا معتمِد بعد حجب المشكو منه"
    assert roles, roles


def test_a_grievance_naming_nobody_is_untouched(client):
    """وشكوى بلا مشكو منه تمضي كما كانت — لا يضيق المسار بلا سبب."""
    r = client.post("/api/requests", headers=auth_headers(login(client, *EMP)),
                    json={"request_type_code": "REQGRV",
                          "payload_json": {"subject": "بلا مشكو منه",
                                           "category": "other",
                                           "details": "شكوى عامة.",
                                           "confidential": True}})
    assert r.status_code in (200, 201), r.text[:250]
    rid = r.json()["id"]
    try:
        d = client.get(f"/api/requests/{rid}",
                       headers=auth_headers(login(client, *HR)))
        assert d.status_code == 200, d.status_code
    finally:
        db = SessionLocal()
        try:
            db.execute(sa_delete(models.RequestApproval).where(
                models.RequestApproval.request_id == rid))
            db.execute(sa_delete(models.Task).where(
                models.Task.related_entity_type == "request",
                models.Task.related_entity_id == rid))
            db.execute(sa_delete(models.Request).where(models.Request.id == rid))
            db.commit()
        finally:
            db.close()


# ---------------------------------------------------------------------------
# والسؤال يمكن جوابه
# ---------------------------------------------------------------------------

def test_the_accused_field_can_actually_be_answered(client):
    """**الطبقة الثالثة**: سؤاٌل بقائمة فارغة لا يمكن جوابه.

    ``employee_ref`` كان ناقًصا من مصادر الخيارات، وهو نوع حقٍل واحد في
    النظام كلّه: «المُشتكى منه». فيُعرَض عنواُنه وقائمٌة فارغة. ولو بقي
    كذلك لظلّ الحجُب حبًرا: لا يُسمّى طرٌف فلا يُحجَب أحد — فإصلاح الحجب
    وحده تمثيل.
    """
    # الردّ يغلّف المخطّط: ``{"code": ..., "schema": {...}}``.
    body = client.get("/api/requests/types/REQGRV/schema",
                      headers=auth_headers(login(client, *EMP))).json()
    fields = {f["code"]: f for f in (body["schema"].get("fields") or [])}
    accused = fields.get("against_user_id")
    assert accused, f"الحقل غير معروض في المخطّط: {sorted(fields)}"
    assert accused.get("options"), (
        "قائمٌة فارغة — السؤال معروٌض ولا يمكن جوابه: "
        f"{accused.get('setup_required') or accused}")


def test_the_accused_options_stay_inside_the_company(client):
    """ولا يصير دليُل الموظفين مكشوًفا: الخيارات في نطاق الشركة."""
    # الردّ يغلّف المخطّط: ``{"code": ..., "schema": {...}}``.
    body = client.get("/api/requests/types/REQGRV/schema",
                      headers=auth_headers(login(client, *EMP))).json()
    fields = {f["code"]: f for f in (body["schema"].get("fields") or [])}
    ids = {o["value"] for o in fields["against_user_id"]["options"]}

    _uid, emp_id = _user(EMP[0])
    db = SessionLocal()
    try:
        cid = db.get(models.Employee, emp_id).company_id
        mine = {e for (e,) in db.execute(select(models.Employee.id).where(
            models.Employee.company_id == cid))}
        others = {e for (e,) in db.execute(select(models.Employee.id).where(
            models.Employee.company_id != cid))}
    finally:
        db.close()
    assert ids <= mine, f"خيارات من خارج الشركة: {sorted(ids - mine)}"
    assert not (ids & others), sorted(ids & others)
