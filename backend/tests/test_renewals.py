# -*- coding: utf-8 -*-
"""اختبارات قبول تجديد الإقامة (DEMO-001/002): مبكر + عادي + الحالات."""
import io

from tests.conftest import auth_headers, login

PRO = ("100000000003", "deleg123")
MGR = ("100000000001", "manager123")
HR = ("100000000002", "hr12345")
EMP = ("100000000101", "emp12345")   # إقامته تنتهي خلال ~8 أيام → عادي


def _f(name=b"content"):
    return {"file": ("doc.pdf", io.BytesIO(name), "application/pdf")}


def _emp_with_days(client, pro_h, lo, hi):
    """id موظف إقامته المتبقّية ضمن [lo, hi] يومًا (عبر قائمة إقامات المندوب)."""
    permits = client.get("/api/pro/permits", headers=pro_h).json()
    for p in permits:
        if p.get("kind") == "residency" and p.get("days_left") is not None \
                and lo <= p["days_left"] <= hi:
            return p["employee_id"]
    raise AssertionError(f"لا يوجد موظف بإقامة {lo}-{hi} يومًا")


def test_normal_renewal_full_flow(client):
    # الموظف (≤30 يوم) يقدّم → يصل للمندوب مباشرة بلا موافقات
    emp = auth_headers(login(client, *EMP))
    r = client.post("/api/renewals", headers=emp)
    assert r.status_code == 201, r.text
    rn = r.json()
    assert rn["renewal_type"] == "normal" and rn["status"] == "awaiting_contracts"
    rid = rn["id"]

    pro = auth_headers(login(client, *PRO))
    # المندوب يرفع العقدين → بانتظار توقيع الموظف
    for kind in ("renewal_contract_gov", "renewal_contract_internal"):
        client.post(f"/api/renewals/{rid}/upload", headers=pro,
                    data={"doc_type": kind}, files=_f())
    assert client.get(f"/api/renewals/{rid}", headers=pro).json()["status"] == "awaiting_signature"

    # الموظف يرفع النسختين الموقّعتين → تم رفع العقود الموقّعة
    for kind in ("renewal_signed_gov", "renewal_signed_internal"):
        client.post(f"/api/renewals/{rid}/upload", headers=emp,
                    data={"doc_type": kind}, files=_f())
    assert client.get(f"/api/renewals/{rid}", headers=pro).json()["status"] == "contracts_signed"

    # المندوب: جاري التجديد ثم رفع إذن العمل → بانتظار البطاقة
    client.post(f"/api/renewals/{rid}/renewing", headers=pro)
    client.post(f"/api/renewals/{rid}/upload", headers=pro,
                data={"doc_type": "work_permit"}, files=_f())
    assert client.get(f"/api/renewals/{rid}", headers=pro).json()["status"] == "awaiting_civil_card"

    # الموظف يرفع البطاقة المدنية → مكتملة
    client.post(f"/api/renewals/{rid}/upload", headers=emp,
                data={"doc_type": "civil_id"}, files=_f())
    final = client.get(f"/api/renewals/{rid}", headers=pro).json()
    assert final["status"] == "completed"
    # إذن العمل الجديد محفوظ في ملف الموظف
    assert any(d["type"] == "work_permit" for d in final["documents"])


def test_renewal_document_download(client):
    emp = auth_headers(login(client, *EMP))
    r = client.post("/api/renewals", headers=emp)
    assert r.status_code == 201, r.text
    rid = r.json()["id"]

    pro = auth_headers(login(client, *PRO))
    client.post(f"/api/renewals/{rid}/upload", headers=pro,
                data={"doc_type": "renewal_contract_gov"}, files=_f(b"gov-contract"))

    # المندوب يمكنه تنزيل عقد رفعه
    r = client.get(f"/api/renewals/{rid}/document/renewal_contract_gov", headers=pro)
    assert r.status_code == 200
    assert r.content == b"gov-contract"

    # الموظف صاحب الطلب يمكنه تنزيله أيضًا
    r = client.get(f"/api/renewals/{rid}/document/renewal_contract_gov", headers=emp)
    assert r.status_code == 200

    # نوع مستند غير معروف → 400
    assert client.get(f"/api/renewals/{rid}/document/bogus_type", headers=pro).status_code == 400

    # مستند غير مرفوع بعد → 404
    assert client.get(f"/api/renewals/{rid}/document/renewal_signed_gov", headers=pro).status_code == 404

    # موظف آخر لا صلة له بالمعاملة → 404
    other_emp = auth_headers(login(client, "100000000102", "emp12345"))
    r = client.get(f"/api/renewals/{rid}/document/renewal_contract_gov", headers=other_emp)
    assert r.status_code == 404


def test_early_renewal_approval_chain(client):
    pro = auth_headers(login(client, *PRO))
    early_emp = _emp_with_days(client, pro, 31, 90)   # مبكر
    far_emp = _emp_with_days(client, pro, 91, 400)     # >90 → غير مسموح
    # بدون سبب → مرفوض التحقّق
    assert client.post("/api/renewals", headers=pro,
                       data={"employee_id": early_emp}).status_code == 400
    # أكثر من 90 يومًا → غير مسموح
    assert client.post("/api/renewals", headers=pro,
                       data={"employee_id": far_emp, "reason": "x"}).status_code == 400
    # مبكر بسبب → بانتظار موافقة المدير
    r = client.post("/api/renewals", headers=pro,
                    data={"employee_id": early_emp, "reason": "قرب انتهاء الجواز"})
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    assert r.json()["status"] == "pending_manager"

    # الشؤون لا تعتمد قبل المدير
    hr = auth_headers(login(client, *HR))
    assert client.post(f"/api/renewals/{rid}/decide", headers=hr,
                       data={"decision": "approved"}).status_code == 403
    # المدير يعتمد → بانتظار الشؤون
    mgr = auth_headers(login(client, *MGR))
    assert client.post(f"/api/renewals/{rid}/decide", headers=mgr,
                       data={"decision": "approved"}).status_code == 200
    assert client.get(f"/api/renewals/{rid}", headers=mgr).json()["status"] == "pending_hr"
    # الشؤون تعتمد → محوّل للمندوب (بانتظار رفع العقود)
    assert client.post(f"/api/renewals/{rid}/decide", headers=hr,
                       data={"decision": "approved"}).status_code == 200
    assert client.get(f"/api/renewals/{rid}", headers=pro).json()["status"] == "awaiting_contracts"


def test_early_renewal_reject_requires_reason(client):
    from datetime import date, timedelta
    pro = auth_headers(login(client, *PRO))
    # موظف جديد بإقامة تنتهي خلال 60 يومًا (مستقل — DB مشتركة بين الاختبارات)
    eid = client.post("/api/employees", headers=pro, json={
        "name": "موظف رفض", "civil_id": "199911223399", "basic_salary": 300}).json()["id"]
    exp = (date.today() + timedelta(days=60)).isoformat()
    client.post(f"/api/employees/{eid}/permits", headers=pro,
                params={"kind": "residency", "number": "RES-REJ", "expiry_date": exp})
    r = client.post("/api/renewals", headers=pro, data={"employee_id": eid, "reason": "سفر"})
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    mgr = auth_headers(login(client, *MGR))
    # رفض بلا سبب → 400
    assert client.post(f"/api/renewals/{rid}/decide", headers=mgr,
                       data={"decision": "rejected"}).status_code == 400
    # رفض بسبب → مرفوض + يبقى في السجل
    assert client.post(f"/api/renewals/{rid}/decide", headers=mgr,
                       data={"decision": "rejected", "reject_reason": "غير مبرّر"}).status_code == 200
    d = client.get(f"/api/renewals/{rid}", headers=mgr).json()
    assert d["status"] == "rejected" and d["reject_reason"] == "غير مبرّر"
