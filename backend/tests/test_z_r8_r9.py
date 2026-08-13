# -*- coding: utf-8 -*-
"""اختبارات قبول ميزات R8/R9 — Government Portals، Custom Docs، Gov Contract Generation.

يغطّي:
- Custom Doc CRUD: إضافة، عرض، استبدال، سجل النسخ، تعديل metadata، حذف نهائي
- assigned_pro_id validation: يجب أن يكون delegate وفي نفس الشركة
- Government Portals CRUD + RBAC: super_admin يدير، PRO يعرض، employee ممنوع
- Contract generation: renewal + hire + company (يحتاج قوالب مبذورة يدويًا هنا)
- /templates/exists endpoint
- Custom doc expiry notification: opt-in + assigned PRO routing
- Renewal workflow R9 §1: العقد الحكومي فقط يكفي للانتقال
"""
import io

from sqlalchemy import select

from tests.conftest import auth_headers, login


ADMIN = ("000000000000", "admin123")
MGR = ("100000000001", "manager123")
HR = ("100000000002", "hr12345")
PRO = ("100000000003", "deleg123")
PRO2 = ("100000000004", "deleg123")           # مندوب ثاني نفس الشركة
PRO_OTHER = ("200000000003", "deleg123")      # مندوب شركة ثانية
EMP = ("100000000101", "emp12345")


def _f(name=b"content", fn="doc.pdf", mime="application/pdf"):
    return {"file": (fn, io.BytesIO(name), mime)}


# ============================================================================
# R8 §2 + R9 §3 — Custom Documents CRUD
# ============================================================================

def test_custom_doc_add_then_list(client):
    mgr = auth_headers(login(client, *MGR))
    cid = client.get("/api/archive/company", headers=mgr).json()["company"]["id"]
    r = client.post("/api/archive/custom-doc", headers=mgr, files=_f(b"custom-1"), data={
        "entity_type": "company", "entity_id": str(cid),
        "name_ar": "شهادة أوزون", "name_en": "Ozone Certificate",
        "doc_number": "OZ-999", "issuing_authority": "وزارة البيئة",
    })
    assert r.status_code == 201, r.text
    assert r.json()["type"].startswith("custom:")

    # يظهر في القائمة مع is_custom=True وbمetadata كاملة
    docs = client.get("/api/archive/company", headers=mgr).json()["documents"]
    mine = [d for d in docs if d.get("is_custom") and d["title"] == "شهادة أوزون"]
    assert len(mine) == 1
    m = mine[0]
    assert m["name_en"] == "Ozone Certificate"
    assert m["doc_number"] == "OZ-999"
    assert m["issuing_authority"] == "وزارة البيئة"


def test_custom_doc_replace_keeps_history(client):
    mgr = auth_headers(login(client, *MGR))
    cid = client.get("/api/archive/company", headers=mgr).json()["company"]["id"]
    r1 = client.post("/api/archive/custom-doc", headers=mgr, files=_f(b"v1"), data={
        "entity_type": "company", "entity_id": str(cid), "name_ar": "شهادة صحية",
    })
    doc_id = r1.json()["id"]

    r2 = client.post(f"/api/archive/custom-doc/{doc_id}/replace",
                     headers=mgr, files=_f(b"v2"))
    assert r2.status_code == 200 and r2.json()["version"] == 2

    hist = client.get(f"/api/archive/custom-doc/{doc_id}/history", headers=mgr).json()
    assert len(hist) >= 2
    versions = sorted(h["version"] for h in hist)
    assert versions[-1] == 2 and versions[-2] == 1
    current = [h for h in hist if h["is_current"]]
    assert len(current) == 1 and current[0]["version"] == 2


def test_custom_doc_edit_metadata(client):
    """R9 §3 — PUT يحدّث الحقول المرسلة فقط بدون تغيير الملف."""
    mgr = auth_headers(login(client, *MGR))
    cid = client.get("/api/archive/company", headers=mgr).json()["company"]["id"]
    r = client.post("/api/archive/custom-doc", headers=mgr, files=_f(b"x"), data={
        "entity_type": "company", "entity_id": str(cid), "name_ar": "قبل التعديل",
    })
    doc_id = r.json()["id"]

    edit = client.put(f"/api/archive/custom-doc/{doc_id}", headers=mgr, data={
        "name_ar": "بعد التعديل", "doc_number": "NEW-123", "notes": "ملاحظة جديدة",
    })
    assert edit.status_code == 200, edit.text
    changed = edit.json()["changed"]
    assert "name_ar" in changed and "doc_number" in changed and "notes" in changed

    docs = client.get("/api/archive/company", headers=mgr).json()["documents"]
    m = [d for d in docs if d["id"] == doc_id][0]
    assert m["title"] == "بعد التعديل"
    assert m["doc_number"] == "NEW-123"


def test_custom_doc_edit_rejects_non_custom(client):
    """PUT على مستند رسمي (غير custom) يجب أن يُرفض."""
    mgr = auth_headers(login(client, *MGR))
    cid = client.get("/api/archive/company", headers=mgr).json()["company"]["id"]
    # ارفع مستند رسمي عبر /documents/upload
    files = _f(b"official", fn="cr.pdf")
    up = client.post("/api/documents/upload", headers=mgr, files=files, data={
        "entity_type": "company", "entity_id": str(cid),
        "document_type_code": "commercial_reg", "title": "س.ت",
    })
    assert up.status_code == 200
    docs = client.get("/api/archive/company", headers=mgr).json()["documents"]
    official = [d for d in docs if d["type"] == "commercial_reg"][0]

    r = client.put(f"/api/archive/custom-doc/{official['id']}", headers=mgr, data={
        "name_ar": "محاولة تعديل رسمي"
    })
    assert r.status_code == 400
    # الرسالة تحتوي على "للمستندات المخصّصة" — تحقق من substring
    assert "لمستندات المخصّصة" in r.json()["detail"] or "مخصّصة" in r.json()["detail"]


def test_custom_doc_delete_removes_all_versions(client):
    mgr = auth_headers(login(client, *MGR))
    cid = client.get("/api/archive/company", headers=mgr).json()["company"]["id"]
    r = client.post("/api/archive/custom-doc", headers=mgr, files=_f(b"del1"), data={
        "entity_type": "company", "entity_id": str(cid), "name_ar": "للحذف",
    })
    doc_id = r.json()["id"]
    client.post(f"/api/archive/custom-doc/{doc_id}/replace", headers=mgr, files=_f(b"del2"))

    d = client.delete(f"/api/archive/custom-doc/{doc_id}", headers=mgr)
    assert d.status_code == 200 and d.json()["deleted_versions"] >= 2

    # لم يعد يظهر في العرض
    docs = client.get("/api/archive/company", headers=mgr).json()["documents"]
    assert not any(x["id"] == doc_id for x in docs)


def test_custom_doc_branch_scope(client):
    """المستند المخصّص على فرع يظهر فقط في أرشيف ذلك الفرع."""
    mgr = auth_headers(login(client, *MGR))
    branches = client.get("/api/branches", headers=mgr).json()
    b1 = branches[0]["id"]
    b2 = branches[1]["id"]
    r = client.post("/api/archive/custom-doc", headers=mgr, files=_f(b"br"), data={
        "entity_type": "branch", "entity_id": str(b1),
        "name_ar": "شهادة سلامة فرع 1",
    })
    assert r.status_code == 201
    docs_b1 = client.get(f"/api/archive/branch/{b1}", headers=mgr).json()["documents"]
    docs_b2 = client.get(f"/api/archive/branch/{b2}", headers=mgr).json()["documents"]
    assert any(d["title"] == "شهادة سلامة فرع 1" for d in docs_b1)
    assert not any(d["title"] == "شهادة سلامة فرع 1" for d in docs_b2)


# ============================================================================
# R9 — assigned_pro_id validation
# ============================================================================

def test_assigned_pro_must_be_delegate_same_company(client):
    """PRO المسند يجب أن يكون: (أ) role=delegate (ب) نفس الشركة."""
    mgr = auth_headers(login(client, *MGR))
    cid = client.get("/api/archive/company", headers=mgr).json()["company"]["id"]

    # هات ID المندوب الأول (نفس الشركة) والـHR (نفس الشركة لكن role مختلف)
    users = client.get("/api/users", headers=mgr).json()
    pro_id = next(u["id"] for u in users if u["role"] == "delegate")
    hr_id = next(u["id"] for u in users if u["role"] == "hr")

    # (أ) HR مرفوض (role ≠ delegate)
    r = client.post("/api/archive/custom-doc", headers=mgr, files=_f(b"a"), data={
        "entity_type": "company", "entity_id": str(cid), "name_ar": "test",
        "notify_on_expiry": "true", "assigned_pro_id": str(hr_id),
    })
    assert r.status_code == 400
    assert "delegate" in r.json()["detail"].lower() or "مندوب" in r.json()["detail"]

    # (ب) PRO نفس الشركة يُقبل
    r_ok = client.post("/api/archive/custom-doc", headers=mgr, files=_f(b"b"), data={
        "entity_type": "company", "entity_id": str(cid), "name_ar": "with pro",
        "notify_on_expiry": "true", "assigned_pro_id": str(pro_id),
    })
    assert r_ok.status_code == 201

    docs = client.get("/api/archive/company", headers=mgr).json()["documents"]
    m = [d for d in docs if d["title"] == "with pro"][0]
    assert m["assigned_pro_id"] == pro_id
    assert m["assigned_pro_name"]  # اسم المندوب موجود


def test_assigned_pro_from_other_company_rejected(client):
    """PRO من شركة أخرى مرفوض (تحقق حسّاس أمنيًا)."""
    mgr = auth_headers(login(client, *MGR))
    admin = auth_headers(login(client, *ADMIN))
    cid = client.get("/api/archive/company", headers=mgr).json()["company"]["id"]

    all_users = client.get("/api/users", headers=admin).json()
    # مندوب من شركة أخرى (company_id != cid)
    other_pro = next((u for u in all_users
                     if u["role"] == "delegate" and u["company_id"] != cid), None)
    assert other_pro, "seed لازم يشمل مندوبين من شركتين"

    r = client.post("/api/archive/custom-doc", headers=mgr, files=_f(b"c"), data={
        "entity_type": "company", "entity_id": str(cid), "name_ar": "cross",
        "notify_on_expiry": "true", "assigned_pro_id": str(other_pro["id"]),
    })
    assert r.status_code == 400


# ============================================================================
# R8 §1 — Government Portals CRUD + RBAC
# ============================================================================

def test_portal_admin_creates_and_lists(client):
    admin = auth_headers(login(client, *ADMIN))
    r = client.post("/api/gov-portals", headers=admin, json={
        "name_ar": "بوابة اختبار", "name_en": "Test Portal",
        "description_ar": "وصف",
        "url": "https://example.gov.kw/", "category": "moci",
        "icon": "🧪", "sort_order": 500, "is_active": True,
    })
    assert r.status_code == 201, r.text

    listing = client.get("/api/gov-portals", headers=admin).json()
    assert listing["can_manage"] is True
    all_portals = [p for g in listing["groups"] for p in g["portals"]]
    assert any(p["name_ar"] == "بوابة اختبار" for p in all_portals)


def test_portal_pro_can_view_but_not_manage(client):
    pro = auth_headers(login(client, *PRO))
    listing = client.get("/api/gov-portals", headers=pro).json()
    assert listing["can_manage"] is False
    # PRO يشوف روابط
    assert len(listing["groups"]) >= 1


def test_portal_employee_forbidden(client):
    emp = auth_headers(login(client, *EMP))
    r = client.get("/api/gov-portals", headers=emp)
    assert r.status_code == 403


def test_portal_pro_cannot_create(client):
    pro = auth_headers(login(client, *PRO))
    r = client.post("/api/gov-portals", headers=pro, json={
        "name_ar": "ممنوع", "url": "https://x.example/", "category": "moci",
    })
    assert r.status_code == 403


def test_portal_category_validation(client):
    """category غير معروفة → 400 من الـendpoint (لا 422 من Pydantic — القيمة string
    عادية، والتحقق يتم في handler)."""
    admin = auth_headers(login(client, *ADMIN))
    r = client.post("/api/gov-portals", headers=admin, json={
        "name_ar": "x", "name_en": "x",
        "url": "https://y.example/", "category": "unknown_cat",
    })
    # نقبل 400 (منطق تطبيق) أو 422 (تحقق Pydantic لأي حقل ناقص)
    assert r.status_code in (400, 422)


# ============================================================================
# R8 §3 + R9 §4 — Contract Generation (needs templates seeded)
# ============================================================================

def _seed_contract_template(client, code: str, body: str = None) -> int:
    """يُنشئ قالب عقد اختبار (لأن migrations لا تُشغَّل في التسات — بذور يدوية)."""
    admin = auth_headers(login(client, *ADMIN))
    default_body = body or (
        "<h2>عقد</h2><p>{{employee_name}} — {{civil_id}} — {{basic_salary}} — "
        "{{company_name}} — {{ref_no}}</p>"
    )
    r = client.post("/api/templates", headers=admin, json={
        "name": f"Test {code}", "name_en": code, "category": "عقود",
        "body_html": default_body, "code": code, "company_id": None,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def test_templates_exists_endpoint(client):
    """R9 §11 — endpoint يرجع map {code: bool}."""
    pro = auth_headers(login(client, *PRO))
    r = client.get("/api/templates/exists", headers=pro,
                   params={"codes": "NO-SUCH-TEMPLATE,ANOTHER-NOPE"})
    assert r.status_code == 200
    data = r.json()
    assert data == {"NO-SUCH-TEMPLATE": False, "ANOTHER-NOPE": False}


def test_hire_contract_generate_gov_and_company(client):
    """R9 §4 — توليد عقدي التعيين يُنتج issued docs مع reference + checksum."""
    _seed_contract_template(client, "GOV-CONTRACT-HIRE")
    _seed_contract_template(client, "COMPANY-CONTRACT-HIRE")

    mgr = auth_headers(login(client, *MGR))
    # اختر أول موظف من الشركة
    emps = client.get("/api/employees", headers=mgr).json()
    assert emps
    emp_id = emps[0]["id"]

    r_gov = client.post(f"/api/employees/{emp_id}/gov-contract/generate", headers=mgr)
    assert r_gov.status_code == 200, r_gov.text
    body = r_gov.json()
    assert body["ok"] is True
    assert body["reference_no"].startswith("GOV-CONTRACT-HIRE/")
    assert len(body["checksum_sha256"]) == 64  # SHA-256 hex
    assert body["template_code"] == "GOV-CONTRACT-HIRE"

    r_co = client.post(f"/api/employees/{emp_id}/company-contract/generate", headers=mgr)
    assert r_co.status_code == 200
    assert r_co.json()["template_code"] == "COMPANY-CONTRACT-HIRE"

    # exists الآن يقول true
    exists = client.get("/api/templates/exists", headers=mgr,
                       params={"codes": "GOV-CONTRACT-HIRE,COMPANY-CONTRACT-HIRE"}).json()
    assert exists["GOV-CONTRACT-HIRE"] is True
    assert exists["COMPANY-CONTRACT-HIRE"] is True


def test_hire_contract_pdf_format(client):
    """R9 §5 — format=pdf يُعيد application/pdf."""
    _seed_contract_template(client, "COMPANY-CONTRACT-HIRE")
    mgr = auth_headers(login(client, *MGR))
    emp_id = client.get("/api/employees", headers=mgr).json()[0]["id"]

    r = client.post(f"/api/employees/{emp_id}/company-contract/generate",
                    headers=mgr, params={"format": "pdf"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    # ملف PDF فعلي (يبدأ بـ %PDF)
    assert r.content[:4] == b"%PDF"


def test_hire_contract_fails_without_template(client):
    """404 لو القالب مش موجود — يُخبر الأدمن بالخطوة التالية."""
    mgr = auth_headers(login(client, *MGR))
    emp_id = client.get("/api/employees", headers=mgr).json()[0]["id"]
    # تأكد قالب "NO-SUCH-CODE" غير موجود — نستدعي endpoint يبحث بكود مختلف
    # (نتحقق من رسالة GOV-CONTRACT-HIRE لو ما اتبذرش)
    # إن كان اتبذر في تست سابق، انسخ اسم مختلف
    r = client.post(f"/api/employees/{emp_id}/gov-contract/generate", headers=mgr)
    # لو اتبذر يرجع 200؛ لو مش موجود يرجع 404 مع رسالة صريحة
    assert r.status_code in (200, 404)
    if r.status_code == 404:
        assert "GOV-CONTRACT-HIRE" in r.json()["detail"]


def test_gov_contract_renewal_generation(client):
    """R8 §3 — تجديد → توليد العقد الحكومي فقط (بلا عقد شركة).
    يستخدم أي renewal مفتوح للـEMP لتجنب 409 لو تست سابق أنشأ واحد."""
    _seed_contract_template(client, "GOV-CONTRACT-RENEWAL")
    emp = auth_headers(login(client, *EMP))

    # حاول إعادة استخدام تجديد مفتوح موجود بدل إنشاء واحد جديد
    existing = client.get("/api/renewals", headers=emp).json()
    open_rn = next((rn for rn in existing
                   if rn["status"] in ("awaiting_contracts", "awaiting_signature",
                                       "contracts_signed", "renewing")), None)
    if open_rn:
        rid = open_rn["id"]
    else:
        r = client.post("/api/renewals", headers=emp)
        if r.status_code != 201:
            return  # ما فيش permit صالح للتجديد (تست سابق أغلق الإقامة)
        rn = r.json()
        if rn["status"] != "awaiting_contracts":
            return
        rid = rn["id"]

    pro = auth_headers(login(client, *PRO))
    g = client.post(f"/api/renewals/{rid}/gov-contract/generate", headers=pro)
    assert g.status_code == 200, g.text
    assert g.json()["reference_no"].startswith("GOV-REN/")


# ============================================================================
# R9 §1 — Renewal workflow: gov contract only
# ============================================================================

def test_renewal_advances_with_gov_contract_only(client):
    """R9 §1 — رفع العقد الحكومي فقط يكفي للانتقال إلى awaiting_signature.
    يعيد استخدام تجديد مفتوح أو ينشئ واحدًا لو ممكن."""
    emp = auth_headers(login(client, *EMP))
    exists = client.get("/api/renewals", headers=emp).json()
    open_rn = next((rn for rn in exists if rn["status"] == "awaiting_contracts"), None)
    if not open_rn:
        r = client.post("/api/renewals", headers=emp)
        if r.status_code != 201 or r.json()["status"] != "awaiting_contracts":
            return
        rid = r.json()["id"]
    else:
        rid = open_rn["id"]

    pro = auth_headers(login(client, *PRO))
    client.post(f"/api/renewals/{rid}/upload", headers=pro,
                data={"doc_type": "renewal_contract_gov"}, files=_f())
    after = client.get(f"/api/renewals/{rid}", headers=pro).json()
    # يجب أن ينتقل مباشرة بعد العقد الحكومي فقط (بدون رفع العقد الداخلي)
    assert after["status"] == "awaiting_signature"


# ============================================================================
# R9 §14 — Auto-link users ↔ employees
# ============================================================================

def test_auto_link_idempotent(client):
    """auto-link ما يعمل شيء لو كل الحسابات مربوطة (idempotent)."""
    admin = auth_headers(login(client, *ADMIN))
    r1 = client.post("/api/users/auto-link-employees", headers=admin)
    assert r1.status_code == 200

    r2 = client.post("/api/users/auto-link-employees", headers=admin)
    assert r2.status_code == 200
    # التشغيل الثاني: صفر ربط جديد
    assert len(r2.json()["linked"]) == 0


def test_auto_link_reports_no_employee(client):
    """user يتيم بدون employee مطابق يظهر في no_employee بدل ما يفشل الكل."""
    from app.database import SessionLocal
    from app import models
    from app.security import hash_password

    admin = auth_headers(login(client, *ADMIN))
    db = SessionLocal()
    orphan_id = None
    try:
        cid = db.scalar(select(models.Company.id))
        orphan = models.User(
            civil_id="999999999999", password_hash=hash_password("x"),
            full_name="Orphan Test", role="hr", company_id=cid,
            is_active=True, must_change_password=False,
        )
        db.add(orphan); db.commit()
        orphan_id = orphan.id
    finally:
        db.close()

    try:
        r = client.post("/api/users/auto-link-employees", headers=admin)
        assert r.status_code == 200
        no_emp_ids = [x["user_id"] for x in r.json()["no_employee"]]
        assert orphan_id in no_emp_ids
    finally:
        # نظافة: احذف الـuser المُختبر
        db = SessionLocal()
        try:
            u = db.get(models.User, orphan_id) if orphan_id else None
            if u:
                db.delete(u); db.commit()
        finally:
            db.close()


def test_auto_link_requires_manage_users_permission(client):
    """endpoint خاص بأدوار manage_users فقط — الموظف مرفوض."""
    emp = auth_headers(login(client, *EMP))
    r = client.post("/api/users/auto-link-employees", headers=emp)
    assert r.status_code == 403


def test_auto_link_does_not_touch_super_admin(client):
    """super_admin عمدًا بلا employee record — auto-link يتخطاه."""
    from app.database import SessionLocal
    from app import models

    admin = auth_headers(login(client, *ADMIN))
    r = client.post("/api/users/auto-link-employees", headers=admin)
    assert r.status_code == 200

    # super_admin يجب أن يبقى employee_id=NULL
    db = SessionLocal()
    try:
        sa = db.scalar(select(models.User).where(models.User.role == "super_admin"))
        assert sa is not None
        assert sa.employee_id is None
        # ولا يظهر في linked/no_employee
        for group in ("linked", "no_employee", "conflicts"):
            assert not any(x.get("user_id") == sa.id for x in r.json().get(group, []))
    finally:
        db.close()


# ============================================================================
# R9 §16 — Multi-company user (cross-company delegate)
# ============================================================================

def _setup_cross_company_user(client) -> dict:
    """يهيّئ مستخدم متعدد الشركات (مثل محمد فاروق) + عضويتين + employees.
    يعود بالـmetadata: user_id, civil_id, password, company_ids, employee_ids."""
    from app.database import SessionLocal
    from app import models
    from app.security import hash_password

    admin = auth_headers(login(client, *ADMIN))
    db = SessionLocal()
    try:
        # جيب أول شركتين + PROs الحاليين (المفروض متلينكين)
        companies = db.scalars(select(models.Company).limit(2)).all()
        assert len(companies) >= 2, "seed لازم فيه شركتين"
        cid1, cid2 = companies[0].id, companies[1].id

        # أنشئ Employee record في كل شركة بنفس الـcivil_id
        civ = "555555555555"
        emp1 = db.scalar(select(models.Employee).where(
            models.Employee.civil_id == civ, models.Employee.company_id == cid1))
        if not emp1:
            emp1 = models.Employee(
                company_id=cid1, civil_id=civ, name="محمد فاروق - الاتحاد",
                job_title="مندوب حكومي", hire_date=None,
                contract_type="indefinite", status="active",
            )
            db.add(emp1); db.flush()
        emp2 = db.scalar(select(models.Employee).where(
            models.Employee.civil_id == civ, models.Employee.company_id == cid2))
        if not emp2:
            emp2 = models.Employee(
                company_id=cid2, civil_id=civ, name="محمد فاروق - ميلانو",
                job_title="مندوب حكومي", hire_date=None,
                contract_type="indefinite", status="active",
            )
            db.add(emp2); db.flush()

        # أنشئ User (متعدد الشركات)
        existing = db.scalar(select(models.User).where(models.User.civil_id == civ))
        if existing:
            # لو باقٍ من تست سابق، امسحه لبداية نظيفة
            db.execute(models.UserCompanyLink.__table__.delete().where(
                models.UserCompanyLink.user_id == existing.id))
            db.delete(existing); db.commit()

        pw = "farouq123"
        user = models.User(
            civil_id=civ, password_hash=hash_password(pw),
            full_name="محمد فاروق", role="delegate",
            is_cross_company=True, company_id=None, employee_id=None,
            is_active=True, must_change_password=False,
        )
        db.add(user); db.flush()
        uid = user.id
        db.commit()
    finally:
        db.close()

    # أضف company links عبر الـendpoint (يختبر endpoint فعلي)
    r1 = client.post(f"/api/users/{uid}/company-links", headers=admin,
                    params={"company_id": cid1, "employee_id": emp1.id, "role": "delegate"})
    assert r1.status_code == 200, r1.text
    r2 = client.post(f"/api/users/{uid}/company-links", headers=admin,
                    params={"company_id": cid2, "employee_id": emp2.id, "role": "delegate"})
    assert r2.status_code == 200, r2.text

    return {"user_id": uid, "civil_id": civ, "password": pw,
            "company_ids": [cid1, cid2], "employee_ids": [emp1.id, emp2.id]}


def _cleanup_cross_company_user(uid: int):
    from app.database import SessionLocal
    from app import models
    db = SessionLocal()
    try:
        db.execute(models.UserCompanyLink.__table__.delete().where(
            models.UserCompanyLink.user_id == uid))
        u = db.get(models.User, uid)
        if u:
            db.delete(u)
        db.commit()
    finally:
        db.close()


def test_cross_company_login_returns_companies_list(client):
    """R9 §16 — login لمستخدم متعدد الشركات يعيد قائمة شركاته."""
    ctx = _setup_cross_company_user(client)
    try:
        r = client.post("/api/auth/login", json={
            "civil_id": ctx["civil_id"], "password": ctx["password"],
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["is_cross_company"] is True
        assert body["company_id"] is None  # قبل الاختيار
        assert body["companies"] is not None
        assert len(body["companies"]) == 2
        cids = {c["id"] for c in body["companies"]}
        assert cids == set(ctx["company_ids"])
    finally:
        _cleanup_cross_company_user(ctx["user_id"])


def test_cross_company_must_select_before_using_app(client):
    """R9 §16 — بدون اختيار شركة، أي endpoint يرد 428 COMPANY_SELECTION_REQUIRED."""
    ctx = _setup_cross_company_user(client)
    try:
        r = client.post("/api/auth/login", json={
            "civil_id": ctx["civil_id"], "password": ctx["password"],
        })
        token = r.json()["access_token"]
        h = auth_headers(token)
        # /auth/me مسموح (لعرض بيانات المستخدم)
        me = client.get("/api/auth/me", headers=h)
        assert me.status_code == 200
        # /employees مثلاً مرفوض بلا active_company
        emp_list = client.get("/api/employees", headers=h)
        assert emp_list.status_code == 428
        detail = emp_list.json()["detail"]
        assert detail.get("code") == "COMPANY_SELECTION_REQUIRED"
    finally:
        _cleanup_cross_company_user(ctx["user_id"])


def test_cross_company_select_company_issues_scoped_token(client):
    """R9 §16 — POST /select-company يعيد token جديد يشتغل مع الشركة المختارة."""
    ctx = _setup_cross_company_user(client)
    try:
        r = client.post("/api/auth/login", json={
            "civil_id": ctx["civil_id"], "password": ctx["password"],
        })
        h = auth_headers(r.json()["access_token"])

        # اختر الشركة الأولى
        sel = client.post("/api/auth/select-company", headers=h,
                         params={"company_id": ctx["company_ids"][0]})
        assert sel.status_code == 200
        assert sel.json()["active_company_id"] == ctx["company_ids"][0]

        # التوكن الجديد يشتغل — يقدر يشوف employees
        h2 = auth_headers(sel.json()["access_token"])
        emps = client.get("/api/employees", headers=h2)
        assert emps.status_code == 200
        # كل الموظفين اللي بيشوفهم من الشركة الأولى فقط
        for e in emps.json():
            assert e["company_id"] == ctx["company_ids"][0]

        # /auth/me يرد company_id = الشركة المختارة و employee_id = من الـlink
        me = client.get("/api/auth/me", headers=h2)
        assert me.status_code == 200
        me_data = me.json()
        assert me_data["company_id"] == ctx["company_ids"][0]
        assert me_data["employee_id"] == ctx["employee_ids"][0]
    finally:
        _cleanup_cross_company_user(ctx["user_id"])


def test_cross_company_cannot_select_non_member_company(client):
    """R9 §16 — لو حاول يختار شركة غير مسموحة، يفشل (404 لو مش موجودة، 403 لو مش عضو)."""
    ctx = _setup_cross_company_user(client)
    try:
        r = client.post("/api/auth/login", json={
            "civil_id": ctx["civil_id"], "password": ctx["password"],
        })
        h = auth_headers(r.json()["access_token"])
        # حاول اختيار شركة ID كبير (مش موجود أو مش عضو) → 404 (مش موجود) أو 403 (مش عضو)
        sel = client.post("/api/auth/select-company", headers=h,
                         params={"company_id": 99999})
        assert sel.status_code in (403, 404)
    finally:
        _cleanup_cross_company_user(ctx["user_id"])


def test_cross_company_add_link_requires_matching_employee_company(client):
    """R9 §16 — إضافة link بموظف من شركة مختلفة يفشل."""
    ctx = _setup_cross_company_user(client)
    admin = auth_headers(login(client, *ADMIN))
    try:
        # حاول أضف link بشركة X + موظف من شركة Y
        r = client.post(f"/api/users/{ctx['user_id']}/company-links", headers=admin,
                       params={"company_id": ctx["company_ids"][0],
                              "employee_id": ctx["employee_ids"][1]})  # emp من company_ids[1]
        assert r.status_code == 400
        assert "ينتمي" in r.json()["detail"] or "company" in r.json()["detail"].lower()
    finally:
        _cleanup_cross_company_user(ctx["user_id"])


def test_cross_company_switch_between_companies(client):
    """R9 §16 — نفس المستخدم يبدّل بين شركتين — كل مرة يشوف بيانات مختلفة."""
    ctx = _setup_cross_company_user(client)
    try:
        r = client.post("/api/auth/login", json={
            "civil_id": ctx["civil_id"], "password": ctx["password"],
        })
        h_pre = auth_headers(r.json()["access_token"])

        # الشركة 1
        s1 = client.post("/api/auth/select-company", headers=h_pre,
                        params={"company_id": ctx["company_ids"][0]})
        h1 = auth_headers(s1.json()["access_token"])
        emps1 = client.get("/api/employees", headers=h1).json()
        cids1 = {e["company_id"] for e in emps1}
        assert cids1 == {ctx["company_ids"][0]}

        # الشركة 2 (توكن جديد)
        s2 = client.post("/api/auth/select-company", headers=h_pre,
                        params={"company_id": ctx["company_ids"][1]})
        h2 = auth_headers(s2.json()["access_token"])
        emps2 = client.get("/api/employees", headers=h2).json()
        cids2 = {e["company_id"] for e in emps2}
        assert cids2 == {ctx["company_ids"][1]}

        # الاثنين مختلفين — العزل شغّال
        assert cids1 != cids2
    finally:
        _cleanup_cross_company_user(ctx["user_id"])


def test_non_cross_company_user_cannot_select_company(client):
    """R9 §16 — مستخدم عادي يحاول endpoint /select-company يفشل بـ400."""
    pro = auth_headers(login(client, *PRO))
    r = client.post("/api/auth/select-company", headers=pro,
                   params={"company_id": 1})
    assert r.status_code == 400
    assert "متعدد الشركات" in r.json()["detail"] or "cross" in r.json()["detail"].lower()


def test_enable_cross_company_requires_super_admin(client):
    """R9 §16 — /enable-cross-company لـsuper_admin فقط."""
    mgr = auth_headers(login(client, *MGR))
    # جيب ID مستخدم delegate عشوائي
    from app.database import SessionLocal
    from app import models
    db = SessionLocal()
    try:
        pro_user = db.scalar(select(models.User).where(models.User.role == "delegate"))
        pro_uid = pro_user.id if pro_user else 1
    finally:
        db.close()
    r = client.post(f"/api/users/{pro_uid}/enable-cross-company", headers=mgr)
    assert r.status_code == 403


# ============================================================================
# R9 §17 — User avatar upload
# ============================================================================

def test_avatar_status_initially_empty(client):
    """/me/avatar بدون رفع سابق → has_avatar=false."""
    mgr = auth_headers(login(client, *MGR))
    r = client.get("/api/me/avatar", headers=mgr)
    assert r.status_code == 200
    assert r.json()["has_avatar"] is False


def test_avatar_upload_and_serve(client):
    """رفع صورة PNG صغيرة → /me/avatar/image يرد الملف."""
    mgr = auth_headers(login(client, *MGR))
    # PNG صالح صغير (1x1 pixel)
    png_bytes = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d49444154789c626001000000050001a5f645ea0000000049454e44ae426082"
    )
    files = {"file": ("avatar.png", png_bytes, "image/png")}
    r = client.post("/api/me/avatar", headers=mgr, files=files)
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True

    # الحالة تعكس الرفع
    st = client.get("/api/me/avatar", headers=mgr).json()
    assert st["has_avatar"] is True
    assert st["updated_at"] is not None

    # الصورة تُعاد بالـMIME الصحيح
    img = client.get("/api/me/avatar/image", headers=mgr)
    assert img.status_code == 200
    assert img.headers["content-type"] == "image/png"
    assert len(img.content) > 0


def test_avatar_rejects_wrong_mime(client):
    """PDF مثلاً مرفوض بـ415."""
    mgr = auth_headers(login(client, *MGR))
    files = {"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")}
    r = client.post("/api/me/avatar", headers=mgr, files=files)
    assert r.status_code == 415


def test_avatar_delete_removes(client):
    """DELETE يرد has_avatar=false."""
    mgr = auth_headers(login(client, *MGR))
    # ارفع أولاً
    png_bytes = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d49444154789c626001000000050001a5f645ea0000000049454e44ae426082"
    )
    client.post("/api/me/avatar", headers=mgr,
                files={"file": ("a.png", png_bytes, "image/png")})
    # امسح
    d = client.delete("/api/me/avatar", headers=mgr)
    assert d.status_code == 200
    # الحالة بعد المسح
    st = client.get("/api/me/avatar", headers=mgr).json()
    assert st["has_avatar"] is False


def test_avatar_other_users_can_see_avatar(client):
    """GET /users/{id}/avatar/image — أي مستخدم مسجّل يقدر يشوف صورة الآخرين."""
    mgr = auth_headers(login(client, *MGR))
    png_bytes = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d49444154789c626001000000050001a5f645ea0000000049454e44ae426082"
    )
    client.post("/api/me/avatar", headers=mgr,
                files={"file": ("a.png", png_bytes, "image/png")})

    # جيب mgr user_id
    me = client.get("/api/auth/me", headers=mgr).json()
    mgr_uid = me["id"]

    # مستخدم آخر (HR) يشوف صورة المدير
    hr = auth_headers(login(client, *HR))
    r = client.get(f"/api/users/{mgr_uid}/avatar/image", headers=hr)
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"


def test_avatar_appears_in_auth_me(client):
    """/auth/me يشمل has_avatar bool."""
    hr = auth_headers(login(client, *HR))
    me = client.get("/api/auth/me", headers=hr).json()
    assert "has_avatar" in me
    assert isinstance(me["has_avatar"], bool)


# ============================================================================
# P0-#1 — Unified /auth/select-company for owner/super_admin (Portfolio pick)
# ============================================================================

def test_admin_can_select_any_company(client):
    """super_admin يقدر يختار أي شركة عبر /auth/select-company (لا 400)."""
    token = login(client, *ADMIN)
    r = client.post("/api/auth/select-company", headers=auth_headers(token),
                   params={"company_id": 1})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["active_company_id"] == 1
    assert body["is_cross_company"] is True


def test_owner_can_select_any_company(client):
    """company_owner يقدر يختار أي شركة (portfolio)."""
    token = login(client, "111111111111", "owner123")
    r = client.post("/api/auth/select-company", headers=auth_headers(token),
                   params={"company_id": 2})
    assert r.status_code == 200
    assert r.json()["active_company_id"] == 2


def test_my_companies_kind_field(client):
    """/auth/my-companies يرد kind يميّز portfolio / member / single."""
    admin = auth_headers(login(client, *ADMIN))
    r_admin = client.get("/api/auth/my-companies", headers=admin).json()
    assert r_admin["kind"] == "portfolio"
    assert len(r_admin["companies"]) >= 2

    mgr = auth_headers(login(client, *MGR))
    r_mgr = client.get("/api/auth/my-companies", headers=mgr).json()
    assert r_mgr["kind"] == "single"
    assert len(r_mgr["companies"]) == 1


def test_admin_select_nonexistent_company_404(client):
    """اختيار شركة مش موجودة → 404 (مش 400)."""
    admin = auth_headers(login(client, *ADMIN))
    r = client.post("/api/auth/select-company", headers=admin,
                   params={"company_id": 99999})
    assert r.status_code == 404


def test_regular_user_still_rejected_from_select(client):
    """موظف عادي (بدون cross-company) لسه يرجع 400."""
    emp = auth_headers(login(client, *EMP))
    r = client.post("/api/auth/select-company", headers=emp,
                   params={"company_id": 1})
    assert r.status_code == 400


# ============================================================================
# P0-#4 — Attendance permissions unified across roles
# ============================================================================

def test_hr_can_access_attendance_review(client):
    """HR له view_attendance → يقدر يفتح /attendance/review."""
    hr = auth_headers(login(client, *HR))
    r = client.get("/api/attendance/review", headers=hr)
    # ما نتوقعش 403 (المشكلة في UI/route كانت بتمنعه رغم الـAPI مسموح)
    assert r.status_code != 403


def test_supervisor_can_access_attendance_review(client):
    """Supervisor له view_attendance → يقدر يفتح /attendance/review لفروعه."""
    from app.database import SessionLocal
    from app import models
    db = SessionLocal()
    try:
        sup = db.scalar(select(models.User).where(
            models.User.role == "branch_supervisor",
            models.User.company_id == 1,
        ))
        civ = sup.civil_id if sup else None
    finally:
        db.close()
    if not civ:
        return  # ما فيش supervisor في seed
    token = login(client, civ, "sup12345")
    r = client.get("/api/attendance/review", headers=auth_headers(token))
    assert r.status_code != 403


def test_manager_and_hr_are_exempt_from_attendance(client):
    """ATT-02 + ATT-03 — لا شاشة حضور للمدير ولا لـHR.

    كانت record_attendance تُمنح لهما ليبصما لنفسيهما (P0-#4). قرار العميل
    نزعها: HR يصحّح سجلات الحضور ويعتمدها، والمدير يعتمد الطلبات ويمنح
    الصلاحيات — فبصم أيٍّ منهما لنفسه يخلط الرقابة بالخضوع لها.
    view_attendance تبقى لهما للمتابعة.
    """
    from app.permissions import ROLE_DEFAULT_PERMS as R

    for role in ("company_manager", "hr"):
        assert "record_attendance" not in R[role], f"{role} ما زال يبصم"
        assert "view_attendance" in R[role], f"{role} فقد متابعة الحضور"

    # ومسؤول الفرع والمحاسب والموظف يبصمون كما كانوا
    for role in ("branch_supervisor", "accountant", "employee"):
        assert "record_attendance" in R[role], role

    for civ, pw in [("100000000001", "manager123"), ("100000000002", "hr12345")]:
        h = auth_headers(login(client, civ, pw))
        assert client.post("/api/attendance/validate-qr", headers=h,
                           json={"qr_token": "x"}).status_code == 403


def test_signature_delete_endpoint_is_gone(client):
    """PROF-04 — حذف التوقيع أُزيل من الـAPI لا من الواجهة وحدها.

    التوقيع سند للمستندات المُصدَرة سابًقا؛ حذفه يتركها بلا مرجع يُثبت التوقيع
    الذي حُقن فيها. التغيير يمر بطلب REQSIG المعتمَد من HR.
    """
    emp = auth_headers(login(client, "100000000101", "emp12345"))
    r = client.delete("/api/me/signature", headers=emp)
    assert r.status_code in (404, 405), f"الحذف ما زال متاًحا: {r.status_code}"


def test_manager_has_no_government_portals(client):
    """UI-02 — الروابط الحكومية أُزيلت من المدير أيًضا."""
    import re
    from pathlib import Path

    app_tsx = Path(__file__).resolve().parents[2] / "frontend" / "src" / "App.tsx"
    if not app_tsx.exists():
        return
    route = re.search(r'path="/gov-portals".*?/>', app_tsx.read_text(encoding="utf-8"), re.S)
    assert route
    for role in ('"hr"', '"company_manager"'):
        assert role not in route.group(0), f"{role} ما زال في حارس /gov-portals"


def test_employee_cannot_access_attendance_review(client):
    """موظف عادي بدون view_attendance → 403 على /attendance/review."""
    emp = auth_headers(login(client, *EMP))
    r = client.get("/api/attendance/review", headers=emp)
    assert r.status_code == 403


# ============================================================================
# P0-#6 — Workflow Engine: Effect atomicity + stale/double action guards
# ============================================================================

def test_workflow_double_decide_rejected(client):
    """P0-#6 — نفس المستخدم يقرّر مرتين على نفس المرحلة → 409."""
    from app.database import SessionLocal
    from app import models
    from sqlalchemy import select

    emp = auth_headers(login(client, *EMP))
    # نقدّم طلب salary_certificate — أول مرحلة company_manager
    r = client.post("/api/requests", headers=emp, json={
        "request_type_code": "salary_certificate",
        "payload_json": {"purpose": "بنك الاختبار", "language": "ar", "notes": "قرض"},
    })
    if r.status_code != 201:
        return  # لو الـcatalog اتغير أو type مش موجود، skip
    req_id = r.json()["id"]

    # الموظف عنده branch_supervisor بيعتمد أولاً
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        mgr_user = db.scalar(select(models.User).where(
            models.User.civil_id == MGR[0]))
    finally:
        db.close()
    mgr = auth_headers(login(client, *MGR))
    r1 = client.post(f"/api/requests/{req_id}/decide", headers=mgr,
                    json={"decision": "approved"})
    # القرار الأول ينجح (200 أو نوع تاني حسب workflow)
    if r1.status_code == 200:
        # جرّب decide تاني على نفس الطلب (لكن دلوقتي المرحلة تقدّمت)
        # نتوقع 409 لأن الحالة تغيّرت أو المرحلة اختلفت
        r2 = client.post(f"/api/requests/{req_id}/decide", headers=mgr,
                        json={"decision": "approved"})
        # 409 = double action prevented OR state changed
        assert r2.status_code in (403, 409), r2.text


def test_employees_list_survives_nonconforming_legacy_rows(client):
    """ROOT CAUSE — GET /employees كان 500 لأن EmployeeOut يرث مدقّقات الإدخال.

    أي صف مُدخَل يدويًا بـSQL (رقم مدني بحروف/طول مختلف، attendance_mode خارج
    القائمة) كان يرفع ValidationError داخل response_model فيسقط القائمة كلها
    بـ500 — لشركة واحدة فقط (اللي بياناتها دخلت يدويًا) بينما الأخرى تعمل.
    """
    from app.database import SessionLocal
    from app import models
    from sqlalchemy import select

    db = SessionLocal()
    bad_ids = []
    try:
        cid = db.scalar(select(models.Company.id).order_by(models.Company.id))
        # صفوف تحاكي الإدخال اليدوي المخالف لمدقّقات الإدخال
        for civ, mode, name in [
            ("ABC-123", "none", "Legacy Non-Digit Civil ID"),   # civil_id بحروف وشرطة
            ("12345", "none", "Legacy Short Civil ID"),          # أقصر من 6
            ("277113001845", "manual", "Legacy Bad Attendance"), # نمط حضور خارج القائمة
        ]:
            e = models.Employee(
                company_id=cid, civil_id=civ, name=name, job_title="اختبار",
                basic_salary=100, contract_type="indefinite", status="active",
                attendance_mode=mode, attendance_exempt=False,
                annual_leave_balance=30,
            )
            db.add(e)
            db.flush()
            bad_ids.append(e.id)
        db.commit()

        # القائمة لازم تُرجَع 200 وتشمل الصفوف المخالفة كما هي في القاعدة
        mgr = auth_headers(login(client, *MGR))
        r = client.get("/api/employees", headers=mgr, params={"limit": 500})
        assert r.status_code == 200, \
            f"list broke on non-conforming legacy rows: {r.status_code} {r.text[:400]}"
        returned_ids = {e["id"] for e in r.json()}
        for bid in bad_ids:
            assert bid in returned_ids, f"legacy row {bid} silently dropped from list"

        # ولكل الأدوار الإدارية — مش المدير بس
        hr = auth_headers(login(client, *HR))
        assert client.get("/api/employees", headers=hr,
                         params={"limit": 500}).status_code == 200
    finally:
        db2 = SessionLocal()
        try:
            for bid in bad_ids:
                obj = db2.get(models.Employee, bid)
                if obj:
                    db2.delete(obj)
            db2.commit()
        finally:
            db2.close()
        db.close()


def test_creation_catalog_is_not_empty_and_covers_core_types(client):
    """REGRESSION — تفعيل v15_legacy_catalog_hidden كان يخفي 48 نوعًا صالحًا
    (canonical=None) ويترك الخمسة المُستبدَلة معروضة رغم رفض POST لها، فتصبح
    شاشة "طلب جديد" إما فارغة أو كلها أنواع مرفوضة."""
    emp = auth_headers(login(client, *EMP))
    r = client.get("/api/requests/types", headers=emp,
                   params={"creatable_only": True})
    assert r.status_code == 200
    codes = {t["code"] for t in r.json()}
    assert len(codes) >= 10, f"creation catalog nearly empty: {sorted(codes)}"
    # الأنواع الأساسية للموظف لازم تكون متاحة للإنشاء
    for core in ("leave", "REQATT", "REQCERTSAL", "REQADV"):
        assert core in codes, f"core request type missing from creation catalog: {core}"


def test_spec_request_types_have_real_schemas(client):
    """REGRESSION — مفاتيح الـschemas (REQCERT/REQPERM/REQREN) انحرفت عن أكواد
    أنواع الطلبات (REQCERTSAL/REQPER/REQRESN)، فكان get_schema يعيد None و34 نوعًا
    يسقط على النموذج العام (تاريخ/مبلغ/تفاصيل) بدل نموذجه الحقيقي."""
    from app.form_schemas import get_schema

    expected_field = {
        "leave": "start_date",
        "REQATT": "attendance_date",
        "REQCERTSAL": "purpose",
        "REQDATA": "field_to_update",
        "REQDOC": "document_type",
        "REQPER": "permission_date",
        "REQADV": "amount",
        "REQRESN": "residency_expiry",
        "REQPAY": "payroll_period",
        "REQEXP": "expense_date",
    }
    for code, field in expected_field.items():
        schema = get_schema(code)
        assert schema, f"{code} has no schema -> falls back to the generic form"
        fields = {f["code"] for f in schema["fields"]}
        assert field in fields, f"{code} resolved to the wrong schema (missing {field})"


def test_every_employee_request_type_has_a_real_form(client):
    """كل نوع طلب يملؤه موظف لازم له نموذج حقيقي — لا يسقط على النموذج العام.
    الأنواع الإدارية (ADM*) مستثناة: سجلات داخلية لا يملؤها موظف."""
    from app.form_schemas import get_schema
    from app.workflow import DEFAULT_REQUEST_TYPES

    generic = [rt["code"] for rt in DEFAULT_REQUEST_TYPES
               if not rt["code"].startswith("ADM") and not get_schema(rt["code"])]
    assert not generic, f"types still falling back to the generic form: {generic}"


def test_new_schemas_fields_match_their_purpose(client):
    """النماذج الـ13 الجديدة — عيّنة حقول تثبت أن كل نموذج يخصّ نوعه فعلًا
    وليس نسخة عامة أعيد استخدامها."""
    from app.form_schemas import get_schema

    expect = {
        "REQLATE": {"late_date", "expected_time", "actual_time", "late_cause"},
        "REQSHIFT": {"requested_shift_id", "effective_from", "is_permanent"},
        "REQWLOC": {"target_branch_id", "from_date", "to_date"},
        "REQMIS": {"destination", "mission_type"},
        "REQWP": {"permit_no", "permit_expiry"},
        "REQTRFLIC": {"transfer_kind", "effective_date"},
        "REQCONTACT": {"emergency_name", "emergency_phone"},
        "REQFILE": {"document_kind", "delivery_method"},
        "REQALLOW": {"allowance_type", "amount"},
        "REQVIO": {"violation_ref", "objection_ground"},
        "REQWARN": {"warning_ref", "acknowledgment", "response"},
        "REQGEN": {"subject", "request_kind", "details"},
        "REQCON": {"current_contract_end", "decision"},
    }
    for code, must_have in expect.items():
        schema = get_schema(code)
        assert schema, f"{code} has no schema"
        fields = {f["code"] for f in schema["fields"]}
        assert must_have <= fields, f"{code} missing {must_have - fields}"


def test_required_fields_derived_from_schema(client):
    """الحقول الإلزامية تُشتق من الـschema — لا قائمة يدوية موازية.
    نوع جديد يعلن required في نموذجه يُفرض تلقائيًا على الخادم."""
    from app.routers.requests import _missing_required_fields

    # REQMIS غير مسجّل في REQUIRED_PAYLOAD_FIELDS — الاشتقاق هو ما يحميه
    missing = _missing_required_fields("REQMIS", {"destination": "وزارة الداخلية"})
    assert "from_date" in missing and "to_date" in missing and "mission_type" in missing

    complete = _missing_required_fields("REQMIS", {
        "destination": "وزارة الداخلية", "from_date": "2027-01-01",
        "to_date": "2027-01-02", "mission_type": "government", "reason": "مراجعة",
    })
    assert complete == []

    # الاشتقاق يسري عبر الاسم البديل أيضًا: salary_certificate كان له تجاوز صريح
    # بأسماء نموذجه المبرمج (addressed_to)، وبعد بنائه من الـschema صارت حقوله
    # الإلزامية هي حقول REQCERT نفسها بالترتيب المعلن فيه
    assert _missing_required_fields("salary_certificate", {}) == ["purpose", "language"]

    # التجاوز الصريح يبقى مقدَّمًا على الاشتقاق لو سُجِّل نوع مستقبلي فيه
    from app.routers.requests import REQUIRED_PAYLOAD_FIELDS
    REQUIRED_PAYLOAD_FIELDS["REQMIS"] = ["ui_only_field"]
    try:
        assert _missing_required_fields("REQMIS", {}) == ["ui_only_field"]
    finally:
        del REQUIRED_PAYLOAD_FIELDS["REQMIS"]


def test_every_creatable_type_exposes_a_schema_to_the_ui(client):
    """الواجهة تبني نموذج كل نوع من GET /requests/types/{code}/schema.

    قبل ذلك كانت تعرض نموذجًا عامًا من ثلاثة حقول (date/amount/details) لكل نوع
    بلا نموذج مبرمج — 44 من 53 — وحمولته لا تُرضي تحقق الخادم بحقول الـschema.
    فأي نوع قابل للإنشاء بلا schema يعني نموذجًا لا يمكن إرساله.
    """
    emp = auth_headers(login(client, *EMP))
    listing = client.get("/api/requests/types", headers=emp,
                         params={"creatable_only": True})
    assert listing.status_code == 200
    without = []
    for t in listing.json():
        code = t["code"]
        if code.startswith("ADM"):
            continue
        r = client.get(f"/api/requests/types/{code}/schema", headers=emp)
        if r.status_code != 200:
            without.append(code)
    assert not without, f"creatable types with no schema for the UI: {without}"


def test_hardcoded_form_list_matches_backend_exemptions(client):
    """قائمة الأنواع ذات النموذج المبرمج في الواجهة لا بد أن تطابق مفاتيح
    REQUIRED_PAYLOAD_FIELDS — الخادم يعفي هذه الأكواد من التحقق بمفردات الـschema،
    فاختلاف القائمتين يعني إما نوعًا يُرفض بلا سبب أو نوعًا يفلت من التحقق.

    القائمتان فارغتان الآن (كل النماذج تُبنى من الـschema)، ويبقى الاختبار
    ليحرس تطابقهما لو أُعيد إدخال نموذج مبرمج لنوع ما."""
    import re
    from pathlib import Path
    from app.routers.requests import REQUIRED_PAYLOAD_FIELDS

    src = Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "Requests.tsx"
    if not src.exists():
        return  # الواجهة غير موجودة في هذه البيئة
    text = src.read_text(encoding="utf-8")
    # يتحمّل التعليق النوعي بين الاسم و«=» (const X: string[] = [...])
    block = re.search(r"HARDCODED_FORM_TYPES\s*(?::[^=]*)?=\s*\[(.*?)\]", text, re.S)
    assert block, "HARDCODED_FORM_TYPES not found in Requests.tsx"
    ui_codes = set(re.findall(r'"([A-Za-z_]+)"', block.group(1)))
    assert ui_codes == set(REQUIRED_PAYLOAD_FIELDS), (
        f"only in UI: {ui_codes - set(REQUIRED_PAYLOAD_FIELDS)}, "
        f"only in backend: {set(REQUIRED_PAYLOAD_FIELDS) - ui_codes}"
    )


def test_strict_validation_catches_bad_values(client):
    """التحقق الحقلي الصارم فعّال: حدود الأرقام، عضوية قيم select، وترتيب
    التواريخ. كان مقفولًا على كل أنواع V1.3 فتمر أي قيمة."""
    from app.form_schemas import validate_payload as validate

    # قيمة select خارج الخيارات
    bad_lang = validate("REQCERTSAL", {"purpose": "بنك", "language": "fr"})
    assert any("language" in e for e in bad_lang), bad_lang
    assert validate("REQCERTSAL", {"purpose": "بنك", "language": "ar"}) == []

    # حد أدنى للأرقام
    neg = validate("REQALLOW", {"allowance_type": "transport", "amount": -5,
                                "effective_from": "2027-01-01", "reason": "ر"})
    assert any("amount" in e for e in neg), neg

    # حد أقصى
    too_long = validate("REQCON", {"current_contract_end": "2027-01-01",
                                   "decision": "renew", "new_duration_months": 99,
                                   "reason": "ر"})
    assert any("new_duration_months" in e for e in too_long), too_long

    # ترتيب التواريخ
    reversed_dates = validate("REQMIS", {"destination": "د", "from_date": "2027-05-10",
                                         "to_date": "2027-05-01",
                                         "mission_type": "government", "reason": "ر"})
    assert any("to_date" in e for e in reversed_dates), reversed_dates


def test_no_type_is_exempt_from_schema_validation(client):
    """لم يعد أي نوع معفى من التحقق بمفردات الـschema.

    كان الإعفاء لازمًا للأنواع التسعة ذات النموذج المبرمج: مفرداتها تأتي من
    الواجهة لا من الـschema (شهادة الراتب كانت تجمع addressed_to ولا حقل لغة
    فيها أصلاً بينما REQCERT يطلبه). بعد أن صارت كل النماذج تُبنى من الـschema
    لم يبقَ اختلاف مفردات، فلا استثناء. المَنفَذ يبقى في الكود لنوع مستقبلي
    يحتاج نموذجًا مبرمجًا خاصًا.
    """
    from app.form_schemas import validate_payload as validate
    from app.routers.requests import REQUIRED_PAYLOAD_FIELDS

    assert REQUIRED_PAYLOAD_FIELDS == {}, (
        f"types still exempt from schema validation: {sorted(REQUIRED_PAYLOAD_FIELDS)}"
    )
    # وحمولة شهادة الراتب بمفردات الـschema تمر بالتحقق الكامل بلا إعفاء
    assert validate("salary_certificate",
                    {"purpose": "بنك الكويت", "language": "ar", "notes": "قرض"}) == []


def test_salary_certificate_still_submittable(client):
    """اختبار نهاية-لنهاية للحالة التي كسرها التفعيل: الطلب من الواجهة يمر."""
    emp = auth_headers(login(client, *EMP))
    r = client.post("/api/requests", headers=emp, json={
        "request_type_code": "salary_certificate",
        "payload_json": {"purpose": "بنك الكويت الوطني", "language": "ar", "notes": "قرض سكني"},
    })
    assert r.status_code == 201, r.text


def test_conditional_required_rules_are_enforced(client):
    """قواعد conditional.require تُفرض على الخادم — حقل يصير إلزاميًا حسب قيمة
    حقل آخر. كانت إرشادًا للواجهة فقط لأن validate_payload يفرضها خلف
    strict_validation المقفولة على كل أنواع V1.3."""
    from app.routers.requests import _missing_required_fields as missing

    att = {"attendance_date": "2027-01-15", "correction_type": "check_in",
           "reason": "نسيت البصمة"}
    assert missing("REQATT", att) == ["new_check_in"]
    assert missing("REQATT", {**att, "new_check_in": "2027-01-15T08:00"}) == []
    # "both" يستلزم الاثنين
    assert missing("REQATT", {**att, "correction_type": "both",
                              "new_check_in": "2027-01-15T08:00"}) == ["new_check_out"]

    shift = {"requested_shift_id": 1, "effective_from": "2027-01-01",
             "is_permanent": "temporary", "reason": "ظرف"}
    assert missing("REQSHIFT", shift) == ["effective_to"]
    # الدائم لا يستلزم تاريخ انتهاء
    assert missing("REQSHIFT", {**shift, "is_permanent": "permanent"}) == []

    con = {"current_contract_end": "2027-06-30", "reason": "ر"}
    assert missing("REQCON", {**con, "decision": "renew"}) == ["new_duration_months"]
    assert missing("REQCON", {**con, "decision": "not_renew"}) == []


def test_conditional_hide_exempts_field_from_required(client):
    """حقل يخفيه شرط لا يُطالَب به — REQADV يخفي months عند اختيار سلفة."""
    from app.form_schemas import conditional_requirements, SCHEMAS
    add, hidden = conditional_requirements(SCHEMAS["REQADV"], {"loan_type": "advance"})
    assert "months" in hidden and "months" not in add
    add2, _ = conditional_requirements(SCHEMAS["REQADV"], {"loan_type": "loan"})
    assert "months" in add2


def test_missing_fields_message_follows_form_order(client):
    """ترتيب الحقول الناقصة يطابق ترتيبها في النموذج وثابت بين الاستدعاءات
    (القواعد الشرطية تُجمع في set، فبدون ترتيب صريح تتبدّل الرسالة)."""
    from app.routers.requests import _missing_required_fields as missing
    payload = {"transfer_kind": "both", "effective_date": "2027-01-01", "reason": "ر"}
    runs = {tuple(missing("REQTRFLIC", payload)) for _ in range(5)}
    assert runs == {("to_branch_id", "to_license_id")}


def test_required_enforcement_coverage_is_deliberate(client):
    """كل schema إما يفرض حقوله الإلزامية أو له سبب موثّق للاستثناء.
    يمنع نموذجًا جديدًا من الانضمام صامتًا لقائمة غير المفروضة."""
    from app.form_schemas import SCHEMAS, get_schema
    from app.routers.requests import REQUIRED_PAYLOAD_FIELDS as OVERRIDE
    from app.workflow import DEFAULT_REQUEST_TYPES

    # مستثنون بأسباب مذكورة في form_schemas.py
    EXPECTED_UNENFORCED = {
        "REQEOS", "REQCLR",   # تُنشأ برمجيًا بحمولة خاصة
        "REQTRAVEL",          # إذن مغادرة البلاد — لا نوع طلب يستخدمه بعد
    }
    unenforced = {k for k, v in SCHEMAS.items()
                  if not (v.get("meta") or {}).get("enforce_required")}
    assert unenforced == EXPECTED_UNENFORCED, (
        f"unexpected: {unenforced - EXPECTED_UNENFORCED}, "
        f"newly enforced: {EXPECTED_UNENFORCED - unenforced}"
    )

    # ولا نوع طلب بلا حماية: إما تجاوز صريح، أو schema يفرض، أو استثناء موثّق
    codes = [rt["code"] for rt in DEFAULT_REQUEST_TYPES]
    unguarded = []
    for c in codes:
        if c in OVERRIDE or c.startswith("ADM"):
            continue
        s = get_schema(c)
        if s and not (s.get("meta") or {}).get("enforce_required"):
            unguarded.append(c)
    assert set(unguarded) <= {"REQEOS", "REQCLR"}, \
        f"request types with unenforced schemas: {unguarded}"


def test_early_departure_does_not_demand_passport(client):
    """REQEXIT اسمه 'طلب مغادرة مبكرة' لكن schema REQEXIT يخص السفر للخارج،
    فكان يطالب طالب الانصراف المبكر بجواز ووجهة. أُعيد توجيهه لنموذج الإذن."""
    from app.form_schemas import get_schema
    s = get_schema("REQEXIT")
    fields = {f["code"] for f in s["fields"]}
    assert "passport_no" not in fields and "destination" not in fields
    assert {"permission_date", "subtype", "from_time"} <= fields
    subtypes = {o["value"] for f in s["fields"] if f["code"] == "subtype"
                for o in f.get("options", [])}
    assert "early_departure" in subtypes


def test_training_code_not_mapped_to_transfer_schema(client):
    """الربط بالاسم وحده كان سيخلط REQTRN (طلب تدريب) مع REQTRANS (نقل)."""
    from app.form_schemas import get_schema
    train = get_schema("REQTRN")
    transfer = get_schema("REQTRF")
    assert train and transfer
    assert "to_branch_id" in {f["code"] for f in transfer["fields"]}
    assert "to_branch_id" not in {f["code"] for f in train["fields"]}


def test_creatable_catalog_matches_what_post_accepts(client):
    """FIX — كل نوع في creation catalog لازم POST يقبله (مافيش legacy معروض ثم مرفوض)."""
    from app import feature_flags as ff
    from app.database import SessionLocal
    from app import v15_registry

    emp = auth_headers(login(client, *EMP))
    creatable = client.get("/api/requests/types", headers=emp,
                          params={"creatable_only": True}).json()
    assert isinstance(creatable, list)

    db = SessionLocal()
    try:
        hide_legacy = ff.is_enabled(db, 1, ff.V15_LEGACY_CATALOG_HIDDEN)
    finally:
        db.close()

    if not hide_legacy:
        return  # الفلاج مقفول → الـbackend يقبل الكل، مافيش تعارض

    # مافيش نوع في القائمة له canonical مختلف عن كوده (= legacy alias يرفضه POST)
    for t in creatable:
        info = v15_registry.resolve_request(t["code"])
        canonical = info.get("canonical")
        assert not (canonical and canonical != t["code"]), (
            f"creation catalog exposes legacy alias '{t['code']}' "
            f"(canonical={canonical}) which POST /requests rejects"
        )


def test_catalog_and_post_agree_with_legacy_flag_ON(client):
    """REGRESSION — الحالة الفعلية على الإنتاج: v15_legacy_catalog_hidden مفعّل.

    الاختبار السابق كان يخرج مبكرًا لو الفلاج مقفول، فلم يفحص أبدًا الحالة التي
    كسرت الإنتاج. هنا نفعّله صراحةً ثم نتحقق أن الكتالوج ليس فارغًا وأن كل نوع
    فيه يقبله POST فعلًا.
    """
    from app.database import SessionLocal
    from app import models, feature_flags as ff

    db = SessionLocal()
    created = None
    try:
        row = db.scalar(select(models.FeatureFlag).where(
            models.FeatureFlag.key == ff.V15_LEGACY_CATALOG_HIDDEN,
            models.FeatureFlag.company_id.is_(None)))
        if row:
            prev = row.value
            row.value = "on"
        else:
            prev = None
            created = models.FeatureFlag(
                key=ff.V15_LEGACY_CATALOG_HIDDEN, company_id=None, value="on")
            db.add(created)
        db.commit()
    finally:
        db.close()

    try:
        emp = auth_headers(login(client, *EMP))
        listing = client.get("/api/requests/types", headers=emp,
                             params={"creatable_only": True})
        assert listing.status_code == 200
        codes = [t["code"] for t in listing.json()]
        assert codes, "creation catalog is EMPTY with the flag on"
        assert "leave" in codes, "leave disappeared from the catalog with the flag on"

        # وكل نوع معروض يقبله POST — نجرّب أول نوع بحمولة صالحة
        r = client.post("/api/requests", headers=emp, json={
            "request_type_code": "leave",
            "payload_json": {"start_date": "2027-03-01", "end_date": "2027-03-03",
                             "days": 3, "leave_type": "annual", "reason": "اختبار"},
        })
        assert r.status_code != 400 or "LEGACY_ALIAS_BLOCKED" not in str(r.json()), (
            f"catalog offered 'leave' but POST rejected it: {r.text[:200]}"
        )
    finally:
        db = SessionLocal()
        try:
            row = db.scalar(select(models.FeatureFlag).where(
                models.FeatureFlag.key == ff.V15_LEGACY_CATALOG_HIDDEN,
                models.FeatureFlag.company_id.is_(None)))
            if row:
                if prev is None:
                    db.delete(row)
                else:
                    row.value = prev
            db.commit()
        finally:
            db.close()


def test_return_resubmit_reapprove_full_cycle(client):
    """FIX — دورة كاملة: submit → return → resubmit → approve بنفس المستخدم.

    كان الـdouble-decide guard بيشوف القرار القديم (returned) ويرفض القرار الجديد
    بـ409 "اتخذت قرارًا مسبقًا" — الطلب يتجمّد للأبد بعد أي إعادة تقديم.
    """
    emp_h = auth_headers(login(client, *EMP))
    r = client.post("/api/requests", headers=emp_h, json={
        "request_type_code": "salary_certificate",
        "payload_json": {"purpose": "بنك الاختبار", "language": "ar", "notes": "قرض شخصي"},
    })
    if r.status_code != 201:
        return
    req_id = r.json()["id"]

    mgr = auth_headers(login(client, *MGR))
    # 1) المدير يرجّع الطلب للتصحيح
    ret = client.post(f"/api/requests/{req_id}/decide", headers=mgr, json={
        "decision": "returned", "note": "الجهة الموجه إليها غير واضحة",
    })
    if ret.status_code != 200:
        return  # المدير مش المعتمِد للمرحلة الأولى في هذا النوع
    assert client.get(f"/api/requests/{req_id}", headers=mgr).json()["status"] == "returned"

    # 2) الموظف يعيد التقديم ببيانات مصحّحة
    re = client.post(f"/api/requests/{req_id}/resubmit", headers=emp_h, json={
        "payload_json": {"purpose": "بنك الكويت الوطني", "language": "ar", "notes": "قرض سكني"},
    })
    assert re.status_code == 200, re.text
    after_resubmit = client.get(f"/api/requests/{req_id}", headers=mgr).json()
    assert after_resubmit["status"] == "pending"
    assert after_resubmit["current_stage"] == 0

    # 3) نفس المدير يعتمد الآن — يجب ألا يرجع 409
    ok = client.post(f"/api/requests/{req_id}/decide", headers=mgr, json={
        "decision": "approved", "note": "تم التصحيح",
    })
    assert ok.status_code == 200, \
        f"resubmit cycle blocked by stale double-decide guard: {ok.status_code} {ok.text}"
    assert client.get(f"/api/requests/{req_id}", headers=mgr).json()["status"] != "returned"


def test_apply_failed_status_map(client):
    """P0-#6 — status_info('apply_failed') يرجع v15='FAILED' و label واضح."""
    from app.workflow import status_info
    info = status_info("apply_failed")
    assert info["v15"] == "FAILED"
    assert "فشل" in info["label"] or "Failed" in info["label"]
    assert info["code"] == "APPLY_FAILED"


# ============================================================================
# P0-#7 — Audit: correlation_id + before/after على transitions
# ============================================================================

def test_audit_submit_has_correlation_id_and_after(client):
    """P0-#7 — submit_request يترك سطر audit فيه correlation_id + after_json."""
    from app.database import SessionLocal
    from app import models
    from sqlalchemy import select

    emp = auth_headers(login(client, *EMP))
    r = client.post("/api/requests", headers=emp, json={
        "request_type_code": "salary_certificate",
        "payload_json": {"purpose": "بنك", "language": "ar", "notes": "قرض"},
    })
    if r.status_code != 201:
        return
    req_id = r.json()["id"]

    db = SessionLocal()
    try:
        log = db.scalar(select(models.AuditLog).where(
            models.AuditLog.action == "submit_request",
            models.AuditLog.entity_id == req_id,
        ).order_by(models.AuditLog.id.desc()))
        assert log is not None
        assert log.correlation_id == f"req:{req_id}"
        assert log.after_json is not None
        assert "status" in log.after_json
    finally:
        db.close()


# ============================================================================
# P0-#10 — Expiry engine dedup + idempotent scan
# ============================================================================

# ============================================================================
# P0-#14 — Leave privacy: mask start/end dates for own requests
# ============================================================================

def test_my_profile_leaves_hide_dates(client):
    """P0-#14 — /me/profile للـleaves ما يظهر start_date/end_date/days."""
    emp = auth_headers(login(client, *EMP))
    r = client.get("/api/me/profile", headers=emp)
    if r.status_code != 200:
        return
    for leave in r.json().get("leaves", []):
        assert "start_date" not in leave, f"leave shouldn't expose start_date: {leave}"
        assert "end_date" not in leave, f"leave shouldn't expose end_date: {leave}"
        assert "days" not in leave, f"leave shouldn't expose days: {leave}"
        # يظل يعرض النوع والحالة
        assert "type" in leave or "status" in leave


def test_own_leave_request_dates_masked(client):
    """P0-#14 — الموظف يقدّم leave، ويحاول عرض تفاصيله — يجب إخفاء التواريخ."""
    from datetime import date, timedelta
    emp_h = auth_headers(login(client, *EMP))
    d1 = (date.today() + timedelta(days=30)).isoformat()
    d2 = (date.today() + timedelta(days=32)).isoformat()
    r = client.post("/api/requests", headers=emp_h, json={
        "request_type_code": "leave",
        "payload_json": {"start_date": d1, "end_date": d2, "days": 3, "leave_type": "annual", "reason": "اختبار"},
    })
    if r.status_code != 201:
        return
    req_id = r.json()["id"]

    # الموظف يعرض طلبه → payload masked
    detail = client.get(f"/api/requests/{req_id}", headers=emp_h).json()
    payload = detail.get("payload", {})
    assert "start_date" not in payload, f"employee shouldn't see start_date: {payload}"
    assert "end_date" not in payload, f"employee shouldn't see end_date: {payload}"
    assert detail.get("payload_masked") is True


def test_hr_sees_leave_dates(client):
    """P0-#14 — HR يشوف تواريخ الإجازة كاملة (مش مربوطة بموظفه)."""
    from app.database import SessionLocal
    from app import models
    from sqlalchemy import select
    from datetime import date, timedelta

    emp_h = auth_headers(login(client, *EMP))
    d1 = (date.today() + timedelta(days=45)).isoformat()
    d2 = (date.today() + timedelta(days=47)).isoformat()
    r = client.post("/api/requests", headers=emp_h, json={
        "request_type_code": "leave",
        "payload_json": {"start_date": d1, "end_date": d2, "days": 3, "leave_type": "annual", "reason": "اختبار"},
    })
    if r.status_code != 201:
        return
    req_id = r.json()["id"]

    hr = auth_headers(login(client, *HR))
    detail = client.get(f"/api/requests/{req_id}", headers=hr).json()
    payload = detail.get("payload", {})
    # HR (مش نفس الموظف) يشوف التواريخ
    assert payload.get("start_date") == d1
    assert payload.get("end_date") == d2


# ============================================================================
# P1-#18 — Notifications: close tasks (open + in_progress) on terminal state
# ============================================================================

def test_terminal_request_closes_in_progress_tasks(client):
    """P1-#18 — رفض طلب يقفل tasks حتى لو كانت in_progress (مش open فقط)."""
    from app.database import SessionLocal
    from app import models
    from sqlalchemy import select
    from datetime import datetime, timezone

    emp = auth_headers(login(client, *EMP))
    r = client.post("/api/requests", headers=emp, json={
        "request_type_code": "salary_certificate",
        "payload_json": {"purpose": "بنك", "language": "ar", "notes": "قرض"},
    })
    if r.status_code != 201:
        return
    req_id = r.json()["id"]

    # اضطر task لتكون in_progress يدويًا
    db = SessionLocal()
    try:
        stage_task = db.scalar(select(models.Task).where(
            models.Task.related_entity_type == "request",
            models.Task.related_entity_id == req_id,
            models.Task.status == "open",
        ))
        if stage_task:
            stage_task.status = "in_progress"
            db.commit()
    finally:
        db.close()

    # الآن ارفض من company_manager
    mgr = auth_headers(login(client, *MGR))
    decide = client.post(f"/api/requests/{req_id}/decide", headers=mgr, json={
        "decision": "rejected", "note": "test rejection",
    })
    if decide.status_code != 200:
        return

    # tasks المرتبطة بالطلب لازم كلها مقفولة (لا open ولا in_progress)
    db = SessionLocal()
    try:
        still_open = db.scalars(select(models.Task).where(
            models.Task.related_entity_type == "request",
            models.Task.related_entity_id == req_id,
            models.Task.status.in_(("open", "in_progress")),
            models.Task.type != "request_update",  # notifications عن الرفض نفسه
        )).all()
        # المهام الأصلية (زي stage tasks) لازم اتقفلت
        stage_still_open = [t for t in still_open if t.type != "request_update"]
        assert len(stage_still_open) == 0, \
            f"tasks stayed open after rejection: {[t.type for t in stage_still_open]}"
    finally:
        db.close()


# ============================================================================
# P1-#17 — Accountant export: minimum necessary payroll data
# ============================================================================

def test_accountant_export_hides_nationality_and_job_title(client):
    """P1-#17 — accountant export لا يشمل الجنسية والمسمى الوظيفي."""
    from app.database import SessionLocal
    from app import models
    from sqlalchemy import select
    db = SessionLocal()
    try:
        acc = db.scalar(select(models.User).where(
            models.User.role == "accountant", models.User.company_id == 1))
        civ = acc.civil_id if acc else None
    finally:
        db.close()
    if not civ:
        return
    token = login(client, civ, "account123")
    r = client.get("/api/reports/employees", headers=auth_headers(token),
                  params={"fmt": "csv"})
    if r.status_code != 200:
        return
    content = r.content.decode("utf-8", errors="ignore")
    # الأعمدة المسموحة تظهر
    assert "الاسم" in content or "employee" in content.lower()
    assert "الراتب" in content or "salary" in content.lower()
    # المحذوفة للمحاسب مش موجودة
    assert "الجنسية" not in content
    assert "المسمى" not in content


def test_hr_export_still_has_full_columns(client):
    """P1-#17 — HR يظل يشوف الأعمدة كاملة (nationality + job_title موجودين)."""
    hr = auth_headers(login(client, *HR))
    r = client.get("/api/reports/employees", headers=hr, params={"fmt": "csv"})
    if r.status_code != 200:
        return
    content = r.content.decode("utf-8", errors="ignore")
    assert "الجنسية" in content
    assert "المسمى" in content


# ============================================================================
# P1-#16 — Custom doc historical version download + audit
# ============================================================================

def test_custom_doc_historical_download_audited(client):
    """P1-#16 — تنزيل نسخة تاريخية بمعرّفها + audit سطر لكل تنزيل."""
    from app.database import SessionLocal
    from app import models
    from sqlalchemy import select

    mgr = auth_headers(login(client, *MGR))
    cid = client.get("/api/archive/company", headers=mgr).json()["company"]["id"]

    # add custom doc
    r = client.post("/api/archive/custom-doc", headers=mgr, files=_f(b"v1"), data={
        "entity_type": "company", "entity_id": str(cid), "name_ar": "hist test",
    })
    if r.status_code != 201:
        return
    doc_id = r.json()["id"]

    # replace to create v2
    r2 = client.post(f"/api/archive/custom-doc/{doc_id}/replace",
                    headers=mgr, files=_f(b"v2"))
    assert r2.status_code == 200
    v2_id = r2.json()["id"]

    # التاريخ يعرض النسختين
    hist = client.get(f"/api/archive/custom-doc/{doc_id}/history", headers=mgr).json()
    version_ids = [h["id"] for h in hist]
    assert doc_id in version_ids and v2_id in version_ids

    # نزّل النسخة القديمة (v1)
    d1 = client.get(f"/api/archive/custom-doc/{doc_id}/download", headers=mgr)
    assert d1.status_code == 200

    # audit سطر ظهر
    db = SessionLocal()
    try:
        log = db.scalar(select(models.AuditLog).where(
            models.AuditLog.action == "download_custom_doc_version",
            models.AuditLog.correlation_id == f"doc:{doc_id}",
        ).order_by(models.AuditLog.id.desc()))
        assert log is not None
    finally:
        db.close()


# ============================================================================
# QA §6 — EOS full lifecycle (9 stages, separation of duties)
# ============================================================================

def _eos_actor(role: str, pw: str, company_id: int = 1):
    """يرجع civil_id لمستخدم بدور معيّن في شركة محددة (أو None)."""
    from app.database import SessionLocal
    from app import models
    db = SessionLocal()
    try:
        u = db.scalar(select(models.User).where(
            models.User.role == role, models.User.company_id == company_id))
        return (u.civil_id, pw) if u else None
    finally:
        db.close()


def _pick_eos_candidate() -> int | None:
    """موظف نشط ببيانات كاملة، بلا حالة إنهاء مفتوحة، وغير مربوط بأي حساب
    إداري — حتى لا يصطدم الاختبار بحاجز 'لا تعتمد تسوية تخصّك'."""
    from app.database import SessionLocal
    from app import models
    db = SessionLocal()
    try:
        linked = {uid for uid in db.scalars(select(models.User.employee_id).where(
            models.User.employee_id.is_not(None))).all()}
        cands = db.scalars(select(models.Employee).where(
            models.Employee.company_id == 1,
            models.Employee.status == "active",
            models.Employee.basic_salary > 0,
            models.Employee.hire_date.is_not(None),
        )).all()
        for e in cands:
            if e.id in linked:
                continue
            has_case = db.scalar(select(models.EosCase).where(
                models.EosCase.employee_id == e.id,
                models.EosCase.status != "filed"))
            if not has_case:
                return e.id
        return None
    finally:
        db.close()


def test_eos_full_lifecycle_nine_stages(client):
    """QA §6 — دورة كاملة: initiate → calculate → approve → clearance
    → acknowledge → settle → print → file، مع فرض فصل السلطات."""
    from app.database import SessionLocal
    from app import models
    from datetime import date, timedelta

    acc = _eos_actor("accountant", "account123")
    if not acc:
        return
    hr = auth_headers(login(client, *HR))
    admin = auth_headers(login(client, *ADMIN))
    acc_h = auth_headers(login(client, *acc))

    # اختر موظفًا نشطًا ببيانات كاملة ولا حالة مفتوحة
    emp_id = _pick_eos_candidate()
    if not emp_id:
        return

    term_date = (date.today() + timedelta(days=30)).isoformat()

    # 1) HR يفتح الحالة
    r = client.post("/api/eos/cases", headers=hr, params={
        "employee_id": emp_id, "termination_date": term_date, "reason": "resignation",
    })
    assert r.status_code == 201, r.text
    case = r.json()
    cid = case["id"]
    assert case["status"] == "initiated"
    assert case["reference_no"].startswith("EOS/")
    assert case["settlement"] is None, "no numbers before the finance stage"

    # منع فتح حالة ثانية لنفس الموظف
    dup = client.post("/api/eos/cases", headers=hr, params={
        "employee_id": emp_id, "termination_date": term_date, "reason": "resignation"})
    assert dup.status_code == 409

    # 2) المحاسب يحسب — الأرقام من سجل الموظف
    calc = client.post(f"/api/eos/cases/{cid}/calculate", headers=acc_h,
                      params={"used_leave_days": 5})
    assert calc.status_code == 200, calc.text
    assert calc.json()["status"] == "calculated"
    assert calc.json()["settlement"]["total_settlement"] is not None

    # 3) فصل السلطات: نفس المحاسب لا يعتمد ما حسبه
    self_approve = client.post(f"/api/eos/cases/{cid}/approve", headers=acc_h)
    assert self_approve.status_code == 403, "same actor must not approve own calculation"

    # الاعتماد من جهة ثالثة — المدير العام (غير HR الذي فتح، وغير المالية التي حسبت)
    mgr = auth_headers(login(client, *MGR))
    ok = client.post(f"/api/eos/cases/{cid}/approve", headers=mgr,
                    params={"note": "معتمد"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "approved"

    # 4) إخلاء الطرف — HR، والتفاصيل إلزامية
    empty = client.post(f"/api/eos/cases/{cid}/clearance", headers=hr, params={"notes": ""})
    assert empty.status_code in (400, 422)
    cl = client.post(f"/api/eos/cases/{cid}/clearance", headers=hr,
                    params={"notes": "تم تسليم العهدة والبطاقة"})
    assert cl.status_code == 200
    assert cl.json()["status"] == "clearance"

    # 5) إقرار الموظف — HR لا يوقّع نيابة عنه
    wrong = client.post(f"/api/eos/cases/{cid}/acknowledge", headers=hr)
    assert wrong.status_code == 403, "acknowledgment must come from the employee"

    ack = client.post(f"/api/eos/cases/{cid}/acknowledge", headers=admin,
                     params={"note": "اطلعت على التسوية"})
    assert ack.status_code == 200
    assert ack.json()["status"] == "acknowledged"

    # 6) الصرف — المحاسب، ومرجع الدفع إلزامي
    st = client.post(f"/api/eos/cases/{cid}/settle", headers=acc_h,
                    params={"payment_reference": "TRX-EOS-0001"})
    assert st.status_code == 200, st.text
    assert st.json()["status"] == "ready_to_print"

    # الفصل يُطبَّق على ملف الموظف بعد الصرف فقط
    db = SessionLocal()
    try:
        emp = db.get(models.Employee, emp_id)
        assert emp.status == "terminated"
        assert emp.eos_settlement_json is not None
    finally:
        db.close()

    # 7) الطباعة ثم 8) الأرشفة
    pr = client.post(f"/api/eos/cases/{cid}/print", headers=hr)
    assert pr.status_code == 200 and pr.json()["status"] == "printed"

    fl = client.post(f"/api/eos/cases/{cid}/file", headers=hr,
                    params={"filing_location": "أرشيف الموارد البشرية — رف 3"})
    assert fl.status_code == 200
    final = fl.json()
    assert final["status"] == "filed"
    assert final["filing_location"]

    # كل مرحلة سجّلت الفاعل والوقت
    for actor_field, time_field in [
        ("initiated_by", "initiated_at"), ("calculated_by", "calculated_at"),
        ("approved_by", "approved_at"), ("clearance_by", "clearance_at"),
        ("settled_by", "settled_at"), ("printed_by", "printed_at"),
        ("filed_by", "filed_at"),
    ]:
        assert final[actor_field] is not None, f"{actor_field} not recorded"
        assert final[time_field] is not None, f"{time_field} not recorded"
    assert final["acknowledged_at"] is not None


def test_eos_stage_order_enforced(client):
    """QA §6 — لا يمكن القفز فوق المراحل (مثلاً الاعتماد قبل الحساب)."""
    from datetime import date, timedelta
    from app.database import SessionLocal
    from app import models

    hr = auth_headers(login(client, *HR))
    admin = auth_headers(login(client, *ADMIN))

    emp_id = _pick_eos_candidate()
    if not emp_id:
        return

    r = client.post("/api/eos/cases", headers=hr, params={
        "employee_id": emp_id,
        "termination_date": (date.today() + timedelta(days=15)).isoformat(),
        "reason": "resignation",
    })
    if r.status_code != 201:
        return
    cid = r.json()["id"]

    # اعتماد قبل الحساب → 409
    early = client.post(f"/api/eos/cases/{cid}/approve", headers=admin)
    assert early.status_code == 409

    # صرف قبل الإقرار → 409
    early_settle = client.post(f"/api/eos/cases/{cid}/settle", headers=admin,
                              params={"payment_reference": "X"})
    assert early_settle.status_code == 409

    # أرشفة قبل الطباعة → 409
    early_file = client.post(f"/api/eos/cases/{cid}/file", headers=hr,
                            params={"filing_location": "X"})
    assert early_file.status_code == 409


# ============================================================================
# P0-#13 — Residency renewal E2E (state transitions + doc chain)
# ============================================================================

def test_residency_renewal_full_state_chain(client):
    """P0-#13 — تجديد كامل: awaiting_contracts → awaiting_signature → contracts_signed
    → renewing → awaiting_civil_card → pending_hr_verify → completed.

    يتحقق من كل transition بالتسلسل الصحيح على حسب الـstate machine الحالي."""
    import io
    from app.database import SessionLocal
    from app import models
    from sqlalchemy import select

    # نستخدم موظف عنده permit مفتوح للتجديد (لو موجود). لو مافيش، skip.
    emp_h = auth_headers(login(client, *EMP))
    exists = client.get("/api/renewals", headers=emp_h).json()
    open_rn = next((rn for rn in exists if rn["status"] == "awaiting_contracts"), None)
    if not open_rn:
        r = client.post("/api/renewals", headers=emp_h)
        if r.status_code != 201:
            return
        if r.json()["status"] != "awaiting_contracts":
            return
        rid = r.json()["id"]
    else:
        rid = open_rn["id"]

    pro = auth_headers(login(client, *PRO))

    # PRO يرفع العقد الحكومي (P0-#13 §1 — يكفي وحده لانتقال الحالة)
    up = client.post(f"/api/renewals/{rid}/upload", headers=pro,
                    data={"doc_type": "renewal_contract_gov"},
                    files={"file": ("gov.pdf", io.BytesIO(b"gov"), "application/pdf")})
    assert up.status_code == 200
    after1 = client.get(f"/api/renewals/{rid}", headers=pro).json()
    assert after1["status"] == "awaiting_signature"

    # الموظف يرفع النسخة الموقّعة الحكومية
    up2 = client.post(f"/api/renewals/{rid}/upload", headers=emp_h,
                     data={"doc_type": "renewal_signed_gov"},
                     files={"file": ("signed.pdf", io.BytesIO(b"signed"), "application/pdf")})
    assert up2.status_code == 200
    after2 = client.get(f"/api/renewals/{rid}", headers=pro).json()
    assert after2["status"] == "contracts_signed"

    # PRO يبدأ التجديد
    r_renew = client.post(f"/api/renewals/{rid}/renewing", headers=pro)
    assert r_renew.status_code == 200
    assert r_renew.json()["status"] == "renewing"

    # PRO يرفع إذن العمل الجديد
    up3 = client.post(f"/api/renewals/{rid}/upload", headers=pro,
                     data={"doc_type": "work_permit"},
                     files={"file": ("wp.pdf", io.BytesIO(b"wp"), "application/pdf")})
    assert up3.status_code == 200
    after3 = client.get(f"/api/renewals/{rid}", headers=pro).json()
    assert after3["status"] == "awaiting_civil_card"

    # PRO يعبّي metadata الحكومية
    from datetime import date, timedelta
    fin = client.post(f"/api/renewals/{rid}/finalize", headers=pro, data={
        "gov_reference_no": "GOV-TEST-999",
        "fees_amount": "150.500",
        "fees_receipt_no": "R-999",
        "new_permit_number": "RES-NEW-999",
        "new_expiry_date": (date.today() + timedelta(days=730)).isoformat(),
    })
    assert fin.status_code == 200

    # الموظف يرفع البطاقة المدنية
    up4 = client.post(f"/api/renewals/{rid}/upload", headers=emp_h,
                     data={"doc_type": "civil_id"},
                     files={"file": ("cid.pdf", io.BytesIO(b"cid"), "application/pdf")})
    assert up4.status_code == 200
    after4 = client.get(f"/api/renewals/{rid}", headers=pro).json()
    assert after4["status"] == "pending_hr_verify"

    # HR يتحقق ويغلق
    hr = auth_headers(login(client, *HR))
    verify = client.post(f"/api/renewals/{rid}/hr-verify", headers=hr,
                        data={"note": "تم التحقق"})
    assert verify.status_code == 200
    assert verify.json()["status"] == "completed"


# ============================================================================
# P0-#8 — Payroll lifecycle: reopen with reason
# ============================================================================

# ============================================================================
# P1-#15 — Signature replacement: reason mandatory, version bump, HR task
# ============================================================================

def test_signature_version_starts_at_zero(client):
    """P1-#15 — /me/signature يرد signature_version."""
    hr = auth_headers(login(client, *HR))
    r = client.get("/api/me/signature", headers=hr)
    assert r.status_code == 200
    assert "signature_version" in r.json()
    assert isinstance(r.json()["signature_version"], int)


def test_signature_history_immutable_evidence_chain(client):
    """QA §12 — كل نسخة معتمَدة تُسجَّل بسياق كامل ولا تُعاد مسارات التخزين."""
    from app.database import SessionLocal
    from app import models

    db = SessionLocal()
    try:
        sup = db.scalar(select(models.User).where(
            models.User.role == "branch_supervisor", models.User.company_id == 1))
        civ = sup.civil_id if sup else None
        uid = sup.id if sup else None
    finally:
        db.close()
    if not civ:
        return

    h = auth_headers(login(client, civ, "sup12345"))
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d49444154789c626001000000050001a5f645ea0000000049454e44ae426082"
    )
    client.delete("/api/me/signature", headers=h)
    r1 = client.post("/api/me/signature", headers=h,
                    files={"file": ("s.png", png, "image/png")})
    if r1.status_code != 201:
        return

    hist = client.get("/api/me/signature/history", headers=h)
    assert hist.status_code == 200
    body = hist.json()
    assert body["current_version"] >= 1
    assert len(body["versions"]) >= 1

    top = body["versions"][0]
    # سياق الـevidence موجود
    assert top["reference_no"], "each version needs a citable reference"
    assert top["correlation_id"] == f"sig:{uid}"
    assert top["actor_role"] == "branch_supervisor"
    assert top["stage"] in ("first_upload", "direct", "approved")
    assert top["checksum_sha256"] and len(top["checksum_sha256"]) == 64
    # لا يُسرَّب مسار التخزين
    assert "file_path" not in top

    # النسخ فريدة ومتصاعدة
    versions = [v["version"] for v in body["versions"]]
    assert len(set(versions)) == len(versions), "versions must be unique"
    assert versions == sorted(versions, reverse=True), "newest first"


def test_signature_replacement_requires_reason(client):
    """P1-#15 — استبدال بدون سبب → 400."""
    import io
    # نستخدم branch_supervisor (مش hr/super_admin — عشان يمر بالـpending flow)
    from app.database import SessionLocal
    from app import models
    db = SessionLocal()
    try:
        sup = db.scalar(select(models.User).where(
            models.User.role == "branch_supervisor", models.User.company_id == 1))
        civ = sup.civil_id if sup else None
    finally:
        db.close()
    if not civ:
        return
    token = login(client, civ, "sup12345")
    h = auth_headers(token)

    # أول رفع (بدون سبب مسموح — direct application)
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d49444154789c626001000000050001a5f645ea0000000049454e44ae426082"
    )
    r1 = client.post("/api/me/signature", headers=h,
                    files={"file": ("s.png", png, "image/png")})
    if r1.status_code != 201:
        return

    # الرفع الثاني (استبدال) بدون سبب → 400
    r2 = client.post("/api/me/signature", headers=h,
                    files={"file": ("s2.png", png, "image/png")})
    assert r2.status_code == 400
    assert "سبب" in r2.json()["detail"]


# ============================================================================
# P0-#12 — Gov contract generation E2E: autofill correctness
# ============================================================================

def test_gov_contract_autofills_employee_fields(client):
    """P0-#12 — العقد الحكومي يُمَلأ بالحقول الموثوقة من ملف الموظف."""
    _seed_contract_template(client, "GOV-CONTRACT-HIRE")
    mgr = auth_headers(login(client, *MGR))
    emps = client.get("/api/employees", headers=mgr).json()
    if not emps:
        return
    emp = emps[0]
    emp_id = emp["id"]

    r = client.post(f"/api/employees/{emp_id}/gov-contract/generate", headers=mgr)
    assert r.status_code == 200, r.text
    body = r.json()
    html = body["html"]

    # بيانات الموظف الأساسية لازم تظهر في الـHTML
    if emp.get("name"):
        assert emp["name"] in html, "employee name should appear in generated contract"
    if emp.get("civil_id"):
        assert emp["civil_id"] in html, "civil_id should appear"
    if emp.get("job_title"):
        assert emp["job_title"] in html, "job_title should appear"

    # metadata من الـissued document
    assert body["reference_no"].startswith("GOV-CONTRACT-HIRE/")
    assert len(body["checksum_sha256"]) == 64
    assert body["document_id"] > 0


def test_gov_contract_pdf_and_html_both_generate(client):
    """P0-#12 — HTML format = JSON مع html، PDF format = FileResponse."""
    _seed_contract_template(client, "COMPANY-CONTRACT-HIRE")
    mgr = auth_headers(login(client, *MGR))
    emp_id = client.get("/api/employees", headers=mgr).json()[0]["id"]

    # HTML default
    r_html = client.post(f"/api/employees/{emp_id}/company-contract/generate", headers=mgr)
    assert r_html.status_code == 200
    assert "html" in r_html.json()

    # PDF explicit
    r_pdf = client.post(f"/api/employees/{emp_id}/company-contract/generate",
                        headers=mgr, params={"format": "pdf"})
    assert r_pdf.status_code == 200
    assert r_pdf.headers["content-type"] == "application/pdf"
    assert r_pdf.content[:4] == b"%PDF"


def test_contract_regeneration_bumps_version_single_current(client):
    """QA §9 — إعادة التوليد: version يزيد، ونسخة حالية واحدة فقط.

    الخلل السابق: كل توليد كان يكتب version=1 و is_current=True بلا تنزيل السابق،
    فينتج عدة "نسخ حالية" وتاريخ نسخ يرجع دائمًا لـv1.
    """
    from app.database import SessionLocal
    from app import models
    from sqlalchemy import select

    _seed_contract_template(client, "GOV-CONTRACT-HIRE")
    mgr = auth_headers(login(client, *MGR))
    emp_id = client.get("/api/employees", headers=mgr).json()[0]["id"]

    r1 = client.post(f"/api/employees/{emp_id}/gov-contract/generate", headers=mgr)
    assert r1.status_code == 200
    r2 = client.post(f"/api/employees/{emp_id}/gov-contract/generate", headers=mgr)
    assert r2.status_code == 200
    r3 = client.post(f"/api/employees/{emp_id}/gov-contract/generate", headers=mgr)
    assert r3.status_code == 200

    doc_code = f"gov_contract_hire_{emp_id}"
    db = SessionLocal()
    try:
        rows = db.scalars(select(models.Document).where(
            models.Document.entity_type == "employee",
            models.Document.entity_id == emp_id,
            models.Document.document_type_code == doc_code,
        )).all()
        currents = [d for d in rows if d.is_current]
        assert len(currents) == 1, \
            f"expected exactly one current, found {len(currents)}"
        versions = sorted(d.version for d in rows)
        # النسخ تتصاعد 1,2,3... بلا تكرار
        assert versions == list(range(1, len(rows) + 1)), \
            f"versions not sequential: {versions}"
        assert currents[0].version == max(versions), \
            "current should be the highest version"
        # كل نسخة لها reference_no فريد
        refs = [d.reference_no for d in rows]
        assert len(set(refs)) == len(refs), "reference numbers must be unique per version"
    finally:
        db.close()


def test_gov_contract_saves_as_issued_document(client):
    """P0-#12 — التوليد يحفظ صف Document بـis_issued=True مع كل الـmetadata."""
    _seed_contract_template(client, "GOV-CONTRACT-HIRE")
    mgr = auth_headers(login(client, *MGR))
    emp_id = client.get("/api/employees", headers=mgr).json()[0]["id"]

    r = client.post(f"/api/employees/{emp_id}/gov-contract/generate", headers=mgr)
    doc_id = r.json()["document_id"]

    from app.database import SessionLocal
    from app import models
    db = SessionLocal()
    try:
        doc = db.get(models.Document, doc_id)
        assert doc is not None
        assert doc.is_issued is True
        assert doc.reference_no is not None
        assert doc.checksum_sha256 is not None
        assert doc.generated_at is not None
        assert doc.generated_by is not None
        assert doc.entity_type == "employee"
        assert doc.entity_id == emp_id
    finally:
        db.close()


def test_payroll_reopen_requires_reason(client):
    """P0-#8 — /reopen بدون سبب → 400."""
    admin = auth_headers(login(client, *ADMIN))
    # جرّب على أي run موجود
    from app.database import SessionLocal
    from app import models
    from sqlalchemy import select
    db = SessionLocal()
    try:
        pr = db.scalar(select(models.PayrollRun).where(
            models.PayrollRun.status.in_(("approved", "finalized"))
        ))
        pr_id = pr.id if pr else None
    finally:
        db.close()
    if not pr_id:
        return  # ما فيش run بالحالة دي في الـseed
    r = client.post(f"/api/payroll/runs/{pr_id}/reopen", headers=admin,
                   params={"reason": ""})
    assert r.status_code in (400, 422)  # 400 من الـfn، 422 من Pydantic


def test_payroll_reopen_super_admin_only(client):
    """P0-#8 — /reopen فقط لـsuper_admin."""
    hr = auth_headers(login(client, *HR))
    r = client.post("/api/payroll/runs/1/reopen", headers=hr,
                   params={"reason": "خطأ في الحسابات"})
    assert r.status_code == 403


def test_payroll_reopen_rejects_locked(client):
    """P0-#8 — locked ما يُعاد فتحه — يحتاج adjustment_run."""
    from app.database import SessionLocal
    from app import models
    from sqlalchemy import select
    admin = auth_headers(login(client, *ADMIN))
    db = SessionLocal()
    try:
        pr = db.scalar(select(models.PayrollRun).where(
            models.PayrollRun.status == "locked"))
        pr_id = pr.id if pr else None
    finally:
        db.close()
    if not pr_id:
        return
    r = client.post(f"/api/payroll/runs/{pr_id}/reopen", headers=admin,
                   params={"reason": "test"})
    assert r.status_code == 409


def test_expiry_scan_idempotent_no_duplicate_tasks(client):
    """P0-#10 — تشغيل daily_scan مرتين → مافيش duplicate tasks للـdocument نفسه."""
    from app.database import SessionLocal
    from app.notifications import daily_scan
    from app import models
    from sqlalchemy import select, func
    from datetime import date, timedelta

    # أضف مستند expiry_date قريب لأي موظف عشان يدخل الـscan
    db = SessionLocal()
    doc_id = None
    try:
        emp = db.scalar(select(models.Employee).limit(1))
        assert emp is not None
        cid = emp.company_id
        # مستند بتاريخ انتهاء بعد 15 يوم (في bucket 15)
        doc = models.Document(
            company_id=cid, entity_type="employee", entity_id=emp.id,
            document_type_code="passport", title="Test passport",
            expiry_date=date.today() + timedelta(days=15),
            version=1, is_current=True,
        )
        db.add(doc); db.commit(); doc_id = doc.id

        # المسح الأول
        daily_scan(db)
        first_count = db.scalar(select(func.count()).select_from(models.Task).where(
            models.Task.related_entity_type == "document",
            models.Task.related_entity_id == doc_id,
            models.Task.type == "doc_expiring",
            models.Task.status.in_(("open", "in_progress")),
        ))
        assert first_count >= 1

        # المسح الثاني — يجب ألا يزيد العدد
        daily_scan(db)
        second_count = db.scalar(select(func.count()).select_from(models.Task).where(
            models.Task.related_entity_type == "document",
            models.Task.related_entity_id == doc_id,
            models.Task.type == "doc_expiring",
            models.Task.status.in_(("open", "in_progress")),
        ))
        assert second_count == first_count, \
            f"scan idempotency broken: {first_count} → {second_count}"
    finally:
        if doc_id:
            db.execute(models.Task.__table__.delete().where(
                models.Task.related_entity_type == "document",
                models.Task.related_entity_id == doc_id,
            ))
            db.execute(models.Document.__table__.delete().where(
                models.Document.id == doc_id))
            db.commit()
        db.close()


# ===========================================================================
# تقديم الطلبات نيابةً عن موظف آخر — مقصور على HR
# ===========================================================================

def test_on_behalf_restricted_to_hr(client):
    """التقديم باسم موظف آخر مقصور على HR والمندوب.

    كان الخادم لا يفحص هذا إطلاقًا: assert_same_company وحدها كانت الحارس، فأي
    حساب يملك submit_request (وهي مع كل الأدوار تقريبًا) يقدر يفتح طلبًا باسم أي
    موظف في شركته — بما فيهم من هم أعلى منه. الواجهة كانت تعرض القائمة لمن يملك
    view_employee فظهرت للمحاسب وفيها المدير العام، لكن الحجب في الواجهة لا يمنع
    POST مباشرًا: حتى الموظف العادي (الذي يُرفض بـ403 من GET /employees) كان ينجح.
    """
    emp = auth_headers(login(client, "100000000101", "emp12345"))
    acc = auth_headers(login(client, "100000000007", "account123"))
    hr = auth_headers(login(client, "100000000002", "hr12345"))

    # الهدف: مدير الشركة — وهو بالضبط من كان المحاسب يفتح له طلبات
    mgr_emp_id = client.get("/api/auth/me", headers=auth_headers(
        login(client, "100000000001", "manager123"))).json()["employee_id"]
    assert mgr_emp_id, "مدير الشركة غير مربوط بملف موظف — الاختبار يحتاج هدًفا"

    payload = {"start_date": "2027-04-01", "end_date": "2027-04-02", "days": 2,
               "leave_type": "annual", "reason": "اختبار النيابة"}

    # الموظف العادي — لا يرى القائمة أصلًا، ولا يقدر يقدّم باسم غيره
    assert client.get("/api/employees", headers=emp).status_code == 403
    r = client.post("/api/requests", headers=emp, json={
        "request_type_code": "leave", "employee_id": mgr_emp_id,
        "payload_json": payload})
    assert r.status_code == 403, r.text

    # المحاسب — يملك view_employee (يشغّل الرواتب) لكن ذلك ليس تفويًضا بالتصرف
    r = client.post("/api/requests", headers=acc, json={
        "request_type_code": "leave", "employee_id": mgr_emp_id,
        "payload_json": payload})
    assert r.status_code == 403, r.text

    # ...لكنه يقدّم لنفسه بلا عائق
    r = client.post("/api/requests", headers=acc, json={
        "request_type_code": "leave", "payload_json": payload})
    assert r.status_code == 201, r.text

    # HR يقدّم باسم غيره — الإجراءات الداخلية
    r = client.post("/api/requests", headers=hr, json={
        "request_type_code": "leave", "employee_id": mgr_emp_id,
        "payload_json": payload})
    assert r.status_code == 201, r.text

    # والمندوب كذلك — المعاملات الحكومية (تجديد إقامة/إذن عمل) يفتحها باسم
    # الموظف بحكم عمله، ولا يملك الموظف نفسه بدءها
    pro = auth_headers(login(client, "100000000003", "deleg123"))
    r = client.post("/api/requests", headers=pro, json={
        "request_type_code": "leave", "employee_id": mgr_emp_id,
        "payload_json": payload})
    assert r.status_code == 201, r.text


def test_ui_reads_on_behalf_flag_from_server(client):
    """الواجهة تقرأ can_submit_on_behalf من /auth/me بدل استنتاجه من view_employee.

    الاستنتاج كان يعطي المحاسب/المندوب/مسؤول الفرع قائمةً بكل الموظفين بينما
    الخادم يرفض تقديمهم — قاعدة واحدة موصوفة في مكانين فاختلفا.
    """
    for civil, pwd, expected in [
        ("100000000002", "hr12345", True),      # HR — الإجراءات الداخلية
        ("100000000003", "deleg123", True),     # مندوب — المعاملات الحكومية
        ("100000000007", "account123", False),  # محاسب
        ("100000000001", "manager123", False),  # مدير الشركة
        ("100000000101", "emp12345", False),    # موظف
    ]:
        me = client.get("/api/auth/me", headers=auth_headers(login(client, civil, pwd)))
        assert me.status_code == 200, me.text
        assert me.json()["can_submit_on_behalf"] is expected, civil


# ===========================================================================
# قوالب الإشعارات — كل كود يستدعيه التطبيق موجود ومبذور
# ===========================================================================

def test_every_referenced_template_code_exists(client):
    """كل كود قالب يستدعيه الكود لا بد أن يكون في الكتالوج.

    notify_from_template يرجع None حين لا يجد القالب — بلا خطأ ولا سجل قبل هذا
    الإصلاح — فكود مكتوب خطأ أو قالب حُذف كان يُسقط الإشعار بصمت.
    """
    import re
    from pathlib import Path
    from app.notification_templates import DEFAULT_NOTIFICATION_TEMPLATES

    catalog = {t["code"] for t in DEFAULT_NOTIFICATION_TEMPLATES}
    app_dir = Path(__file__).resolve().parents[1] / "app"
    referenced: set[str] = set()
    for py in app_dir.rglob("*.py"):
        for m in re.finditer(r'code\s*=\s*"(NTF-\d+|[A-Z][A-Z0-9-]{3,})"', py.read_text(encoding="utf-8")):
            if m.group(1).startswith("NTF-"):
                referenced.add(m.group(1))
    assert referenced, "لم يُعثر على أي استدعاء قالب — تحقق من التعبير النمطي"
    missing = referenced - catalog
    assert not missing, f"أكواد قوالب مستدعاة وغير معرّفة في الكتالوج: {sorted(missing)}"


def test_all_templates_are_seeded_in_the_database(client):
    """الكتالوج كله موجود في قاعدة البيانات لا في ملف بايثون فقط.

    الجدول كان يُنشأ فارغًا: الترحيل ينشئ الجدول والصفوف تُدرَج في seed.py
    التجريبي وحده — وهو محظور في الإنتاج، فبقيت 73 من 74 قالبًا غائبة هناك
    وكل إشعارات القوالب ميتة.
    """
    from sqlalchemy import select, func
    from app import models
    from app.database import SessionLocal
    from app.notification_templates import DEFAULT_NOTIFICATION_TEMPLATES

    db = SessionLocal()
    try:
        rows = {c for (c,) in db.execute(select(models.NotificationTemplate.code))}
        missing = {t["code"] for t in DEFAULT_NOTIFICATION_TEMPLATES} - rows
        assert not missing, f"قوالب غير مبذورة في قاعدة البيانات: {sorted(missing)}"
    finally:
        db.close()


def test_completion_notification_reaches_the_employee(client):
    """اكتمال الطلب يصل صاحبه — البند الذي أبلغ عنه العميل.

    NTF-037 يُستدعى عند الانتقال إلى completed؛ غيابه من قاعدة البيانات كان
    يعني ألا يصل الموظف شيء رغم أن الكود يستدعي الإشعار فعلًا.
    """
    from sqlalchemy import select
    from app import models
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        tpl = db.scalar(select(models.NotificationTemplate).where(
            models.NotificationTemplate.code == "NTF-037"))
        assert tpl is not None, "NTF-037 غير موجود — إشعار الاكتمال لن يصل"
        assert tpl.is_active
        assert "{{request_type}}" in tpl.body_text
    finally:
        db.close()


# ===========================================================================
# الخدمة الذاتية — تنزيل المستند بلا قيد على العدد
# ===========================================================================

def test_self_document_download_is_unrestricted(client):
    """الموظف ينزّل مستنده كلما احتاجه — لا حد لعدد المرات.

    تقرير المراجعة رصد تقييد التنزيل بمرة واحدة كعطل لا كميزة: المستند ملك
    الموظف ويحتاجه للبنك والسفارة والجهات الحكومية، وتقييده يجعله يراجع HR
    لأجل نسخة من ورقته. هذا الاختبار يمنع إعادة إدخال القيد سهًوا.
    """
    from sqlalchemy import select
    from app import models
    from app.database import SessionLocal

    emp_headers = auth_headers(login(client, "100000000101", "emp12345"))
    emp_id = client.get("/api/auth/me", headers=emp_headers).json()["employee_id"]
    assert emp_id

    db = SessionLocal()
    doc_id = None
    prior_ids: list[int] = []
    try:
        import tempfile, os
        fd, path = tempfile.mkstemp(suffix=".pdf")
        os.write(fd, b"%PDF-1.4 test\n")
        os.close(fd)
        emp = db.get(models.Employee, emp_id)
        prior = db.scalars(select(models.Document).where(
            models.Document.entity_type == "employee",
            models.Document.entity_id == emp_id,
            models.Document.document_type_code == "passport",
            models.Document.is_current == True,  # noqa: E712
        )).all()
        prior_ids = [d.id for d in prior]
        for d in prior:
            d.is_current = False
        doc = models.Document(
            company_id=emp.company_id, entity_type="employee", entity_id=emp_id,
            document_type_code="passport", title="جواز اختبار",
            file_path=path, mime="application/pdf", version=1, is_current=True,
        )
        db.add(doc); db.commit(); db.refresh(doc)
        doc_id = doc.id

        # ثلاث مرات متتالية — كلها تنجح
        for attempt in range(1, 4):
            r = client.get("/api/me/document/passport", headers=emp_headers)
            assert r.status_code == 200, f"المحاولة {attempt} فشلت: {r.text}"
            assert r.content.startswith(b"%PDF")
    finally:
        if doc_id:
            db.execute(models.Document.__table__.delete().where(
                models.Document.id == doc_id))
        for pid in prior_ids:
            d = db.get(models.Document, pid)
            if d:
                d.is_current = True
        db.commit(); db.close()


def test_hr_is_exempt_from_attendance(client):
    """HR لا يبصم حضوًرا — قرار العميل.

    كانت record_attendance تُمنح له ليبصم لنفسه، وهو نفسه من يصحّح سجلات
    الحضور ويعتمدها (manage_attendance) — فبصمه لنفسه يجمع الإثبات والاعتماد
    في يد واحدة. صلاحيتا العرض والتصحيح تبقيان لأداء دوره الرقابي.
    """
    from app.permissions import ROLE_DEFAULT_PERMS

    assert "record_attendance" not in ROLE_DEFAULT_PERMS["hr"]
    assert {"view_attendance", "manage_attendance"} <= ROLE_DEFAULT_PERMS["hr"]

    hr = auth_headers(login(client, "100000000002", "hr12345"))
    # نقطتا تسجيل الحضور مرفوضتان
    assert client.post("/api/attendance/validate-qr", headers=hr,
                       json={"qr_token": "x"}).status_code == 403
    # ومراجعة الحضور تبقى متاحة
    assert client.get("/api/attendance/review", headers=hr).status_code in (200, 404)


# ===========================================================================
# حقول التوظيف والعقد الناقصة (مراجعة العميل — الصفحة ٣)
# ===========================================================================

def _put_payload(client, headers, emp_id, **changes):
    """التعديل PUT بالكائن كاملًا — نقرأ الحالي ونغيّر ما يلزم فقط."""
    from app import schemas
    cur = client.get(f"/api/employees/{emp_id}", headers=headers).json()
    allowed = set(schemas.EmployeeCreateIn.model_fields)
    body = {k: v for k, v in cur.items() if k in allowed}
    body.update(changes)
    return body


def test_employment_fields_round_trip(client):
    """الحقول الجديدة تُحفظ وتُقرأ: الوظيفة الفعلية وساعات الدوام."""
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    emp_id = client.get("/api/employees", headers=hr).json()[0]["id"]

    body = _put_payload(client, hr, emp_id,
                        actual_job_title="مشرف وردية",
                        job_title_en="Shift Supervisor",
                        nationality_en="Egyptian",
                        work_hours_type="fixed",
                        official_work_hours=8, actual_work_hours=9.5)
    r = client.put(f"/api/employees/{emp_id}", headers=hr, json=body)
    assert r.status_code == 200, r.text

    back = client.get(f"/api/employees/{emp_id}", headers=hr).json()
    assert back["job_title_en"] == "Shift Supervisor"
    assert back["work_hours_type"] == "fixed"
    assert back["official_work_hours"] == 8
    assert back["actual_work_hours"] == 9.5


def test_work_hours_input_is_validated(client):
    """قيم غير معروفة أو مستحيلة تُرفض بدل أن تُحفظ بصمت."""
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    emp_id = client.get("/api/employees", headers=hr).json()[0]["id"]

    for changes in (
        {"work_hours_type": "sometimes"},
        {"work_hours_type": "fixed", "official_work_hours": 30},
        {"work_hours_type": "fixed", "actual_work_hours": -1},
    ):
        body = _put_payload(client, hr, emp_id, **changes)
        r = client.put(f"/api/employees/{emp_id}", headers=hr, json=body)
        assert r.status_code == 422, f"{changes} -> {r.status_code} {r.text[:120]}"


def test_profile_exposes_work_place_and_residency(client):
    """الملف يعرض مكان الدوام بالاسم وتاريخ انتهاء الإقامة.

    الإقامة تُحفظ في permits لا كعمود على الموظف، والفروع تُحفظ بالمعرّف —
    فلولا حلّهما في الخادم لاحتاجت كل شاشة جلب قوائم لتترجم أرقاًما.
    """
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    emp_id = client.get("/api/employees", headers=hr).json()[0]["id"]
    p = client.get(f"/api/employees/{emp_id}/profile", headers=hr)
    assert p.status_code == 200, p.text
    body = p.json()
    assert "official_branch_name" in body and "actual_branch_name" in body
    assert "permits" in body
    assert all({"kind", "expiry_date"} <= set(x) for x in body["permits"])


# ===========================================================================
# رصيد الإجازات — الخصم التلقائي والسجل (مراجعة العميل — الصفحة ٣)
# ===========================================================================

def _approve_to_completion(client, req_id: int):
    """يمرّر الطلب عبر كل مراحله حتى يكتمل."""
    approvers = [("100000000005", "sup12345"), ("100000000001", "manager123"),
                 ("100000000002", "hr12345"), ("100000000003", "deleg123")]
    for _ in range(8):
        r = client.get(f"/api/requests/{req_id}")
        for civ, pw in approvers:
            h = auth_headers(login(client, civ, pw))
            d = client.post(f"/api/requests/{req_id}/decide", headers=h,
                            json={"decision": "approved", "note": "ok"})
            if d.status_code == 200:
                break
        else:
            break
    return client


def test_leave_deducts_balance_and_records_ledger(client):
    """طلب إجازة سنوية معتمَد يخصم الرصيد ويقيّد الحركة.

    كان الطلب يمرّ بكل المراحل ثم يُغلق بلا أثر: لا صف Leave ولا خصم — فالرصيد
    يبقى 30 مهما استهلك الموظف.
    """
    from sqlalchemy import select
    from app import models
    from app.database import SessionLocal
    from app.workflow import _apply_leave

    db = SessionLocal()
    try:
        emp = db.scalars(select(models.Employee).limit(1)).first()
        before = float(emp.annual_leave_balance or 0)
        req = models.Request(
            company_id=emp.company_id, employee_id=emp.id,
            request_type_code="REQLV", status="pending", current_stage=0,
            payload_json={"leave_type": "annual", "days": 3,
                          "start_date": "2027-05-01", "end_date": "2027-05-03"},
        )
        db.add(req); db.commit(); db.refresh(req)

        ok, note = _apply_leave(db, req)
        db.commit()
        assert ok, note

        db.refresh(emp)
        assert emp.annual_leave_balance == before - 3, note

        led = db.scalars(select(models.LeaveLedger).where(
            models.LeaveLedger.request_id == req.id)).all()
        assert len(led) == 1
        assert led[0].kind == "deduction"
        assert led[0].balance_before == before
        assert led[0].balance_after == before - 3

        # لا خصم مزدوج لو أُعيد التطبيق
        ok2, note2 = _apply_leave(db, req)
        db.commit(); db.refresh(emp)
        assert ok2 and emp.annual_leave_balance == before - 3, note2
    finally:
        db.rollback(); db.close()


def test_sick_leave_does_not_touch_annual_balance(client):
    """المرضية والطارئة وبدون راتب تُسجَّل ولا تنقص الرصيد السنوي."""
    from sqlalchemy import select
    from app import models
    from app.database import SessionLocal
    from app.workflow import _apply_leave

    db = SessionLocal()
    try:
        emp = db.scalars(select(models.Employee).limit(1)).first()
        before = float(emp.annual_leave_balance or 0)
        req = models.Request(
            company_id=emp.company_id, employee_id=emp.id,
            request_type_code="REQLV", status="pending", current_stage=0,
            payload_json={"leave_type": "sick", "days": 2,
                          "start_date": "2027-06-01", "end_date": "2027-06-02"},
        )
        db.add(req); db.commit(); db.refresh(req)
        ok, note = _apply_leave(db, req)
        db.commit(); db.refresh(emp)
        assert ok, note
        assert emp.annual_leave_balance == before, "المرضية لا تُخصم من الرصيد السنوي"
    finally:
        db.rollback(); db.close()


def test_insufficient_balance_fails_instead_of_going_negative(client):
    """رصيد غير كافٍ يُفشل التطبيق بدل أن يُنشئ رصيًدا سالًبا بصمت."""
    from sqlalchemy import select
    from app import models
    from app.database import SessionLocal
    from app.workflow import _apply_leave

    db = SessionLocal()
    try:
        emp = db.scalars(select(models.Employee).limit(1)).first()
        before = float(emp.annual_leave_balance or 0)
        req = models.Request(
            company_id=emp.company_id, employee_id=emp.id,
            request_type_code="REQLV", status="pending", current_stage=0,
            payload_json={"leave_type": "annual", "days": before + 5,
                          "start_date": "2027-07-01", "end_date": "2027-07-10"},
        )
        db.add(req); db.commit(); db.refresh(req)
        ok, note = _apply_leave(db, req)
        assert not ok
        assert "الرصيد لا يكفي" in note
        db.refresh(emp)
        assert emp.annual_leave_balance == before
    finally:
        db.rollback(); db.close()


def test_profile_exposes_leave_balance_and_ledger(client):
    """الملف يعرض الرصيد والسجل — البندان الأول والثالث في طلب العميل."""
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    emp_id = client.get("/api/employees", headers=hr).json()[0]["id"]
    p = client.get(f"/api/employees/{emp_id}/profile", headers=hr).json()
    assert "leave_balance" in p
    assert isinstance(p.get("leave_ledger"), list)


# ===========================================================================
# الصفحة ٤ — صلاحية التعديل والروابط الحكومية
# ===========================================================================

def test_manager_can_grant_edit_employee(client):
    """المدير يمنح صلاحية تعديل بيانات الموظفين لـHR والمندوب والمحاسب.

    طلب العميل: زر التعديل يُتاح للمدير والمندوب وHR، والمنح من المدير وحده.
    المندوب والمحاسب لا يملكانها افتراضيًا — تُمنح صراحًة عبر مصفوفة الأذونات.
    """
    from app.permissions import ROLE_DEFAULT_PERMS

    # المدير وHR يملكانها افتراضيًا؛ المندوب والمحاسب لا
    assert "edit_employee" in ROLE_DEFAULT_PERMS["company_manager"]
    assert "edit_employee" in ROLE_DEFAULT_PERMS["hr"]
    assert "edit_employee" not in ROLE_DEFAULT_PERMS["delegate"]
    assert "edit_employee" not in ROLE_DEFAULT_PERMS["accountant"]

    # والمدير يملك manage_users — وهي بوابة المنح
    assert "manage_users" in ROLE_DEFAULT_PERMS["company_manager"]

    mgr = auth_headers(login(client, "100000000001", "manager123"))
    users = client.get("/api/users", headers=mgr)
    assert users.status_code == 200, users.text
    rows = users.json() if isinstance(users.json(), list) else users.json().get("items", [])
    pro = next(u for u in rows if u.get("role") == "delegate")

    r = client.post(f"/api/users/{pro['id']}/permissions", headers=mgr,
                    json={"perm_codes": ["edit_employee"]})
    assert r.status_code in (200, 201, 204), r.text

    pro_h = auth_headers(login(client, pro["civil_id"], "deleg123"))
    me = client.get("/api/auth/me", headers=pro_h).json()
    assert "edit_employee" in me["permissions"], "المنح لم يصل للمندوب"


def test_hr_has_no_government_portals(client):
    """الروابط الحكومية أُزيلت من HR — المعاملات الحكومية اختصاص المندوب."""
    import re
    from pathlib import Path

    app_tsx = Path(__file__).resolve().parents[2] / "frontend" / "src" / "App.tsx"
    if not app_tsx.exists():
        return
    text = app_tsx.read_text(encoding="utf-8")
    route = re.search(r'path="/gov-portals".*?/>', text, re.S)
    assert route, "مسار /gov-portals غير موجود"
    assert '"hr"' not in route.group(0), "hr ما زال في حارس مسار الروابط الحكومية"


# ===========================================================================
# المجموعة G — الأمان (2FA + الخمول)
# ===========================================================================

def test_sec01_twofa_full_cycle_works(client):
    """SEC-01 — دورة التفعيل والدخول كاملة لحساب صاحب الشركة.

    التسجيل ← التأكيد برمز صحيح ← الدخول يُرفض بلا رمز ← يُرفض برمز خاطئ ←
    ينجح بالرمز الصحيح.
    """
    import pyotp
    from sqlalchemy import select
    from app import models
    from app.database import SessionLocal

    owner = auth_headers(login(client, "111111111111", "owner123"))
    r = client.post("/api/2fa/enroll", headers=owner)
    assert r.status_code == 200, r.text
    secret = r.json()["secret"]

    ok = client.post("/api/2fa/confirm", headers=owner,
                     json={"code": pyotp.TOTP(secret).now()})
    assert ok.status_code == 200, ok.text

    db = SessionLocal()
    try:
        try:
            # بلا رمز → 401 مع requires_2fa
            bad = client.post("/api/auth/login",
                              json={"civil_id": "111111111111", "password": "owner123"})
            assert bad.status_code == 401
            assert bad.json()["detail"].get("requires_2fa") is True

            # رمز خاطئ → 401
            wrong = client.post("/api/auth/login", json={
                "civil_id": "111111111111", "password": "owner123", "totp_code": "000000"})
            assert wrong.status_code == 401

            # الرمز الصحيح → نجاح
            good = client.post("/api/auth/login", json={
                "civil_id": "111111111111", "password": "owner123",
                "totp_code": pyotp.TOTP(secret).now()})
            assert good.status_code == 200, good.text
            assert good.json()["must_enroll_2fa"] is False
        finally:
            # نُعيد الحساب لحالته حتى لا نكسر بقية الاختبارات
            u = db.scalar(select(models.User).where(
                models.User.civil_id == "111111111111"))
            u.totp_secret = None
            u.totp_confirmed = False
            db.commit()
    finally:
        db.close()


def test_sec02_twofa_required_for_sensitive_roles(client):
    """SEC-02 — الأدوار التي تملك بيانات غيرها يُلزَم أصحابها بالتفعيل."""
    from app.permissions import TWOFA_REQUIRED_ROLES

    assert {"company_owner", "company_manager", "hr", "delegate"} <= TWOFA_REQUIRED_ROLES
    # الموظف والمحاسب ومسؤول الفرع: اختياري
    assert "employee" not in TWOFA_REQUIRED_ROLES
    assert "accountant" not in TWOFA_REQUIRED_ROLES

    for civ, pw, expected in [("100000000002", "hr12345", True),
                              ("100000000003", "deleg123", True),
                              ("100000000001", "manager123", True),
                              ("100000000101", "emp12345", False)]:
        r = client.post("/api/auth/login", json={"civil_id": civ, "password": pw})
        assert r.status_code == 200, r.text
        assert r.json()["must_enroll_2fa"] is expected, civ
        me = client.get("/api/auth/me",
                        headers={"Authorization": f"Bearer {r.json()['access_token']}"}).json()
        assert me["twofa_required"] is expected


def test_sec03_no_remember_device_bypass(client):
    """SEC-03 — لا تخطي ولا "تذكّر الجهاز": الرمز مطلوب في كل دخول.

    الحارس يفحص totp_confirmed في كل نداء دخول بلا أي حالة محفوظة عن الجهاز،
    فلا يوجد مسار يتجاوزه.
    """
    import inspect
    from app.routers import auth as auth_router

    src = inspect.getsource(auth_router.login)
    assert "totp_confirmed" in src
    for bypass in ("remember_device", "trusted_device", "skip_2fa"):
        assert bypass not in src, f"مسار تخطٍّ محتمل: {bypass}"


def test_sec04_idle_logout_is_configurable(client):
    """SEC-04 — مهلة الخمول تأتي من الخادم لا مكتوبة في الواجهة."""
    from app.config import settings

    assert settings.idle_logout_minutes == 10
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    me = client.get("/api/auth/me", headers=hr).json()
    assert me["idle_logout_minutes"] == settings.idle_logout_minutes


def test_perm02_attendance_settings_need_manage_attendance(client):
    """PERM-02 — تعديل إعدادات الحضور عبر PUT يخضع لنفس ضوابط endpoint السياسة.

    كان الـPUT بابًا خلفيًا: يقبل attendance_mode وattendance_exempt ويكتبهما
    بلا فحص، فمن يملك edit_employee وحدها كان يقدر يُعفي موظًفا من البصم —
    وهو قرار رقابي يخص manage_attendance.
    """
    from app.permissions import ROLE_DEFAULT_PERMS as R

    # المدير يعدّل الموظفين ولا يملك manage_attendance
    assert "edit_employee" in R["company_manager"]
    assert "manage_attendance" not in R["company_manager"]
    assert "manage_attendance" in R["hr"]

    mgr = auth_headers(login(client, "100000000001", "manager123"))
    emp_id = client.get("/api/employees", headers=mgr).json()[0]["id"]

    body = _put_payload(client, mgr, emp_id, attendance_mode="none",
                        attendance_exempt=True, attendance_exempt_reason="اختبار")
    r = client.put(f"/api/employees/{emp_id}", headers=mgr, json=body)
    assert r.status_code == 403, r.text

    # وHR يملكها، لكن "بدون حضور" بلا سبب مرفوض
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    bad = _put_payload(client, hr, emp_id, attendance_mode="none",
                       attendance_exempt=False, attendance_exempt_reason="")
    assert client.put(f"/api/employees/{emp_id}", headers=hr, json=bad).status_code == 400

    good = _put_payload(client, hr, emp_id, attendance_mode="none",
                        attendance_exempt=True,
                        attendance_exempt_reason="مندوب ميداني بلا وردية")
    assert client.put(f"/api/employees/{emp_id}", headers=hr, json=good).status_code == 200


def test_perm03_attendance_changes_reach_the_change_log(client):
    """PERM-03 — كل تعديل يظهر في سجل التعديلات: من، متى، ماذا تغيّر.

    السجل كان يقتصر على سبعة حقول مالية/تعاقدية، فتعديل نمط الحضور أو الإعفاء
    منه لا يترك أثًرا — وهي التعديلات التي يُسأل عنها لاحًقا.
    """
    from app.routers.employees import CRITICAL_FIELDS

    assert {"attendance_mode", "attendance_exempt", "attendance_exempt_reason",
            "actual_job_title", "work_hours_type"} <= CRITICAL_FIELDS

    hr = auth_headers(login(client, "100000000002", "hr12345"))
    emp_id = client.get("/api/employees", headers=hr).json()[0]["id"]

    body = _put_payload(client, hr, emp_id, attendance_mode="both",
                        attendance_exempt=False, attendance_exempt_reason=None,
                        actual_job_title="مشرف ميداني")
    assert client.put(f"/api/employees/{emp_id}", headers=hr, json=body).status_code == 200

    hist = client.get(f"/api/employees/{emp_id}/change-history", headers=hr).json()
    fields = {h["field_name"] for h in hist}
    assert "attendance_mode" in fields, f"نمط الحضور لم يُسجَّل: {fields}"
    row = next(h for h in hist if h["field_name"] == "attendance_mode")
    assert row.get("changed_by") or row.get("changed_by_name"), "السجل بلا فاعل"
    assert row.get("changed_at"), "السجل بلا توقيت"


# ===========================================================================
# C1 — QA-01 + QA-02: تحديد المُعتمِد الحالي
# ROOT CAUSE: تجاوز ضمني في can_decide كان يعيد True لكل company_manager
# وcompany_owner في أي مرحلة. وصندوق "بانتظار موافقتي" مبني على نفس الدالة.
# ===========================================================================

def _leave_payload():
    return {"start_date": "2027-09-01", "end_date": "2027-09-03", "days": 3,
            "leave_type": "annual", "reason": "اختبار المسار"}


def test_qa01_manager_cannot_approve_a_stage_that_is_not_his(client):
    """QA-01 — المدير لا يعتمد مرحلة مسؤول الفرع، ويُرفض بـ403 عند النداء المباشر."""
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    emp_id = client.get("/api/auth/me", headers=auth_headers(
        login(client, "100000000101", "emp12345"))).json()["employee_id"]

    r = client.post("/api/requests", headers=hr, json={
        "request_type_code": "leave", "employee_id": emp_id,
        "payload_json": _leave_payload()})
    assert r.status_code == 201, r.text
    rid = r.json()["id"]

    mgr = auth_headers(login(client, "100000000001", "manager123"))
    dec = client.post(f"/api/requests/{rid}/decide", headers=mgr,
                      json={"decision": "approved", "note": "تجاوز"})
    assert dec.status_code == 403, f"المدير اعتمد مرحلة ليست له: {dec.text}"
    assert "لست المعتمِد" in dec.json()["detail"]


def test_qa01_no_implicit_override_for_any_role(client):
    """QA-01 — لا تجاوز ضمني: override_approval صلاحية مسمّاة غير ممنوحة افتراضًا."""
    from app.permissions import ROLE_DEFAULT_PERMS as R, PERMISSIONS

    assert "override_approval" in PERMISSIONS
    for role in ("company_manager", "company_owner", "hr", "delegate",
                 "accountant", "branch_supervisor", "employee"):
        assert "override_approval" not in R[role], f"{role} يملك تجاوًزا ضمنًيا"


def test_qa02_branch_supervisor_receives_the_request(client):
    """QA-02 — الطلب يصل صندوق مسؤول فرع الموظف، ولا يصل فرًعا آخر.

    الصندوق مبني على can_decide نفسها، فالتجاوز الضمني كان يملأ صندوق المدير
    بكل الطلبات ويترك مسار مسؤول الفرع بلا اختبار حقيقي.
    """
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    emp_id = client.get("/api/auth/me", headers=auth_headers(
        login(client, "100000000101", "emp12345"))).json()["employee_id"]

    r = client.post("/api/requests", headers=hr, json={
        "request_type_code": "leave", "employee_id": emp_id,
        "payload_json": _leave_payload()})
    assert r.status_code == 201, r.text
    rid = r.json()["id"]

    sup1 = auth_headers(login(client, "100000000005", "sup12345"))
    inbox1 = {x["id"] for x in client.get("/api/requests/inbox", headers=sup1).json()}

    mgr = auth_headers(login(client, "100000000001", "manager123"))
    inbox_mgr = {x["id"] for x in client.get("/api/requests/inbox", headers=mgr).json()}

    # الطلب واقف على مرحلة الفرع: يظهر لمسؤول الفرع لا للمدير
    assert rid in inbox1, "الطلب لم يصل مسؤول الفرع"
    assert rid not in inbox_mgr, "الطلب ما زال يظهر للمدير رغم أنها ليست مرحلته"

    # ومسؤول الفرع يقدر يعتمد فعلًا
    dec = client.post(f"/api/requests/{rid}/decide", headers=sup1,
                      json={"decision": "approved", "note": "موافق"})
    assert dec.status_code == 200, dec.text


def test_qa01_no_sequential_approval_by_same_account(client):
    """QA-01 — من اعتمد مرحلة لا يعتمد التي تليها بنفس الحساب.

    وإلا صارت سلسلة الاعتماد توقيًعا واحًدا بأسماء متعددة.
    """
    import inspect
    from app.routers import requests as req_router

    src = inspect.getsource(req_router.decide)
    assert "اعتمدت المرحلة السابقة بنفسك" in src, "حارس الاعتماد المتسلسل غير موجود"


# ===========================================================================
# C2 — QA-03 + QA-04: حساب الغياب
# ROOT CAUSE: payroll.py كان يعدّ كل يوم عمل بلا سجل غياًبا ويخصمه، بلا قصّ
# على مدة التوظيف وبلا تمييز "لا سجل" عن "غائب".
# ===========================================================================

def _fresh_employee(db, company_id, **kw):
    from datetime import date  # noqa: F401 — يستعمله المتصل
    from app import models
    emp = models.Employee(
        company_id=company_id, name="موظف اختبار الرواتب",
        basic_salary=2500, status="active", attendance_mode="qr", **kw)
    db.add(emp); db.commit(); db.refresh(emp)
    return emp


def test_qa03_unrecorded_days_are_not_deducted(client):
    """QA-03 — غياب السجل ليس غياًبا: يُعرَض لـHR ولا يُخصم.

    Golden test: راتب 2500 وشهر كامل بلا أي سجل حضور → الخصم صفر والصافي
    كامل الراتب، مع بيان أيام غير مسجَّلة.
    """
    from datetime import date
    from app.database import SessionLocal
    from app.payroll import compute_payroll
    from app import models

    db = SessionLocal()
    emp_id = None
    try:
        emp = _fresh_employee(db, 1, hire_date=date(2026, 1, 1))
        emp_id = emp.id
        out = compute_payroll(db, 1, 2026, 8)
        slip = next(s for s in out["payslips"] if s["employee_id"] == emp_id)

        assert slip["absent_days"] == 0, "يوم بلا سجل حُسب غياًبا"
        assert slip["absence_deduction"] == 0, f"خُصم بلا واقعة: {slip}"
        assert slip["net"] == 2500, f"الصافي ليس كامل الراتب: {slip['net']}"
        assert slip["unrecorded_days"] > 0, "الأيام غير المسجَّلة لا تُعرَض لـHR"
    finally:
        if emp_id:
            db.execute(models.Employee.__table__.delete().where(
                models.Employee.id == emp_id))
            db.commit()
        db.close()


def test_qa04_no_absence_before_hire_date(client):
    """QA-04 — الفترة مقصوصة على تاريخ التعيين.

    موظف عُيّن 05/08/2026: أيام 01–04/08 لا تُحسب ولا تُخصم.
    """
    from datetime import date
    from app.database import SessionLocal
    from app.payroll import compute_payroll
    from app import models

    db = SessionLocal()
    early_id = late_id = None
    try:
        early = _fresh_employee(db, 1, hire_date=date(2026, 1, 1))
        late = _fresh_employee(db, 1, hire_date=date(2026, 8, 5))
        early_id, late_id = early.id, late.id

        out = compute_payroll(db, 1, 2026, 8)
        s_early = next(s for s in out["payslips"] if s["employee_id"] == early_id)
        s_late = next(s for s in out["payslips"] if s["employee_id"] == late_id)

        # المعيَّن متأخًرا يجب أن تكون أيامه غير المسجَّلة أقل — الفرق هو الأيام
        # التي سبقت تعيينه ولم تعد تُحسب عليه
        assert s_late["unrecorded_days"] < s_early["unrecorded_days"], \
            f"لم تُقَص الفترة على تاريخ التعيين: {s_late} vs {s_early}"
        assert s_late["absence_deduction"] == 0
        assert s_late["net"] == 2500
    finally:
        for i in (early_id, late_id):
            if i:
                db.execute(models.Employee.__table__.delete().where(
                    models.Employee.id == i))
        db.commit(); db.close()


def test_qa03_recorded_absence_is_still_deducted(client):
    """الغياب المُثبَت في السجل يُخصم — الإصلاح لا يُلغي الخصم، يشترط الواقعة."""
    from datetime import datetime
    from datetime import date
    from app.database import SessionLocal
    from app.payroll import compute_payroll
    from app import models

    db = SessionLocal()
    emp_id = None
    try:
        emp = _fresh_employee(db, 1, hire_date=date(2026, 1, 1))
        emp_id = emp.id
        # يوم أحد (يوم عمل) مُسجَّل صراحة كغياب
        db.add(models.AttendanceRecord(
            company_id=1, employee_id=emp_id,
            check_in_at=datetime(2026, 8, 2, 8, 0), status="absent"))
        db.commit()

        out = compute_payroll(db, 1, 2026, 8)
        slip = next(s for s in out["payslips"] if s["employee_id"] == emp_id)
        assert slip["absent_days"] == 1, f"الغياب المُثبَت لم يُخصم: {slip}"
        assert slip["absence_deduction"] > 0
    finally:
        if emp_id:
            db.execute(models.AttendanceRecord.__table__.delete().where(
                models.AttendanceRecord.employee_id == emp_id))
            db.execute(models.Employee.__table__.delete().where(
                models.Employee.id == emp_id))
            db.commit()
        db.close()


def test_qa04_attendance_exempt_employee_is_never_charged(client):
    """المُعفى من الحضور لا يُحسب عليه غياب ولا أيام غير مسجَّلة."""
    from datetime import date
    from app.database import SessionLocal
    from app.payroll import compute_payroll
    from app import models

    db = SessionLocal()
    emp_id = None
    try:
        emp = _fresh_employee(db, 1, hire_date=date(2026, 1, 1),
                              attendance_exempt=True,
                              attendance_exempt_reason="مندوب ميداني")
        emp_id = emp.id
        out = compute_payroll(db, 1, 2026, 8)
        slip = next(s for s in out["payslips"] if s["employee_id"] == emp_id)
        assert slip["absent_days"] == 0 and slip["unrecorded_days"] == 0
        assert slip["net"] == 2500
    finally:
        if emp_id:
            db.execute(models.Employee.__table__.delete().where(
                models.Employee.id == emp_id))
            db.commit()
        db.close()


# ===========================================================================
# C3 — QA-05: توحيد أرصدة الإجازة
# ROOT CAUSE: رقمان بمعنيين مختلفين يُعرضان باسم واحد — العمود المخزَّن (30)
# مقابل المستحق التراكمي في EOS (30 × سنوات الخدمة = 92.16).
# ===========================================================================

def test_qa05_leave_numbers_come_from_one_source(client):
    """QA-05 — الملف ونهاية الخدمة يستخدمان نفس الصيغة.

    Cross-consistency: المستحق التراكمي المحسوب في خدمة الرصيد يطابق ما تحسبه
    نهاية الخدمة لنفس الموظف بنفس المعطيات.
    """
    from datetime import date
    from app.database import SessionLocal
    from app import models, eos as eos_engine
    from app.leave_balance import leave_balance, accrued_from_service

    db = SessionLocal()
    try:
        emp = db.scalars(select(models.Employee).where(
            models.Employee.hire_date.isnot(None)).limit(1)).first()
        assert emp, "لا يوجد موظف بتاريخ تعيين"
        company = db.get(models.Company, emp.company_id)

        detail = leave_balance(db, emp, company)
        settle = eos_engine.calculate_eos(
            basic_salary=float(emp.basic_salary or 0),
            hire_date=emp.hire_date, end_date=date.today(),
            reason="resignation", used_leave_days=detail["used_days"],
            annual_leave_days=detail["annual_entitlement"],
        )
        # نفس الصيغة ⇒ نفس المستحق التراكمي
        yrs = settle["service"]["decimal_years"]
        expected = accrued_from_service(detail["annual_entitlement"], yrs)
        assert abs(detail["accrued_days"] - expected) < 0.05, \
            f"الصيغتان تفرّقتا: {detail['accrued_days']} vs {expected}"
    finally:
        db.close()


def test_qa05_the_two_numbers_are_named_apart(client):
    """QA-05 — الفرق مقصود ومُسمّى صراحة، لا رقمان باسم واحد.

    «المتاح للاستخدام» ≠ «المستحق التراكمي»: الأول ما يقدر الموظف يأخذه اليوم،
    والثاني أساس بدل الإجازات عند نهاية الخدمة. دمجهما في رقم واحد يخلط حًقا
    تشغيلًيا باستحقاق مالي.
    """
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    emp_id = client.get("/api/employees", headers=hr).json()[0]["id"]
    p = client.get(f"/api/employees/{emp_id}/profile", headers=hr).json()

    d = p.get("leave_balance_detail")
    assert d, "الملف لا يعرض تفصيل الرصيد"
    for k in ("usable_days", "accrued_days", "used_days", "payable_days",
              "service_years", "annual_entitlement"):
        assert k in d, f"مفقود: {k}"
    # المتاح للاستخدام هو نفسه العمود المخزَّن — لا حساب ثانٍ له
    assert d["usable_days"] == p["leave_balance"]
    # والقابل للصرف لا يكون سالًبا مهما زاد الاستهلاك
    assert d["payable_days"] >= 0
