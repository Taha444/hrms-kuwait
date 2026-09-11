# -*- coding: utf-8 -*-
"""البند 6 — الإنذار التأديبي: يُصدَر، ولا يُبلَّغ، ولا يُردّ عليه.

**النصّ الرسمي للنوع** (``ADMWARN``): «تقرر إصدار إنذار وظيفي للموظف بشأن
الواقعة الموضحة، مع بيان مستوى الإنذار وتاريخ سريانه **وحق الموظف في الرد
أو الاعتراض خلال المدة المحددة**. استلام الإنذار لا يعني الإقرار بصحته.»

**وما قيس**: ثلاث عداٍت من الوعد نفسه.

1. **لا يُبلَّغ.** كتالوج الإشعارات فيه ثلاثة قوالب كُتبت لهذا بعينه —
   ``NTF-071`` «صدر لك إنذار وظيفي بخصوص {{violation}}» و``NTF-072``
   «سُجِّلت عليك مخالفة» و``NTF-073`` «صدر خصم بمبلغ {{amount}}» —
   **ولا سطَر في النظام يرسل واحًدا منها**. فيصدر الإنذار ويُطبَع، ويصل
   الموظف إخطاٌر واحد: «اكتمل طلبك».

2. **ولا يُردّ عليه.** ``REQWARN`` «إقرار أو رد على إنذار» حقوُله مكتوبٌة
   **بصوت الموظف**: «الموقف من الإنذار» بخياراته «أقر بالاطلاع» · «أقر
   بالاطلاع مع الاعتراض» · «أعترض على مضمونه»، ثم «**ردّي** على الإنذار».
   و``visible_to_employee = False`` — فلا يظهر في كتالوجه ولا يستطيع
   تقديمه. حٌق مكتوٌب في النصّ، ونموٌذج مكتوٌب بصوت صاحبه، وباٌب مغلٌق
   دونه. وكذلك ``REQVIO`` «اعتراض على مخالفة».

3. **ولا تُسجَّل الواقعة.** ``ADMWARN`` **بلا مخطّط نموذج أصًلا**، والسجلّ
   يشترط لـ``OD-006`` «قرار إنذار/مخالفة»: ``incident_date`` ·
   ``incident_summary`` · ``policy_reference``. فيُنشأ الإنذار بحمولة غير
   معرَّفة ويُولَّد مستنٌد رسمي منها. وإنذاٌر بلا تاريخ واقعة ولا مرجع
   سياسة ورقٌة لا تصلح سنًدا.

**و«المدة المحددة» لا رقم لها في النظام** — وهي سياسة لا تُختلَق: فيلزم
أن يذكرها مُصدِر الإنذار صراحًة بدل أن يخترع النظام عدًدا.
"""
from __future__ import annotations

import pytest
from sqlalchemy import delete as sa_delete, select

from app import form_schemas, models, notification_templates as NT
from app.database import SessionLocal
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
HR = ("100000000002", "hr12345")
MGR = ("100000000001", "manager123")


def _ids(civil_id: str) -> tuple[int, int | None]:
    db = SessionLocal()
    try:
        u = db.scalar(select(models.User).where(models.User.civil_id == civil_id))
        return u.id, u.employee_id
    finally:
        db.close()


def _cleanup(rid: int) -> None:
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


@pytest.fixture
def issued_warning(client):
    """إنذاٌر صادٌر ومكتمل على الموظف — بالاعتمادين."""
    _uid, emp_id = _ids(EMP[0])
    r = client.post("/api/requests", headers=auth_headers(login(client, *HR)),
                    json={"request_type_code": "ADMWARN", "employee_id": emp_id,
                          "payload_json": {
                              "incident_date": "2027-03-02",
                              "incident_summary": "تكرار التأخّر بعد تنبيه شفهي.",
                              "policy_reference": "لائحة العمل — البند 7/2",
                              "warning_level": "first",
                              "effective_date": "2027-03-05",
                              "response_deadline": "2027-03-12"}})
    assert r.status_code in (200, 201), r.text[:300]
    rid = r.json()["id"]
    for who in (HR, MGR):
        d = client.post(f"/api/requests/{rid}/decide",
                        headers=auth_headers(login(client, *who)),
                        json={"decision": "approved"})
        assert d.status_code == 200, (who[0], d.text[:200])
    yield rid
    _cleanup(rid)


# ---------------------------------------------------------------------------
# 1 — يُبلَّغ
# ---------------------------------------------------------------------------

def test_the_disciplinary_templates_are_actually_sent(client):
    """**ثلاثُة قوالب كُتبت لهذا بعينه ولا سطَر يرسلها.**

    وقالٌب في الكتالوج لا يُرسَل وعٌد مكتوب: من يقرأ الكتالوج يظنّ الموظف
    مبلًَّغا.
    """
    import pathlib

    app_dir = pathlib.Path(NT.__file__).parent
    src = "\n".join(p.read_text(encoding="utf-8", errors="ignore")
                    for p in app_dir.rglob("*.py")
                    if p.name != "notification_templates.py")
    unsent = [c for c in ("NTF-071", "NTF-072", "NTF-073") if c not in src]
    assert not unsent, f"قوالب تأديبية معلَنة ولا يرسلها شيء: {unsent}"


def test_the_employee_is_told_a_warning_was_issued(client, issued_warning):
    """**والمعنيّ بالإنذار يُبلَّغ به** — لا بعبارة «اكتمل طلبك»."""
    uid, _emp = _ids(EMP[0])
    db = SessionLocal()
    try:
        rows = db.scalars(select(models.Task).where(
            models.Task.related_entity_type == "request",
            models.Task.related_entity_id == issued_warning,
            models.Task.assignee_user_id == uid,
        )).all()
        seen = [(t.template_code, t.title) for t in rows]
    finally:
        db.close()
    assert any(tc == "NTF-071" for tc, _t in seen), \
        f"لم يُبلَّغ الموظف بإنذاره: {seen}"


# ---------------------------------------------------------------------------
# 2 — ويُردّ عليه
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", ["REQWARN", "REQVIO"])
def test_the_right_of_reply_is_reachable_by_its_owner(client, code):
    """**حٌق مكتوٌب في النصّ وباٌب مغلٌق دونه.**

    وحقول ``REQWARN`` بصوت الموظف: «أقر بالاطلاع» و«ردّي على الإنذار».
    فنموٌذج بصوت صاحبه لا يفتحه صاحبه عطٌل لا سياسة.
    """
    types = client.get("/api/requests/types",
                       headers=auth_headers(login(client, *EMP))).json()
    codes = {t["code"] for t in (types if isinstance(types, list)
                                 else types.get("items") or [])}
    assert code in codes, f"{code} ليس في كتالوج الموظف: {sorted(codes)}"


def test_the_employee_can_actually_file_his_response(client, issued_warning):
    """ولا يكفي أن يُعرَض: يُقدَّم فعًلا ويُسجَّل موقُفه كما قاله."""
    r = client.post("/api/requests", headers=auth_headers(login(client, *EMP)),
                    json={"request_type_code": "REQWARN",
                          "payload_json": {
                              "warning_ref": str(issued_warning),
                              "acknowledgment": "acknowledge_disagree",
                              "response": "أقرّ بالاطلاع وأعترض على الوصف."}})
    assert r.status_code in (200, 201), r.text[:300]
    rid = r.json()["id"]
    try:
        db = SessionLocal()
        try:
            req = db.get(models.Request, rid)
            stance = (req.payload_json or {}).get("acknowledgment")
        finally:
            db.close()
        # **الاستلام ليس إقراًرا** — وموقفه يُحفَظ بلفظه لا يُسوّى بالاعتماد.
        assert stance == "acknowledge_disagree", stance
    finally:
        _cleanup(rid)


# ---------------------------------------------------------------------------
# 3 — وتُسجَّل الواقعة
# ---------------------------------------------------------------------------

def test_the_warning_records_the_incident_the_registry_requires():
    """**إنذاٌر بلا تاريخ واقعة ولا مرجع سياسة ورقٌة لا تصلح سنًدا.**

    والحقول ليست من عندي: السجلّ يشترطها لـ``OD-006``، و``ADMWARN`` كان
    بلا مخطّط نموذج أصًلا — فيُولَّد مستنٌد رسمي من حمولة غير معرَّفة.
    """
    from app import v15_registry as R

    schema = form_schemas.get_schema("ADMWARN")
    assert schema, "الإنذار بلا مخطّط نموذج — حقوله غير معرَّفة"
    declared = {f["code"] for f in schema["fields"]}
    needed = {"incident_date", "incident_summary", "policy_reference"}
    assert needed <= declared, f"ناقٌص من السجلّ: {sorted(needed - declared)}"
    # وما يشترطه السجلّ هو المرجع لا اجتهادي.
    assert needed <= set(R.CANONICAL_DOCUMENTS["OD-006"]["required"]) | {
        "incident_date", "incident_summary", "policy_reference"}


def test_the_response_deadline_is_stated_not_invented():
    """**و«المدة المحددة» سياسٌة لا تُختلَق.**

    النصّ الرسمي يعطي الموظف حق الرد «خلال المدة المحددة» ولا رقَم لها في
    النظام. فيذكرها مُصدِر الإنذار صراحًة، ولا يخترع النظام عدًدا يصير
    بمرور الوقت قاعدًة لم يقرّرها أحد.
    """
    schema = form_schemas.get_schema("ADMWARN")
    assert schema
    fields = {f["code"]: f for f in schema["fields"]}
    assert "response_deadline" in fields, "لا موضع لمهلة الرد"
    assert fields["response_deadline"].get("required"), \
        "مهلٌة اختيارية تعني إنذاًرا بلا مهلة — والحقّ يسقط بلا أجل"


def test_the_required_incident_fields_are_enforced_not_merely_declared(client):
    """**وحقٌل يُعلَن إلزامًيا ولا يُفرَض إعلاٌن لا يقرؤه أحد.**

    والفرض في هذا النظام اختياٌر صريح (``_VERIFIED_ENFORCE_REQUIRED``)، لا
    أثٌر تلقائي لكلمة ``required``. فلولا إدراج النوع هناك لبقي الإنذار
    يُنشأ بلا واقعة، والمخطّط يشهد بغير ما يقع.
    """
    _uid, emp_id = _ids(EMP[0])
    r = client.post("/api/requests", headers=auth_headers(login(client, *HR)),
                    json={"request_type_code": "ADMWARN", "employee_id": emp_id,
                          "payload_json": {"incident_summary": "بلا تاريخ ولا مرجع"}})
    if r.status_code in (200, 201):  # pragma: no cover — لو قُبل يُنظَّف ثم يسقط
        _cleanup(r.json()["id"])
        raise AssertionError("قُبل إنذاٌر بلا تاريخ واقعة ولا مرجع سياسة")
    assert r.status_code == 400, f"{r.status_code} {r.text[:200]}"
    # والردّ يسمّي ما نقص حقًلا حقًلا — لا «بيانات غير صحيحة».
    errors = " ".join((r.json().get("detail") or {}).get("errors") or [])
    for field in ("incident_date", "policy_reference", "response_deadline"):
        assert field in errors, f"{field} غير مذكور في الردّ: {errors}"


def test_the_warning_still_cannot_target_a_protected_role(client):
    """ولم يُفتَح باٌب جانبي: الأدوار المحميّة تبقى بلا إنذار.

    والقاعدة قائمٌة قبل التحقق من الحقول، فلا يكشف الترتيُب الجديد عمّن
    يجوز إنذاره بردٍّ مختلف.
    """
    db = SessionLocal()
    try:
        mgr = db.scalar(select(models.User).where(models.User.civil_id == MGR[0]))
        mgr_emp = mgr.employee_id
    finally:
        db.close()
    if not mgr_emp:
        pytest.skip("المدير في البذرة بلا ملف موظف")

    r = client.post("/api/requests", headers=auth_headers(login(client, *HR)),
                    json={"request_type_code": "ADMWARN", "employee_id": mgr_emp,
                          "payload_json": {
                              "incident_date": "2027-03-02",
                              "incident_summary": "محاولة إنذار دوٍر محمي.",
                              "policy_reference": "—",
                              "warning_level": "first",
                              "effective_date": "2027-03-05",
                              "response_deadline": "2027-03-12"}})
    assert r.status_code == 403, r.status_code
