# -*- coding: utf-8 -*-
"""اختبار محرّك الطلبات end-to-end: طلب إجازة عبر كل المراحل + إلغاء المدير."""
import io

from tests.conftest import auth_headers, login


def _emp_id(client):
    token = login(client, "100000000001", "manager123")
    emps = client.get("/api/employees", headers=auth_headers(token)).json()
    # الموظف صاحب الخدمة الذاتية (أحمد)
    return next(e["id"] for e in emps if e["civil_id"] == "100000000101")


def test_produces_document_types_have_default_template_code(client):
    """P0-02/P2-02: كل نوع طلب produces_document=True مرتبط بأحد قوالب HRMS-PR الرسمية
    (أو None صراحًة حين لا يوجد قالب مطابق فعليًا بين الـ42 — لا يُهمَل الحقل بصمت)."""
    from app import workflow

    for rt in workflow.DEFAULT_REQUEST_TYPES:
        if rt.get("produces_document"):
            assert "default_template_code" in rt, f"{rt['code']} missing default_template_code key"


def test_new_request_types_available(client):
    emp = login(client, "100000000101", "emp12345")
    codes = {x["code"] for x in client.get("/api/requests/types", headers=auth_headers(emp)).json()}
    assert {"exit_permission", "advance", "loan"} <= codes


def test_advance_request_flows_to_accountant(client):
    emp = login(client, "100000000101", "emp12345")
    rid = client.post("/api/requests", headers=auth_headers(emp), json={
        "request_type_code": "advance", "payload_json": {"loan_type": "advance", "amount": 200, "first_deduction_month": "2027-01", "reason": "ظرف"}}).json()["id"]
    # المدير يعتمد → ينتقل الطلب للمحاسب للتنفيذ
    mgr = login(client, "100000000001", "manager123")
    client.post(f"/api/requests/{rid}/decide", headers=auth_headers(mgr), json={"decision": "approved"})
    acc = login(client, "100000000007", "account123")
    tasks = client.get("/api/tasks/my", headers=auth_headers(acc)).json()
    assert any(tk.get("related_entity_id") == rid for tk in tasks)
    # P0-01: المحاسب يملك approve_request فعليًا فيقدر يُنهي استلام السلفة (كان 403 قبل الإصلاح)
    r = client.post(f"/api/requests/{rid}/received", headers=auth_headers(acc))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "completed"


def test_accountant_can_decide_approval_stage_assigned_to_them(client):
    """P0-01: أي مرحلة اعتماد (لا pickup فقط) مسندة للمحاسب يجب أن يقدر يعتمدها/يرفضها."""
    emp = login(client, "100000000101", "emp12345")
    rid = client.post("/api/requests", headers=auth_headers(emp), json={
        "request_type_code": "REQPAY",
        # R7-E — payslip_copy مرفق مطلوب لاعتراض الراتب
        "payload_json": {"payroll_period": "2026-06", "reason": "خطأ حساب",
                         "_attachments": ["payslip_copy"]},
    }).json()["id"]
    acc = login(client, "100000000007", "account123")
    r = client.post(f"/api/requests/{rid}/decide", headers=auth_headers(acc), json={"decision": "approved"})
    assert r.status_code == 200, r.text


def test_hr_can_submit_request_on_employees_behalf(client):
    """P0-05: HR كان بلا submit_request إطلاًقا فلا يقدر ينشئ REQEOS/REQCLR/ADM* نيابًة عن الموظف."""
    emp_id = _emp_id(client)
    hr = login(client, "100000000002", "hr12345")
    r = client.post("/api/requests", headers=auth_headers(hr), json={
        "request_type_code": "REQEOS", "employee_id": emp_id,
        "payload_json": {"hire_date": "2020-01-15", "last_day": "2026-07-01", "salary_basis": 480,
                         "service_duration": "6 سنوات", "entitlements": 1450.5, "deductions": 120,
                         "net": 1330.5},
    })
    assert r.status_code == 201, r.text

    # P6-27 — يُغلق ما فُتح. هذا الاختبار يقيس **صلاحية** HR في التقديم
    # نيابًة، لا دورة حياة الخروج. وتركُ طلب خروج مفتوًحا على موظف
    # مشترك يمنع اختباًرا لاحًقا في هذا الملف نفسه من فتح خروجه —
    # وهو ما كشفه حارس «خروج واحد» حين أُضيف.
    from sqlalchemy import delete as _del

    from app import models as _m
    from app.database import SessionLocal as _S

    _db = _S()
    try:
        _rid = r.json()["id"]
        _db.execute(_del(_m.Task).where(
            _m.Task.related_entity_type == "request",
            _m.Task.related_entity_id == _rid))
        _db.execute(_del(_m.Request).where(_m.Request.id == _rid))
        _db.commit()
    finally:
        _db.close()


def test_generated_document_has_working_verification_code(client):
    """P2-01: كل مستند مُولَّد يحمل رمز تحقق يمكن لأي طرف خارجي (بلا حساب) التأكد منه
    عبر GET /verify/{code} — تُعاد بيانات غير حساسة فقط (نوع الطلب/الشركة/الحالة)."""
    emp = login(client, "100000000101", "emp12345")
    rid = client.post("/api/requests", headers=auth_headers(emp), json={
        "request_type_code": "salary_certificate",
        "payload_json": {"purpose": "بنك", "language": "ar", "notes": "قرض"}}).json()["id"]
    mgr = login(client, "100000000001", "manager123")
    client.post(f"/api/requests/{rid}/decide", headers=auth_headers(mgr), json={"decision": "approved"})

    detail = client.get(f"/api/requests/{rid}", headers=auth_headers(mgr)).json()
    doc = next(d for d in detail["documents"] if d["kind"] == "generated_pdf")

    from app import verification
    from app.database import SessionLocal
    from app import models
    db = SessionLocal()
    try:
        doc_row = db.query(models.RequestDocument).filter(
            models.RequestDocument.request_id == rid, models.RequestDocument.kind == "generated_pdf"
        ).first()
        code = verification.generate_code(doc_row.id, rid)
    finally:
        db.close()

    r = client.get(f"/api/verify/{code}")  # بلا أي رمز دخول — تحقق عمومي
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True
    assert "company_name" in body and "request_type" in body

    bad = client.get(f"/api/verify/{code}xx")
    assert bad.json()["valid"] is False


def test_reqeos_and_reqclr_complete_with_full_pdf(client):
    """P0-05: REQEOS/REQCLR يكتملان فعليًا (لا يتوقفان عند المحاسب) وتصدر لهما PDF كاملة
    تضم كل مراحل الاعتماد بما فيها المرحلة الأخيرة المولّدة للمستند نفسها (كانت تُفقد بسبب
    autoflush=False قبل db.flush() المضافة في decide())."""
    emp_id = _emp_id(client)
    hr = login(client, "100000000002", "hr12345")
    acc = login(client, "100000000007", "account123")
    mgr = login(client, "100000000001", "manager123")

    rid = client.post("/api/requests", headers=auth_headers(hr), json={
        "request_type_code": "REQEOS", "employee_id": emp_id,
        "payload_json": {"hire_date": "2020-01-15", "last_day": "2026-07-01", "salary_basis": 480,
                         "service_duration": "6 سنوات", "entitlements": 1450.5, "deductions": 120,
                         "net": 1330.5},
    }).json()["id"]
    client.post(f"/api/requests/{rid}/decide", headers=auth_headers(hr), json={"decision": "approved"})
    client.post(f"/api/requests/{rid}/decide", headers=auth_headers(acc), json={"decision": "approved"})
    r = client.post(f"/api/requests/{rid}/decide", headers=auth_headers(mgr), json={"decision": "approved"})
    # P5-23 — قرار المالك: تسوية نهاية الخدمة تُوقَّع. فالاكتمال صار بعد
    # رفع النسخة الموقّعة لا عند آخر اعتماد. والادّعاء نفسه باقٍ —
    # «يكتمل فعًلا ولا يتوقّف عند المحاسب» — لكن خطّ نهايته تحرّك.
    assert r.status_code == 200 and r.json()["status"] == "awaiting_signature", r.text

    detail = client.get(f"/api/requests/{rid}", headers=auth_headers(hr)).json()
    assert any(d["kind"] == "generated_pdf" for d in detail["documents"])

    signed = client.post(f"/api/requests/{rid}/documents", headers=auth_headers(hr),
                         data={"kind": "signed_scan"},
                         files={"file": ("signed.pdf", b"%PDF-1.4 signed",
                                         "application/pdf")})
    assert signed.status_code in (200, 201), signed.text[:200]
    after = client.get(f"/api/requests/{rid}", headers=auth_headers(hr)).json()
    assert after["status"] == "completed", after["status"]

    rid2 = client.post("/api/requests", headers=auth_headers(hr), json={
        "request_type_code": "REQCLR", "employee_id": emp_id,
        "payload_json": {"assets": "لابتوب", "finance_status": "لا التزامات",
                         "department_signoffs": "تم"},
    }).json()["id"]
    # V2.2 §13.10 (AC-10) — المرحلة الأولى صارت متوازية: كل جهة تُقرّ نصيبها،
    # ولا تتقدّم المرحلة إلا باكتمال المنطبقات (All-of). المندوب ليس منها هنا
    # لأن الحمولة لا تحمل has_gov_documents.
    sup = login(client, "100000000005", "sup12345")
    first = client.post(f"/api/requests/{rid2}/decide", headers=auth_headers(acc),
                        json={"decision": "approved"})
    assert first.status_code == 200, first.text
    assert first.json()["status"] != "completed", "أُغلق الطلب وجهة لم تُقرّ بعد"

    # HR ليس جهة في هذه المرحلة، فلا يقرّر فيها
    early = client.post(f"/api/requests/{rid2}/decide", headers=auth_headers(hr),
                        json={"decision": "approved"})
    assert early.status_code in (403, 404), "غير الجهة قرّر في مرحلة متوازية"

    client.post(f"/api/requests/{rid2}/decide", headers=auth_headers(sup),
                json={"decision": "approved"})
    r2 = client.post(f"/api/requests/{rid2}/decide", headers=auth_headers(hr),
                     json={"decision": "approved"})
    # P5-23 — وإخلاء الطرف يُوقَّع أيًضا بقرار المالك.
    assert r2.status_code == 200 and r2.json()["status"] == "awaiting_signature", r2.text
    signed2 = client.post(f"/api/requests/{rid2}/documents", headers=auth_headers(hr),
                          data={"kind": "signed_scan"},
                          files={"file": ("signed2.pdf", b"%PDF-1.4 signed",
                                          "application/pdf")})
    assert signed2.status_code in (200, 201), signed2.text[:200]
    assert client.get(f"/api/requests/{rid2}", headers=auth_headers(hr)
                      ).json()["status"] == "completed"

    # P6-27 — اكتمال REQEOS صار يفتح حالة نهاية خدمة (المرجع). وهذا
    # الاختبار يقيس اكتمال الطلب وإخراج المستند، لا دورة حياة الخروج —
    # فتركُ المرجع مفتوًحا يمنع اختباًرا لاحًقا من فتح خروج للموظف نفسه.
    from sqlalchemy import delete as _del

    from app import models as _m
    from app.database import SessionLocal as _S

    _db = _S()
    try:
        _db.execute(_del(_m.EosCase).where(_m.EosCase.employee_id == emp_id))
        _db.commit()
    finally:
        _db.close()


def test_generated_document_body_has_no_raw_payload_keys_or_role_codes(client):
    """P0-03/P0-04: نص المستند المولَّد يستخدم تسميات عربية للحقول وأدوار الاعتماد،
    لا مفاتيح payload الخام (مثل amount/purpose) ولا رموز الأدوار التقنية (company_manager)."""
    from app import workflow

    class _FakeReq:
        payload_json = {"amount": 200, "purpose": "سبب ما", "destination": "دبي"}
        code = "REQGEN"

    class _FakeRt:
        code = "REQGEN"

    lines = workflow._body_lines(_FakeRt(), _FakeReq(), None)
    text = " ".join(lines)
    assert "amount:" not in text and "purpose:" not in text and "destination:" not in text
    assert "المبلغ" in text and "الغرض" in text and "جهة السفر" in text


def test_sensitive_documents_include_explicit_legal_note(client):
    """P1-02: المستندات التأديبية/الحساسة (ADMWARN مثًلا) تضم ملاحظة قانونية صريحة معنونة
    فوق نص REQUEST_OFFICIAL_TEXT الحذر أصًلا، تؤكد حق الرد وتفصل الاستلام عن الإقرار."""
    from app import workflow

    class _FakeReq:
        payload_json = {}

    class _FakeRt:
        code = "ADMWARN"

    lines = workflow._body_lines(_FakeRt(), _FakeReq(), None)
    assert any(line.startswith("ملاحظة قانونية:") for line in lines)


def test_employee_sees_curated_self_service_catalog_not_all_types(client):
    """P0-06: الموظف يرى قائمة مصفّاة (خدمة ذاتية) لا كل الأنواع — لا يظهر له ADMEMP الداخلي."""
    emp = login(client, "100000000101", "emp12345")
    admin = login(client, "000000000000", "admin123")
    emp_codes = {x["code"] for x in client.get("/api/requests/types", headers=auth_headers(emp)).json()}
    all_codes = {x["code"] for x in client.get("/api/requests/types", headers=auth_headers(admin)).json()}
    assert len(emp_codes) < len(all_codes)
    assert "ADMEMP" not in emp_codes and "ADMWARN" not in emp_codes
    assert "leave" in emp_codes and "REQGRV" in emp_codes


def test_full_leave_workflow(client):
    emp_token = login(client, "100000000101", "emp12345")
    # 1) العامل يقدّم طلب إجازة
    r = client.post("/api/requests", headers=auth_headers(emp_token), json={
        "request_type_code": "leave",
        # QA-10 — مرحلة المندوب صارت مشروطة بالسفر خارج البلاد. هذا الاختبار
        # يغطّي المسار الكامل بما فيه المندوب، فيلزمه سفر صريح؛ الإجازة بلا سفر
        # تُغلَق عند HR ولها اختبارها الخاص.
        "payload_json": {"start_date": "2026-08-01", "end_date": "2026-08-10",
                         "days": 10, "reason": "سفر", "leave_type": "annual",
                         "travel_required": True, "destination": "مصر"},
    })
    assert r.status_code == 201, r.text
    req_id = r.json()["id"]
    assert r.json()["status"] == "pending"

    # 2) مسؤول الفرع يعتمد (أول مرحلة)
    sup = login(client, "100000000005", "sup12345")
    r = client.post(f"/api/requests/{req_id}/decide", headers=auth_headers(sup),
                    json={"decision": "approved"})
    assert r.status_code == 200, r.text

    # RW-04 — أُزيلت مرحلة "اعتماد المدير العام": لا تضيف قراًرا فوق قرار
    # المسؤول المباشر، وكانت تؤخّر إجازة أُقرّت فعًلا. فالمدير لم يعد معتمًِدا
    # لهذه المرحلة ويُرفض استدعاؤه.
    mgr = login(client, "100000000001", "manager123")
    denied = client.post(f"/api/requests/{req_id}/decide", headers=auth_headers(mgr),
                         json={"decision": "approved"})
    assert denied.status_code in (403, 404), denied.text

    # 3) HR يحدّث الرصيد → الحالة awaiting_signature
    hr = login(client, "100000000002", "hr12345")
    r = client.post(f"/api/requests/{req_id}/decide", headers=auth_headers(hr),
                    json={"decision": "approved"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "awaiting_signature"

    # HR يحدد موعد التوقيع
    r = client.post(f"/api/requests/{req_id}/appointment", headers=auth_headers(hr),
                    json={"scheduled_at": "2026-07-20T10:00:00", "location": "مقر الشركة"})
    assert r.status_code == 200

    # 5) HR يرفع النسخة الموقّعة → ينتقل لمرحلة المندوب (awaiting_delegate)
    files = {"file": ("signed.pdf", io.BytesIO(b"signed-content"), "application/pdf")}
    r = client.post(f"/api/requests/{req_id}/documents", headers=auth_headers(hr),
                    data={"kind": "signed_scan"}, files=files)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "awaiting_delegate"

    # 6) المندوب يرفع إذن المغادرة → completed
    delegate = login(client, "100000000004", "deleg123")
    files = {"file": ("exit.pdf", io.BytesIO(b"exit-permit"), "application/pdf")}
    r = client.post(f"/api/requests/{req_id}/documents", headers=auth_headers(delegate),
                    data={"kind": "exit_permit"}, files=files)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "completed"

    # المستند المُولَّد متاح، وهو PDF حقيقي (FIX-007)
    r = client.get(f"/api/requests/{req_id}/document/generated_pdf", headers=auth_headers(hr))
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"

    # دورة حياة الطباعة/الأرشفة (FIX-008): لا أرشفة قبل الطباعة
    r = client.post(f"/api/requests/{req_id}/document/generated_pdf/mark-filed", headers=auth_headers(hr))
    assert r.status_code == 409
    r = client.post(f"/api/requests/{req_id}/document/generated_pdf/mark-printed", headers=auth_headers(hr))
    assert r.status_code == 200 and r.json()["print_status"] == "printed"
    r = client.post(f"/api/requests/{req_id}/document/generated_pdf/mark-filed", headers=auth_headers(hr))
    assert r.status_code == 200 and r.json()["print_status"] == "filed"
    docs = client.get(f"/api/requests/{req_id}", headers=auth_headers(hr)).json()["documents"]
    gp = next(d for d in docs if d["kind"] == "generated_pdf")
    assert gp["print_status"] == "filed" and gp["printed_at"] and gp["filed_at"]


def test_manager_can_cancel_anytime(client):
    emp_token = login(client, "100000000101", "emp12345")
    r = client.post("/api/requests", headers=auth_headers(emp_token), json={
        "request_type_code": "leave",
        "payload_json": {"start_date": "2026-09-01", "end_date": "2026-09-05", "days": 5, "leave_type": "annual", "reason": "اختبار"},
    })
    req_id = r.json()["id"]
    mgr = login(client, "100000000001", "manager123")
    r = client.post(f"/api/requests/{req_id}/cancel?note=ظروف+العمل", headers=auth_headers(mgr))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled"


def test_request_stages_progress(client):
    """مسار الطلب يعكس التسلسل الهرمي: مرحلة تمّت، الحالية، والباقي قادم."""
    emp_token = login(client, "100000000101", "emp12345")
    r = client.post("/api/requests", headers=auth_headers(emp_token), json={
        "request_type_code": "leave",
        "payload_json": {"start_date": "2026-10-01", "end_date": "2026-10-03", "days": 3, "leave_type": "annual", "reason": "اختبار"},
    })
    req_id = r.json()["id"]
    # المرحلة 0 الآن (مسؤول الفرع)
    detail = client.get(f"/api/requests/{req_id}", headers=auth_headers(emp_token)).json()
    states = [s["state"] for s in detail["stages"]]
    assert states[0] == "current"
    assert states[1] == "pending"

    # بعد اعتماد مسؤول الفرع → المرحلة 0 تمّت، المرحلة 1 الحالية
    sup = login(client, "100000000005", "sup12345")
    client.post(f"/api/requests/{req_id}/decide", headers=auth_headers(sup),
                json={"decision": "approved", "note": "موافق"})
    detail = client.get(f"/api/requests/{req_id}", headers=auth_headers(emp_token)).json()
    assert detail["stages"][0]["state"] == "done"
    assert detail["stages"][0]["approver_name"]  # يظهر اسم المعتمِد
    assert detail["stages"][1]["state"] == "current"


def test_salary_certificate_to_pickup(client):
    emp_token = login(client, "100000000101", "emp12345")
    r = client.post("/api/requests", headers=auth_headers(emp_token), json={
        "request_type_code": "salary_certificate",
        "payload_json": {"purpose": "بنك الكويت", "language": "ar", "notes": "قرض"},
    })
    req_id = r.json()["id"]
    mgr = login(client, "100000000001", "manager123")
    r = client.post(f"/api/requests/{req_id}/decide", headers=auth_headers(mgr),
                    json={"decision": "approved"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ready_for_pickup"
