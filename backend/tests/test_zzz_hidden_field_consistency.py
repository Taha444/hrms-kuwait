# -*- coding: utf-8 -*-
"""P9-32 — لا تناقض بين البيانات والمسار: حقل مخفيّ لا يحمل قيمة.

**ما ظهر بالقياس:**

الشرط كان يُفرَض في اتجاه واحد فقط — «أشّر السفر ⇒ الوجهة مطلوبة».
أما العكس فلا. فأرسلتُ طلب إجازة فيه ``destination: القاهرة``
و``passport_action: renew`` وخانة السفر **غير مؤشَّرة**، فقُبل 201
ومراحله ``[مسؤول الفرع، شؤون الموظفين]`` — **بلا مرحلة المندوب**.

البيانات تقول سفر، والمسار يقول لا سفر. ولا أحد يلاحظ: يسافر الموظف
بلا إذن مغادرة البلاد.

**والقاعدة عامّة لا خاصّة بالسفر**: تُشتقّ من إعلان ``conditional``
نفسه، فتحمي كل حقل مشروط يُضاف غًدا. ومن لم يرَ الحقل لا يملؤه —
فقيمةٌ فيه إما واجهة قديمة أو طلب مباشر، وكلاهما يُنتج مساًرا خاطًئا.

**وتُفحَص خارج بوّابة ``strict``** للسبب الذي تُفحَص لأجله المرفقات:
مسار خاطئ ليس اختيارًيا. وثلاثة نماذج غير صارمة فعًلا — REQEOS وREQCLR
وREQTRAVEL — والقاعدة تحميها كلها.

(وظننتُ أوًلا أن ``REQLV`` نفسها غير صارمة، اعتماًدا على تعليق في
تعريفها. وهو قديم: كتلة ``_VERIFIED_ENFORCE_REQUIRED`` أدناه تتجاوزه
وتُفعّل الصرامة. صُحّح التعليق — تعليق يخالف ما يقع يُقرأ ويُصدَّق.)
"""
from __future__ import annotations

from sqlalchemy import select

from app import form_schemas, models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")

BASE = {"start_date": "2027-03-01", "end_date": "2027-03-05", "days": 5,
        "leave_type": "annual", "reason": "زيارة"}


def _emp_id() -> int:
    db = SessionLocal()
    try:
        return db.scalar(select(models.Employee.id).where(
            models.Employee.civil_id == EMP[0]))
    finally:
        db.close()


def test_the_leave_form_asks_about_travel_explicitly():
    """خطّ الأساس: النموذج **يسأل** — بلا سؤال لا معنى لقياس التناقض."""
    s = form_schemas.get_schema("REQLV")
    field = next((f for f in s["fields"] if f["code"] == "travel_required"), None)
    assert field, "لا سؤال صريح عن السفر"
    assert field["type"] == "checkbox", field
    conds = [c for c in (s.get("conditional") or [])
             if (c.get("when") or {}).get("travel_required") is True]
    assert conds, "السؤال لا يحكم شيًئا"


def test_travel_data_without_the_flag_is_refused(client):
    """**جوهر البند**: بيانات سفر بلا تأشير كانت تمرّ بلا مرحلة المندوب."""
    hdr = auth_headers(login(client, *EMP))
    r = client.post("/api/requests", headers=hdr, json={
        "employee_id": _emp_id(), "request_type_code": "REQLV",
        "payload_json": {**BASE, "travel_required": False,
                         "destination": "القاهرة"}})
    assert r.status_code == 400, (
        f"قُبل تناقض بين البيانات والمسار: {r.status_code} {r.text[:200]}"
    )
    msg = str(r.json().get("detail"))
    assert "destination" in msg, msg
    # والرسالة تقول ما العمل، لا «غير صالح» وحدها.
    assert "امسح الحقل" in msg or "صحّح الشرط" in msg, msg


def test_the_flag_without_the_data_is_still_refused(client):
    """والاتجاه الآخر يبقى مفروًضا: سفر بلا وجهة لا يُرسَل للمندوب."""
    hdr = auth_headers(login(client, *EMP))
    r = client.post("/api/requests", headers=hdr, json={
        "employee_id": _emp_id(), "request_type_code": "REQLV",
        "payload_json": {**BASE, "travel_required": True}})
    assert r.status_code == 400, r.status_code
    assert "destination" in str(r.json().get("detail"))


def test_a_consistent_travel_request_routes_to_the_delegate(client):
    """والمتّسق يمرّ **ويدخل** مرحلة المندوب — وإلا كان المنع بلا مقابل."""
    hdr = auth_headers(login(client, *EMP))
    r = client.post("/api/requests", headers=hdr, json={
        "employee_id": _emp_id(), "request_type_code": "REQLV",
        "payload_json": {**BASE, "travel_required": True,
                         "destination": "القاهرة"}})
    assert r.status_code == 201, r.text[:200]
    body = client.get(f"/api/requests/{r.json()['id']}", headers=hdr).json()
    roles = [s.get("role") for s in body.get("stages", [])]
    assert "delegate" in roles, f"سفر بلا مرحلة مندوب: {roles}"


def test_a_consistent_non_travel_request_skips_the_delegate(client):
    """وإجازة بلا سفر لا تُرسَل للمندوب: مرحلة على كل طلب تعني لا مرحلة."""
    hdr = auth_headers(login(client, *EMP))
    r = client.post("/api/requests", headers=hdr, json={
        "employee_id": _emp_id(), "request_type_code": "REQLV",
        "payload_json": {**BASE, "travel_required": False, "reason": "راحة"}})
    assert r.status_code == 201, r.text[:200]
    body = client.get(f"/api/requests/{r.json()['id']}", headers=hdr).json()
    roles = [s.get("role") for s in body.get("stages", [])]
    assert "delegate" not in roles, f"مندوب على إجازة بلا سفر: {roles}"


def test_an_empty_hidden_field_is_not_an_error(client):
    """ولا يُرفض حقل مخفيّ فارغ: الواجهة ترسل مفاتيحها كلها.

    رفضُ ``""`` أو ``None`` يجعل كل طلب سليم يُردّ — وهو ما يحوّل
    قاعدة صحيحة إلى عطل.
    """
    hdr = auth_headers(login(client, *EMP))
    r = client.post("/api/requests", headers=hdr, json={
        "employee_id": _emp_id(), "request_type_code": "REQLV",
        "payload_json": {**BASE, "travel_required": False,
                         "destination": "", "return_date": None,
                         "reason": "راحة"}})
    assert r.status_code == 201, (
        f"رُفض حقل مخفيّ فارغ: {r.text[:200]}"
    )


def test_the_rule_is_general_not_written_per_form():
    """**والقاعدة عامّة**: تُشتقّ من الإعلان فتحمي ما يُضاف غًدا.

    قاعدة مكتوبة لحقل السفر وحده تترك كل حقل مشروط آخر بلا حماية —
    وهو نمط «قاعدة واحدة في موضعين» نفسه، بصيغة أخرى.
    """
    import inspect

    src = inspect.getsource(form_schemas.validate_payload)
    assert "for code_ in sorted(hidden)" in src, "القاعدة غير مشتقّة من hidden"
    assert "travel_required" not in src, (
        "القاعدة مكتوبة لحقل بعينه — فكل حقل مشروط آخر بلا حماية"
    )


def test_it_runs_outside_the_strict_gate():
    """وتعمل حين تُطفَأ الصرامة صراحًة — لا تحتمي بها.

    ``submit_request`` يمرّر ``strict=False`` للأكواد ذات النموذج
    المبرمج، وثلاثة نماذج غير صارمة بتعريفها. فالقاعدة داخل البوّابة
    تترك هؤلاء بلا حماية — ومسار خاطئ ليس اختيارًيا.
    """
    errors = form_schemas.validate_payload(
        "REQLV", {**BASE, "travel_required": False, "destination": "القاهرة"},
        strict=False)
    assert any("destination" in e for e in errors), (
        f"القاعدة سقطت مع إطفاء الصرامة: {errors}"
    )


def test_some_schemas_really_are_lax():
    """وليس هذا احتياًطا نظرًيا: نماذج غير صارمة موجودة فعًلا."""
    lax = [c for c in form_schemas.SCHEMAS
           if not (form_schemas.get_schema(c).get("meta") or {}).get(
               "strict_validation")]
    assert lax, "لا نموذج غير صارم — راجع موضع القاعدة، فالبوّابة تكفي"


def test_the_orphan_travel_form_stays_unreachable():
    """**والسفر له نموذجان، أحدهما لا يصل** — ولم أوصّفه بالتخمين.

    ``REQTRAVEL`` (alias ``exit_permit``) يطلب ``travel_date``
    و``passport_no`` — حقلان لا يسألهما مسار الإجازة. ولا نوع طلب
    يصل إليه، ولا alias حيّ، ولا ذكر في سجلّ V1.5: شيفرة ميتة.

    وتوصيلُه يخلق مسارين لطلب إذن مغادرة واحد، ببيانات مختلفة —
    وهو التناقض الذي يحذّر منه هذا البند بعينه.

    وحذفُه يُلقي بمعلومة لا أملكها: لماذا سُئل عن رقم الجواز هنا ولا
    يُسأل هناك؟ وهل تحتاج الشركة طلب إذن مغادرة **مستقًلا** عن
    الإجازة (سفر عمل مثًلا)؟ ذلك قرار عمل.

    فيسقط هذا الاختبار يوم يصير النموذج حًيا — وهو الوقت الصحيح
    لحسم السؤال، لا يوم يُقدَّم طلبان متناقضان لنفس السفرة.
    """
    from app import workflow

    codes = {rt["code"] for rt in workflow.DEFAULT_REQUEST_TYPES}
    aliases = (form_schemas.SCHEMAS["REQTRAVEL"].get("meta") or {}).get(
        "legacy_aliases", [])
    reachable = ("REQTRAVEL" in codes
                 or "REQTRAVEL" in form_schemas.REQUEST_TYPE_SCHEMA_MAP.values()
                 or any(a in codes for a in aliases))
    assert not reachable, (
        "صار REQTRAVEL قابًلا للوصول — احسم أوًلا: هل إذن المغادرة طلب "
        "مستقلّ أم مرحلة داخل الإجازة؟ وجودهما مًعا مساران لسفرة واحدة."
    )
