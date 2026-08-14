# -*- coding: utf-8 -*-
"""مصفوفة RBAC — الدليل الذي يطلبه سجل QA لبنود الصلاحيات (01، 21، 29).

الغرض ليس تغطية إضافية بل **إثبات**: كل بند صلاحيات في السجل يطلب "مصفوفة
RBAC" كدليل. هنا تُبنى المصفوفة من النظام نفسه لا من افتراض، فيظهر أي انحراف
بين ما يمنحه الدور نظرًيا وما تسمح به نقاط النهاية فعلًا.
"""
import pytest

from tests.conftest import auth_headers, login

# (الوصف، الرقم المدني، كلمة المرور)
ACCOUNTS = [
    ("company_owner", "111111111111", "owner123"),
    ("company_manager", "100000000001", "manager123"),
    ("hr", "100000000002", "hr12345"),
    ("delegate", "100000000003", "deleg123"),
    ("branch_supervisor", "100000000005", "sup12345"),
    ("employee", "100000000101", "emp12345"),
]


def _headers(client, civil_id, password):
    return auth_headers(login(client, civil_id, password))


@pytest.mark.parametrize("role,civil_id,password", ACCOUNTS)
def test_rbac_permissions_reach_the_client(client, role, civil_id, password):
    """ما يمنحه الدور نظرًيا يصل الواجهة فعلًا عبر /auth/me.

    الواجهة تبني قوائمها من ``user.permissions``؛ فإن لم تصلها صلاحية، اختفى
    الرابط عند من يملكه — وهو عرَض QA-21 (المالك يرى عدد الموظفين بلا صفحة).
    """
    from app.permissions import ROLE_DEFAULT_PERMS

    hdr = _headers(client, civil_id, password)
    me = client.get("/api/auth/me", headers=hdr)
    assert me.status_code == 200, me.text
    got = set(me.json().get("permissions") or [])
    expected = set(ROLE_DEFAULT_PERMS.get(role, set()))
    missing = expected - got
    assert not missing, f"صلاحيات لم تصل الواجهة للدور {role}: {sorted(missing)}"


def test_rbac_owner_can_open_employees_page(client):
    """QA-21 — المالك يرى عدد الموظفين، فيجب أن تُفتح له صفحتهم.

    عدّاد بلا صفحة يفتحها هو طريق مسدود: يرى الرقم ولا يصل إلى ما وراءه.
    """
    hdr = _headers(client, "111111111111", "owner123")
    me = client.get("/api/auth/me", headers=hdr).json()
    assert "view_employee" in (me.get("permissions") or []), \
        "المالك بلا view_employee — الرابط سيختفي في الواجهة"

    r = client.get("/api/employees", headers=hdr)
    assert r.status_code == 200, f"صفحة الموظفين مغلقة على المالك: {r.status_code} {r.text[:200]}"
    assert isinstance(r.json(), list)


def test_rbac_gov_portals_delegate_only(client):
    """QA-29 — بوابات الجهات للمندوب وحده، على الخادم لا الواجهة."""
    allowed = client.get("/api/gov-portals", headers=_headers(client, "100000000003", "deleg123"))
    assert allowed.status_code == 200, allowed.text
    for role, cid, pw in ACCOUNTS:
        if role == "delegate":
            continue
        r = client.get("/api/gov-portals", headers=_headers(client, cid, pw))
        assert r.status_code in (403, 404), f"{role} وصل لبوابات الجهات: {r.status_code}"


def test_rbac_stage_approval_is_not_transitive(client):
    """QA-01 — لا اعتماد لمرحلة ليست لك، حتى لو كنت أعلى رتبة."""
    from app import models
    from app.database import SessionLocal
    from sqlalchemy import select

    emp = auth_headers(login(client, "100000000101", "emp12345"))
    r = client.post("/api/requests", headers=emp, json={
        "request_type_code": "REQCERTSAL",
        "payload_json": {"purpose": "بنك", "language": "ar", "include_salary": True},
    })
    if r.status_code not in (200, 201):
        pytest.skip(f"تعذّر إنشاء الطلب: {r.status_code}")
    rid = r.json()["id"]

    db = SessionLocal()
    try:
        req = db.get(models.Request, rid)
        rt = db.scalar(select(models.RequestType).where(
            models.RequestType.code == req.request_type_code))
        stage_roles = {s.get("role") for s in ((rt.approval_chain_json if rt else None) or [])}
    finally:
        db.close()

    # دور ليس في السلسلة إطلاًقا يجب أن يُرفض
    for role, cid, pw in ACCOUNTS:
        if role in stage_roles or role == "employee":
            continue
        hdr = _headers(client, cid, pw)
        d = client.post(f"/api/requests/{rid}/decide", headers=hdr,
                        json={"decision": "approved", "note": ""})
        assert d.status_code in (403, 404), (
            f"{role} اعتمد مرحلة ليست له (السلسلة: {stage_roles}) → {d.status_code}"
        )


def test_2fa_recovery_code_breaks_the_lockout(client):
    """QA-30 — من يفقد هاتفه له مخرج، ورمز الاسترداد يُستهلك مرة واحدة.

    قبل هذا: الدخول يستلزم رمز TOTP، وتعطيل 2FA يستلزم جلسة تستلزم الدخول —
    حلقة مغلقة لا مخرج منها إلا تعديل يدوي في قاعدة البيانات.
    """
    import pyotp

    from app import models
    from app.database import SessionLocal
    from sqlalchemy import select

    civil_id, password = "100000000002", "hr12345"
    hdr = _headers(client, civil_id, password)

    enroll = client.post("/api/2fa/enroll", headers=hdr)
    assert enroll.status_code == 200, enroll.text
    secret = enroll.json()["secret"]

    confirm = client.post("/api/2fa/confirm", headers=hdr,
                          json={"code": pyotp.TOTP(secret).now()})
    assert confirm.status_code == 200, confirm.text
    codes = confirm.json().get("recovery_codes")
    assert codes and len(codes) == 10, "لم تُصدر رموز استرداد عند التفعيل"

    db = SessionLocal()
    try:
        u = db.scalar(select(models.User).where(models.User.civil_id == civil_id))
        assert u.totp_recovery_hashes, "الرموز لم تُخزَّن"
        assert not any(c in str(u.totp_recovery_hashes) for c in codes), \
            "الرموز مخزَّنة نًصا — يجب تخزين تجزئتها فقط"
    finally:
        db.close()

    # الدخول بلا رمز مرفوض
    no_code = client.post("/api/auth/login", json={"civil_id": civil_id, "password": password})
    assert no_code.status_code == 401

    # وبرمز الاسترداد يُقبَل — وهذا هو المخرج
    used = codes[0]
    ok = client.post("/api/auth/login", json={
        "civil_id": civil_id, "password": password, "totp_code": used})
    assert ok.status_code == 200, f"رمز الاسترداد لم يُقبل: {ok.text[:200]}"

    # ولا يصلح مرة ثانية
    again = client.post("/api/auth/login", json={
        "civil_id": civil_id, "password": password, "totp_code": used})
    assert again.status_code == 401, "رمز الاسترداد أُعيد استخدامه"

    # والباقي تسعة، ومعروض في الحالة
    hdr2 = auth_headers(ok.json()["access_token"])
    st = client.get("/api/2fa/status", headers=hdr2).json()
    assert st.get("recovery_codes_remaining") == 9, st

    # وإعادة التوليد تبطل القديم
    regen = client.post("/api/2fa/recovery/regenerate", headers=hdr2,
                        json={"password": password})
    assert regen.status_code == 200, regen.text
    assert len(regen.json()["recovery_codes"]) == 10
    stale = client.post("/api/auth/login", json={
        "civil_id": civil_id, "password": password, "totp_code": codes[1]})
    assert stale.status_code == 401, "رمز قديم ما زال صالًحا بعد إعادة التوليد"

    # تنظيف: نعطّل 2FA حتى لا نؤثّر على بقية الاختبارات
    fresh = client.post("/api/auth/login", json={
        "civil_id": civil_id, "password": password,
        "totp_code": regen.json()["recovery_codes"][0]})
    client.post("/api/2fa/disable", headers=auth_headers(fresh.json()["access_token"]),
                json={"password": password})
