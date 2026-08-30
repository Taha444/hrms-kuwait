# -*- coding: utf-8 -*-
"""GC-03/05/06/09/10 — مصادر الحقول ولقطة الإصدار وجاهزية البيئة.

كل بند هنا يشترك في سؤال واحد: **هل الرقم المطبوع في العقد هو الرقم
الصحيح، ومن أين جاء؟** العقد يُقدَّم لجهة رسمية ويوقّعه الموظف، فرقم خاطئ
فيه ليس عطًلا في شاشة بل التزام مكتوب على طرفين.
"""
from __future__ import annotations

import pytest

from app import models
from app.database import SessionLocal
from app.routers import renewals as RN
from tests.conftest import auth_headers, login


@pytest.fixture
def renewal_case():
    """معاملة تجديد على موظف بذرة مكتمل البيانات — تُنشأ دائًما.

    لا تخطٍّ مكان دليل، ولا استعارة لمعاملة أنشأها اختبار آخر: تلك قد
    تكون على موظف ناقص عمًدا، فيسقط هذا الاختبار لسبب لا يخصّه ويشير إلى
    المكان الخطأ.
    """
    db = SessionLocal()
    rid = None
    try:
        emp = db.query(models.Employee).join(
            models.Permit,
            models.Permit.employee_id == models.Employee.id).filter(
            models.Permit.kind == "residency",
            models.Employee.name_en.isnot(None),
            models.Employee.passport_number.isnot(None),
        ).first()
        assert emp is not None, "لا موظف مكتمل بإقامة في بيانات البذرة"
        permit = db.query(models.Permit).filter(
            models.Permit.employee_id == emp.id,
            models.Permit.kind == "residency").first()
        rn = models.ResidencyRenewal(
            company_id=emp.company_id, employee_id=emp.id,
            permit_id=permit.id, renewal_type="residency",
            status="new", created_by=1)
        db.add(rn)
        db.commit()
        rid = rn.id
        yield rid
    finally:
        if rid:
            obj = db.get(models.ResidencyRenewal, rid)
            if obj:
                db.delete(obj)
                db.commit()
        db.close()


# ---------------------------------------------------------------------------
# GC-05 — الأجر من المسيّر المعتمد
# ---------------------------------------------------------------------------
def test_wage_comes_from_the_approved_payroll_not_the_employee_file():
    """راتب الملف قابل للتعديل في أي لحظة؛ وأجر المسيّر المعتمد التزام.

    عقد يذكر رقًما لم يعتمده أحد يُوقَّع ويُقدَّم لجهة رسمية.
    """
    db = SessionLocal()
    try:
        emp = db.query(models.Employee).filter(
            models.Employee.company_id == 1).first()
        emp.basic_salary = 400
        db.add(models.PayrollRun(
            company_id=1, period="2099-12", status="approved",
            totals_json={"payslips": [{"employee_id": emp.id,
                                       "basic_salary": 555}]}))
        db.commit()

        wage, source = RN._approved_wage(db, emp)
        assert wage == "555", f"أُخذ الأجر من الملف ({wage}) لا من المسيّر المعتمد"
        assert source.startswith("payroll:"), f"مصدر غير مسجَّل: {source}"
    finally:
        db.query(models.PayrollRun).filter(
            models.PayrollRun.period == "2099-12").delete()
        db.commit()
        db.close()


def test_prepared_payroll_is_not_treated_as_approved():
    """مسيّر محضَّر لم يعتمده أحد — العقد يذكر الأجر التزاًما لا اقتراًحا."""
    db = SessionLocal()
    try:
        emp = db.query(models.Employee).filter(
            models.Employee.company_id == 1).first()
        emp.basic_salary = 400
        db.add(models.PayrollRun(
            company_id=1, period="2099-11", status="prepared",
            totals_json={"payslips": [{"employee_id": emp.id,
                                       "basic_salary": 999}]}))
        db.commit()
        wage, source = RN._approved_wage(db, emp)
        # لا يُشترط أن يكون المصدر الملف: قد يوجد مسيّر معتمد آخر. المهم
        # أن الرقم غير المعتمد لا يصل العقد أبًدا.
        assert wage != "999", f"أُخذ الأجر من مسيّر لم يُعتمد (المصدر: {source})"
        assert "2099-11" not in source
    finally:
        db.query(models.PayrollRun).filter(
            models.PayrollRun.period == "2099-11").delete()
        db.commit()
        db.close()


def test_wage_falls_back_to_the_employee_file_never_to_the_request():
    """موظف جديد بلا مسيّر يبقى قابًلا للتعاقد — والمصدر يُسمّى.

    الممنوع ليس ملف الموظف بل payload الطلب: من يستطيع تحرير أجره في
    نموذج يستطيع تزويره.
    """
    db = SessionLocal()
    try:
        emp = db.query(models.Employee).filter(
            models.Employee.company_id == 2).first()
        emp.basic_salary = 321
        db.commit()
        wage, source = RN._approved_wage(db, emp)
        if source == "employee_master":
            assert wage == "321"
        else:
            # وُجد مسيّر معتمد لهذه الشركة — وهو المصدر الأولى. المهم أن
            # المصدر مسمّى دائًما، فلا يُقرأ رقم بلا أصل معروف.
            assert source.startswith("payroll:")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# GC-06 — رقم الإقامة الفعلي
# ---------------------------------------------------------------------------
def test_residence_field_carries_the_real_permit_number(renewal_case):
    """كود المستند الداخلي يُطبع في خانة رسمية فيبدو رقم إقامة وهو ليس كذلك."""
    db = SessionLocal()
    try:
        rn = db.get(models.ResidencyRenewal, renewal_case)
        emp = db.get(models.Employee, rn.employee_id)
        permit = db.query(models.Permit).filter(
            models.Permit.employee_id == emp.id,
            models.Permit.kind == "residency").order_by(
            models.Permit.expiry_date.desc()).first()
        assert permit is not None, "لا إقامة مسجَّلة — لا يُختبر رقمها"
        company = db.get(models.Company, rn.company_id)
        ctx = RN._gov_contract_context(db, emp, company, rn)
        assert ctx["residence_no"] == permit.number, (
            f"خانة الإقامة تحمل {ctx['residence_no']!r} "
            f"بدل رقم الإقامة {permit.number!r}"
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# GC-10 — لقطة الإصدار
# ---------------------------------------------------------------------------
def test_issued_snapshot_records_the_values_used():
    """«بأي راتب صدر عقد مارس؟» سؤال يُجاب من السجلّ لا من فتح الملف."""
    from app import gov_contract_docx as G

    ctx = {src: "x" for _, src, _, _ in G.FIELD_SOURCES}
    ctx.update({"contract_date": "01/03/2026", "wage": "450",
                "wage_source": "payroll:2026-02",
                "contract_type_raw": "definite"})
    _c, _e, _m, missing, snap = G.generate(ctx)
    assert not missing
    assert snap["fields"]["wage"] == "450"
    assert snap["wage_source"] == "payroll:2026-02"
    assert snap["contract_term"] == "definite"
    assert snap["template_sha256"] == G.OFFICIAL_SHA256, (
        "اللقطة لا تُثبت أي نموذج صدر به العقد"
    )
    assert snap["issued_at"]


def test_snapshot_is_frozen_when_employee_data_changes_later():
    """جوهر GC-10: تغيّر بيانات الموظف لاحًقا لا يغيّر عقًدا صادًرا."""
    from app import gov_contract_docx as G

    ctx = {src: "x" for _, src, _, _ in G.FIELD_SOURCES}
    ctx.update({"contract_date": "01/03/2026", "wage": "450"})
    *_, snap1 = G.generate(ctx)

    ctx["wage"] = "900"                      # رُفع الراتب بعد الإصدار
    *_, snap2 = G.generate(ctx)

    assert snap1["fields"]["wage"] == "450", "اللقطة الأولى تغيّرت بأثر رجعي"
    assert snap2["fields"]["wage"] == "900"


# ---------------------------------------------------------------------------
# GC-09 — جاهزية البيئة
# ---------------------------------------------------------------------------
def test_environment_report_never_claims_ready_without_both():
    """LibreOffice بلا خطوط عربية أسوأ من غيابه.

    يُنتج ملًفا يبدو سليًما وهو مربّعات فارغة — والتوليد يعود بنجاح
    وتُحسب بصمته ويصل الموظف ليوقّعه.
    """
    from app import gov_contract_docx as G

    rep = G.environment_report()
    assert set(rep) >= {"libreoffice", "arabic_fonts_found", "can_render_pdf",
                        "status", "note"}
    if rep["status"] == "ok":
        assert rep["can_render_pdf"] and rep["arabic_fonts_found"], (
            "وُصفت البيئة بالجاهزية وأحد الشرطين ناقص"
        )


def test_deep_health_surfaces_gov_contract_readiness(client):
    """الحال يظهر في فحص الصحّة، فيُكتشف قبل التقديم لا بعده."""
    # F-001 — تفصيل فحص الصحّة صار امتيازًا: المجهول يرى حالة
    # المكوّنات بلا أرقامها، فما يفحص المحتوى يُصادِق.
    _h = auth_headers(login(client, "000000000000", "admin123"))
    r = client.get("/api/health/deep", headers=_h)
    assert r.status_code in (200, 503), r.text
    checks = r.json().get("checks", {})
    assert "gov_contract" in checks, "جاهزية العقد لا تظهر في فحص الصحّة"
    assert "status" in checks["gov_contract"]


# ---------------------------------------------------------------------------
# GC-03 — كل حقل من مصدره
# ---------------------------------------------------------------------------
def test_every_field_source_resolves_from_the_database(renewal_case):
    """لا حقل يُملأ من الهواء: كل مصدر إمّا عمود أو مشتقّ معلوم."""
    from app import gov_contract_docx as G
    from app.routers.templates import _resolve_authoritative_data

    db = SessionLocal()
    try:
        rn = db.get(models.ResidencyRenewal, renewal_case)
        emp = db.get(models.Employee, rn.employee_id)
        company = db.get(models.Company, rn.company_id)
        ctx = _resolve_authoritative_data(db, emp, extras={})
        ctx.update(RN._gov_contract_context(db, emp, company, rn))
        values, missing = G.build_values(ctx)
        assert not missing, f"حقول بلا مصدر رغم اكتمال البيانات: {missing}"
        assert len(values) >= len(G.FIELD_SOURCES)
    finally:
        db.close()
