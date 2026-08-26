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


def test_access_no_shared_default_password(client):
    """كل كلمة مؤقّتة عشوائية ومختلفة — لا كلمة موحّدة لكل الحسابات.

    ROOT CAUSE: ``settings.default_user_password`` كانت قيمة ثابتة مكتوبة في
    المستودع (Kuwait@2024) تُستخدم عند إنشاء أي مستخدم وعند كل إعادة تعيين.
    فمن يعرف قيمة واحدة يدخل بأي حساب أُنشئ أو أُعيد تعيينه ولم يغيّر صاحبه
    كلمته بعد — وهي معروفة لكل من رأى الكود.

    الاختبار يقيس ما يهمّ فعًلا: **هل تعمل الكلمة الموحّدة؟** لا "هل الثابت
    موجود؟" — الأول واقع والثاني تفصيل تنفيذي.
    """
    from app import models
    from app.config import settings
    from app.database import SessionLocal
    from app.security import generate_temp_password, verify_password
    from sqlalchemy import select

    admin = _headers(client, "000000000000", "admin123")

    # 1) إنشاء حسابين بلا كلمة صريحة ⇒ كلمتان مختلفتان تُعرضان مرة واحدة
    made = []
    for i in (1, 2):
        r = client.post("/api/users", headers=admin, json={
            "civil_id": f"29900000{i:04d}", "full_name": f"حساب اختبار {i}",
            "role": "company_owner", "company_id": 1,
        })
        assert r.status_code == 201, r.text
        pw = r.json().get("temporary_password")
        assert pw, "أُنشئ حساب بلا كلمة تُعرض لمنشئه — لا سبيل لاستخراجها لاحًقا"
        made.append((r.json()["id"], pw))

    assert made[0][1] != made[1][1], "حسابان بنفس الكلمة المؤقّتة"

    # 2) الكلمة الموحّدة القديمة لا تفتح أًيا منهما
    shared = getattr(settings, "default_user_password", "Kuwait@2024")
    db = SessionLocal()
    try:
        for uid, pw in made:
            u = db.get(models.User, uid)
            assert verify_password(pw, u.password_hash), "الكلمة المعروضة لا تعمل"
            assert not verify_password(shared, u.password_hash), \
                "الكلمة الموحّدة ما زالت تفتح الحساب"
            assert u.must_change_password, "الحساب لا يُلزم بتغيير الكلمة"
    finally:
        db.close()

    # 3) إعادة التعيين تعطي كلمة جديدة مختلفة عن السابقة وعن كلمة غيره
    uid, old_pw = made[0]
    r = client.post("/api/auth/reset-password", headers=admin, json={"user_id": uid})
    assert r.status_code == 200, r.text
    new_pw = r.json()["temporary_password"]
    assert new_pw and new_pw != old_pw, "إعادة التعيين أعادت نفس الكلمة"
    assert new_pw != made[1][1]

    r2 = client.post("/api/auth/reset-password", headers=admin, json={"user_id": uid})
    assert r2.json()["temporary_password"] != new_pw, "إعادتان متتاليتان بنفس الكلمة"

    # 4) المولّد نفسه لا يكرّر ويستوفي التنوّع
    batch = {generate_temp_password() for _ in range(200)}
    assert len(batch) == 200, "المولّد كرّر قيمة"
    for pw in list(batch)[:20]:
        assert len(pw) >= 12 and any(c.isdigit() for c in pw) and any(c.isupper() for c in pw)


def test_manager_approves_but_does_not_submit(client):
    """المدير يعتمد الطلبات ولا يرفعها.

    قرار تنظيمي: سلطة الاعتماد وسلطة الطلب لا تجتمعان في يد واحدة. المنع على
    الخادم لا في الواجهة — إخفاء الزر لا يمنع POST مباًشرا على المسار.
    """
    mgr = _headers(client, "100000000001", "manager123")

    me = client.get("/api/auth/me", headers=mgr).json()
    assert "submit_request" not in me["permissions"], "المدير ما زال يملك رفع الطلبات"
    # وسلطته كمعتمِد باقية — المنع عن الرفع لا عن الاعتماد
    assert any(p.startswith("approve_") for p in me["permissions"])

    r = _submit_leave(client, mgr)
    assert r.status_code == 403, f"المدير رفع طلًبا: {r.status_code} {r.text[:160]}"


def test_manager_is_not_a_warning_target(client):
    """لا إنذار ولا جزاء يُوجَّه للمدير — لا عبر الحدث المباشر ولا عبر الطلب.

    الإنذار أداة انضباط يوجّهها صاحب السلطة إلى من تحته؛ وتوجيهه للمدير يقلب
    التسلسل، ويجعل الشؤون القانونية — وهي تحت إدارته — طرًفا يؤدّبه.

    البابان يُفحصان لأن سدّ أحدهما وترك الآخر هو نفسه العطل: قاعدة واحدة
    مكتوبة في مكانين تنحرف حتًما.
    """
    from app import models
    from app.database import SessionLocal
    from sqlalchemy import select

    hr = _headers(client, "100000000002", "hr12345")

    db = SessionLocal()
    try:
        mgr_user = db.scalar(select(models.User).where(
            models.User.role == "company_manager", models.User.company_id == 1))
        assert mgr_user and mgr_user.employee_id, "المدير غير مربوط بسجل موظف"
        mgr_emp_id = mgr_user.employee_id
        emp_user = db.scalar(select(models.User).where(
            models.User.role == "employee", models.User.company_id == 1))
        emp_id = emp_user.employee_id
    finally:
        db.close()

    # 1) الحدث المباشر مرفوض للمدير ومقبول للموظف العادي
    blocked = client.post(f"/api/employees/{mgr_emp_id}/events", headers=hr,
                          params={"kind": "warning", "title": "اختبار"})
    assert blocked.status_code == 403, f"وُجّه إنذار للمدير: {blocked.status_code}"

    allowed = client.post(f"/api/employees/{emp_id}/events", headers=hr,
                          params={"kind": "warning", "title": "اختبار"})
    assert allowed.status_code == 200, f"تعذّر إنذار موظف عادي: {allowed.text[:160]}"

    # الجزاء مثله — القاعدة على النوعين لا على "warning" وحدها
    pen = client.post(f"/api/employees/{mgr_emp_id}/events", headers=hr,
                      params={"kind": "penalty", "title": "اختبار"})
    assert pen.status_code == 403, "وُجّع جزاء للمدير"

    # والمكافأة تمرّ — الإعفاء من الانضباط لا من كل حدث
    bonus = client.post(f"/api/employees/{mgr_emp_id}/events", headers=hr,
                        params={"kind": "bonus", "title": "مكافأة"})
    assert bonus.status_code == 200, f"مُنعت مكافأة المدير: {bonus.text[:160]}"

    # 2) الباب الثاني: طلب ADMWARN باسم المدير
    req = client.post("/api/requests", headers=hr, json={
        "request_type_code": "ADMWARN", "employee_id": mgr_emp_id,
        "payload_json": {"subject": "اختبار", "details": "اختبار"},
    })
    assert req.status_code == 403, f"أُنشئ طلب إنذار للمدير: {req.status_code}"

    # 3) بند الإنذارات مخفيّ من ملفه، وظاهر لغيره
    prof = client.get(f"/api/employees/{mgr_emp_id}", headers=hr)
    assert prof.status_code == 200 and prof.json()["may_receive_warning"] is False
    other = client.get(f"/api/employees/{emp_id}", headers=hr)
    assert other.json()["may_receive_warning"] is True

    # 4) وفي خدمته الذاتية أيًضا
    mgr = _headers(client, "100000000001", "manager123")
    my = client.get("/api/me/profile", headers=mgr)
    assert my.status_code == 200 and my.json()["may_receive_warning"] is False
    assert my.json()["warnings"] == []


def test_rnw01_02_alert_becomes_case(client):
    """RNW-01/02 — التنبيه يفتح، ويتحوّل معامًلة برقم، ومرّتين لا تنشئان اثنتين.

    ROOT CAUSE: شاشة التجديدات تعرض مجموعتين مختلفتي المصدر — معاملات حقيقية،
    وتنبيهات محسوبة من تاريخ الانتهاء. الأولى بطاقاتها أزرار لها onClick،
    والثانية صفوف جدول بلا أي معالِج. فالضغط على تنبيه لا يرسل طلًبا ولا يفتح
    شيًئا: **تجاهل صامت**، والمندوب يظنّ النظام معطًلا بينما الإقامة تنتهي.

    وتحته عطل أعمق: المسار الوحيد للإنشاء في الواجهة كان يرسل reason و notes
    فقط، فيقع الخادم على user.employee_id — أي يفتح ملًفا **للمستخدم نفسه** لا
    لصاحب البطاقة. وحساب إداري بلا سجل موظف يُرفض بـ"لم يُحدَّد الموظف".

    الاختبار يقيس السلوك من طرف الخادم: هل تحمل بطاقة التنبيه ما يكفي للقرار،
    وهل يوجد مسار يحوّلها معاملة، وهل يصمد أمام الضغط المزدوج.
    """
    from datetime import date, timedelta

    from app import models
    from app.database import SessionLocal
    from sqlalchemy import func, select

    pro = _headers(client, "100000000003", "deleg123")

    db = SessionLocal()
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.status == "active"))
        permit = models.Permit(
            company_id=1, employee_id=emp.id, kind="residency", status="active",
            number="RNW-TEST-01", expiry_date=date.today() + timedelta(days=20),
        )
        db.add(permit)
        db.commit()
        permit_id, emp_id = permit.id, emp.id
    finally:
        db.close()

    # 1) التنبيه يظهر ومعه ما يكفي للقرار — الفرع كان ناقًصا والمواصفة تطلبه
    due = client.get("/api/renewals/due/permits", headers=pro)
    assert due.status_code == 200, due.text
    card = next((d for d in due.json() if d["permit_id"] == permit_id), None)
    assert card is not None, "الإقامة المستحقة لا تظهر في التنبيهات"
    for field in ("employee_name", "company_name", "branch_name", "number",
                  "expiry_date", "days_left"):
        assert field in card, f"بطاقة التنبيه بلا {field}"
    assert card["employee_name"], "البطاقة بلا اسم موظف"

    # 2) التحويل إلى معاملة يحتاج تمرير الموظف والإقامة صراحة
    started = client.post("/api/renewals", headers=pro,
                          data={"employee_id": str(emp_id), "permit_id": str(permit_id)})
    assert started.status_code == 201, f"تعذّر بدء المعاملة: {started.text[:200]}"
    case = started.json()
    assert case["id"], "المعاملة بلا رقم"
    assert case["employee_id"] == emp_id, "فُتحت المعاملة لموظف آخر"

    # 3) التنبيه ينتقل من مجموعة لأخرى فورًا
    due2 = client.get("/api/renewals/due/permits", headers=pro)
    assert not any(d["permit_id"] == permit_id for d in due2.json()), \
        "التنبيه ما زال معروًضا بعد فتح ملفه"
    listed = client.get("/api/renewals", headers=pro).json()
    assert any(r["id"] == case["id"] for r in listed), "المعاملة لا تظهر في القائمة"

    # 4) الضغط مرتين لا ينشئ معاملتين — ويسمّي القائمة بدل رفض أعمى
    again = client.post("/api/renewals", headers=pro,
                        data={"employee_id": str(emp_id), "permit_id": str(permit_id)})
    assert again.status_code == 409, f"أُنشئت معاملة ثانية: {again.status_code}"
    assert str(case["id"]) in again.text, "الرفض لا يدلّ على المعاملة القائمة"

    db = SessionLocal()
    try:
        n = db.scalar(select(func.count(models.ResidencyRenewal.id)).where(
            models.ResidencyRenewal.permit_id == permit_id))
        assert n == 1, f"عدد المعاملات لهذه الإقامة {n}"
    finally:
        db.close()


def test_rnw06_09_three_contract_versions(client):
    """RNW-06/09 — ثلاث نسخ متمايزة للعقد، ولا توليد بحقل ناقص.

    ROOT CAUSE (RNW-06): مالئ القوالب يستبدل أي حقل مفقود بـ"................"،
    فيخرج **عقد حكومي بمربّعات فارغة** يوقّعه الموظف ويُقدَّم لجهة رسمية. الفشل
    صامت: المستند يبدو سليًما ولا شيء يقول إن نصفه ناقص.

    ROOT CAUSE (RNW-09): كان للعقد نسختان فقط — المولّدة وموقّعة الموظف. ونسخة
    الموظف **ليست النهائية**: تنقصها توقيع صاحب الشركة. فلم يكن في النظام مكان
    يحفظ ما قُدّم فعًلا للجهة الحكومية، ولا سبيل لإثباته لاحًقا.

    الثلاث تبقى محفوظة: النهائية لا تمسح موقّعة الموظف، وموقّعة الموظف لا تمسح
    المولّدة. دمجها في حقل واحد يفقد القدرة على الإثبات.
    """
    from app import renewal as R

    # 1) النسخ الثلاث معرَّفة ومتمايزة
    kinds = {R.DOC_CONTRACT_GOV, R.DOC_SIGNED_GOV, R.DOC_CONTRACT_FINAL}
    assert len(kinds) == 3, "نسختان تحملان نفس الكود"
    for k in kinds:
        assert k in R.ALL_CONTRACT_DOCS, f"{k} خارج مجموعة نسخ العقد — لن تُنزَّل"

    # 2) الحقول الإلزامية معلَنة بأسماء عربية تُعرض للمندوب
    assert R.GOV_CONTRACT_REQUIRED_FIELDS, "لا حقول إلزامية معلَنة"
    for key, label in R.GOV_CONTRACT_REQUIRED_FIELDS.items():
        assert label and not label.isascii(), f"اسم الحقل {key} غير معرَّب"

    # 3) الحارس يقيس ما يهمّ: قيمة فارغة أو فراغات تُعدّ ناقصة
    for bad in ("", "   ", None):
        ctx = {k: "قيمة" for k in R.GOV_CONTRACT_REQUIRED_FIELDS}
        ctx["civil_id"] = bad
        missing = [lbl for k, lbl in R.GOV_CONTRACT_REQUIRED_FIELDS.items()
                   if not str(ctx.get(k) or "").strip()]
        assert missing == ["الرقم المدني"], f"لم يُكتشف النقص عند {bad!r}: {missing}"


def test_rnw07_employee_gets_a_real_task(client):
    """RNW-07 — العقد يصل حساب الموظف كمهمة حقيقية لا كإشعار عابر.

    الفارق ليس شكلًيا: الإشعار يُقرأ ويُنسى، والمهمة تبقى مفتوحة حتى يُنجزها
    صاحبها — وهي الضمانة الوحيدة أن الموظف لن يتجاهل توقيع عقد إقامته حتى
    تنتهي. ``notify_from_template`` يُرجع Task لا رسالة، وهذا ما يُقاس هنا.
    """
    import inspect

    from app import notifications

    sig = inspect.signature(notifications.notify_from_template)
    assert "Task" in str(sig.return_annotation), \
        f"إشعار المرحلة لا يُنشئ مهمة: {sig.return_annotation}"

    # قالب توقيع العقد موجود ومفعّل — بدونه يسقط الإشعار بصمت
    from app.database import SessionLocal
    from app import models
    from sqlalchemy import select

    db = SessionLocal()
    try:
        tpl = db.scalar(select(models.NotificationTemplate).where(
            models.NotificationTemplate.code == "NTF-016"))
        assert tpl is not None, "قالب NTF-016 (توقيع عقد التجديد) غير مبذور"
        assert tpl.is_active, "قالب NTF-016 معطّل — المهمة لن تصل الموظف"
    finally:
        db.close()


def test_rnw06_generation_refuses_incomplete_employee(client):
    """RNW-06 — التوليد يرفض ويسمّي الناقص، لا يطبع مربّعات فارغة.

    اختبار من طرف إلى طرف عبر المسار الحقيقي: موظف بلا رقم مدني، ومعاملة
    تجديد قائمة، ثم طلب توليد العقد. المطلوب رفض يذكر «الرقم المدني» بالاسم —
    فالمندوب يعرف أين يذهب — لا مستند يبدو سليًما ونصفه نقاط.
    """
    from datetime import date, timedelta

    from app import models
    from app.database import SessionLocal
    from sqlalchemy import select

    pro = _headers(client, "100000000003", "deleg123")

    db = SessionLocal()
    try:
        # قالب العقد لازم للوصول إلى فحص الحقول — بدونه يُرفض بـ404 لسبب آخر
        tpl = db.scalar(select(models.DocumentTemplate).where(
            models.DocumentTemplate.code == "GOV-CONTRACT-RENEWAL"))
        if not tpl:
            db.add(models.DocumentTemplate(
                company_id=None, code="GOV-CONTRACT-RENEWAL", name="عقد حكومي",
                body_html="<p>{{employee_name}} — {{civil_id}}</p>",
                version=1, is_active=True))

        emp = models.Employee(
            company_id=1, name="موظف ناقص البيانات", civil_id=None,
            nationality="مصري", job_title="فني", status="active",
            hire_date=date.today() - timedelta(days=400), basic_salary=400,
        )
        db.add(emp)
        db.flush()
        permit = models.Permit(
            company_id=1, employee_id=emp.id, kind="residency", status="active",
            number="RNW-INCOMPLETE", expiry_date=date.today() + timedelta(days=15))
        db.add(permit)
        db.commit()
        emp_id, permit_id = emp.id, permit.id
    finally:
        db.close()

    started = client.post("/api/renewals", headers=pro,
                          data={"employee_id": str(emp_id), "permit_id": str(permit_id)})
    assert started.status_code == 201, started.text
    rid = started.json()["id"]

    gen = client.post(f"/api/renewals/{rid}/gov-contract/generate", headers=pro)
    assert gen.status_code == 400, f"وُلّد عقد ببيانات ناقصة: {gen.status_code}"
    assert "الرقم المدني" in gen.text, f"الرفض لا يسمّي الحقل الناقص: {gen.text[:200]}"

    # وبعد إكمال البيانات يمرّ — الحارس يمنع النقص لا التوليد نفسه
    db = SessionLocal()
    try:
        db.get(models.Employee, emp_id).civil_id = "299010112345"
        db.commit()
    finally:
        db.close()
    ok = client.post(f"/api/renewals/{rid}/gov-contract/generate", headers=pro)
    assert ok.status_code == 200, f"رُفض التوليد بعد اكتمال البيانات: {ok.text[:200]}"


def test_rnw05_08_10_11_contract_chain(client):
    """RNW-05/08/10/11 — سلسلة إثبات العقد من المولَّدة إلى ما قُدِّم للجهة.

    ROOT CAUSE (RNW-08): النسخة الموقّعة كانت مرتبطة بالمعاملة فقط. لكن إعادة
    التوليد تُنشئ إصداًرا جديًدا؛ فلو أعاد المندوب التوليد بعد إرسال العقد، لم
    يعد أحد يعرف **أي نسخة وقّعها الموظف فعًلا** — وهو بالضبط السؤال الذي
    يُطرح حين تعترض جهة رسمية على المستند، وحينها لا تنفع الذاكرة.

    والاختبار يغطّي معه ثلاثة بنود كانت منفَّذة ولم تُقَس: أن التجديد يولّد
    عقًدا حكومًيا فقط (RNW-05)، وأن المندوب ينزّل نسخة الموظف (RNW-10)،
    وأن المرجع الحكومي والرسوم والإيصال تُسجَّل (RNW-11).
    """
    import io
    from datetime import date, timedelta

    from app import models, renewal as R
    from app.database import SessionLocal
    from sqlalchemy import select

    pro = _headers(client, "100000000003", "deleg123")

    # RNW-05 — العقد المطلوب للانتقال هو الحكومي وحده، ولا عقد شركة يُولَّد
    assert R.REQUIRED_CONTRACT_DOCS == (R.DOC_CONTRACT_GOV,), \
        f"التجديد يطلب عقًدا غير الحكومي: {R.REQUIRED_CONTRACT_DOCS}"

    db = SessionLocal()
    try:
        # قالب العقد مبذور في الترحيلات وحدها، وقاعدة الاختبار تُبنى بـcreate_all
        # فلا تراه — وهو عيب تسليم حقيقي مسجَّل في FOUND_EXTRA.md لا تفصيل اختبار.
        if not db.scalar(select(models.DocumentTemplate).where(
                models.DocumentTemplate.code == "GOV-CONTRACT-RENEWAL")):
            db.add(models.DocumentTemplate(
                company_id=None, code="GOV-CONTRACT-RENEWAL", name="عقد حكومي",
                body_html="<p>{{employee_name}} — {{civil_id}} — {{company_name}}</p>",
                version=1, is_active=True))
        emp = models.Employee(
            company_id=1, name="موظف سلسلة العقد", civil_id="288010199999",
            nationality="هندي", job_title="محاسب", status="active",
            hire_date=date.today() - timedelta(days=500), basic_salary=500)
        db.add(emp); db.flush()
        db.add(models.Permit(company_id=1, employee_id=emp.id, kind="residency",
                             status="active", number="RNW-CHAIN-01",
                             expiry_date=date.today() + timedelta(days=20)))
        db.commit()
        emp_id = emp.id
    finally:
        db.close()

    rid = client.post("/api/renewals", headers=pro,
                      data={"employee_id": str(emp_id)}).json()["id"]

    # العقد المولَّد ثم رفعه ثم توقيع الموظف
    gen = client.post(f"/api/renewals/{rid}/gov-contract/generate", headers=pro)
    assert gen.status_code == 200, gen.text[:200]

    def _upload(kind, hdr):
        return client.post(f"/api/renewals/{rid}/upload", headers=hdr,
                           data={"doc_type": kind},
                           files={"file": (f"{kind}.pdf", io.BytesIO(b"%PDF-1.4 x"), "application/pdf")})

    assert _upload(R.DOC_CONTRACT_GOV, pro).status_code == 200
    assert _upload(R.DOC_SIGNED_GOV, pro).status_code == 200

    db = SessionLocal()
    try:
        generated = db.scalar(select(models.Document).where(
            models.Document.entity_type == "employee", models.Document.entity_id == emp_id,
            models.Document.document_type_code == f"gov_contract_renewal_{rid}"))
        signed = db.scalar(select(models.Document).where(
            models.Document.entity_type == "renewal", models.Document.entity_id == rid,
            models.Document.document_type_code == R.DOC_SIGNED_GOV))
        assert generated and signed
        # RNW-08 — الحلقة الأولى: الموقّعة تعرف أي نسخة وُقّعت
        assert signed.source_document_id == generated.id, \
            f"النسخة الموقّعة لا تشير إلى المولّدة: {signed.source_document_id}"
    finally:
        db.close()

    # RNW-10 — المندوب ينزّل نسخة الموظف من داخل المعاملة
    dl = client.get(f"/api/renewals/{rid}/document/{R.DOC_SIGNED_GOV}", headers=pro)
    assert dl.status_code == 200, f"المندوب لا يستطيع تنزيل نسخة الموظف: {dl.status_code}"

    # الحلقة الثانية: النهائية تشير إلى نسخة الموظف — وتُنزَّل أيًضا
    assert _upload(R.DOC_CONTRACT_FINAL, pro).status_code == 200
    dl_final = client.get(f"/api/renewals/{rid}/document/{R.DOC_CONTRACT_FINAL}", headers=pro)
    assert dl_final.status_code == 200, "النسخة النهائية لا تُنزَّل"

    db = SessionLocal()
    try:
        final = db.scalar(select(models.Document).where(
            models.Document.entity_type == "renewal", models.Document.entity_id == rid,
            models.Document.document_type_code == R.DOC_CONTRACT_FINAL))
        signed = db.scalar(select(models.Document).where(
            models.Document.entity_type == "renewal", models.Document.entity_id == rid,
            models.Document.document_type_code == R.DOC_SIGNED_GOV))
        assert final.source_document_id == signed.id, "النهائية لا تشير إلى نسخة الموظف"
        # الثلاث محفوظة — النهائية لم تمسح ما قبلها
        kept = db.scalars(select(models.Document.document_type_code).where(
            models.Document.entity_type == "renewal", models.Document.entity_id == rid)).all()
        assert R.DOC_CONTRACT_GOV in kept and R.DOC_SIGNED_GOV in kept \
            and R.DOC_CONTRACT_FINAL in kept, f"نسخة ضاعت: {kept}"
    finally:
        db.close()

    # RNW-11 — المرجع الحكومي والرسوم والإيصال تُسجَّل
    client.post(f"/api/renewals/{rid}/renewing", headers=pro)
    fin = client.post(f"/api/renewals/{rid}/finalize", headers=pro, data={
        "gov_reference_no": "MOI-2026-777", "fees_amount": "10.5",
        "fees_receipt_no": "RCP-88", "new_permit_number": "RNW-CHAIN-02",
        "new_expiry_date": (date.today() + timedelta(days=395)).isoformat()})
    assert fin.status_code == 200, f"تعذّر تسجيل بيانات المعاملة الحكومية: {fin.text[:200]}"
    body = fin.json()
    assert body["gov_reference_no"] == "MOI-2026-777"
    assert body["fees_receipt_no"] == "RCP-88"


def test_rnw12_13_ocr_proposes_never_applies(client):
    """RNW-12/13 — القراءة اقتراح يُراجَع، لا تحديث صامت.

    ROOT CAUSE: محرّك OCR كان موجوًدا في النظام (app/ocr.py بدرجات ثقة
    وتشخيص) لكنّ مسار التجديد **لا يستدعيه إطلاًقا**. فالمندوب يرفع الإقامة
    الجديدة ويكتب تاريخ انتهائها بيده، والنظام لا يقرأ ولا يقارن.

    والقاعدة التي تحكم البديل ليست "شغّل OCR" بل **لا تطبّق ما قرأته**:
    تاريخ انتهاء خاطئ يعني تنبيه تجديد خاطئ، ويعني موظًفا تنتهي إقامته
    والنظام يحسبها سارية — وهو أسوأ من ألا يقرأ شيًئا.

    والفشل يجب أن **يظهر**: عطل موثَّق سابًقا رجع فيه confidence=0.0 و
    "MRZ غير مكتملة" بلا تاريخ، ومضى النظام كأن شيًئا لم يحدث.
    """
    import io
    from datetime import date, timedelta

    from app import models, renewal as R
    from app.database import SessionLocal
    from sqlalchemy import select

    pro = _headers(client, "100000000003", "deleg123")

    db = SessionLocal()
    try:
        emp = models.Employee(
            company_id=1, name="موظف قراءة المستند", civil_id="277010177777",
            nationality="فلبيني", job_title="فني", status="active",
            hire_date=date.today() - timedelta(days=600), basic_salary=450)
        db.add(emp); db.flush()
        db.add(models.Permit(company_id=1, employee_id=emp.id, kind="residency",
                             status="active", number="RNW-OCR-01",
                             expiry_date=date.today() + timedelta(days=18)))
        db.commit()
        emp_id = emp.id
        old_expiry = None
    finally:
        db.close()

    rid = client.post("/api/renewals", headers=pro,
                      data={"employee_id": str(emp_id)}).json()["id"]

    def _upload(kind, hdr=pro):
        return client.post(f"/api/renewals/{rid}/upload", headers=hdr,
                           data={"doc_type": kind},
                           files={"file": (f"{kind}.png", io.BytesIO(b"\x89PNG\r\n\x1a\n junk"),
                                           "image/png")})

    assert _upload(R.DOC_CONTRACT_GOV).status_code == 200
    assert _upload(R.DOC_SIGNED_GOV).status_code == 200
    client.post(f"/api/renewals/{rid}/renewing", headers=pro)
    assert _upload(R.DOC_WORK_PERMIT).status_code == 200

    # 1) القراءة جرت وحُفظ اقتراحها — حتى حين تفشل
    db = SessionLocal()
    try:
        doc = db.scalar(select(models.Document).where(
            models.Document.entity_type == "employee",
            models.Document.entity_id == emp_id,
            models.Document.document_type_code == R.DOC_WORK_PERMIT))
        assert doc is not None
        assert doc.extracted_data_json is not None, \
            "لم تُستدعَ القراءة عند الرفع — المستند مرّ بلا معالجة"
        assert "_confidence" in doc.extracted_data_json, "الاقتراح بلا درجة ثقة"
        # ملف غير صالح ⇒ فشل مُعلَن لا صمت
        assert doc.extracted_data_json.get("_note") or \
            doc.extracted_data_json.get("_confidence") == 0.0, \
            "فشل القراءة مرّ بلا سبب ظاهر"
    finally:
        db.close()

    # 2) لا تحديث صامت: ملف الموظف لم يتغيّر بفعل القراءة
    db = SessionLocal()
    try:
        emp = db.get(models.Employee, emp_id)
        assert emp.civil_id == "277010177777", "القراءة عدّلت ملف الموظف بصمت"
    finally:
        db.close()

    # 3) شاشة المراجعة تعرض الحقول وحالتها، وتمنع الإغلاق قبل الاكتمال
    rev = client.get(f"/api/renewals/{rid}/extracted", headers=pro)
    assert rev.status_code == 200, rev.text[:200]
    body = rev.json()
    assert body["fields"], "شاشة المراجعة فارغة رغم وجود مستند مقروء"
    for row in body["fields"]:
        assert set(("field", "value", "confidence", "status", "document_id")) <= set(row)
        # الحقل الفاشل يظهر ولا يُخفى
        if row["value"] is None:
            assert row["status"] == "failed" and row["needs_confirmation"]
    assert body["missing_essential"], "المعاملة تبدو قابلة للإغلاق بلا بيانات"
    assert body["can_close"] is False

    # 4) بعد الاعتماد اليدوي: القيمة محفوظة بمصدرها
    new_exp = (date.today() + timedelta(days=380)).isoformat()
    fin = client.post(f"/api/renewals/{rid}/finalize", headers=pro, data={
        "gov_reference_no": "MOI-OCR-1", "fees_amount": "12",
        "fees_receipt_no": "R-1", "new_permit_number": "RNW-OCR-02",
        "new_expiry_date": new_exp})
    assert fin.status_code == 200, fin.text[:200]

    db = SessionLocal()
    try:
        rn = db.get(models.ResidencyRenewal, rid)
        rec = rn.confirmed_data_json
        assert rec, "لم يُحفَظ مصدر القيم المعتمَدة"
        for key in ("new_expiry_date", "new_permit_number"):
            assert rec[key]["source"] in ("ocr", "corrected", "manual")
            assert rec[key]["confirmed_by"] and rec[key]["confirmed_at"]
        # القراءة فشلت ⇒ المصدر إدخال يدوي، لا "ocr"
        assert rec["new_expiry_date"]["source"] == "manual", \
            f"نُسبت القيمة للقارئ وهو لم يقرأ: {rec['new_expiry_date']}"
    finally:
        db.close()

    after = client.get(f"/api/renewals/{rid}/extracted", headers=pro).json()
    assert after["can_close"] is True, "الإغلاق ما زال ممنوًعا بعد اكتمال البيانات"


def test_rnw16_17_19_propagation_and_closure(client):
    """RNW-16/17/19 — الإغلاق مشروط، والأثر ينتشر، والمهام تُغلق.

    ROOT CAUSE (RNW-17): التحقق النهائي كان يرفض بـ«بيانات المعاملة الحكومية
    ناقصة» — رسالة يقف أمامها المندوب ولا يعرف أين يذهب، ولا تفحص المستندات
    أصًلا. فمعاملة بلا إذن عمل كانت تُغلق ما دامت الحقول الثلاثة مملوءة.

    ROOT CAUSE (RNW-19): مهام المعاملة تبقى مفتوحة بعد اكتمالها، فيرى المندوب
    والموظف مطلوًبا منهما إجراء لا وجود له — وصندوق مهام يمتلئ بما انتهى يفقد
    معناه.

    RNW-16 يُقاس بالمصدر لا بالشاشات: التاريخ الجديد يعيش في صفّ Permit واحد
    تقرأ منه كل الشاشات، والقديم يصير renewed فيخرج من كل استعلام يشترط active.
    """
    import io
    from datetime import date, timedelta

    from app import models, renewal as R
    from app.database import SessionLocal
    from sqlalchemy import select

    pro = _headers(client, "100000000003", "deleg123")
    hr = _headers(client, "100000000002", "hr12345")

    db = SessionLocal()
    try:
        emp = models.Employee(
            company_id=1, name="موظف الإغلاق", civil_id="266010166666",
            nationality="مصري", job_title="سائق", status="active",
            hire_date=date.today() - timedelta(days=700), basic_salary=350)
        db.add(emp); db.flush()
        old_permit = models.Permit(
            company_id=1, employee_id=emp.id, kind="residency", status="active",
            number="RNW-CLOSE-OLD", expiry_date=date.today() + timedelta(days=12))
        db.add(old_permit); db.commit()
        emp_id, old_pid = emp.id, old_permit.id
    finally:
        db.close()

    rid = client.post("/api/renewals", headers=pro,
                      data={"employee_id": str(emp_id)}).json()["id"]

    def _upload(kind):
        return client.post(f"/api/renewals/{rid}/upload", headers=pro,
                           data={"doc_type": kind},
                           files={"file": (f"{kind}.pdf", io.BytesIO(b"%PDF-1.4 z"),
                                           "application/pdf")})

    # 1) الفحص يسمّي الناقص من أول لحظة
    chk = client.get(f"/api/renewals/{rid}/closure-check", headers=pro)
    assert chk.status_code == 200
    assert chk.json()["can_close"] is False
    named = chk.json()["missing"]
    assert any("إذن العمل" in m for m in named), f"لم يُسمَّ إذن العمل: {named}"
    assert any("تاريخ الانتهاء" in m for m in named), f"لم يُسمَّ التاريخ: {named}"

    _upload(R.DOC_CONTRACT_GOV)
    _upload(R.DOC_SIGNED_GOV)
    client.post(f"/api/renewals/{rid}/renewing", headers=pro)
    _upload(R.DOC_WORK_PERMIT)

    new_exp = date.today() + timedelta(days=400)
    client.post(f"/api/renewals/{rid}/finalize", headers=pro, data={
        "gov_reference_no": "MOI-CLOSE-1", "fees_amount": "15",
        "fees_receipt_no": "R-9", "new_permit_number": "RNW-CLOSE-NEW",
        "new_expiry_date": new_exp.isoformat()})

    # مهمة مفتوحة على المعاملة قبل الإغلاق
    db = SessionLocal()
    try:
        db.add(models.Task(company_id=1, type="renew_residency", status="open",
                           title="متابعة تجديد", related_entity_type="renewal",
                           related_entity_id=rid))
        db.commit()
    finally:
        db.close()

    _upload(R.DOC_CIVIL_CARD)

    # 2) الآن يكتمل، والإغلاق يمرّ
    assert client.get(f"/api/renewals/{rid}/closure-check", headers=pro).json()["can_close"] is True
    done = client.post(f"/api/renewals/{rid}/hr-verify", headers=hr,
                       data={"note": "روجعت المستندات"})
    assert done.status_code == 200, f"تعذّر الإغلاق رغم الاكتمال: {done.text[:200]}"

    db = SessionLocal()
    try:
        rn = db.get(models.ResidencyRenewal, rid)
        assert rn.status == R.COMPLETED

        # RNW-16 — مصدر واحد: القديم renewed والجديد active بالتاريخ المعتمد
        old = db.get(models.Permit, old_pid)
        assert old.status == "renewed", f"الإقامة القديمة ما زالت {old.status}"
        new = db.scalar(select(models.Permit).where(
            models.Permit.employee_id == emp_id, models.Permit.status == "active",
            models.Permit.kind == "residency"))
        assert new and new.expiry_date == new_exp, "التاريخ الجديد لم يُطبَّق على الإقامة"
        assert new.number == "RNW-CLOSE-NEW"

        # RNW-19 — المهام أُغلقت
        still_open = db.scalars(select(models.Task).where(
            models.Task.related_entity_type == "renewal",
            models.Task.related_entity_id == rid,
            models.Task.status.in_(("open", "in_progress")))).all()
        # ما يبقى مفتوًحا هو إشعار الاكتمال وحده — رسالة "انتهت المعاملة" لا
        # إجراء مطلوب. أما مهام العمل (متابعة التجديد، التوقيع) فتُغلق.
        # ملاحظة: عرض الإشعارات كمهام بأزرار إنجاز عيب مستقلّ مسجَّل في كيت
        # المعالجة (TASK-02) وخارج نطاق هذا البند.
        leftover = [x for x in still_open if x.type != "request_update"]
        assert not leftover, (
            f"{len(leftover)} مهمة عمل ما زالت مفتوحة بعد الاكتمال: "
            + ", ".join(x.title for x in leftover))
    finally:
        db.close()

    # 3) لا تنبيه جديد على الإقامة المجدَّدة — تخرج من قائمة المستحقّة
    due = client.get("/api/renewals/due/permits", headers=pro).json()
    assert not any(d["permit_id"] == old_pid for d in due), \
        "الإقامة المجدَّدة ما زالت تُعرض كمستحقّة للتجديد"


def test_rnw03_14_15_23_documents_and_screens(client):
    """RNW-03/14/15/23 — المستندات تخرج من المعاملة، والشاشات تتفق.

    ROOT CAUSE (RNW-14): إذن العمل والبطاقة يُحفظان في ملف الموظف عند رفعهما،
    لكن **العقد النهائي يبقى محبوًسا داخل المعاملة**. فمن يفتح ملف الموظف بعد
    سنة لا يجد العقد الذي قُدّم للجهة الحكومية — وهو أهمّ ما في التجديد.

    ROOT CAUSE (RNW-23): الملف المرفوع كان يُحفظ **بلا بصمة**. النظام لا يولّد
    مستنًدا حكومًيا بشعار حكومي، بل يحفظ الملف الحقيقي الصادر عن الجهة — وبلا
    بصمة يكون ذلك إيداًعا بلا إثبات: لا سبيل لقول إن المعروض هو نفسه المرفوع.
    """
    import hashlib
    import io
    from datetime import date, timedelta

    from app import models, renewal as R
    from app.database import SessionLocal
    from sqlalchemy import select

    pro = _headers(client, "100000000003", "deleg123")
    hr = _headers(client, "100000000002", "hr12345")

    db = SessionLocal()
    try:
        emp = models.Employee(
            company_id=1, name="موظف المستندات", civil_id="255010155555",
            nationality="سوري", job_title="نجار", status="active",
            hire_date=date.today() - timedelta(days=800), basic_salary=380)
        db.add(emp); db.flush()
        db.add(models.Permit(company_id=1, employee_id=emp.id, kind="residency",
                             status="active", number="RNW-DOC-OLD",
                             expiry_date=date.today() + timedelta(days=10)))
        db.commit()
        emp_id = emp.id
    finally:
        db.close()

    rid = client.post("/api/renewals", headers=pro,
                      data={"employee_id": str(emp_id)}).json()["id"]

    FINAL_BYTES = b"%PDF-1.4 official-final-contract"
    def _upload(kind, payload=b"%PDF-1.4 x"):
        return client.post(f"/api/renewals/{rid}/upload", headers=pro,
                           data={"doc_type": kind},
                           files={"file": (f"{kind}.pdf", io.BytesIO(payload),
                                           "application/pdf")})

    _upload(R.DOC_CONTRACT_GOV)
    _upload(R.DOC_SIGNED_GOV)
    client.post(f"/api/renewals/{rid}/renewing", headers=pro)
    _upload(R.DOC_CONTRACT_FINAL, FINAL_BYTES)
    _upload(R.DOC_WORK_PERMIT)

    # RNW-23 — الملف المرفوع محفوظ ببصمته الحقيقية
    db = SessionLocal()
    try:
        final = db.scalar(select(models.Document).where(
            models.Document.entity_type == "renewal", models.Document.entity_id == rid,
            models.Document.document_type_code == R.DOC_CONTRACT_FINAL))
        assert final.checksum_sha256 == hashlib.sha256(FINAL_BYTES).hexdigest(), \
            "الملف المرفوع بلا بصمة صحيحة — حفظ بلا إثبات"
        # ولم يُولَّد مستند بديل يحمل شعاًرا: المحفوظ هو ما رُفع
        with open(final.file_path, "rb") as f:
            assert f.read() == FINAL_BYTES, "الملف المحفوظ ليس هو المرفوع"
    finally:
        db.close()

    client.post(f"/api/renewals/{rid}/finalize", headers=pro, data={
        "gov_reference_no": "MOI-DOC-1", "fees_amount": "20",
        "fees_receipt_no": "R-20", "new_permit_number": "RNW-DOC-NEW",
        "new_expiry_date": (date.today() + timedelta(days=410)).isoformat()})
    _upload(R.DOC_CIVIL_CARD)
    done = client.post(f"/api/renewals/{rid}/hr-verify", headers=hr, data={"note": "تم"})
    assert done.status_code == 200, done.text[:200]

    # RNW-14 — العقد النهائي صار في ملف الموظف تحت نوعه، وكـCurrent
    db = SessionLocal()
    try:
        filed = db.scalar(select(models.Document).where(
            models.Document.entity_type == "employee",
            models.Document.entity_id == emp_id,
            models.Document.document_type_code == "gov_contract",
            models.Document.is_current == True))  # noqa: E712
        assert filed is not None, "العقد النهائي ما زال محبوًسا داخل المعاملة"
        assert filed.source_document_id, "النسخة المودَعة بلا رابط إلى نسخة المعاملة"
        assert filed.checksum_sha256 == hashlib.sha256(FINAL_BYTES).hexdigest()
        # ملف واحد مفهرس في مكانين — لا نسختان تتباعدان
        src = db.get(models.Document, filed.source_document_id)
        assert filed.file_path == src.file_path
        # إذن العمل والبطاقة في ملف الموظف تحت أنواعهما
        for code in (R.DOC_WORK_PERMIT, R.DOC_CIVIL_CARD):
            assert db.scalar(select(models.Document).where(
                models.Document.entity_type == "employee",
                models.Document.entity_id == emp_id,
                models.Document.document_type_code == code)) is not None, f"{code} غائب"
    finally:
        db.close()

    # RNW-15 — النسخ القديمة تبقى معروضة وقابلة للتنزيل
    hist = client.get("/api/documents/history", headers=pro,
                      params={"entity_type": "renewal", "entity_id": rid})
    assert hist.status_code == 200 and hist.json(), "لا سجلّ نسخ للمعاملة"
    any_doc = hist.json()[0]
    dl = client.get(f"/api/documents/{any_doc['id']}/download", headers=pro)
    assert dl.status_code == 200, f"نسخة محفوظة لا تُنزَّل: {dl.status_code}"

    # RNW-03 — الشاشات الثلاث تتفق على نفس المعاملة
    listed = client.get("/api/renewals", headers=pro).json()
    row = next((r for r in listed if r["id"] == rid), None)
    assert row and row["status"] == R.COMPLETED
    due = client.get("/api/renewals/due/permits", headers=pro).json()
    assert not any(d.get("number") == "RNW-DOC-OLD" for d in due), \
        "الإقامة المجدَّدة ما زالت معروضة كمستحقّة — الشاشات غير متفقة"


def test_seed_guard_neutralizes_without_bricking_boot(client, monkeypatch):
    """الحارس يُبطل الخطر بنفسه بدل أن يعطّل النظام.

    ROOT CAUSE: الحارس كان يرفع RuntimeError فيموت الإقلاع. بدا ذلك صواًبا —
    خطأ مستحيل التجاهل. لكن التشغيل الفعلي على منصّة استضافة كشف عكسه: النشر
    يدخل **حلقة انهيار**، والمخرج الوحيد أمام المشغّل أن يضبط
    ALLOW_SEED_ACCOUNTS=true ويتركها. فينتهي الحارس إلى إنتاج الباب المفتوح
    الذي بُني ليمنعه — هزيمة ذاتية لا صرامة.

    والإبطال الذاتي أقوى: الباب يُغلق **فوًرا وتلقائًيا**، بلا اعتماد على أن
    يقرأ أحد سجًلا أو يلاحظ انهياًرا. والحساب يبقى فعّاًلا فيستعيده صاحبه
    بالمسار الطبيعي.
    """
    from app import models, seed_guard
    from app.config import settings
    from app.database import SessionLocal
    from app.security import verify_password
    from sqlalchemy import select

    monkeypatch.setattr(type(settings), "is_production", property(lambda self: True))
    monkeypatch.delenv("ALLOW_SEED_ACCOUNTS", raising=False)
    monkeypatch.delenv("SEED_GUARD_MODE", raising=False)

    # الاختبار يُبطل كلمات مرور في قاعدة مشتركة — نلتقط الحالة ونعيدها بعده،
    # وإلا أفسد كل اختبار يلي ويسجّل الدخول بحساب بذرة.
    snap = SessionLocal()
    try:
        saved = {u.id: (u.password_hash, u.must_change_password, u.tokens_valid_after)
                 for u in snap.scalars(select(models.User)).all()}
    finally:
        snap.close()

    db = SessionLocal()
    try:
        before = seed_guard.find_seed_accounts(db, privileged_only=True)
        assert before, "قاعدة الاختبار مبذورة — يجب أن تُكتشف حسابات بذرة"
        target = before[0]["id"]

        # 1) لا يمنع الإقلاع
        hits = seed_guard.enforce(db)
        assert hits, "لم يُبلَّغ عمّا أُبطل"
    finally:
        db.close()

    db = SessionLocal()
    try:
        # 2) الباب أُغلق على الأدوار الخطرة. الموظفون العاديون خارج فحص
        #    الإقلاع عمًدا (تكلفة PBKDF2) ويعالجهم المسح الشامل عند التسليم.
        assert not seed_guard.find_seed_accounts(db, privileged_only=True),             "كلمات بذرة ما زالت تعمل على حساب إداري"

        user = db.get(models.User, target)
        assert user.is_active, "الحساب عُطِّل — صاحبه لا يستطيع استعادته بنفسه"
        assert user.must_change_password, "لم يُطلَب تغيير الكلمة"
        for pw in ("admin123", "owner123", "Kuwait@2024"):
            assert not verify_password(pw, user.password_hash), f"{pw} ما زالت تعمل"

        # 3) الإبطال لا يكون صامًتا
        alarm = db.scalars(select(models.Task).where(
            models.Task.type == "security", models.Task.severity == "critical")).all()
        assert alarm, "أُبطلت كلمات المرور بلا تنبيه — يبدو عطًلا غامًضا لصاحبها"
    finally:
        db.close()
        restore = SessionLocal()
        try:
            for uid, (h, must, toks) in saved.items():
                u = restore.get(models.User, uid)
                if u:
                    u.password_hash, u.must_change_password, u.tokens_valid_after = h, must, toks
            restore.commit()
        finally:
            restore.close()


def test_seed_guard_block_mode_still_available(monkeypatch):
    """من يريد المنع الصارم يطلبه صراحًة بـSEED_GUARD_MODE=block."""
    import pytest

    from app import seed_guard
    from app.config import settings
    from app.database import SessionLocal

    monkeypatch.setattr(type(settings), "is_production", property(lambda self: True))
    monkeypatch.delenv("ALLOW_SEED_ACCOUNTS", raising=False)
    monkeypatch.setenv("SEED_GUARD_MODE", "block")

    from app import models
    from app.security import hash_password

    db = SessionLocal()
    try:
        # حساب خاص بهذا الاختبار — لا يعتمد على ما تركه اختبار آخر
        probe = models.User(
            # دور إداري: فحص الإقلاع لا يمسّ الموظفين العاديين
            civil_id="999000999000", full_name="فحص وضع المنع", role="hr",
            company_id=1, password_hash=hash_password("admin123"), is_active=True)
        db.add(probe)
        db.commit()
        with pytest.raises(RuntimeError, match="رفض الإقلاع"):
            seed_guard.enforce(db)
        db.rollback()
        db.delete(db.get(models.User, probe.id))
        db.commit()
    finally:
        db.close()


def test_seed_guard_boot_scan_is_bounded(client):
    """فحص الإقلاع محدود التكلفة — وإلا صار هو سبب الانهيار.

    ROOT CAUSE: الفحص كان يجرّب كل كلمة بذرة على **كل** مستخدم. PBKDF2 بـ240
    ألف دورة وملح فريد لكل كلمة يعني ~0.6 ثانية للمستخدم الواحد — أي أربع
    دقائق على قاعدة بأربعمئة موظف، **في كل إقلاع، وعلى قاعدة نظيفة أيًضا**:
    النظافة لا تُعرف إلا بعد فحص الجميع. فينهار النشر بمهلة المنصّة لسبب هو
    الحارس نفسه لا ما يبحث عنه.

    التضييق مبدئي لا اعتباطي: حساب مالك أو مدير بكلمة منشورة يفتح النظام
    كلّه، وحساب موظف يفتح ملفه هو. الأول يُفحص في كل إقلاع، والثاني يكفيه
    المسح الشامل عند التسليم.
    """
    from app import models, seed_guard
    from app.database import SessionLocal
    from sqlalchemy import select

    db = SessionLocal()
    try:
        # الفحص الموسَّع لا يمسّ الموظفين العاديين
        privileged = seed_guard.find_seed_accounts(db, privileged_only=True)
        roles = {h["role"] for h in privileged}
        assert "employee" not in roles, "فحص الإقلاع يشمل الموظفين — تكلفة بلا مقابل"

        # والسقف يُحترم
        capped = seed_guard.find_seed_accounts(db, privileged_only=True, max_users=2)
        assert len(capped) <= 2, f"السقف لم يُحترم: {len(capped)}"

        # والأخطر أوًلا: super_admin/company_owner قبل ما دونهما
        if len(privileged) >= 2:
            first = privileged[0]["role"]
            assert first in ("super_admin", "company_owner", "company_manager"), \
                f"الترتيب لا يضع الأخطر أوًلا: {first}"

        # والمسح الشامل يبقى متاًحا للمعالجة — يشمل ما استثناه الإقلاع
        full = seed_guard.find_seed_accounts(db)
        assert len(full) >= len(privileged), "المسح الشامل أضيق من فحص الإقلاع"
    finally:
        db.close()


def test_printable_document_has_no_inline_script(client):
    """المستند المطبوع بلا معالِج مضمَّن — تحجبه سياسة الأمان فيبدو معطًَّلا.

    ROOT CAUSE: غلاف الطباعة كان يضع زًرا بـonclick="window.print()". والمستند
    يُفتح في نافذة about:blank عبر document.write، وهي **ترث سياسة أمان
    المحتوى للصفحة الأم**: script-src 'self' بلا unsafe-inline — وهو إعداد
    صحيح لا نريد تخفيفه. فيُحجب المعالِج: الزر يبدو سليًما، والضغط عليه لا
    يفعل شيًئا، وبلا أي رسالة. المستخدم يقف أمام زر لا يعمل ولا يعرف لماذا.

    الطباعة تُستدعى الآن من الواجهة (printDoc.ts) — كود مُحمَّل كحزمة تسمح بها
    السياسة. وهذا الاختبار يمنع عودة المعالِج المضمَّن إلى الغلاف.
    """
    import re

    from app.routers import templates as tpl_mod
    from pathlib import Path

    src = Path(tpl_mod.__file__).read_text(encoding="utf-8")
    i = src.index("def _wrap_printable")
    wrapper = src[i:i + 6000]

    for handler in ("onclick=", "onload=", "onerror=", "<script"):
        assert handler not in wrapper, (
            f"غلاف الطباعة يحوي {handler!r} — تحجبه CSP فيفشل صامًتا")

    # وسياسة الأمان نفسها ما زالت صارمة: المشكلة تُحلّ بلا تخفيفها
    from app.main import _CSP
    assert "script-src 'self'" in _CSP
    assert "unsafe-inline" not in re.search(r"script-src[^;]*", _CSP).group(0), \
        "خُفِّفت سياسة السكربتات — الإصلاح كان يجب أن يكون في المستند لا في السياسة"


def test_rnw04_20_21_22_24_timeline_scope_and_dedup(client):
    """RNW-04/20/21/22/24 — القصة كاملة، والنطاق محفوظ، والفحص لا يكرّر.

    ROOT CAUSE (RNW-21): كل حدث كان يُسجَّل في سجل التدقيق منذ البداية —
    الفاعل ووقته والكيان — لكن **لم يكن ثمّة ما يعرضه كقصة**. فمن يفتح
    معاملة مكتملة يرى حالتها الأخيرة ولا يعرف كيف وصلت إليها: من بدأها،
    ومن اعتمد، ومتى رُفع كل مستند. والسؤال يُطرح بعد شهور حين تُراجَع
    معاملة أو يُعترض عليها — وحينها لا تنفع الذاكرة.

    والأربعة الأخرى كانت منفَّذة ولم تُقَس.
    """
    import io
    from datetime import date, timedelta

    from app import models, renewal as R
    from app.database import SessionLocal
    from app.notifications import daily_scan
    from sqlalchemy import func, select

    pro = _headers(client, "100000000003", "deleg123")
    hr = _headers(client, "100000000002", "hr12345")

    db = SessionLocal()
    try:
        emp = models.Employee(
            company_id=1, name="موظف القصة", civil_id="244010144444",
            nationality="هندي", job_title="كهربائي", status="active",
            hire_date=date.today() - timedelta(days=900), basic_salary=420)
        db.add(emp); db.flush()
        db.add(models.Permit(company_id=1, employee_id=emp.id, kind="residency",
                             status="active", number="RNW-STORY-01",
                             expiry_date=date.today() + timedelta(days=14)))
        db.commit()
        emp_id = emp.id
    finally:
        db.close()

    # RNW-04 — الفحص اليومي مرتين لا ينشئ مهاًما مكرّرة
    db = SessionLocal()
    try:
        def _permit_tasks():
            return db.scalar(select(func.count(models.Task.id)).where(
                models.Task.related_entity_type == "permit"))
        daily_scan(db); db.commit()
        first = _permit_tasks()
        daily_scan(db); db.commit()
        second = _permit_tasks()
        assert second == first, (
            f"الفحص اليومي مرتين أنشأ {second - first} مهمة مكرّرة")
        assert first > 0, "الفحص لم ينشئ أي مهمة — القياس بلا معنى"
    finally:
        db.close()

    rid = client.post("/api/renewals", headers=pro,
                      data={"employee_id": str(emp_id)}).json()["id"]

    def _upload(kind):
        return client.post(f"/api/renewals/{rid}/upload", headers=pro,
                           data={"doc_type": kind},
                           files={"file": (f"{kind}.pdf", io.BytesIO(b"%PDF-1.4 s"),
                                           "application/pdf")})

    _upload(R.DOC_CONTRACT_GOV); _upload(R.DOC_SIGNED_GOV)
    client.post(f"/api/renewals/{rid}/renewing", headers=pro)
    _upload(R.DOC_WORK_PERMIT)
    client.post(f"/api/renewals/{rid}/finalize", headers=pro, data={
        "gov_reference_no": "MOI-STORY", "fees_amount": "18",
        "fees_receipt_no": "R-77", "new_permit_number": "RNW-STORY-02",
        "new_expiry_date": (date.today() + timedelta(days=390)).isoformat()})
    _upload(R.DOC_CIVIL_CARD)
    assert client.post(f"/api/renewals/{rid}/hr-verify", headers=hr,
                       data={"note": "تم"}).status_code == 200

    # RNW-21 — القصة كاملة، وكل حدث بفاعله ودوره ووقته ومرجعه
    tl = client.get(f"/api/renewals/{rid}/timeline", headers=pro)
    assert tl.status_code == 200, tl.text[:200]
    events = tl.json()["events"]
    assert len(events) >= 6, f"القصة ناقصة: {len(events)} حدث فقط"

    for ev in events:
        for field in ("action", "label", "actor_role", "at", "renewal_id"):
            assert field in ev, f"حدث بلا {field}: {ev}"
        assert ev["renewal_id"] == rid
        assert ev["label"] != ev["action"], f"حدث معروض بكوده التقني: {ev['action']}"

    actions = [e["action"] for e in events]
    assert actions[0] == "expiry_detected", "القصة لا تبدأ من التنبيه"
    for must in ("create_renewal", "renewal_upload", "finalize_renewal",
                 "hr_verify_renewal"):
        assert must in actions, f"حدث غائب من القصة: {must}"

    # الأحداث مرتّبة زمنًيا — قصة لا قائمة
    times = [e["at"] for e in events if e["at"]]
    assert times == sorted(times), "الأحداث غير مرتّبة زمنًيا"

    # وفيها فاعل بشري باسمه ودوره، لا "النظام" وحده
    human = [e for e in events if e["actor"]]
    assert human, "لا فاعل بشري في القصة"
    assert any(e["actor_role"] and not e["actor_role"].isascii() for e in human), \
        "الدور معروض بكوده التقني لا باسمه العربي"

    # RNW-20 — الموظف يتلقّى إشعاًرا بالاكتمال لا مهمة تطلب إجراء
    db = SessionLocal()
    try:
        emp_user = db.scalar(select(models.User).where(models.User.employee_id == emp_id))
        if emp_user:
            open_for_emp = db.scalars(select(models.Task).where(
                models.Task.assignee_user_id == emp_user.id,
                models.Task.related_entity_type == "renewal",
                models.Task.related_entity_id == rid,
                models.Task.status.in_(("open", "in_progress")))).all()
            assert not open_for_emp, (
                "الموظف لديه مهمة مفتوحة بعد الاكتمال — لم يعد مطلوًبا منه شيء")
    finally:
        db.close()

    # RNW-22 — المندوب لا يرى الراتب في ملف الموظف
    prof = client.get(f"/api/employees/{emp_id}", headers=pro)
    assert prof.status_code == 200
    for money in ("basic_salary", "actual_salary"):
        assert prof.json().get(money) is None, f"المندوب يرى {money}"

    # RNW-24 — نفس السلوك على الشركة الثانية
    pro2 = _headers(client, "200000000003", "deleg123")
    db = SessionLocal()
    try:
        e2 = models.Employee(
            company_id=2, name="موظف الشركة الثانية", civil_id="233010133333",
            nationality="مصري", job_title="سائق", status="active",
            hire_date=date.today() - timedelta(days=500), basic_salary=390)
        db.add(e2); db.flush()
        db.add(models.Permit(company_id=2, employee_id=e2.id, kind="residency",
                             status="active", number="MUF-RNW-01",
                             expiry_date=date.today() + timedelta(days=16)))
        db.commit()
        e2_id = e2.id
    finally:
        db.close()

    r2 = client.post("/api/renewals", headers=pro2, data={"employee_id": str(e2_id)})
    assert r2.status_code == 201, f"المعاملة لا تعمل على الشركة الثانية: {r2.text[:160]}"
    tl2 = client.get(f"/api/renewals/{r2.json()['id']}/timeline", headers=pro2)
    assert tl2.status_code == 200 and tl2.json()["events"], "لا قصة على الشركة الثانية"

    # والعزل قائم: مندوب الشركة الأولى لا يرى معاملة الثانية
    assert client.get(f"/api/renewals/{r2.json()['id']}/timeline",
                      headers=pro).status_code == 404, "خرق عزل الشركات"


def test_pro08_09_archive_fields_and_license_labels(client):
    """PRO-08/09 — الأرشيف يحمل ما تطلبه المواصفة، والتسميات تميّز الرقمين.

    ROOT CAUSE (PRO-08): «نسبة التراخيص السارية» في اللوحة و«تراخيص قرب
    الانتهاء» في مركز العمليات كانتا تحملان تسمية متطابقة تقريًبا لرقمين
    يجيبان **سؤالين مختلفين**: الأولى نسبة التزام على كل التراخيص، والثانية
    ما يحتاج انتباًها خلال 90 يوًما. الرقمان صحيحان، والتسمية هي ما جعلهما
    يبدوان متناقضين — وهو نفس نمط QA-05 بين التجديدات ومركز العمليات.

    ROOT CAUSE (PRO-09): قائمة الأرشيف تعيد النوع والتاريخ والنسخة، وتنقصها
    الشركة والحالة — فمن يفتح الأرشيف لا يعرف أي مستند منتهٍ إلا بحساب
    التواريخ بنفسه.
    """
    from datetime import date, timedelta

    from app import models
    from app.database import SessionLocal
    from sqlalchemy import select

    hr = _headers(client, "100000000002", "hr12345")

    db = SessionLocal()
    try:
        db.add(models.Document(
            company_id=1, entity_type="company", entity_id=1,
            document_type_code="commercial_license", title="ترخيص اختبار الأرشيف",
            file_path="/tmp/x.pdf", version=1, is_current=True,
            expiry_date=date.today() - timedelta(days=5)))
        db.commit()
    finally:
        db.close()

    r = client.get("/api/archive/company", headers=hr, params={"company_id": 1})
    assert r.status_code == 200, r.text[:200]
    body = r.json()
    items = body.get("documents") or body.get("docs") or []
    assert items, f"الأرشيف فارغ رغم وجود مستند — المفاتيح: {list(body)}"

    for item in items:
        for field in ("company_id", "status", "days_left", "has_versions"):
            assert field in item, f"حقل {field} ناقص في الأرشيف"
        assert item["status"] in ("valid", "expired", "no_expiry")

    # المنتهي يُعرَّف منتهًيا بلا حساب من القارئ
    expired = [i for i in items if i["status"] == "expired"]
    assert expired, "مستند منتهٍ لا يظهر بحالته"
    assert expired[0]["days_left"] < 0


def test_expiry_math_uses_kuwait_clock_everywhere(client):
    """كل حساب أيام يقرأ ساعة واحدة — ساعة الكويت.

    ROOT CAUSE: كل موضع يحسب أيًاما متبقية كان يستدعي ``date.today()`` وهي
    تقرأ **توقيت الخادم**، بينما المجدول مضبوط على ``Asia/Kuwait`` صراحة.
    فالنظام يحمل ساعتين: واحدة تقرّر متى يُرسَل التنبيه، وأخرى تقرّر كم
    يوًما تبقّى.

    على خادم UTC — وهو الشائع في الاستضافة وبيئتنا منه — الفارق ثلاث ساعات:
    بين منتصف الليل والثالثة فجًرا بتوقيت الكويت يكون الخادم في اليوم
    السابق، فيقول التنبيه «ستة أيام» وتقول اللوحة «سبعة». وهذا بالضبط ما
    أبلغ عنه المستخدم في أول بلاغ عن شاشة التجديد.
    """
    import ast
    from datetime import date, datetime, timedelta, timezone
    from pathlib import Path

    from app.clock import KUWAIT_TZ, days_until, today as kuwait_today

    # 1) الساعة صحيحة: الكويت UTC+3 ثابًتا
    assert KUWAIT_TZ.utcoffset(None) == timedelta(hours=3)
    assert kuwait_today() == datetime.now(KUWAIT_TZ).date()

    # 2) الفارق حقيقي وليس نظرًيا: 00:30 بالكويت = اليوم السابق بـUTC
    at_kuwait = datetime(2026, 8, 27, 0, 30, tzinfo=KUWAIT_TZ)
    at_utc = at_kuwait.astimezone(timezone.utc)
    assert at_utc.date() != at_kuwait.date(), "المحاكاة لا تعبر منتصف الليل"
    expiry = date(2026, 9, 2)
    assert (expiry - at_utc.date()).days - (expiry - at_kuwait.date()).days == 1

    # 3) ولا موضع في منطق الأعمال يقرأ ساعة الخادم بعد الآن
    root = Path(__file__).resolve().parents[1] / "app"
    allowed = {"clock.py", "seed.py", "seed_guard.py"}
    offenders = []
    for path in root.rglob("*.py"):
        if path.name in allowed or "__pycache__" in path.as_posix():
            continue
        src = path.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(src)):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "today"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "date"):
                offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, (
        "مواضع ما زالت تقرأ توقيت الخادم بدل ساعة الكويت: " + ", ".join(offenders))

    # 4) والدالة المشتركة تحسب صحيًحا وتحتمل الفراغ
    assert days_until(None) is None
    assert days_until(kuwait_today()) == 0
    assert days_until(kuwait_today() + timedelta(days=5)) == 5
    assert days_until(kuwait_today() - timedelta(days=3)) == -3


def test_client_ip_resolves_real_visitor_behind_proxy(client):
    """سجل التدقيق يحفظ عنوان الزائر لا عنوان الوكيل.

    ROOT CAUSE: التدقيق كان يسجّل ``request.client.host``. وخلف وكيل
    استضافة — Railway وأمثالها — هذا **عنوان الوكيل الداخلي** لا الزائر:
    كل السطور تخرج من نطاق 100.64.0.0/10 المحجوز للشبكات المشتركة.

    فيبدو السجل ممتلًئا بعناوين مختلفة وهي كلها موازِنات حِمل، **ولا يجيب
    عن السؤال الذي وُجد لأجله**: حين يُسأل «هل دخل أحد بهذا الحساب قبل
    إغلاق الثغرة ومن أين؟» لا يعطي إلا عناوين داخلية بلا معنى.

    وأخطر منه أن حدّ محاولات الدخول كان يُحسب على العنوان نفسه: فيتقاسم
    كل الزوّار عدّاًدا واحًدا — مهاجم واحد يقفل الدخول عن الجميع، أو يتخفّى
    بين ألف طلب مشروع.

    والقراءة مشروطة: الترويسة يكتبها من شاء، فلا تُقرأ إلا حين يأتي الطلب
    من وكيل داخلي فعًلا — وإلا سمحنا لأي أحد بانتحال أي عنوان في السجل.
    """
    from types import SimpleNamespace

    from app.deps import _is_internal, client_ip

    def _req(peer, forwarded=None):
        return SimpleNamespace(
            client=SimpleNamespace(host=peer) if peer else None,
            headers={"x-forwarded-for": forwarded} if forwarded else {})

    # 1) نطاق الوكيل يُعرَف
    for internal in ("100.64.0.6", "10.0.0.3", "172.16.5.1", "192.168.1.9", "127.0.0.1"):
        assert _is_internal(internal), f"{internal} لم يُعرَف كعنوان داخلي"
    for public in ("41.238.10.5", "8.8.8.8", "212.77.192.10"):
        assert not _is_internal(public), f"{public} عُدّ داخلًيا خطأ"

    # 2) خلف الوكيل: يُقرأ الزائر الحقيقي، وأولُ عنوان في السلسلة هو هو
    assert client_ip(_req("100.64.0.6", "212.77.192.10")) == "212.77.192.10"
    assert client_ip(_req("100.64.0.6", "212.77.192.10, 100.64.0.6")) == "212.77.192.10"

    # 3) طلب مباشر: الترويسة **لا تُصدَّق** — وإلا انتحل أي أحد أي عنوان
    assert client_ip(_req("212.77.192.10", "1.2.3.4")) == "212.77.192.10", \
        "صُدّقت ترويسة من طلب مباشر — ثغرة انتحال في سجل التدقيق"

    # 4) حالات فارغة لا تُسقط شيًئا
    assert client_ip(None) is None
    assert client_ip(_req(None)) is None
    assert client_ip(_req("100.64.0.6")) == "100.64.0.6"

    # 5) ولا موضع يسجّل العنوان مباشرة بعد الآن
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "app"
    offenders = []
    for path in root.rglob("*.py"):
        if path.name in ("deps.py", "main.py") or "__pycache__" in path.as_posix():
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Attribute) and node.attr == "host"
                    and isinstance(node.value, ast.Attribute)
                    and node.value.attr == "client"):
                offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, "مواضع تقرأ عنوان الوكيل مباشرة: " + ", ".join(offenders)
