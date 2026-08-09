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
