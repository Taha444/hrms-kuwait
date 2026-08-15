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


def test_no_raw_enum_or_code_leaks_in_ui():
    """QA-22/QA-14 (sweep) — المواضع التي كانت تعرض قيمة خام تستخدم تسمية الآن.

    SKILL-9 يسأل: هل لنفس الوظيفة مسار آخر؟ كان الجواب نعم ثلاث مرات — نوع
    الإقامة في شاشة التعيين وفي ملف الموظف، وكود نوع المستند في "ملفي"
    (أُصلح في ملف الموظف وحده أول مرة)، وحالة الشركة في مُنتقي الشركات.

    الفحص مقصور على هذه المواضع بعينها: مسحٌ عام بتعبير نمطي يعطي إيجابيات
    كاذبة (‎${...}‎ داخل قوالب نصية، و‎key={...}‎، وتمرير الخصائص).
    """
    from pathlib import Path

    pages = Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages"
    if not pages.exists():
        return
    checks = [
        ("EmployeeProfile.tsx", "permitKindAr(x.kind)", "نوع الإقامة خام في ملف الموظف"),
        ("EmployeeOnboarding.tsx", "permitKindAr(p.kind)", "نوع الإقامة خام في شاشة التعيين"),
        ("MyProfile.tsx", "d.type_label", "كود نوع المستند خام في ملفي"),
        ("CompanyPicker.tsx", "statusAr(c.status)", "حالة الشركة خام في مُنتقي الشركات"),
    ]
    for filename, needle, why in checks:
        f = pages / filename
        if not f.exists():
            continue
        assert needle in f.read_text(encoding="utf-8"), why


def test_manual_expiry_correction_syncs_permit(client):
    """QA-06 — التصحيح اليدوي متاح، ويُزامن سجل التصريح.

    الرفع يقبل تاريًخا يدوًيا لكن لا سبيل لتعديله بعده، فتصحيح تاريخ قرأه OCR
    خطأً كان يستلزم إعادة رفع المستند كله. والأهم: التصحيح يجب أن يمسّ Permit
    وإلا افترق العدّاد عن المستند — أصل عطل "الإقامات السارية = 0".
    """
    from datetime import date, timedelta

    from app import models
    from app.database import SessionLocal
    from sqlalchemy import select

    db = SessionLocal()
    doc_id = permit_id = None
    try:
        emp = db.scalar(select(models.Employee))
        assert emp, "لا موظف في البذرة"
        doc = models.Document(
            company_id=emp.company_id, entity_type="employee", entity_id=emp.id,
            document_type_code="residency", title="إقامة اختبار",
            expiry_date=date.today() + timedelta(days=10),
            version=1, is_current=True,
        )
        db.add(doc)
        db.commit()
        doc_id = doc.id
    finally:
        db.close()

    hdr = _headers(client, "100000000002", "hr12345")
    new_date = (date.today() + timedelta(days=300)).isoformat()
    r = client.patch(f"/api/documents/{doc_id}/expiry",
                     params={"expiry_date": new_date, "reason": "قراءة OCR خاطئة"},
                     headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["expiry_date"] == new_date

    db = SessionLocal()
    try:
        doc = db.get(models.Document, doc_id)
        assert doc.expiry_date.isoformat() == new_date, "المستند لم يُحدَّث"
        permit = db.scalar(select(models.Permit).where(
            models.Permit.employee_id == doc.entity_id,
            models.Permit.kind == "residency"))
        assert permit is not None, "التصحيح لم يُزامن سجل التصريح"
        assert permit.expiry_date.isoformat() == new_date, "التصريح على تاريخ مختلف"
        permit_id = permit.id

        # وسجل التدقيق يحمل القيمتين
        log = db.scalar(select(models.AuditLog).where(
            models.AuditLog.action == "correct_document_expiry"
        ).order_by(models.AuditLog.id.desc()))
        assert log is not None and log.user_id and log.ip, "التصحيح بلا فاعل أو IP"
    finally:
        for model, rid in ((models.Document, doc_id), (models.Permit, permit_id)):
            if rid:
                row = db.get(model, rid)
                if row:
                    db.delete(row)
        db.commit()
        db.close()


def test_health_deep_reports_clock_and_migration_currency(client):
    """الخريطة: التشخيصات التشغيلية تظهر في شاشة واحدة بدل التجربة والخطأ.

    انحراف الساعة أبطل رموز 2FA صحيحة ولم يظهر في أي مكان؛ ورأس الترحيلات
    كان يُعرض بلا مقارنة برأس الكود — فترحيل لم يُطبَّق يُكتشف بعطل لا بفحص.
    """
    r = client.get("/api/health/deep")
    body = r.json()
    checks = body.get("checks", {})

    assert "clock" in checks, "انحراف الساعة غير معروض"
    assert checks["clock"]["status"] in ("ok", "fail", "unknown")
    if checks["clock"]["status"] == "fail":
        assert checks["clock"].get("note"), "خلل الساعة بلا تفسير"

    alembic = checks.get("alembic", {})
    if alembic.get("status") != "disabled":
        assert "code_head" in alembic or "code_head_error" in alembic, \
            "لا مقارنة بين رأس القاعدة ورأس الكود"


def test_admin_can_reset_2fa_with_reason(client):
    """QA-30 — المخرج الأخير لمن فقد جهازه ورموزه، وقرار موثَّق لا تعديل يدوي."""
    from app import models
    from app.database import SessionLocal
    from sqlalchemy import select

    import pyotp

    civil_id, password = "100000000004", "deleg123"
    hdr = _headers(client, civil_id, password)
    secret = client.post("/api/2fa/enroll", headers=hdr).json()["secret"]
    client.post("/api/2fa/confirm", headers=hdr, json={"code": pyotp.TOTP(secret).now()})

    db = SessionLocal()
    try:
        target = db.scalar(select(models.User).where(models.User.civil_id == civil_id))
        target_id = target.id
        assert target.totp_confirmed
    finally:
        db.close()

    admin = _headers(client, "000000000000", "admin123")
    # السبب إلزامي — إجراء يُضعف حماية حساب حسّاس
    no_reason = client.post(f"/api/users/{target_id}/2fa/reset",
                            params={"reason": "  "}, headers=admin)
    assert no_reason.status_code == 400, no_reason.text

    ok = client.post(f"/api/users/{target_id}/2fa/reset",
                     params={"reason": "فقد الجهاز ورموز الاسترداد"}, headers=admin)
    assert ok.status_code == 200, ok.text

    # ويدخل الآن بلا رمز
    back = client.post("/api/auth/login", json={"civil_id": civil_id, "password": password})
    assert back.status_code == 200, back.text

    db = SessionLocal()
    try:
        log = db.scalar(select(models.AuditLog).where(
            models.AuditLog.action == "totp_admin_reset").order_by(models.AuditLog.id.desc()))
        assert log is not None and log.user_id, "إعادة التعيين بلا فاعل في التدقيق"
        assert "فقد الجهاز" in (log.detail or ""), "السبب لم يُحفظ"
    finally:
        db.close()


def test_v22_catalog_every_seeded_type_is_classified():
    """V2.2 §12 (STR-04) — كل نوع مبذور له تصنيف: مسار canonical أو إجراء داخلي.

    ROOT CAUSE: السجل كان يحمل 29 مساًرا و50 alias، لكن الـalias تربط أكواد
    V1.3/V1.4 لا أكواد الكتالوج المبذور. فمن 54 نوًعا نشًطا كان 5 فقط لها
    canonical، و4 مسارات من 29 مغطاة — بنية canonical موجودة ومنفصلة تماًما
    عمّا يستخدمه النظام.
    """
    from app import v15_registry as V
    from app.workflow import DEFAULT_REQUEST_TYPES

    aliases = V.LEGACY_REQUEST_ALIASES
    unclassified = []
    canonical_used = set()
    internal = []
    for rt in DEFAULT_REQUEST_TYPES:
        info = aliases.get(rt["code"]) or {}
        if info.get("internal_action"):
            internal.append(rt["code"])
            assert info.get("reason"), f"{rt['code']} إجراء داخلي بلا سبب مكتوب"
        elif info.get("canonical"):
            canonical_used.add(info["canonical"])
        else:
            unclassified.append(rt["code"])

    assert not unclassified, f"أنواع بلا تصنيف canonical: {unclassified}"
    assert internal, "لا إجراءات داخلية مصنَّفة — التصنيف الثلاثي غير مطبَّق"

    # كل canonical مُستخدَم يجب أن يكون موجوًدا في السجل فعلًا
    unknown = canonical_used - set(V.CANONICAL_WORKFLOWS)
    assert not unknown, f"مسارات غير معرّفة في السجل: {sorted(unknown)}"

    # WF-002 (إجازة سفر) وحده بلا نوع مستقل — يُشتقّ من travel_required
    missing = set(V.CANONICAL_WORKFLOWS) - canonical_used
    assert missing <= {"WF-002"}, f"مسارات بلا أي نوع يغطيها: {sorted(missing)}"


def test_v22_internal_actions_are_not_creatable(client):
    """V2.2 §12 — الإجراءات الإدارية الداخلية تخرج من "طلب جديد" وتبقى للقراءة.

    إضافة موظف تُنفَّذ من شاشة التعيين، وإشعار نقص المستندات إشعار لا طلب،
    وتجديد ترخيص الشركة كيانه الشركة لا الموظف. وجودها في كتالوج الإنشاء هو
    نصف الفارق بين 54 و29.
    """
    from app import v15_registry as V

    hr = _headers(client, "100000000002", "hr12345")
    creatable = client.get("/api/requests/types", headers=hr,
                           params={"creatable_only": True})
    assert creatable.status_code == 200, creatable.text
    codes = {t["code"] for t in creatable.json()}

    internal = {c for c, i in V.LEGACY_REQUEST_ALIASES.items()
                if i.get("internal_action")}
    leaked = codes & internal
    assert not leaked, f"إجراءات داخلية ما زالت في كتالوج الإنشاء: {sorted(leaked)}"

    # والكتالوج الكامل يبقى شامًلا لها — الطلبات التاريخية تُقرأ
    full = {t["code"] for t in client.get("/api/requests/types", headers=hr).json()}
    assert internal & full, "الكتالوج الكامل أخفى الإجراءات الداخلية أيًضا"


def test_v22_grouped_catalog_hits_the_targets(client):
    """V2.2 §12 (STR-04) + §13.1 (AC-01) — 29 خدمة، والموظف يرى 15-18.

    ستة أنواع كانت تمثّل "تغيير وظيفي" واحًدا (وردية/موقع/نقل/ترخيص/عقد/راتب
    فعلي) وستة أخرى "طلب عام" — اثنا عشر خياًرا منفصًلا يحتار المستخدم أيّها
    يخصّه فيختار الخطأ ويُرجَع طلبه. التجميع في طبقة العرض وحدها: كل نوع فرعي
    يحتفظ بكوده ونموذجه وسلسلة موافقاته.
    """
    from app import v15_registry as V

    hr = _headers(client, "100000000002", "hr12345")
    emp = _headers(client, "100000000101", "emp12345")
    params = {"creatable_only": True, "grouped": True}

    services = client.get("/api/requests/types", headers=hr, params=params).json()
    # 28 خدمة + WF-002 (إجازة سفر) المشتقّ من travel_required = 29
    assert 28 <= len(services) <= 29, f"عدد الخدمات {len(services)} خارج المستهدف"

    emp_services = client.get("/api/requests/types", headers=emp, params=params).json()
    assert 15 <= len(emp_services) <= 18, \
        f"الموظف يرى {len(emp_services)} خدمة — المستهدف 15-18"

    # لكل خدمة كود صالح للإرسال، ومن له أنواع فرعية يعلنها
    for s in services:
        assert s["code"], f"خدمة بلا كود: {s['name']}"
        subs = s.get("subtypes") or []
        assert subs, f"خدمة بلا أنواع فرعية إطلاًقا: {s['code']}"
        assert s["code"] == subs[0]["code"], "الكود لا يطابق أول نوع فرعي"
        if s.get("has_subtypes"):
            assert len(subs) > 1
            info = V.CANONICAL_WORKFLOWS.get(s["canonical_code"]) or {}
            assert s["name"] == info.get("name_ar"), \
                f"{s['canonical_code']} يحمل اسم نوع فرعي لا اسم المسار"

    # والوضع المسطّح يبقى كما هو — لا كسر لمن يستدعيه
    flat = client.get("/api/requests/types", headers=hr,
                      params={"creatable_only": True}).json()
    assert len(flat) > len(services), "الوضع المسطّح تأثر بالتجميع"
    assert all("subtypes" not in x for x in flat), "التجميع تسرّب للوضع المسطّح"


def test_v22_policy_threshold_stage(client):
    """V2.2 §7 (STR-05) + §14 (RW-06/RW-07) — مرحلة تُضاف فوق الحد فقط.

    ROOT CAUSE: مرحلة "اعتماد فوق الحد" لم يكن لها وجود — لا لأن المحرك لا
    يدعمها بل لأن الحد نفسه لم يكن له وجود في النظام إطلاًقا.
    """
    from app.workflow import _stage_applies

    stage = {"order": 3, "role": "company_owner",
             "when": {"field": "amount", "policy_gt": "finance.extra_approval_threshold",
                      "policy_field": "amount"}}
    snap = {"finance.extra_approval_threshold":
            {"value": {"amount": 500.0}, "version": 1, "source": "company"}}

    assert not _stage_applies(stage, {"amount": 300}, snap), "RW-06: تحت الحد أضاف مرحلة"
    assert _stage_applies(stage, {"amount": 900}, snap), "RW-07: فوق الحد لم يضف مرحلة"
    assert not _stage_applies(stage, {"amount": 500}, snap), "المساواة ليست تجاوًزا"

    # بلا حدّ معتمَد: لا مرحلة إضافية — السلوك القائم بالضبط قبل الجدول
    assert not _stage_applies(stage, {"amount": 9999}, {}), "حدّ غير معتمَد أضاف مرحلة"
    assert not _stage_applies(
        stage, {"amount": 9999},
        {"finance.extra_approval_threshold": {"value": {"amount": 0}}})

    # وقيمة غير رقمية لا تُسقط المحرك
    assert not _stage_applies(stage, {"amount": "غير رقم"}, snap)


def test_v22_policy_reads_from_data_then_company_then_code(client):
    """V2.2 §7 — تسلسل القراءة، وأن الافتراضي يُعلن أنه من الكود لا من سياسة."""
    from datetime import date, timedelta

    from app import models, policy
    from app.database import SessionLocal
    from sqlalchemy import select

    db = SessionLocal()
    made = []
    try:
        cid = db.scalar(select(models.Company.id))

        # لا صف ⇒ الافتراضي، ومصدره معلن
        r = policy.get(db, cid, "finance.extra_approval_threshold")
        assert r["source"] == "code_default" and r["version"] == 0

        # صف عام ⇒ يتقدّم على الافتراضي
        g = models.PolicyRule(company_id=None, key="finance.extra_approval_threshold",
                              value_json={"amount": 250.0}, version=1)
        db.add(g); db.commit(); made.append(g.id)
        r = policy.get(db, cid, "finance.extra_approval_threshold")
        assert r["source"] == "global" and r["value"]["amount"] == 250.0

        # صف الشركة ⇒ يتقدّم على العام
        c = models.PolicyRule(company_id=cid, key="finance.extra_approval_threshold",
                              value_json={"amount": 750.0}, version=1)
        db.add(c); db.commit(); made.append(c.id)
        r = policy.get(db, cid, "finance.extra_approval_threshold")
        assert r["source"] == "company" and r["value"]["amount"] == 750.0

        # قاعدة لم يبدأ سريانها لا تُطبَّق
        future = models.PolicyRule(company_id=cid, key="loan.max_amount",
                                   value_json={"amount": 1.0}, version=2,
                                   effective_from=date.today() + timedelta(days=30))
        db.add(future); db.commit(); made.append(future.id)
        assert policy.get(db, cid, "loan.max_amount")["source"] == "code_default"

        # مفتاح مجهول يُرفَض بدل أن يُخترَع بصمت
        import pytest
        with pytest.raises(KeyError):
            policy.get(db, cid, "key.does.not.exist")
    finally:
        for rid in made:
            row = db.get(models.PolicyRule, rid)
            if row:
                db.delete(row)
        db.commit()
        db.close()
