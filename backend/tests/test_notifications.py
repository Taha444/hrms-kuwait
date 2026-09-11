# -*- coding: utf-8 -*-
"""اختبارات كتالوج قوالب الإشعارات (74) + التفضيلات + تكامل سجل الطباعة/الأرشفة (FIX-004)."""
import io

from tests.conftest import auth_headers, login


def test_the_whole_notification_catalog_is_seeded(client):
    """**كل ما يُعلَن في الكتالوج يُبذَر، ولا يُبذَر ما ليس فيه.**

    كان الشرط رقًما حرفًيا (74) واسُم الاختبار يحمله. وهو يمسك «أُضيف
    قالب» — وليست إضافُة قالب عطًلا؛ ويُخطئ اسُمه يوم يتغيّر الرقم فيصير
    الاسم يقول غير ما يفحص. (وقع: أُضيف ``NTF-075`` لاتفاقية القرض.)

    والخطر الحقيقي أن يفترق المُعلَن عن المبذور: قالٌب يُرسَل ولا يُعرَف،
    أو يُعلَن ولا يوجد. فيُقاس الطرفان أحدهما بالآخر — ولا يحتاج تحديًثا
    كلّما نما الكتالوج.
    """
    from app import notification_templates as NT

    hr = auth_headers(login(client, "100000000002", "hr12345"))
    r = client.get("/api/notifications/templates", headers=hr)
    assert r.status_code == 200
    served = {x["code"] for x in r.json()}
    declared = {t["code"] for t in NT.DEFAULT_NOTIFICATION_TEMPLATES}
    assert served == declared, {"مُعلٌَن ولم يُبذَر": sorted(declared - served),
                                "مبذوٌر بلا إعلان": sorted(served - declared)}
    assert "NTF-001" in served, "الكتالوج فارغ — لا يقيس التساوي شيًئا"

    cats = client.get("/api/notifications/templates/categories", headers=hr).json()
    assert len(cats) == len({t["category"] for t in NT.DEFAULT_NOTIFICATION_TEMPLATES})


def test_preferences_default_enabled_and_updatable(client):
    """P10-33 صحّح أساس هذا الادّعاء — والنيّة التي حماها باقية.

    كان: كل قناة مُفعَّلة افتراًضا. وهو صحيح **للقنوات التي تُسلِّم**:
    من لم يضبط شيًئا يصله الإشعار. لكنه كان يشمل «واتساب» و«بريد» بلا
    مزوّد — بل البريد لا صنف قناة له إطلاًقا — فيرى المستخدم مفاتيح
    مُفعَّلة لا يصله عبرها شيء أبًدا.

    فالادّعاء انتقل من «كلّها مُفعَّلة» إلى «ما يُسلِّم مُفعَّل، وما لا
    يُسلِّم لا يَعِد».
    """
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    prefs = client.get("/api/notifications/preferences", headers=hr).json()
    assert len(prefs) > 0
    deliverable = [p for p in prefs if p["available"]]
    assert deliverable, "لا قناة تُسلِّم — القياس فارغ"
    assert all(p["enabled"] for p in deliverable)
    assert not [p for p in prefs if p["enabled"] and not p["available"]]

    cat = prefs[0]["category"]
    r = client.put("/api/notifications/preferences", headers=hr,
                   json=[{"category": cat, "channel": "in_app", "enabled": False}])
    assert r.status_code == 200
    prefs2 = client.get("/api/notifications/preferences", headers=hr).json()
    updated = next(p for p in prefs2 if p["category"] == cat and p["channel"] == "in_app")
    assert updated["enabled"] is False


def test_print_and_file_send_template_driven_notification(client):
    emp = auth_headers(login(client, "100000000101", "emp12345"))
    r = client.post("/api/requests", headers=emp, json={
        "request_type_code": "loan", "payload_json": {"loan_type": "loan", "amount": 100, "months": 6, "first_deduction_month": "2027-01", "reason": "ظرف"}})
    rid = r.json()["id"]
    mgr = auth_headers(login(client, "100000000001", "manager123"))
    client.post(f"/api/requests/{rid}/decide", headers=mgr, json={"decision": "approved"})
    acc = auth_headers(login(client, "100000000007", "account123"))

    # لا مستند مولَّد لطلب القرض (produces_document=False) — نتحقق من شهادة الراتب بدلًا منه
    r = client.post("/api/requests", headers=emp, json={
        "request_type_code": "salary_certificate",
        "payload_json": {"purpose": "بنك", "language": "ar", "notes": "قرض"}})
    rid2 = r.json()["id"]
    client.post(f"/api/requests/{rid2}/decide", headers=mgr, json={"decision": "approved"})

    r = client.post(f"/api/requests/{rid2}/document/generated_pdf/mark-printed", headers=mgr)
    assert r.status_code == 200
    tasks = client.get("/api/tasks/my", headers=mgr).json()
    assert any(t["type"] == "print_done" for t in tasks)

    r = client.post(f"/api/requests/{rid2}/document/generated_pdf/mark-filed", headers=mgr)
    assert r.status_code == 200
    tasks = client.get("/api/tasks/my", headers=mgr).json()
    assert any(t["type"] == "file_done" for t in tasks)


def test_leave_approval_stage_is_template_driven(client):
    """FIX-004 (تعميم): مسار اعتماد الطلبات الفعلي (لا حدثا الطباعة فقط) يمرّ بالقوالب."""
    emp = auth_headers(login(client, "100000000101", "emp12345"))
    r = client.post("/api/requests", headers=emp, json={
        "request_type_code": "leave",
        "payload_json": {"start_date": "2026-09-01", "end_date": "2026-09-03", "days": 3, "leave_type": "annual", "reason": "اختبار"}})
    rid = r.json()["id"]

    sup = auth_headers(login(client, "100000000005", "sup12345"))
    tasks = client.get("/api/tasks/my", headers=sup).json()
    stage_task = next(t for t in tasks if t["related_entity_id"] == rid and t["type"] == "request_stage")
    assert stage_task["template_code"] == "NTF-033"

    # تقدّم المرحلة يُشعر الموظف بقالب مسمّى أيضًا
    client.post(f"/api/requests/{rid}/decide", headers=sup, json={"decision": "approved"})
    emp_tasks = client.get("/api/tasks/my", headers=emp).json()
    progress_task = next(t for t in emp_tasks if t["related_entity_id"] == rid
                         and t["template_code"] == "NTF-034")
    assert progress_task is not None


def test_renewal_stage_notification_is_template_driven(client):
    """FIX-004 (تعميم): تجديد الإقامة يُشعر عبر قالب مسمّى (NTF-015) لا نداء مباشر."""
    from datetime import date, timedelta
    # R2-B — الموظف يُنشأ عبر HR (المندوب لم يعد يملك create_employee)
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    pro = auth_headers(login(client, "100000000003", "deleg123"))
    eid = client.post("/api/employees", headers=hr, json={
        "name": "موظف إشعار تجديد", "civil_id": "199933445566", "basic_salary": 300}).json()["id"]
    exp = (date.today() + timedelta(days=10)).isoformat()  # ضمن نافذة العادي (0-30) -> AWAITING_CONTRACTS
    client.post(f"/api/employees/{eid}/permits", headers=pro,
                params={"kind": "residency", "number": "RES-NTF", "expiry_date": exp})
    r = client.post("/api/renewals", headers=pro, data={"employee_id": eid})
    assert r.status_code == 201, r.text
    rn = r.json()
    assert rn["status"] == "awaiting_contracts"

    tasks = client.get("/api/tasks/my", headers=pro).json()
    t = next(x for x in tasks if x["related_entity_id"] == rn["id"])
    assert t["template_code"] == "NTF-015"
