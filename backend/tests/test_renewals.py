# -*- coding: utf-8 -*-
"""اختبارات قبول تجديد الإقامة (DEMO-001/002): مبكر + عادي + الحالات."""
import io

from sqlalchemy import select

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
    # R9 §1 — التجديد يحتاج العقد الحكومي فقط للانتقال (الداخلي مسموح لكن اختياري)
    client.post(f"/api/renewals/{rid}/upload", headers=pro,
                data={"doc_type": "renewal_contract_gov"}, files=_f())
    assert client.get(f"/api/renewals/{rid}", headers=pro).json()["status"] == "awaiting_signature"

    # الموظف يرفع النسخة الموقّعة الحكومية → تم رفع العقود الموقّعة
    client.post(f"/api/renewals/{rid}/upload", headers=emp,
                data={"doc_type": "renewal_signed_gov"}, files=_f())
    assert client.get(f"/api/renewals/{rid}", headers=pro).json()["status"] == "contracts_signed"

    # المندوب: جاري التجديد ثم رفع إذن العمل → بانتظار البطاقة
    client.post(f"/api/renewals/{rid}/renewing", headers=pro)
    client.post(f"/api/renewals/{rid}/upload", headers=pro,
                data={"doc_type": "work_permit"}, files=_f())
    assert client.get(f"/api/renewals/{rid}", headers=pro).json()["status"] == "awaiting_civil_card"

    # R4 §7 — المندوب يعبّي بيانات المعاملة الحكومية قبل رفع البطاقة (الحالة renewing تسمح)
    from datetime import date, timedelta
    fin = client.post(f"/api/renewals/{rid}/finalize", headers=pro, data={
        "gov_reference_no": "GOV-2026-000123",
        "fees_amount": "150.500",
        "fees_receipt_no": "R-88991",
        "new_permit_number": "RES-NEW-99887",
        "new_expiry_date": (date.today() + timedelta(days=730)).isoformat(),
    })
    assert fin.status_code == 200, fin.text
    # بعد finalize الحالة awaiting_civil_card

    # الموظف يرفع البطاقة المدنية → PENDING_HR_VERIFY
    client.post(f"/api/renewals/{rid}/upload", headers=emp,
                data={"doc_type": "civil_id"}, files=_f())
    after_civil = client.get(f"/api/renewals/{rid}", headers=pro).json()
    assert after_civil["status"] == "pending_hr_verify"
    assert after_civil["gov_reference_no"] == "GOV-2026-000123"
    assert any(d["type"] == "work_permit" for d in after_civil["documents"])

    # HR يتحقق ويغلق — R6-E يُدوّر Permit تلقائيًا
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    hr_ok = client.post(f"/api/renewals/{rid}/hr-verify", headers=hr,
                       data={"note": "تم التحقق من التطابق"})
    assert hr_ok.status_code == 200, hr_ok.text
    final = client.get(f"/api/renewals/{rid}", headers=pro).json()
    assert final["status"] == "completed"
    assert final["hr_verified_at"] is not None


def test_renewal_document_download(client):
    # R6-E — بما إن اختبار full_flow السابق يُدوّر إقامة EMP (تصبح نشطة 730 يوم بعد HR verify)،
    # نعيد إقامة EMP الأصلية القريبة الانتهاء لتشغيل هذا الاختبار مستقلًا
    from datetime import date, timedelta
    from app import models as _m
    from app.database import SessionLocal as _S
    with _S() as _db:
        emp_user = _db.scalar(select(_m.User).where(_m.User.civil_id == EMP[0]))
        if emp_user and emp_user.employee_id:
            # نُلغي أي إقامة نشطة جديدة ونعيد القريبة الانتهاء
            for p in _db.scalars(select(_m.Permit).where(
                _m.Permit.employee_id == emp_user.employee_id,
                _m.Permit.kind == "residency",
            )).all():
                p.status = "expired"
            _db.add(_m.Permit(
                company_id=emp_user.company_id, employee_id=emp_user.employee_id,
                kind="residency", number="RES-EMP-RESET",
                start_date=date.today() - timedelta(days=700),
                expiry_date=date.today() + timedelta(days=8),
                status="active",
            ))
            _db.commit()

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
    # R2-B — الموظف يُنشأ عبر HR (المندوب لم يعد يملك create_employee)
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    pro = auth_headers(login(client, *PRO))
    eid = client.post("/api/employees", headers=hr, json={
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
