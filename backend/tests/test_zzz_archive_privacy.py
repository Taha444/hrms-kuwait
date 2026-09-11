# -*- coding: utf-8 -*-
"""مستٌند سرٌّي في ملٍّف مفتوح ليس سرًّا.

**العطل المقيس**: ``Document`` بلا علَم سرّية، وقراءُة الأرشيف بلا ترشيح.
فمن يحمل ``view_documents`` — شؤون الموظفين · مدير الشركة · المالك ·
المندوب — يقرأ **كل** ما في ملف الموظف.

وأربعُة مستنداٍت سرّية تُصدَر اليوم: قرار إنذار · قرار خصم · اتفاقية قرض ·
تسوية نهاية خدمة. واثنان منها من عمل هذه الجولة.

**وأوضُحها ضرًرا ``OD-010``** (نتيجة تظلّم): إصداُره يضعه في ملٍّف يقرؤه
مدير الشركة — وربما المشكوّ منه. أي نقٌض لحجب الشكوى الذي بُني في البند 5.

**وقاعدُة الرؤية هي قاعدُة الطلب نفسها** لا نسخٌة ثانية لها: من يرى الطلب
يرى ورقته، ومن حُجب عنه الطلب تُحجَب عنه. ولو كُتبت قاعدٌة مستقلّة
لانحرفت عن ``_get_req`` يوم يتغيّر أحدهما.
"""
from __future__ import annotations

import pytest
from sqlalchemy import delete as sa_delete, select

from app import doc_archive, models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
HR = ("100000000002", "hr12345")
MGR = ("100000000001", "manager123")


def _user(civil: str):
    db = SessionLocal()
    try:
        u = db.scalar(select(models.User).where(models.User.civil_id == civil))
        return u.id, u.employee_id, u.company_id, u.role
    finally:
        db.close()


def _subject_employee(db, cid: int, exclude: set[int]) -> int:
    """ملٌّف لا يملكه أٌي من المختبَرين.

    **وحارٌس يقيس على ملٍّف قد يملكه المختبَر لا يقيس ما يدّعي**: من يرى
    ورقَته بحقّ صاحِب الملف يُظنّ خرًقا للحجب. وربُط المستخدمين بالموظفين
    يتغيّر بأثر اختباراٍت أخرى (ربٌط تلقائي بالرقم المدني)، فلا يُفترَض
    ثابًتا — يُقاس.
    """
    rows = db.scalars(select(models.Employee).where(
        models.Employee.company_id == cid)).all()
    for e in rows:
        if e.id not in exclude:
            return e.id
    raise AssertionError("لا ملفّ حياديّ في هذه الشركة — لا يُقاس الحجب")


@pytest.fixture
def confidential_doc():
    """ورقٌة سرّية في ملٍّف حيادّي، مصدُرها طلٌب سرّي لا يراه المدير."""
    _uid, emp_id, cid, _r = _user(EMP[0])
    _mgr_uid, mgr_emp, _c, _r2 = _user(MGR[0])
    _hr_uid, hr_emp, _c2, _r3 = _user(HR[0])
    db = SessionLocal()
    try:
        emp_id = _subject_employee(db, cid, {mgr_emp, hr_emp})
        req = models.Request(
            company_id=cid, employee_id=emp_id, requester_user_id=_uid,
            request_type_code="REQGRV", status="completed", current_stage=0,
            payload_json={"subject": "قياس خصوصية الأرشيف", "category": "other",
                          "details": "…", "confidential": True})
        db.add(req)
        db.flush()
        doc = models.Document(
            company_id=cid, entity_type="employee", entity_id=emp_id,
            document_type_code="grievance_outcome", title="نتيجة تظلّم",
            file_path="archive/conf_test.pdf", is_current=True, is_issued=True,
            is_confidential=True, source_request_id=req.id)
        db.add(doc)
        db.commit()
        ids = (req.id, doc.id)
    finally:
        db.close()
    yield (*ids, emp_id)
    db = SessionLocal()
    try:
        db.execute(sa_delete(models.Document).where(models.Document.id == ids[1]))
        db.execute(sa_delete(models.Request).where(models.Request.id == ids[0]))
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# القاعدة واحدة
# ---------------------------------------------------------------------------

def test_the_subject_of_the_file_sees_his_own_paper(confidential_doc):
    """صاحُب الملف يرى ورقته — الإنذار يُسلَّم له، والتظلّم تظلُّمه.

    و**صاحُب الملف هو صاحُبه لا من نظنّه**: الورقة تُوضَع في ملٍّف حيادّي
    يُختار بالقياس، فيُسأل عنه من يملكه فعًلا.
    """
    _rid, did, eid = confidential_doc
    db = SessionLocal()
    try:
        doc = db.get(models.Document, did)
        owner = db.scalar(select(models.User).where(
            models.User.employee_id == eid))
        if owner is None:
            # لا حساب لصاحب الملف — يُبنى قارٌئ بصفته لقياس القاعدة وحدها.
            owner = models.User(role="employee", employee_id=eid,
                                company_id=doc.company_id)
        assert doc_archive.may_view_document(db, owner, doc)
    finally:
        db.close()


def _approver_ids(db, req) -> set[int]:
    from app import workflow

    rt = workflow.get_request_type(db, req.company_id, req.request_type_code)
    out: set[int] = set()
    if rt is not None:
        for st in workflow._chain(rt, req):
            out |= {u.id for u in workflow.resolve_stage_approvers(db, req, st)}
    return out


def _an_outsider(db, req, owner_emp_id: int):
    """قارٌئ ليس معتمًِدا ولا صاحَب الملف — يُقاس لا يُفترَض.

    **وكان هذا الحارس يسمّي المدير**، على افتراض أن سلسلة التظلّم مرحلٌة
    واحدة دورها ``hr``. وسلاسُل الأنواع تُقرأ من القاعدة وقد تُخصَّص لكل
    شركة — فوُجد المديُر معتمًِدا فيها، ورؤيتُه الورقة **حٌق لا خرق**.
    فسقط الحارس وهو يقيس شيًئا صحيًحا.

    **والقاعدة ليست «المدير لا يرى» بل «من لا يرى الطلب لا يرى ورقته».**
    فيُختار القارئ بالقياس: أوُل من ليس معتمًِدا ولا مالًكا.
    """
    approvers = _approver_ids(db, req)
    for u in db.scalars(select(models.User).where(
            models.User.company_id == req.company_id,
            models.User.is_active.is_(True))).all():
        if u.id in approvers or u.role == "super_admin":
            continue
        if u.employee_id and u.employee_id == owner_emp_id:
            continue
        return u
    raise AssertionError("كل من في الشركة معتمٌِد أو مالك — لا يُقاس الحجب")


def test_a_non_approver_does_not_see_a_confidential_paper(confidential_doc):
    """**جوهر البند**: من حُجب عنه الطلب تُحجَب عنه ورقته."""
    _rid, did, eid = confidential_doc
    db = SessionLocal()
    try:
        doc = db.get(models.Document, did)
        req = db.get(models.Request, doc.source_request_id)
        outsider = _an_outsider(db, req, eid)
        assert not doc_archive.may_view_document(db, outsider, doc),             f"رآها من ليس معتمًِدا: {outsider.role}"
    finally:
        db.close()


#: كلماُت مرور البذرة — تُقرأ لتسجيل دخول القارئ المحايد المختار.
_SEED_PASSWORDS = {"accountant": "account123", "branch_supervisor": "sup12345",
                   "delegate": "deleg123", "employee": "emp12345",
                   "hr": "hr12345", "company_manager": "manager123",
                   "company_owner": "owner123"}


def _outsider_creds(confidential_doc):
    _rid, did, eid = confidential_doc
    db = SessionLocal()
    try:
        doc = db.get(models.Document, did)
        req = db.get(models.Request, doc.source_request_id)
        u = _an_outsider(db, req, eid)
        pw = _SEED_PASSWORDS.get(u.role)
        assert pw, f"لا كلمَة مرور معروفة لدور {u.role}"
        return (u.civil_id, pw)
    finally:
        db.close()


def test_the_stage_approver_does_see_it(confidential_doc):
    """ومن يعتمد الطلب يرى ورقته — الحجب لا يُعمي من يعالج."""
    _rid, did, _eid = confidential_doc
    db = SessionLocal()
    try:
        user = db.scalar(select(models.User).where(models.User.civil_id == HR[0]))
        doc = db.get(models.Document, did)
        assert doc_archive.may_view_document(db, user, doc)
    finally:
        db.close()


def test_a_confidential_paper_without_a_source_is_hidden():
    """**وورقٌة سرّية بلا مصدٍر تُحجَب** — لا تُقرأ قاعدُتها فلا تُخمَّن."""
    db = SessionLocal()
    try:
        user = db.scalar(select(models.User).where(models.User.civil_id == HR[0]))
        orphan = models.Document(
            company_id=user.company_id, entity_type="employee", entity_id=-1,
            document_type_code="x", is_confidential=True, source_request_id=None)
        assert not doc_archive.may_view_document(db, user, orphan)
    finally:
        db.close()


def test_an_ordinary_paper_is_untouched(confidential_doc):
    """وغيُر السرّي يبقى كما كان — الحارس لا يضيّق ما لم يُطلَب تضييقه."""
    db = SessionLocal()
    try:
        user = db.scalar(select(models.User).where(models.User.civil_id == MGR[0]))
        plain = models.Document(
            company_id=user.company_id, entity_type="employee", entity_id=1,
            document_type_code="passport", is_confidential=False)
        assert doc_archive.may_view_document(db, user, plain)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# والأبواب كلّها تمرّ بها
# ---------------------------------------------------------------------------

def test_the_employee_file_hides_it_from_the_manager(client, confidential_doc):
    """قائمُة ملف الموظف: لا تعرضها للمدير."""
    _rid, _did, emp_id = confidential_doc
    creds = _outsider_creds(confidential_doc)
    body = client.get(f"/api/employees/{emp_id}",
                      headers=auth_headers(login(client, *creds))).json()
    titles = [d.get("title") for d in (body.get("documents") or [])]
    assert "نتيجة تظلّم" not in titles, titles


def test_the_timeline_hides_it_too(client, confidential_doc):
    """**والخطّ الزمني باٌب كالقائمة** — عنواٌن فيه يكشف وجود الورقة."""
    _rid, _did, emp_id = confidential_doc
    creds = _outsider_creds(confidential_doc)
    r = client.get(f"/api/employees/{emp_id}/timeline",
                   headers=auth_headers(login(client, *creds)))
    if r.status_code != 200:
        pytest.skip(f"لا خطّ زمني متاح: {r.status_code}")
    assert "نتيجة تظلّم" not in r.text, r.text[:300]


def test_the_history_endpoint_hides_it(client, confidential_doc):
    """وسجلّ النسخ كذلك."""
    _rid, _did, emp_id = confidential_doc
    creds = _outsider_creds(confidential_doc)
    r = client.get("/api/documents/history",
                   params={"entity_type": "employee", "entity_id": emp_id},
                   headers=auth_headers(login(client, *creds)))
    if r.status_code != 200:
        pytest.skip(f"غير متاح: {r.status_code}")
    assert "نتيجة تظلّم" not in r.text, r.text[:300]


def test_the_rule_is_read_from_the_request_not_rewritten():
    """**ولا قاعدَة رؤيٍة ثانية.**

    لو كُتبت هنا قاعدٌة مستقلّة لانحرفت عن ``_get_req`` يوم يتغيّر
    أحدهما — وهو نمُط «موضعان يصفان قاعدة واحدة».
    """
    import inspect

    src = inspect.getsource(doc_archive.may_view_document)
    assert "resolve_stage_approvers" in src, "قاعدُة الرؤية كُتبت من جديد"
    assert "source_request_id" in src, "لا صلة بالطلب — فالقاعدة مخمَّنة"
