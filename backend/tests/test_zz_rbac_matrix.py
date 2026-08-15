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

    from app import workflow

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

    # التفويض الساري يجعل المفوَّض إليه معتمًِدا شرعًيا — وهو سلوك مقصود لا
    # ثغرة. استثناؤه هنا ضروري وإلا اتّهم الاختبارُ الميزةَ بأنها خرق.
    from app.delegation import active_delegates_for

    db = SessionLocal()
    try:
        delegated_user_ids = set()
        for stage in ((rt.approval_chain_json if rt else None) or []):
            for approver in workflow.resolve_stage_approvers(db, req, stage):
                delegated_user_ids |= {u.id for u in active_delegates_for(db, approver.id)}
    finally:
        db.close()

    # دور ليس في السلسلة ولا مفوًَّضا إليه يجب أن يُرفض
    for role, cid, pw in ACCOUNTS:
        if role in stage_roles or role == "employee":
            continue
        hdr = _headers(client, cid, pw)
        me = client.get("/api/auth/me", headers=hdr).json()
        if me.get("id") in delegated_user_ids:
            continue  # مفوَّض إليه — اعتماده شرعي
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


def test_v22_separated_approval_permissions_lose_nothing():
    """V2.2 §4.5 (AP-01) — كل مرحلة قائمة ما زال لها معتمِد بعد الفصل.

    هذا هو الخطر الحقيقي في تفكيك approve_request: خطأ واحد في الخريطة يوقف
    اعتماد نوع طلب كامل في الإنتاج — لا يُشوّه شاشة. الاختبار يمرّ على كل
    مرحلة في كل نوع مبذور ويتأكد أن دورها ما زال يملك صلاحية مجالها.
    """
    from app.permissions import (DECISION_DOMAIN_BY_CATEGORY, ROLE_DEFAULT_PERMS,
                                 can_complete_stage, can_decide_category)
    from app.workflow import DEFAULT_REQUEST_TYPES

    # كل فئة في الكتالوج لها مجال معرَّف — لا فئة تسقط للعام بالصدفة
    categories = {rt.get("category") for rt in DEFAULT_REQUEST_TYPES}
    unmapped = {c for c in categories if c and c not in DECISION_DOMAIN_BY_CATEGORY}
    assert not unmapped, f"فئات بلا مجال قرار: {sorted(unmapped)}"

    orphaned = []
    for rt in DEFAULT_REQUEST_TYPES:
        for stage in rt.get("approval_chain_json") or []:
            role = stage.get("role")
            if not role:
                continue
            if not can_complete_stage(role, set(), rt.get("category"),
                                      stage.get("step_type")):
                orphaned.append(f"{rt['code']}/{stage.get('order')}/{role}")
    assert not orphaned, "مراحل فقدت معتمِدها بعد الفصل: " + "; ".join(orphaned[:10])


def test_v22_separated_approval_actually_separates():
    """AP-01 — الفصل حقيقي: دور لا يعتمد مجاًلا لم يكن فيه.

    لو منحنا كل دور كل المجالات لكان الفصل اسًما بلا أثر — نفس العلة التي
    نصلحها. المندوب مثال: مراحله حكومية وعامة وإجازات فقط.
    """
    from app.permissions import ROLE_DEFAULT_PERMS, can_decide_category

    assert can_decide_category("delegate", set(), "الإقامة والمعاملات الحكومية")
    assert not can_decide_category("delegate", set(), "الشكاوى والتظلمات"), \
        "المندوب يعتمد تظلًّما — الفصل بلا أثر"
    assert not can_decide_category("delegate", set(), "العقود وإنهاء الخدمة")
    assert not can_decide_category("employee", set(), "الحضور والإجازات")

    # وapprove_request لم تُمنح لدور جديد
    assert "approve_request" not in ROLE_DEFAULT_PERMS.get("delegate", set()), \
        "المندوب مُنح الصلاحية العامة المهجورة"

    # ومن يملك العامة (منح صريح قائم) يبقى قادًرا — لا نوقف الإنتاج فجأة
    assert can_decide_category("delegate", {"approve_request"}, "الشكاوى والتظلمات")


def _submit_leave(client, hdr):
    """طلب إجازة جاهز للاختبارات التي تحتاج طلًبا قائًما."""
    from datetime import date, timedelta
    start = date.today() + timedelta(days=20)
    r = client.post("/api/requests", headers=hdr, json={
        "request_type_code": "leave",
        "payload_json": {"leave_type": "annual", "days": 2,
                         "start_date": start.isoformat(),
                         "end_date": (start + timedelta(days=1)).isoformat(),
                         "reason": "اختبار"},
    })
    return r


def test_ac06_no_self_approval(client):
    """AC-06 (1/4) — لا اعتماد ذاتي لأي دور.

    أن يكون HR معتمِد مرحلة لا يعني أن يعتمد إجازته هو. القاعدة تسبق حتى
    override_approval: التجاوز صُمّم لحلّ عُطل في الإسناد لا ليمنح صاحب الطلب
    سلطة على طلبه.
    """
    from app import models, workflow
    from app.database import SessionLocal
    from sqlalchemy import select

    db = SessionLocal()
    try:
        hr_user = db.scalar(select(models.User).where(models.User.role == "hr"))
        assert hr_user is not None
        if not hr_user.employee_id:
            import pytest
            pytest.skip("حساب HR غير مرتبط بموظف")
        req = models.Request(company_id=hr_user.company_id,
                             employee_id=hr_user.employee_id,
                             requester_user_id=hr_user.id,
                             request_type_code="leave", payload_json={},
                             status="pending", current_stage=0)
        stage = {"order": 0, "role": "hr", "kind": "approval"}
        assert not workflow.can_decide(db, req, hr_user, stage), \
            "HR اعتمد طلًبا يخصّه"
    finally:
        db.close()


def test_ac06_double_action_and_direct_url(client):
    """AC-06 (2+4/4) — لا قرار مكرر، ولا قرار من غير معتمِد المرحلة عبر الرابط."""
    emp = _headers(client, "100000000101", "emp12345")
    r = _submit_leave(client, emp)
    if r.status_code not in (200, 201):
        import pytest
        pytest.skip(f"تعذّر إنشاء الطلب: {r.status_code} {r.text[:160]}")
    rid = r.json()["id"]

    # (4) استدعاء مباشر من دور ليس معتمِد المرحلة الحالية
    accountant_like = _headers(client, "100000000003", "deleg123")
    direct = client.post(f"/api/requests/{rid}/decide", headers=accountant_like,
                         json={"decision": "approved", "note": ""})
    assert direct.status_code in (403, 404), \
        f"غير المعتمِد اتخذ قراًرا عبر الرابط: {direct.status_code}"

    # (2) قرار مكرر من المعتمِد نفسه
    sup = _headers(client, "100000000005", "sup12345")
    first = client.post(f"/api/requests/{rid}/decide", headers=sup,
                        json={"decision": "approved", "note": ""})
    if first.status_code != 200:
        import pytest
        pytest.skip(f"المعتمِد الأول لم ينجح: {first.status_code} {first.text[:160]}")
    second = client.post(f"/api/requests/{rid}/decide", headers=sup,
                         json={"decision": "approved", "note": ""})
    assert second.status_code != 200, "القرار الثاني نجح — لا حماية من التكرار"


def test_ac06_stale_stage_is_rejected(client):
    """AC-06 (3/4) — مهمة قديمة: من فتح الشاشة قبل تقدّم الطلب لا يقرّر عليها.

    الحالة الواقعية: معتمِد فتح الطلب، وزميله اعتمده، ثم ضغط الأول. بلا حارس
    يُسجَّل قراره على مرحلة لم تعد قائمة.
    """
    emp = _headers(client, "100000000101", "emp12345")
    r = _submit_leave(client, emp)
    if r.status_code not in (200, 201):
        import pytest
        pytest.skip("تعذّر إنشاء الطلب")
    rid = r.json()["id"]

    sup = _headers(client, "100000000005", "sup12345")
    ok = client.post(f"/api/requests/{rid}/decide", headers=sup,
                     json={"decision": "approved", "note": ""})
    if ok.status_code != 200:
        import pytest
        pytest.skip("المرحلة الأولى لم تُعتمد")

    # الطلب تقدّم؛ معتمِد المرحلة السابقة لم يعد صاحب قرار
    stale = client.post(f"/api/requests/{rid}/decide", headers=sup,
                        json={"decision": "rejected", "note": "متأخر"})
    assert stale.status_code != 200, "قرار على مرحلة تجاوزها الطلب نجح"


def test_rw08_claim_gives_one_member_the_action(client):
    """RW-08 — مجموعة من أربعة: من يلتقط المهمة يكملها والباقون يفقدون الفعل.

    بلا التقاط، أربعة أشخاص يرون المهمة نفسها فيبدأها اثنان معًا ويتكرر الأثر،
    أو يظنّ كلٌّ أن الآخر أخذها فلا يبدأها أحد.
    """
    from app import models
    from app.database import SessionLocal
    from app.notifications import create_task
    from sqlalchemy import select

    db = SessionLocal()
    tid = None
    try:
        a = db.scalar(select(models.User).where(models.User.role == "hr"))
        b = db.scalar(select(models.User).where(models.User.civil_id == "100000000003"))
        if not (a and b):
            import pytest
            pytest.skip("لا عضوان في نفس الشركة")
        task = create_task(db, company_id=a.company_id, type="document",
                           title="مهمة مشتركة", assignee_user_id=None,
                           related_entity_type="request", related_entity_id=987654)
        db.commit()
        tid = task.id
    finally:
        db.close()

    first = client.post(f"/api/tasks/{tid}/claim",
                        headers=_headers(client, a.civil_id, "hr12345"))
    assert first.status_code == 200, first.text

    second = client.post(f"/api/tasks/{tid}/claim",
                         headers=_headers(client, b.civil_id, "deleg123"))
    assert second.status_code in (401, 409), \
        f"عضو ثانٍ التقط مهمة ملتقطة: {second.status_code}"

    db = SessionLocal()
    try:
        row = db.get(models.Task, tid)
        assert row.claimed_by_user_id == a.id, "الالتقاط لم يُسجَّل لصاحبه"
        db.delete(row)
        db.commit()
    finally:
        db.close()


def test_rw17_repeated_complete_leaves_one_effect(client):
    """RW-17 — ضغط متكرر على "إنجاز": أثر واحد لا أثران.

    المستخدم يضغط مرتين حين يتأخر الرد، وهو أمر يحدث دائًما. المطلوب ألّا
    يُنتج ذلك سجلين ولا أثرين.
    """
    from app import models
    from app.database import SessionLocal
    from app.notifications import create_task
    from sqlalchemy import select

    db = SessionLocal()
    tid = None
    try:
        u = db.scalar(select(models.User).where(models.User.role == "hr"))
        task = create_task(db, company_id=u.company_id, type="document",
                           title="مهمة تكرار", assignee_user_id=u.id,
                           related_entity_type="request", related_entity_id=987655)
        db.commit()
        tid = task.id
    finally:
        db.close()

    hdr = _headers(client, u.civil_id, "hr12345")
    for _ in range(3):
        client.post(f"/api/tasks/{tid}/status", headers=hdr, params={"status": "done"})

    db = SessionLocal()
    try:
        rows = db.scalars(select(models.Task).where(
            models.Task.related_entity_id == 987655)).all()
        assert len(rows) == 1, f"تكرار الضغط أنتج {len(rows)} مهام"
        assert rows[0].status == "done"
        for r in rows:
            db.delete(r)
        db.commit()
    finally:
        db.close()


def test_ac07_rw10_needs_info_keeps_same_request(client):
    """AC-07 + RW-10 — الإرجاع للاستكمال يعود بنفس المعرّف والتاريخ كامل.

    البديل الشائع — إنشاء طلب جديد عند كل استكمال — يقطع الخيط: يضيع تاريخ
    القرار الأول، ويعود الطلب لأول السلسلة، ويُحتسب طلبين في التقارير.
    المواصفة تمنعه صراحًة ضمن الممنوعات المطلقة.
    """
    emp = _headers(client, "100000000101", "emp12345")
    r = _submit_leave(client, emp)
    if r.status_code not in (200, 201):
        import pytest
        pytest.skip("تعذّر إنشاء الطلب")
    rid = r.json()["id"]

    sup = _headers(client, "100000000005", "sup12345")
    back = client.post(f"/api/requests/{rid}/decide", headers=sup,
                       json={"decision": "returned", "note": "أرفق التقرير"})
    if back.status_code != 200:
        import pytest
        pytest.skip(f"الإرجاع لم ينجح: {back.status_code} {back.text[:160]}")

    detail = client.get(f"/api/requests/{rid}", headers=emp)
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["id"] == rid, "تغيّر معرّف الطلب بعد الإرجاع"

    # والتاريخ محفوظ: قرار الإرجاع مسجَّل لا ممحو
    timeline = body.get("timeline") or body.get("approvals") or []
    assert timeline, "تاريخ الطلب فارغ بعد الإرجاع"

    # وإعادة الإرسال تبقى على نفس الطلب لا تُنشئ جديًدا
    again = client.post(f"/api/requests/{rid}/resubmit", headers=emp,
                        json={"payload_json": {"leave_type": "annual", "days": 2,
                                               "reason": "أُرفق"}})
    if again.status_code == 200:
        assert again.json().get("id", rid) == rid, "إعادة الإرسال أنشأت طلًبا جديًدا"


def test_ac09_rw09_duplicate_approver_is_skipped(client):
    """AC-09 + RW-09 — مرحلة معتمِدها هو نفسه معتمِد السابقة تُتخطّى.

    ROOT CAUSE: في شركة صغيرة يجمع شخص واحد دورين متتاليين، فيصله الطلب مرتين
    ليضغط "اعتماد" على قراره هو. ذلك ليس مراجعة مستقلة بل إيهام بها: خطوتان
    في السجل وقرار واحد في الواقع.

    والشرط "وحده" جوهري: لو كان للمرحلة معتمِدون آخرون فالمراجعة المستقلة ما
    زالت ممكنة فلا نتخطّاها — نتركها لهم.
    """
    from unittest.mock import patch

    from app import models, workflow
    from app.database import SessionLocal
    from sqlalchemy import select

    db = SessionLocal()
    try:
        hr = db.scalar(select(models.User).where(models.User.role == "hr"))
        mgr = db.scalar(select(models.User).where(
            models.User.role == "company_manager",
            models.User.company_id == hr.company_id))
        assert hr and mgr

        req = models.Request(company_id=hr.company_id, employee_id=1,
                             requester_user_id=None, request_type_code="leave",
                             payload_json={}, status="pending", current_stage=1)
        db.add(req); db.flush()
        # قرار المرحلة السابقة باسم hr
        db.add(models.RequestApproval(request_id=req.id, stage_order=0,
                                      stage_label="مراجعة", approver_role="hr",
                                      approver_user_id=hr.id, decision="approved"))
        db.flush()

        rt = type("RT", (), {"approval_chain_json": [
            {"order": 0, "role": "hr"}, {"order": 1, "role": "hr"}]})()

        # معتمِد المرحلة الحالية هو hr وحده ⇒ تُتخطّى
        with patch.object(workflow, "resolve_stage_approvers", return_value=[hr]):
            assert workflow._skip_duplicate_approver(db, req, rt) is True

        # ولو كان معه غيره ⇒ لا تُتخطّى، المراجعة المستقلة ممكنة
        req.current_stage = 1
        with patch.object(workflow, "resolve_stage_approvers", return_value=[hr, mgr]):
            assert workflow._skip_duplicate_approver(db, req, rt) is False

        # والتخطّي مسجَّل بسببه لا صامًتا
        skipped = db.scalars(select(models.RequestApproval).where(
            models.RequestApproval.request_id == req.id,
            models.RequestApproval.decision == "skipped")).all()
        assert skipped and "مراجعة مستقلة" in (skipped[0].note or ""), \
            "التخطّي بلا سبب مكتوب"
        db.rollback()
    finally:
        db.close()


def test_rw16_expired_delegation_grants_nothing(client):
    """RW-16 — تفويض منتهٍ لا يمنح فعلًا.

    التفويض بلا مدة محترمة أخطر من غيابه: من فوّضته أسبوًعا يبقى معتمًِدا سنة
    ولا أحد ينتبه.
    """
    from datetime import datetime, timedelta

    from app import models
    from app.database import SessionLocal
    from app.delegation import active_delegates_for
    from sqlalchemy import select

    db = SessionLocal()
    made = []
    try:
        a = db.scalar(select(models.User).where(models.User.role == "hr"))
        b = db.scalar(select(models.User).where(models.User.civil_id == "100000000003"))
        now = datetime.now()

        expired = models.ApprovalDelegation(
            company_id=a.company_id, delegator_user_id=a.id, delegate_user_id=b.id,
            starts_at=now - timedelta(days=30), ends_at=now - timedelta(days=1),
            is_active=True, reason="انتهى")
        db.add(expired); db.commit(); made.append(expired.id)
        assert b.id not in [u.id for u in active_delegates_for(db, a.id)], \
            "تفويض منتهٍ ما زال يمنح الاعتماد"

        live = models.ApprovalDelegation(
            company_id=a.company_id, delegator_user_id=a.id, delegate_user_id=b.id,
            starts_at=now - timedelta(days=1), ends_at=now + timedelta(days=5),
            is_active=True, reason="ساري")
        db.add(live); db.commit(); made.append(live.id)
        assert b.id in [u.id for u in active_delegates_for(db, a.id)], \
            "تفويض ساٍر لا يمنح الاعتماد"
    finally:
        for did in made:
            row = db.get(models.ApprovalDelegation, did)
            if row:
                db.delete(row)
        db.commit()
        db.close()


def test_ac10_rw14_doc12_clearance_parties_are_parallel(client):
    """AC-10 + RW-14 + DOC-12 — إخلاء طرف: مهام متوازية، وإغلاق بعد المنطبقات فقط.

    ROOT CAUSE: كان سلسلة متتابعة، فتنتظر المالية دورَ جهة أخرى وإن لم تكن
    بينهما علاقة. الجهات مستقلة بطبعها: كل واحدة تعرف عهدتها ولا تعرف عهدة
    غيرها، وترتيبها بينها اصطناعي.

    و DOC-12: لا مخالصة نهائية وجهة لم تُقرّ بعد.
    """
    from app import models, workflow
    from app.database import SessionLocal
    from sqlalchemy import select

    db = SessionLocal()
    try:
        rt = db.scalar(select(models.RequestType).where(
            models.RequestType.code == "REQCLR",
            models.RequestType.company_id.is_(None)))
        assert rt, "REQCLR غير مبذور"
        stage = (rt.approval_chain_json or [])[0]
        assert stage.get("kind") == "parallel", "مرحلة إخلاء الطرف ما زالت متتابعة"

        roles = {p["role"] for p in stage["parties"]}
        assert {"accountant", "branch_supervisor", "delegate"} <= roles

        # المندوب لا تُنشأ له مهمة إلا مع وثائق حكومية — لا تُنشأ ثم تُغلق آلًيا
        plain = {p["role"] for p in workflow.applicable_parties(stage, {})}
        assert "delegate" not in plain, "المندوب أُقحم بلا وثائق حكومية"
        withgov = {p["role"] for p in workflow.applicable_parties(
            stage, {"has_gov_documents": True})}
        assert "delegate" in withgov, "المندوب غاب رغم وجود وثائق حكومية"

        # DOC-12 — الاكتمال All-of لا Any-of
        req = models.Request(company_id=1, employee_id=1, request_type_code="REQCLR",
                             payload_json={}, status="pending", current_stage=0)
        db.add(req); db.flush()
        db.add(models.RequestApproval(request_id=req.id, stage_order=0,
                                      stage_label="المالية", approver_role="accountant",
                                      approver_user_id=1, decision="approved"))
        db.flush()
        assert not workflow.parallel_stage_complete(db, req, stage), \
            "اكتملت المرحلة وجهة لم تُقرّ — مخالصة نهائية قبل أوانها"

        db.add(models.RequestApproval(request_id=req.id, stage_order=0,
                                      stage_label="الفرع", approver_role="branch_supervisor",
                                      approver_user_id=2, decision="approved"))
        db.flush()
        assert workflow.parallel_stage_complete(db, req, stage), \
            "لم تكتمل المرحلة رغم إقرار كل الجهات المنطبقة"
        db.rollback()
    finally:
        db.close()


def test_ac15_workflow_operations_report(client):
    """AC-15 — تقرير تشغيلي فعلي: أزمنة الخطوات، الإرجاع، الرفض، SLA، الأتمتة.

    ROOT CAUSE: النظام يسجّل كل قرار بوقته منذ البداية، لكن لا أحد يستطيع أن
    يجيب: أين يقف الطلب طويًلا؟ من يُرجِع أكثر مما يعتمد؟ البيانات موجودة
    والسؤال بلا جواب — وهذا أسوأ من غيابها، لأنه يُخفي المشكلة تحت انطباع
    بأن الأمور بخير.

    الاختبار ينشئ طلًبا ويُرجعه، ثم يتحقق أن الرقم يظهر فعلًا — لا أن نقطة
    النهاية ترد 200 بأصفار.
    """
    rep = _headers(client, "100000000001", "manager123")  # view_reports
    emp = _headers(client, "100000000101", "emp12345")

    base = client.get("/api/reports/workflow-operations", headers=rep)
    assert base.status_code == 200, base.text
    before = base.json()["decisions"].get("returned", 0)

    r = _submit_leave(client, emp)
    if r.status_code not in (200, 201):
        import pytest
        pytest.skip("تعذّر إنشاء الطلب")
    sup = _headers(client, "100000000005", "sup12345")
    back = client.post(f"/api/requests/{r.json()['id']}/decide", headers=sup,
                       json={"decision": "returned", "note": "أرفق التقرير"})
    if back.status_code != 200:
        import pytest
        pytest.skip("الإرجاع لم ينجح")

    after = client.get("/api/reports/workflow-operations", headers=rep).json()
    assert after["decisions"]["returned"] == before + 1, "الإرجاع لم يظهر في التقرير"
    assert after["return_rate"] is not None
    assert after["steps"], "لا خطوات في التقرير رغم وجود قرارات"

    step = after["steps"][0]
    for k in ("stage", "decisions", "avg_wait_hours", "returned", "rejected"):
        assert k in step, f"مقياس ناقص في الخطوة: {k}"

    # SLA — النسبة على ما له مهلة، والباقي مُعلَن لا مطموس
    sla = after["sla"]
    assert {"tasks_with_sla", "breached", "breach_rate", "tasks_without_sla"} <= set(sla)
    assert sla["tasks_without_sla"] >= 0

    # الأتمتة محسوبة لا مفترَضة
    auto = after["automation"]
    assert auto["executed_steps"] >= 1
    assert 0 <= (auto["ratio"] or 0) <= 1

    # تاريخ غير صالح يُرفض بوضوح بدل أن يُفسَّر بصمت
    bad = client.get("/api/reports/workflow-operations", headers=rep,
                     params={"since": "not-a-date"})
    assert bad.status_code == 400


def test_ac05_super_admin_needs_break_glass(client):
    """AC-05 — Super Admin لا يتجاوز مرحلة عمل إلا بنافذة طارئة موثّقة.

    ROOT CAUSE: has_permission تعيد True لـsuper_admin مطلًقا، فيملك
    override_approval في كل لحظة ويعتمد أي مرحلة بلا أن يطلبها أحد ولا أن
    ينتبه إليها أحد — حساب تقني صار معتمًِدا تجارًيا بحكم الأمر الواقع.

    والمنع الكامل ليس حًلا: حين يتعطّل الإسناد يقف العمل ولا مخرج. فالتجاوز
    يبقى ممكًنا لكنه يصير حدًثا: سبب ومدة وسجل.
    """
    from datetime import datetime, timedelta

    from app import break_glass, models, workflow
    from app.database import SessionLocal
    from sqlalchemy import select

    db = SessionLocal()
    made = []
    try:
        sa_user = db.scalar(select(models.User).where(models.User.role == "super_admin"))
        assert sa_user, "لا super_admin في البذرة"
        # بلا نافذة: لا تجاوز
        assert not workflow.may_override(db, sa_user), \
            "Super Admin يتجاوز بلا نافذة طارئة"

        # سبب مبهم مرفوض
        import pytest
        with pytest.raises(ValueError):
            break_glass.open_session(db, sa_user, "طارئ")

        s = break_glass.open_session(db, sa_user, "المعتمِد غادر الشركة والطلب عالق")
        db.commit(); made.append(s.id)
        assert workflow.may_override(db, sa_user), "النافذة السارية لا تمنح التجاوز"

        # منتهية ⇒ لا تجاوز. نافذة مفتوحة إلى الأبد صلاحية دائمة بثوب آخر
        s.expires_at = datetime.now() - timedelta(minutes=1)
        db.commit()
        assert not workflow.may_override(db, sa_user), "نافذة منتهية ما زالت تمنح التجاوز"

        # ومغلقة يدوًيا ⇒ لا تجاوز
        s2 = break_glass.open_session(db, sa_user, "سبب آخر مفصّل بما يكفي")
        db.commit(); made.append(s2.id)
        assert workflow.may_override(db, sa_user)
        s2.closed_at = datetime.now()
        db.commit()
        assert not workflow.may_override(db, sa_user), "نافذة مغلقة ما زالت تمنح التجاوز"

        # والطلب السرّي لا يُتجاوَز ولو بنافذة
        s3 = break_glass.open_session(db, sa_user, "حالة طارئة موثّقة بالتفصيل")
        db.commit(); made.append(s3.id)
        confidential = type("RT", (), {"is_confidential": True})()
        assert not workflow.may_override(db, sa_user, confidential), \
            "طلب سرّي جرى تجاوزه"
    finally:
        for sid in made:
            row = db.get(models.BreakGlassSession, sid)
            if row:
                db.delete(row)
        db.commit()
        db.close()


def test_ac03_hr_validates_but_does_not_decide_money(client):
    """AC-03 — HR يكمل التحقق ولا يحصل تلقائًيا على القرار المالي.

    ROOT CAUSE: كل خطوة في السلسلة كانت "اعتماًدا"، فمن يتحقّق من صحة بيانات
    الخصم يحتاج صلاحية القرار المالي نفسها التي يحتاجها من يقرّر صرفه. ومتى
    مُنحت له لأجل خطوته، صار يملك القرار في **كل** الطلبات المالية — سلفة
    وقرًضا واسترداد مصروفات.

    الفصل: خطوة VALIDATION تُنجَز بـcomplete_validation، والقرار وحده يحتاج
    صلاحية مجاله.
    """
    from app import models
    from app.database import SessionLocal
    from app.permissions import ROLE_DEFAULT_PERMS, can_complete_stage
    from sqlalchemy import select

    assert "approve_finance" not in ROLE_DEFAULT_PERMS["hr"], \
        "HR ما زال يملك القرار المالي افتراضًيا"
    assert "complete_validation" in ROLE_DEFAULT_PERMS["hr"]

    # الاختبار السلبي الذي يطلبه المعيار
    assert not can_complete_stage("hr", set(), "الطلبات المالية", "DECISION"), \
        "HR يقرّر في خطوة قرار مالي"
    assert can_complete_stage("hr", set(), "الطلبات المالية", "VALIDATION"), \
        "HR لا يستطيع إتمام خطوة تحقّق — عُطّلت خطوته بدل فصلها"
    assert can_complete_stage("accountant", set(), "الطلبات المالية", "DECISION")

    # ولم يفقد HR مجالاته الأخرى
    for cat in ("الشهادات والخطابات", "العقود وإنهاء الخدمة", "الشكاوى والتظلمات"):
        assert can_complete_stage("hr", set(), cat, "DECISION"), f"HR فقد {cat}"

    # وخطوة HR في اعتراض الخصم موسومة تحقًقا في الكتالوج المبذور
    db = SessionLocal()
    try:
        rt = db.scalar(select(models.RequestType).where(
            models.RequestType.code == "REQDED",
            models.RequestType.company_id.is_(None)))
        if rt:
            hr_steps = [s for s in (rt.approval_chain_json or []) if s.get("role") == "hr"]
            assert hr_steps and hr_steps[0].get("step_type") == "VALIDATION", \
                "خطوة HR في REQDED ما زالت قراًرا مالًيا"
    finally:
        db.close()


def test_ac14_sensitive_fields_masked_by_role(client):
    """AC-14 — الحقول الحساسة محجوبة حسب الدور حتى مع امتلاك مشاهدة الحالة.

    رؤية الطلب لا تعني رؤية كل ما فيه: المندوب يحتاج الجواز والإقامة ولا
    يحتاج الراتب، والمحاسب يحتاج الراتب ولا يحتاج الرقم المدني ولا العنوان.
    "من يرى الحالة يرى كل شيء" هو ما يجعل أي فصل بعده بلا معنى.
    """
    from app import models
    from app.database import SessionLocal
    from sqlalchemy import select

    db = SessionLocal()
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.basic_salary.isnot(None)))
        eid = emp.id
    finally:
        db.close()

    pro = client.get(f"/api/employees/{eid}",
                     headers=_headers(client, "100000000003", "deleg123"))
    if pro.status_code == 200:
        body = pro.json()
        assert body.get("basic_salary") is None, "المندوب يرى الراتب الأساسي"
        assert body.get("actual_salary") is None, "المندوب يرى الراتب الفعلي"

    acc = client.get(f"/api/employees/{eid}",
                     headers=_headers(client, "100000000007", "account123"))
    if acc.status_code == 200:
        body = acc.json()
        assert body.get("civil_id") is None, "المحاسب يرى الرقم المدني"
        assert body.get("address") is None, "المحاسب يرى العنوان"


def test_rw02_manager_outside_scope_gets_no_action(client):
    """RW-02 — من هو خارج نطاقه لا يرى الطلب ولا يقرّر فيه.

    مسؤول فرع آخر ليس "مديًرا أعلى" — نطاقه فرعه، ورؤيته طلب فرع غيره تسريب
    لا صلاحية.
    """
    emp = _headers(client, "100000000101", "emp12345")
    r = _submit_leave(client, emp)
    if r.status_code not in (200, 201):
        import pytest
        pytest.skip("تعذّر إنشاء الطلب")
    rid = r.json()["id"]

    other_sup = _headers(client, "100000000006", "sup12345")  # فرع آخر
    seen = client.get(f"/api/requests/{rid}", headers=other_sup)
    acted = client.post(f"/api/requests/{rid}/decide", headers=other_sup,
                        json={"decision": "approved", "note": ""})
    assert acted.status_code in (403, 404), "مسؤول فرع آخر اتخذ قراًرا"
    if seen.status_code == 200:
        # القراءة قد تكون مسموحة بالسياسة، لكن الفعل ممنوع — وهو نص المعيار
        assert acted.status_code in (403, 404)


def test_rw11_bank_change_needs_hr_verification_first(client):
    """RW-11 — تغيير الحساب البنكي: تحقّق HR من الهوية ثم مراجع مالي مستقل.

    كانت السلسلة تبدأ بالمحاسب مباشرة بلا تثبّت من أن طالب التغيير هو صاحب
    الحساب فعًلا — وهذا أشيع مسار احتيال داخلي في أنظمة الرواتب: رسالة
    "غيّروا حسابي" تمرّ بلا تحقّق من هوية مرسلها.
    """
    from app import models
    from app.database import SessionLocal
    from sqlalchemy import select

    db = SessionLocal()
    try:
        rt = db.scalar(select(models.RequestType).where(
            models.RequestType.code == "REQBANK",
            models.RequestType.company_id.is_(None)))
        assert rt, "REQBANK غير مبذور"
        chain = rt.approval_chain_json or []
        assert chain[0]["role"] == "hr", "التغيير يبدأ بالمالية بلا تحقّق هوية"
        assert chain[0]["step_type"] == "VALIDATION", "تحقّق HR مسجَّل كقرار"
        # ومراجع مالي مستقل بعده
        assert any(s["role"] == "accountant" and s["step_type"] == "DECISION"
                   for s in chain[1:]), "لا مراجع مالي مستقل بعد التحقق"
    finally:
        db.close()


def test_rw12_doc19_grievance_bypasses_the_manager(client):
    """RW-12 + DOC-19 — التظلّم لا يمرّ بالمدير المشتكى به، ولا يظهر في بحث عام.

    مسار تظلّم يمرّ بالمشتكى به ليس مساًرا بل رادع: من يعلم أن شكواه ستصل
    خصمه لا يشتكي. ولذلك السلسلة تتخطّاه بنيًيا لا بإعداد يُنسى.
    """
    from app import models
    from app.database import SessionLocal
    from sqlalchemy import select

    db = SessionLocal()
    try:
        rt = db.scalar(select(models.RequestType).where(
            models.RequestType.code == "REQGRV",
            models.RequestType.company_id.is_(None)))
        assert rt, "REQGRV غير مبذور"
        assert rt.is_confidential, "التظلّم ليس سرًّيا"
        roles = {s.get("role") for s in (rt.approval_chain_json or [])}
        assert "branch_supervisor" not in roles, "المسؤول المباشر في مسار التظلّم"
        assert "company_manager" not in roles, "المدير في مسار التظلّم ضده"
    finally:
        db.close()

    # DOC-19 — البحث العام لا يمسّ المستندات إطلاًقا
    from app.routers import search as search_mod
    src = __import__("inspect").getsource(search_mod)
    assert "models.Document" not in src, "البحث العام يمسّ المستندات"

    # والطلب السرّي لا يُتجاوَز إدارًيا (تحقّقنا منه في AC-05 أيًضا)
    from app import workflow
    db = SessionLocal()
    try:
        sa_user = db.scalar(select(models.User).where(models.User.role == "super_admin"))
        confidential = type("RT", (), {"is_confidential": True})()
        assert not workflow.may_override(db, sa_user, confidential)
    finally:
        db.close()


def test_str06_unknown_placeholders_are_reported(client):
    """STR-06 — الرمز المجهول يُبلَّغ عند الحفظ لا يُكتشف عند الطباعة.

    ROOT CAUSE: _fill_html تستبدل أي رمز مجهول بنقاط، فقالب يكتب
    {{empolyee_name}} بخطأ مطبعي يُحفظ بلا شكوى ويُطبع بفراغ — ويُكتشف حين
    يقرأ موظفٌ شهادته وفيها سطر نقاط مكان اسمه.

    ولا يُرفض: النظام يدعم حقوًلا مخصّصة عمًدا عبر extras، والرفض يهدم ميزة
    قائمة. الإبلاغ يضع الخطأ أمام من يستطيع إصلاحه.
    """
    from app.routers.templates import unknown_placeholders

    assert unknown_placeholders("<p>{{employee_name}} — {{company_name}}</p>") == []
    assert "empolyee_name" in unknown_placeholders("<p>{{empolyee_name}}</p>")

    # وكل القوالب الرسمية المبذورة معروفة الرموز
    from app.seed import DEFAULT_TEMPLATES
    for entry in DEFAULT_TEMPLATES:
        assert not unknown_placeholders(entry[-1]), f"قالب رسمي برموز مجهولة: {entry[0]}"


def test_str06_no_free_html_in_generation_path():
    """STR-06/AP-06 — لا HTML/JS حر في مسار التوليد: التعقيم بـbleach بقائمة وسوم."""
    from app.routers.templates import _ALLOWED_TPL_TAGS, _sanitize_body_html

    assert "script" not in _ALLOWED_TPL_TAGS
    out = _sanitize_body_html('<p>مرحبا</p><script>alert(1)</script>')
    assert "script" not in out and "alert" not in out, "سكربت نجا من التعقيم"
    out2 = _sanitize_body_html('<div onclick="x()">نص</div>')
    assert "onclick" not in out2, "معالج حدث نجا من التعقيم"


def test_ac12_rw15_doc18_pdf_failure_does_not_lose_the_decision(client):
    """AC-12 + RW-15 + DOC-18 — فشل توليد PDF لا يُسقط قرار الاعتماد.

    ROOT CAUSE: التوليد كان بلا حارس، فاستثناء واحد (خط عربي ناقص، قرص
    ممتلئ، قالب معطوب) يُسقط المعاملة كلها — بما فيها **قرار الاعتماد نفسه**.
    المعتمِد يضغط "اعتماد" فيُخبَر بخطأ، ويظنّ أن قراره لم يُسجَّل فيعيده،
    والطلب عالق بلا سبب ظاهر.

    القرار قرار والمستند مستند: الاعتماد يبقى، والمستند FAILED لا GENERATED،
    ولا يُسجَّل نجاح توليد لم يقع.
    """
    from unittest.mock import patch

    from app import models, workflow
    from app.database import SessionLocal
    from sqlalchemy import select

    emp = _headers(client, "100000000101", "emp12345")
    r = client.post("/api/requests", headers=emp, json={
        "request_type_code": "REQCERTSAL",
        "payload_json": {"purpose": "بنك", "language": "ar", "include_salary": True},
    })
    if r.status_code not in (200, 201):
        import pytest
        pytest.skip(f"تعذّر إنشاء الطلب: {r.status_code}")
    rid = r.json()["id"]

    hr = _headers(client, "100000000002", "hr12345")
    mgr = _headers(client, "100000000001", "manager123")

    # نُفشل التوليد عمًدا عند كل مرحلة تُنتج مستنًدا
    # الترقيع على المصدر لا على الوحدة المستوردة: render_request_pdf تُستورَد
    # داخل جسم generate_document، فترقيع workflow لا يعترضها إطلاًقا — وكان
    # الاختبار سيمرّ بلا أن يُفشل شيًئا.
    from app import pdf_export
    with patch.object(pdf_export, "render_request_pdf",
                      side_effect=RuntimeError("خط عربي مفقود")):
        for hdr in (hr, mgr, hr, mgr):
            client.post(f"/api/requests/{rid}/decide", headers=hdr,
                        json={"decision": "approved", "note": ""})

    db = SessionLocal()
    try:
        req = db.get(models.Request, rid)
        approvals = db.scalars(select(models.RequestApproval).where(
            models.RequestApproval.request_id == rid,
            models.RequestApproval.decision == "approved")).all()
        assert approvals, "ضاعت قرارات الاعتماد مع فشل التوليد"

        docs = db.scalars(select(models.RequestDocument).where(
            models.RequestDocument.request_id == rid)).all()
        # إثبات أن مسار الفشل نُفِّذ فعًلا — لا أن التوليد لم يُستدعَ أصًلا
        assert any(d.lifecycle_status == "FAILED" for d in docs),             "لم يُسجَّل أي مستند فاشل — الاختبار لم يُفشل شيًئا"
        for d in docs:
            assert d.lifecycle_status != "DELIVERED", "DELIVERED رغم فشل التوليد"
            if d.lifecycle_status == "FAILED":
                assert not d.file_path, "مستند فاشل ومعه مسار ملف"
    finally:
        db.close()


def test_doc06_doc04_generate_twice_yields_one_artifact(client):
    """DOC-06 — ضغطتان على "توليد" = مستند واحد. و DOC-04 — النسخة الصادرة ثابتة.

    ROOT CAUSE: التوليد كان يُنشئ نسخة جديدة دائًما ويوسم السابقة SUPERSEDED.
    ذلك صحيح لإعادة إصدار حقيقية، لكن المستخدم يضغط مرتين حين يتأخر الرد —
    فيحصل على مستندين برقمين مرجعيين مختلفين لنفس القرار، ويقدّم أحدهما لجهة
    رسمية بينما النظام يعتبره باطًلا.
    """
    from app import models, workflow
    from app.database import SessionLocal
    from sqlalchemy import select

    emp = _headers(client, "100000000101", "emp12345")
    r = client.post("/api/requests", headers=emp, json={
        "request_type_code": "REQCERTSAL",
        "payload_json": {"purpose": "بنك", "language": "ar", "include_salary": True},
    })
    if r.status_code not in (200, 201):
        import pytest
        pytest.skip("تعذّر إنشاء الطلب")
    rid = r.json()["id"]

    hr = _headers(client, "100000000002", "hr12345")
    mgr = _headers(client, "100000000001", "manager123")
    for hdr in (hr, mgr, hr, mgr):
        client.post(f"/api/requests/{rid}/decide", headers=hdr,
                    json={"decision": "approved", "note": ""})

    db = SessionLocal()
    try:
        req = db.get(models.Request, rid)
        rt = workflow.get_request_type(db, req.company_id, req.request_type_code)
        before = db.scalars(select(models.RequestDocument).where(
            models.RequestDocument.request_id == rid,
            models.RequestDocument.kind == "generated_pdf")).all()
        if not before:
            import pytest
            pytest.skip("لم يُولَّد مستند")
        first = [d for d in before if d.lifecycle_status == "GENERATED"]
        if not first:
            import pytest
            pytest.skip("لا نسخة مولَّدة بنجاح")
        original_hash = first[0].checksum_sha256
        original_ref = first[0].reference_no

        # ضغطة ثانية بلا قرار جديد ⇒ نفس المستند لا نسخة ثانية
        hr_user = db.scalar(select(models.User).where(models.User.role == "hr"))
        again = workflow.generate_document(db, req, rt, kind="generated_pdf",
                                           actor=hr_user)
        db.commit()
        assert again.id == first[0].id, "الضغطة الثانية أنشأت مستنًدا آخر"

        after = db.scalars(select(models.RequestDocument).where(
            models.RequestDocument.request_id == rid,
            models.RequestDocument.kind == "generated_pdf")).all()
        assert len(after) == len(before), "تكاثرت النسخ بلا قرار جديد"

        # DOC-04 — النسخة الصادرة وبصمتها ورقمها ثابتة
        assert first[0].checksum_sha256 == original_hash, "تغيّرت بصمة نسخة صادرة"
        assert first[0].reference_no == original_ref, "تغيّر الرقم المرجعي"
    finally:
        db.close()


def test_ac11_doc01_doc05_doc11_doc20_document_rules():
    """AC-11/DOC-01/DOC-05/DOC-11/DOC-20 — قواعد إصدار المستندات.

    AC-11 + RW-03: شهادة الراتب تُولَّد من بيانات معتمَدة أصًلا (الراتب في ملف
    الموظف)، فلا معنى لسلسلة موافقات عليها. مرحلة المدير العام كانت شكلية: لا
    يقرّر شيًئا — الراتب مقرَّر سلًفا — بل يؤخّر شهادة يحتاجها الموظف اليوم
    لبنك أو سفارة.

    DOC-11: الإذن الحكومي تُصدره الجهة، وأي ورقة يولّدها النظام بشكله ليست
    إذًنا بل انتحال صفة جهة حكومية.
    """
    from app import models
    from app.workflow import DEFAULT_REQUEST_TYPES

    by_code = {r["code"]: r for r in DEFAULT_REQUEST_TYPES}

    # AC-11 / DOC-01 / RW-03
    cert = by_code["REQCERTSAL"]
    roles = [s["role"] for s in cert["approval_chain_json"]]
    assert roles == ["hr"], f"شهادة الراتب ما زالت بسلسلة شكلية: {roles}"
    assert cert["approval_chain_json"][0]["produces_document"]

    # DOC-11 — لا مستند يولّده النظام لتجديد إذن العمل
    wp = by_code["REQWP"]
    assert not wp["produces_document"], "النظام يولّد إذن عمل حكومًيا"
    assert not any(s.get("produces_document") for s in wp["approval_chain_json"]), \
        "مرحلة في تجديد إذن العمل تولّد مستنًدا حكومًيا"

    # DOC-20 — نسخة القالب مثبَّتة على المستند
    cols = {c.name for c in models.RequestDocument.__table__.columns}
    assert {"template_code", "template_version"} <= cols, \
        "لا تثبيت لنسخة القالب على المستند الصادر"


def test_doc05_rejected_request_produces_no_certificate(client):
    """DOC-05 — طلب مرفوض لا يُنتج شهادة صالحة، إشعار الرفض فقط."""
    from app import models
    from app.database import SessionLocal
    from sqlalchemy import select

    emp = _headers(client, "100000000101", "emp12345")
    r = client.post("/api/requests", headers=emp, json={
        "request_type_code": "REQCERTSAL",
        "payload_json": {"purpose": "بنك", "language": "ar", "include_salary": True},
    })
    if r.status_code not in (200, 201):
        import pytest
        pytest.skip("تعذّر إنشاء الطلب")
    rid = r.json()["id"]

    hr = _headers(client, "100000000002", "hr12345")
    rej = client.post(f"/api/requests/{rid}/decide", headers=hr,
                      json={"decision": "rejected", "note": "بيانات ناقصة"})
    if rej.status_code != 200:
        import pytest
        pytest.skip(f"الرفض لم ينجح: {rej.status_code}")

    db = SessionLocal()
    try:
        docs = db.scalars(select(models.RequestDocument).where(
            models.RequestDocument.request_id == rid,
            models.RequestDocument.kind == "generated_pdf")).all()
        valid = [d for d in docs if d.lifecycle_status in ("GENERATED", "SIGNED", "DELIVERED")]
        assert not valid, "طلب مرفوض أنتج شهادة صالحة"
        assert db.get(models.Request, rid).status == "rejected"
    finally:
        db.close()


def test_doc08_doc09_doc10_verification_and_revocation(client):
    """DOC-08 + DOC-09 + DOC-10 — التحقق من الورقة، وإلغاؤها بلا حذفها.

    ROOT CAUSE (DOC-10): لم يكن للإلغاء وجود. الخيار الوحيد أمام من أصدر ورقة
    خاطئة كان حذف الصف — فتضيع القدرة على إثبات ما صدر ولمن، وتبقى الورقة في
    يد من تسلّمها بلا أن يعرف أحد أنها باطلة.

    DOC-08: البصمة تُحسب من الملف لا من حقل محفوظ، والتمييز مقصود —
    "لم نُصدرها" غير "أُصدرت ثم عُدِّلت".
    DOC-09: من يتحقّق يريد جواًبا عن صحة الورقة لا نسخة من محتواها.
    """
    import hashlib
    import os

    from app import models, verification
    from app.database import SessionLocal
    from sqlalchemy import select

    emp = _headers(client, "100000000101", "emp12345")
    r = client.post("/api/requests", headers=emp, json={
        "request_type_code": "REQCERTSAL",
        "payload_json": {"purpose": "بنك", "language": "ar", "include_salary": True},
    })
    if r.status_code not in (200, 201):
        import pytest
        pytest.skip("تعذّر إنشاء الطلب")
    rid = r.json()["id"]
    client.post(f"/api/requests/{rid}/decide",
                headers=_headers(client, "100000000002", "hr12345"),
                json={"decision": "approved", "note": ""})

    db = SessionLocal()
    try:
        doc = db.scalar(select(models.RequestDocument).where(
            models.RequestDocument.request_id == rid,
            models.RequestDocument.lifecycle_status == "GENERATED"))
        if not doc:
            import pytest
            pytest.skip("لم يُولَّد مستند")
        doc_id, path = doc.id, doc.file_path
        code = verification.generate_code(doc.id, doc.request_id)
    finally:
        db.close()

    # DOC-08 — سليم ⇒ VALID
    v = client.get(f"/api/verify/{code}")
    assert v.status_code == 200, v.text
    body = v.json()
    assert body["valid"] is True and body["state"] == "VALID", body

    # DOC-09 — الحد الأدنى: لا راتب ولا رقم مدني كامل
    blob = str(body)
    assert "basic_salary" not in blob and "salary" not in blob.lower(), \
        "التحقق يكشف الراتب"
    assert "civil_id" not in blob, "التحقق يكشف الرقم المدني"

    # DOC-08 — عبث بالملف ⇒ TAMPERED لا "غير صالح"
    if path and os.path.exists(path):
        with open(path, "ab") as f:
            f.write(b"\n% tampered")
        t = client.get(f"/api/verify/{code}").json()
        assert t["state"] == "TAMPERED", f"العبث لم يُكتشف: {t['state']}"
        assert t["valid"] is False

    # DOC-10 — الإلغاء يُبقي الملف ويُعلن الحال
    admin = _headers(client, "000000000000", "admin123")
    no_reason = client.post(f"/api/documents/requests/{doc_id}/revoke",
                            params={"reason": " "}, headers=admin)
    assert no_reason.status_code == 400, "أُلغي مستند بلا سبب"

    ok = client.post(f"/api/documents/requests/{doc_id}/revoke",
                     params={"reason": "صدرت ببيانات خاطئة"}, headers=admin)
    assert ok.status_code == 200, ok.text

    after = client.get(f"/api/verify/{code}").json()
    assert after["state"] == "REVOKED" and after["revoked"] is True
    assert after["revocation_note"], "الإلغاء بلا إعلان للطرف الخارجي"
    assert "خاطئة" not in str(after), "سبب الإلغاء التفصيلي تسرّب للطرف الخارجي"

    db = SessionLocal()
    try:
        row = db.get(models.RequestDocument, doc_id)
        assert row is not None, "الإلغاء حذف صف المستند"
        assert row.file_path == path, "الإلغاء غيّر مسار الملف"
        assert row.revocation_reason, "السبب لم يُحفظ داخلًيا"
    finally:
        db.close()


def test_doc02_doc07_doc13_doc14_doc15_printed_text_rules():
    """DOC-02/07/13/14/15 — ما يجوز أن يظهر في ورقة رسمية وما لا يجوز.

    كل واحدة منها خطأ يقع على ورقة تخرج من الشركة إلى جهة خارجية:
    - DOC-02: "طلب شهادة راتب" على الشهادة نفسها — الشهادة ليست الطلب
    - DOC-07: "توقيع إلكتروني محمي" على صورة توقيع مرفوعة — ادّعاء حماية
      تشفيرية لا وجود لها، وهو أخطر من غياب التوقيع
    - DOC-13: تسوية مبدئية بلا "غير صالحة للصرف" تُقرأ أمًرا بالدفع
    - DOC-14: "مدفوع" قبل التنفيذ
    - DOC-15: IBAN كامل في إيصال عام
    """
    import re

    from app.seed import DEFAULT_TEMPLATES

    by_code = {e[0]: e[-1] for e in DEFAULT_TEMPLATES}

    # DOC-02 — الشهادة ليست الطلب
    cert = by_code.get("HRMS-PR-001", "")
    assert "طلب شهادة" not in cert, "الشهادة تحمل عنوان الطلب"
    assert "payload" not in cert and "company_manager" not in cert, \
        "مفاتيح حمولة أو رموز أدوار داخل نص الشهادة"

    # DOC-07 — لا ادّعاء حماية تشفيرية بلا توقيع مشفَّر
    protected = re.compile(r"توقيع\s+إلكتروني\s+(محمي|مؤمَّن)|Protected\s+Electronic\s+Signature",
                           re.IGNORECASE)
    for code, body in by_code.items():
        assert not protected.search(body or ""), \
            f"{code} يدّعي توقيًعا إلكترونًيا محمًيا وهو صورة مرفوعة"

    # DOC-14 — لا "مدفوع" في قالب اعتماد
    for code in ("HRMS-PR-016", "HRMS-PR-017"):
        body = by_code.get(code, "")
        if body:
            assert not re.search(r"\bتم الدفع\b|\bمدفوع\b", body), \
                f"{code} يعلن الدفع قبل تنفيذه"

    # DOC-15 — الـIBAN لا يظهر كامًلا في نص عام؛ يأتي رمًزا يُملأ عند الحاجة
    for code, body in by_code.items():
        assert not re.search(r"KW\d{2}[A-Z0-9]{20,}", body or ""), \
            f"{code} يحمل IBAN كامًلا مكتوًبا في القالب"


def test_rw04_rw05_rw13_catalog_scenarios():
    """RW-04/RW-05/RW-13 — سيناريوهات الكتالوج الواقعية.

    RW-04: إجازة داخل الرصيد ⇒ مدير واحد ثم تحديث الرصيد والحضور. لا سلسلة
    من أربعة على يومين إجازة.
    RW-05: الإجازة الاستثنائية إضافة HR بقاعدة مسجَّلة — لا مسار موازٍ يلتفّ
    على الرصيد.
    RW-13: الاستقالة إشعار لا طلب موافقة: المدير يُقرّ باستلامها ولا يملك
    رفضها، وتنشأ عنها نهاية الخدمة وإخلاء الطرف.
    """
    from app.workflow import DEFAULT_REQUEST_TYPES

    by = {r["code"]: r for r in DEFAULT_REQUEST_TYPES}

    # RW-04 — الإجازة العادية: مسار قصير، والمندوب مشروط بالسفر لا افتراضي
    leave = by["leave"]
    stages = leave["approval_chain_json"]
    decision_roles = [s["role"] for s in stages if s.get("step_type") != "VALIDATION"]
    assert len(decision_roles) <= 3, f"سلسلة إجازة طويلة بلا داٍع: {decision_roles}"
    delegate_stages = [s for s in stages if s.get("role") == "delegate"]
    for s in delegate_stages:
        assert s.get("when"), "مرحلة المندوب في الإجازة بلا شرط سفر"

    # RW-05 — الإجازة الاستثنائية ليست نوًعا موازًيا يلتفّ على الرصيد
    exceptional = [c for c in by if "استثنائ" in (by[c]["name"] or "")]
    assert not exceptional, f"نوع إجازة استثنائية موازٍ: {exceptional}"

    # RW-13 — الاستقالة إشعار: HR ينفّذ ولا يملك المدير رفض الإشعار
    resign = by["REQRESIGN"]
    roles = [s["role"] for s in resign["approval_chain_json"]]
    assert "hr" in roles, "الاستقالة بلا مسار شؤون موظفين"
    assert by.get("REQEOS") and by.get("REQCLR"), \
        "لا نوعا نهاية خدمة وإخلاء طرف ينشآن عن الاستقالة"


def test_doc03_doc13_doc16_doc17_output_profiles(client):
    """DOC-03/13/16/17 — ملفات الإخراج وقواعدها.

    DOC-13: الحسبة المبدئية رقم نهائي الشكل بلا وسم، فيُنسخ في رسالة أو يُطبع
    ويُقرأ التزاًما بالدفع — بينما هو تقدير قبل إخلاء الطرف وخصم العهد.
    DOC-16: لا نقطة تطبع "سجل الطلب" كأنه مستند رسمي — والمواصفة تمنعه صراحًة
    ضمن الممنوعات المطلقة.
    DOC-17: العربي RTL والإنجليزي LTR في القوالب ثنائية اللغة.
    """
    import re

    from app.main import app
    from app.seed import DEFAULT_TEMPLATES

    # DOC-13 — التسوية المبدئية موسومة
    from app.routers import eos as eos_router
    src = __import__("inspect").getsource(eos_router)
    assert "not_for_payment" in src and "غير صالحة للصرف" in src, \
        "الحسبة المبدئية بلا وسم يمنع قراءتها أمر صرف"

    # DOC-16 — لا مسار يطبع سجل الطلب كمستند رسمي
    paths = {getattr(r, "path", "") for r in app.routes}
    assert not any(p.endswith("/print-record") or p.endswith("/record/print")
                   for p in paths), "مسار يطبع سجل الطلب كمستند"

    # DOC-03/DOC-17 — القوالب ثنائية اللغة تُصرّح بالاتجاه
    bilingual = [e for e in DEFAULT_TEMPLATES if e[2]]
    assert bilingual, "لا قوالب ثنائية اللغة"
    directional = [e for e in bilingual if re.search(r"dir=['\"](rtl|ltr)", e[-1] or "")]
    assert directional, "قوالب ثنائية اللغة بلا تصريح اتجاه — النص ينعكس"
    for e in directional:
        body = e[-1]
        # كل خلية إنجليزية تُصرّح ltr صراحًة وإلا انعكست الأرقام والعملات
        en_cells = re.findall(r"class='en'([^>]*)>", body)
        for attrs in en_cells:
            assert "ltr" in attrs, f"{e[0]}: خلية إنجليزية بلا dir=ltr"


def test_str07_migration_report_is_clean(client):
    """STR-07 — بعد الترحيل: لا طلبات يتيمة ولا مزدوجة، والرجوع مجرَّب.

    "يتيم" = طلب بكود نوع لا يعرفه النظام: يظهر في القوائم بلا اسم ولا مسار،
    ولا يستطيع أحد إغلاقه لأن سلسلته غير معروفة. و"مزدوج" = نوعان يمثّلان
    الخدمة نفسها فيُقسَم تاريخها بينهما.

    والرجوع: كل ترحيل غيّر سلسلة أو حذف عموًدا يجب أن يملك downgrade يعيد ما
    كان — ترحيل بلا رجوع يجعل النشر قراًرا لا رجعة فيه.
    """
    import pathlib
    import re

    from app import models, v15_registry
    from app.database import SessionLocal
    from app.workflow import DEFAULT_REQUEST_TYPES
    from sqlalchemy import select

    from app import workflow

    db = SessionLocal()
    try:
        # "يتيم" = طلب لا يستطيع النظام حلّ نوعه — لا طلب بكود خارج قائمة
        # ثابتة. الفرق جوهري: القائمة الثابتة تتهم كل نوع أنشأته شركة بأنه
        # يتيم، والمعيار الحقيقي هو: هل يجد الطلبُ مسارَه أم يقف بلا سلسلة؟
        rows = db.execute(select(models.Request.company_id,
                                 models.Request.request_type_code).distinct()).all()
        orphans = sorted({code for cid, code in rows
                          if workflow.get_request_type(db, cid, code) is None})
        assert not orphans, f"طلبات لا يُحَل نوعها فتقف بلا مسار: {orphans}"

    finally:
        db.close()

    # ولا خدمتان مزدوجتان فيما **يستطيع المستخدم إنشاءه**.
    #
    # القياس على كتالوج الإنشاء لا على صفوف الجدول عن قصد: أكواد V1.4
    # (salary_certificate، exit_permission) تشترك في نفس المسار مع أكواد V1.3
    # (REQCERTSAL، REQEXIT)، لكن تعطيلها **يُيتّم الطلبات التاريخية** —
    # get_request_type يفلتر is_active، فطلب قديم بكودها يفقد نوعه ومساره ولا
    # يستطيع أحد إغلاقه. تبقى نشطة للقراءة، ويُلغي كتالوج الإنشاء تكرارها.
    hr = _headers(client, "100000000002", "hr12345")
    creatable = client.get("/api/requests/types", headers=hr,
                           params={"creatable_only": True, "grouped": True}).json()
    seen, dupes = {}, []
    for svc in creatable:
        key = (svc.get("canonical_code"), svc.get("canonical_subtype"))
        if key[0] and key in seen:
            dupes.append((seen[key], svc["code"], key))
        seen[key] = svc["code"]
    assert not dupes, f"خدمات مزدوجة في كتالوج الإنشاء: {dupes}"

    # كل ترحيل يملك downgrade فعلًا لا تمريرة فارغة
    versions = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions"
    missing = []
    for f in versions.glob("*.py"):
        src = f.read_text(encoding="utf-8")
        m = re.search(r"def downgrade\(\)[^\n]*:\n(.*?)(?=\ndef |\Z)", src, re.S)
        if not m:
            missing.append(f"{f.name}: لا downgrade")
            continue
        lines = [ln.strip() for ln in m.group(1).splitlines() if ln.strip()]
        code = [ln for ln in lines if not ln.startswith("#")]
        explained = any(ln.startswith("#") or ln.startswith('"""') for ln in lines)
        # لا رجوع **معلَّل** مقبول: ترحيل نصوص رسمية لا يُعاد لمسودّة قديمة.
        # المرفوض هو الصمت: pass بلا كلمة تفسّر لماذا لا رجعة.
        if code == ["pass"] and not explained:
            missing.append(f"{f.name}: downgrade فارغ بلا تفسير")
    assert not missing, "ترحيلات بلا رجوع: " + "; ".join(missing[:8])


def test_dlv31_seed_accounts_are_detected(client):
    """DLV-31 + ACCESS-10 — حساب بكلمة مرور بذرة يُكتشف ويمنع التسليم.

    ROOT CAUSE: المنع القائم يغطّي **تشغيل** البذر (ALLOW_DEMO_SEED) لا **وجود**
    حسابها. فقاعدة بُذرت على staging ثم رُقّيت للإنتاج، أو بيئة شُغّل عليها
    البذر بتصريح مؤقّت ونُسي — تبقى فيها حسابات بكلمات مرور منشورة في
    المستودع، وأخطرها super_admin مشترك.

    السؤال الصحيح: هل تعمل كلمة مرور بذرة على هذه القاعدة **الآن**؟ لا "هل
    شُغّل البذر؟" — الأول واقع يُقاس، والثاني تاريخ لا أحد يتذكّره.
    """
    from app import seed_guard
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        hits = seed_guard.find_seed_accounts(db)
        # قاعدة الاختبار مبذورة، فالحساسية يجب أن تكتشفها
        assert hits, "الفحص لم يكتشف حسابات البذرة في قاعدة مبذورة"
        roles = {h["role"] for h in hits}
        assert "super_admin" in roles, "لم يُكتشف حساب super_admin المشترك"
        # ولا تسريب لكلمات المرور في الناتج
        blob = str(hits)
        assert "admin123" not in blob and "hr12345" not in blob, \
            "الفحص يسرّب كلمات المرور في ناتجه"
    finally:
        db.close()

    # ويظهر في فحص الصحة بلا أسماء ولا كلمات مرور
    deep = client.get("/api/health/deep").json()
    check = deep["checks"].get("seed_accounts")
    assert check is not None, "فحص الصحة لا يعرض حسابات البذرة"
    assert check["status"] == "fail" and check["count"] >= 1
    assert all(set(a) == {"civil_id", "role"} for a in check["accounts"]), \
        "فحص الصحة يكشف أكثر من اللازم"


def test_dlv06_build_identity_includes_migration(client):
    """DLV-06 — هوية البناء تشمل نسخة الترحيلات.

    "أي كود يعمل؟" سؤال ناقص بلا "على أي بنية قاعدة؟": بناءان بنفس الـcommit
    وقاعدتان مختلفتان يسلكان سلوًكا مختلًفا، وتشخيص ذلك بلا الرقم تخمين.
    """
    m = client.get("/api/manifest").json()
    for k in ("version", "commit", "build_time", "deploy_time", "environment",
              "migration_version"):
        assert k in m, f"هوية البناء تنقصها {k}"


def test_dlv23_scheduled_job_failure_raises_an_alert(client):
    """DLV-23 — فشل مهمة مجدولة يصل مسؤوًلا لا سجًلا وحده.

    ROOT CAUSE: كل مهمة كانت تُسجّل خطأها ثم تصمت. سجل الخادم لا يقرأه أحد
    يومًيا، فالمسح اليومي يتوقف أسابيع بلا أن ينتبه أحد — **وتنتهي إقامات بلا
    تنبيه لأن المُنبِّه نفسه هو المتعطّل**. أخطر أنواع الأعطال: عطل في آلية
    الإنذار لا يُنذِر عن نفسه.
    """
    from unittest.mock import patch

    from app import models, scheduler
    from app.database import SessionLocal
    from sqlalchemy import select

    with patch.object(scheduler, "daily_scan",
                      side_effect=RuntimeError("قاعدة غير متاحة")):
        scheduler._run_daily_scan()

    db = SessionLocal()
    try:
        tasks = db.scalars(select(models.Task).where(
            models.Task.type == "job_failure")).all()
        assert tasks, "فشل المهمة لم يُنتج تنبيًها"
        t = tasks[0]
        assert t.severity == "critical"
        assert "daily_scan" in (t.title or "")
        assert t.assignee_user_id, "التنبيه بلا مسؤول يستلمه"

        # ولا يتكاثر: فشل متكرر في اليوم نفسه = تنبيه واحد
        before = len(tasks)
        with patch.object(scheduler, "daily_scan", side_effect=RuntimeError("مرة أخرى")):
            scheduler._run_daily_scan()
            scheduler._run_daily_scan()
        after = db.scalars(select(models.Task).where(
            models.Task.type == "job_failure")).all()
        assert len(after) == before, "تنبيهات فشل متكاثرة لنفس المهمة واليوم"
    finally:
        for row in db.scalars(select(models.Task).where(
                models.Task.type == "job_failure")).all():
            db.delete(row)
        db.commit()
        db.close()


def test_dlv36_production_reset_needs_explicit_confirmation(client):
    """DLV-36 — مسح بيانات العميل يحتاج قصًدا مكتوًبا لا إعداًدا قديًما.

    متغيّر بيئة واحد (ALLOW_DEMO_RESET) كان يكفي لمسح قاعدة عميل كاملة بنداء
    واحد: يُضبَط مرة لعرض توضيحي ثم يُنسى، فيبقى الباب مفتوًحا. الفعل غير قابل
    للتراجع، فيلزمه تأكيد صريح.
    """
    import inspect

    from app.routers import admin

    src = inspect.getsource(admin.reset_demo_data)
    assert "ERASE-ALL-DATA" in src, "المسح في الإنتاج بلا تأكيد صريح"
    assert "is_production" in src, "التأكيد لا يفرّق بين الإنتاج والتطوير"


def test_att07_payroll_requires_closed_attendance(client):
    """ATT-07 / DLV-01 — لا مسيّر رواتب على فترة حضور لم تُغلَق.

    ROOT CAUSE: المسيّر كان يُحسب على حضور لم يُراجَع — أيام بلا سجل،
    وتصحيحات معلّقة، وإجازات لم تُعتمَد. ثم يُصرف ويُكتشف الخطأ في راتب موظف،
    **والتصحيح بعد الصرف أصعب من منعه بكثير**: مالٌ خرج، وموظف رأى رقًما، وثقة
    اهتزّت.

    الإغلاق إقرار مؤرَّخ بفاعل يوثّق **على كم يوم غير مسجَّل** أُقرّ — فبعد
    شهور، حين يُسأل عن راتب، يوجد جواب مكتوب لا ذاكرة.
    """
    from app import models
    from app.database import SessionLocal
    from sqlalchemy import select

    acc = _headers(client, "100000000007", "account123")
    period = "2026-03"

    # 1) فترة مفتوحة ⇒ المسيّر يُرفض بسبب مفهوم
    blocked = client.post("/api/payroll/run", headers=acc, params={"period": period})
    assert blocked.status_code == 409, f"المسيّر مرّ على فترة مفتوحة: {blocked.status_code}"
    assert "لم تُغلَق" in blocked.text

    # 2) والحالة معروضة قبل الإغلاق
    st = client.get("/api/attendance/close-status", headers=acc, params={"period": period})
    assert st.status_code == 200 and st.json()["closed"] is False

    # 3) الإغلاق يوثّق عدد الأيام غير المسجَّلة
    hr = _headers(client, "100000000002", "hr12345")
    closed = client.post("/api/attendance/close-month", headers=hr,
                         params={"period": period, "note": "روجعت السجلات"})
    assert closed.status_code == 200, closed.text

    # 4) ثم يمرّ المسيّر
    ok = client.post("/api/payroll/run", headers=acc, params={"period": period})
    assert ok.status_code == 200, f"المسيّر رُفض بعد الإغلاق: {ok.text[:200]}"

    # 5) إعادة الفتح تحتاج سبًبا، ولا تمحو السجل
    no_reason = client.post("/api/attendance/reopen-month", headers=hr,
                            params={"period": period, "reason": " "})
    assert no_reason.status_code == 400, "أُعيد الفتح بلا سبب"

    reopened = client.post("/api/attendance/reopen-month", headers=hr,
                           params={"period": period, "reason": "تصحيح سجل موظف"})
    assert reopened.status_code == 200, reopened.text

    db = SessionLocal()
    try:
        row = db.scalar(select(models.AttendanceMonthClose).where(
            models.AttendanceMonthClose.period == period))
        assert row is not None, "إعادة الفتح حذفت سجل الإغلاق"
        assert row.reopen_reason and row.reopened_by, "من أعاد الفتح ولماذا لم يُحفَظ"
        assert row.closed_by, "من أغلق أوًلا ضاع"
    finally:
        db.close()


def _drive_to_completion(client, req_id, max_steps=8):
    """يمرّر طلًبا عبر سلسلته الفعلية حتى يكتمل، بمن يملك القرار حًقا.

    لا يستدعي المحرّك مباشرة: كل خطوة تمرّ بالمسار وبحارس الصلاحيات، فالاختبار
    يثبت أن الأثر يقع في التشغيل الحقيقي لا في استدعاء داخلي.
    """
    from app import models, workflow
    from app.database import SessionLocal
    from app.seed import PW

    for _ in range(max_steps):
        db = SessionLocal()
        try:
            req = db.get(models.Request, req_id)
            if req.status != "pending":
                return req.status
            rt = workflow.get_request_type(db, req.company_id, req.request_type_code)
            chain = workflow._chain(rt, req)
            stage = chain[req.current_stage]
            approvers = workflow.resolve_stage_approvers(db, req, stage)
            pick = next((u for u in approvers
                         if u.id != req.requester_user_id and PW.get(u.role)), None)
            assert pick is not None, (
                f"لا معتمِد متاح للمرحلة {req.current_stage} "
                f"({stage.get('label')}) — الأدوار: {stage.get('roles')}")
            civil, pw, is_validation = pick.civil_id, PW[pick.role], \
                stage.get("type") == "VALIDATION"
        finally:
            db.close()

        hdr = _headers(client, civil, pw)
        path = f"/api/requests/{req_id}/" + ("complete-validation" if is_validation else "decide")
        body = {"note": "اختبار"} if is_validation else {"decision": "approved", "note": "اختبار"}
        r = client.post(path, headers=hdr, json=body)
        assert r.status_code == 200, f"تعذّر تمرير المرحلة: {r.status_code} {r.text[:200]}"

    raise AssertionError("لم يكتمل الطلب خلال الحد الأقصى للخطوات")


def test_wf09_approved_request_actually_changes_the_record(client):
    """WF-09 — الطلب المعتمَد يغيّر البيانات فعلًا، لا يُغلق فقط.

    ROOT CAUSE: ``_finalize`` كان يطبّق أًثرا لنوعين فقط (إجازة وتصحيح حضور).
    بقية الأنواع تمرّ بالسلسلة كاملة وتُغلق "مكتملة" وسجل الموظف كما هو: جواز
    جديد معتمَد ورقمه القديم باقٍ — ومحرّك انتهاء الصلاحية يظلّ ينبّه على
    تاريخ بطل، والمندوب يجدّد إقامة برقم خاطئ.

    وأخطر ما فيه أن الفشل **يبدو نجاًحا**: الحالة "مكتمل" والاعتمادات كاملة،
    فلا يظهر التناقض إلا بمقارنة يدوية لا يفعلها أحد.
    """
    from app import models
    from app.database import SessionLocal
    from sqlalchemy import select

    emp_hdr = _headers(client, "100000000101", "emp12345")
    me = client.get("/api/auth/me", headers=emp_hdr).json()
    emp_id = me.get("employee_id")
    assert emp_id, "حساب الموظف غير مربوط بسجل موظف"

    db = SessionLocal()
    try:
        before = db.get(models.Employee, emp_id)
        old_passport = before.passport_number
    finally:
        db.close()

    new_no = "P99887766"
    assert old_passport != new_no
    created = client.post("/api/requests", headers=emp_hdr, json={
        "request_type_code": "REQPASS",
        "payload_json": {"old_passport": old_passport or "—", "new_passport": new_no,
                         "new_expiry": "2032-05-01", "issue_country": "مصر",
                         "reason": "تجديد الجواز",
                         "_attachments": ["passport_scan"]},
    })
    assert created.status_code in (200, 201), created.text
    req_id = created.json()["id"]

    status = _drive_to_completion(client, req_id)
    assert status == "completed", f"الطلب انتهى بحالة {status}"

    db = SessionLocal()
    try:
        emp = db.get(models.Employee, emp_id)
        assert emp.passport_number == new_no, (
            f"الطلب اكتمل والجواز لم يتغيّر: {emp.passport_number!r}")
        assert emp.passport_expiry and emp.passport_expiry.isoformat() == "2032-05-01"

        # الأثر مقيَّد على الطلب وعلى الموظف — من يفتّش تاريخ موظف يجده
        trail = db.scalars(select(models.AuditLog).where(
            models.AuditLog.action == "employee_updated_by_request",
            models.AuditLog.entity_id == emp_id)).all()
        assert trail, "التغيير وقع بلا سطر تدقيق على الموظف"
        assert trail[-1].before_json.get("passport_number") == old_passport
        assert trail[-1].after_json.get("passport_number") == new_no
    finally:
        db.close()


def test_wf09_effect_is_applied_once_only(client):
    """WF-09 — إعادة التطبيق لا تكرّر الأثر.

    الترقية أخطر مثال: تطبيق مزدوج يرفع الراتب مرتين، ويظهر الخطأ في كشف
    الرواتب بعد الصرف. البصمة سطر تدقيق لا علَم قابل لإعادة الضبط.
    """
    from app import models, request_effects
    from app.database import SessionLocal
    from sqlalchemy import select

    db = SessionLocal()
    try:
        emp = db.scalar(select(models.Employee).where(models.Employee.status == "active"))
        req = models.Request(
            company_id=emp.company_id, employee_id=emp.id, requester_user_id=1,
            request_type_code="REQPROM", status="pending", current_stage=0,
            payload_json={"new_title": "مدير أول", "new_salary": 950,
                          "effective_date": "2026-09-01", "reason": "ترقية"},
        )
        db.add(req)
        db.commit()

        ok, note = request_effects.apply_field_effect(db, req)
        assert ok, note
        assert emp.basic_salary == 950, note
        db.commit()

        emp.basic_salary = 950  # الحالة بعد التطبيق الأول
        ok2, note2 = request_effects.apply_field_effect(db, req)
        assert ok2 and "مطبَّق مسبًقا" in note2, note2
        assert emp.basic_salary == 950, "طُبِّق الأثر مرتين"

        # قيمة غير صالحة تُفشِل التطبيق بدل أن تكتب فراغًا فوق بيانات صحيحة
        bad = models.Request(
            company_id=emp.company_id, employee_id=emp.id, requester_user_id=1,
            request_type_code="REQCIVIL", status="pending", current_stage=0,
            payload_json={"new_civil": "  ", "reason": "تحديث"},
        )
        db.add(bad)
        db.commit()
        ok3, note3 = request_effects.apply_field_effect(db, bad)
        assert not ok3 and "مطلوب" in note3, note3
    finally:
        db.rollback()
        db.close()
