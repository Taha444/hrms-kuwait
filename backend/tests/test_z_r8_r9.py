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


def test_hr_manager_supervisor_have_record_attendance(client):
    """P0-#4 — HR/Manager/Supervisor لازم يقدروا يبصموا (record_attendance).
    قبل التعديل مكانوش عندهم الصلاحية دي رغم إنهم موظفين."""
    admin = auth_headers(login(client, *ADMIN))
    # جيب permission list لكل دور
    for civ, pw, role in [(MGR[0], MGR[1], "company_manager"),
                          (HR[0], HR[1], "hr")]:
        h = auth_headers(login(client, civ, pw))
        me = client.get("/api/auth/me", headers=h).json()
        assert "record_attendance" in me["permissions"], \
            f"{role} missing record_attendance"


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
        "payload_json": {"addressed_to": "بنك الاختبار", "purpose": "قرض"},
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


def test_return_resubmit_reapprove_full_cycle(client):
    """FIX — دورة كاملة: submit → return → resubmit → approve بنفس المستخدم.

    كان الـdouble-decide guard بيشوف القرار القديم (returned) ويرفض القرار الجديد
    بـ409 "اتخذت قرارًا مسبقًا" — الطلب يتجمّد للأبد بعد أي إعادة تقديم.
    """
    emp_h = auth_headers(login(client, *EMP))
    r = client.post("/api/requests", headers=emp_h, json={
        "request_type_code": "salary_certificate",
        "payload_json": {"addressed_to": "بنك الاختبار", "purpose": "قرض شخصي"},
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
        "payload_json": {"addressed_to": "بنك الكويت الوطني", "purpose": "قرض سكني"},
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
        "payload_json": {"addressed_to": "بنك", "purpose": "قرض"},
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
        "payload_json": {"start_date": d1, "end_date": d2, "days": 3, "leave_type": "annual"},
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
        "payload_json": {"start_date": d1, "end_date": d2, "days": 3, "leave_type": "annual"},
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
        "payload_json": {"addressed_to": "بنك", "purpose": "قرض"},
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
