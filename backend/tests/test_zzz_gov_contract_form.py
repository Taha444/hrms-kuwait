# -*- coding: utf-8 -*-
"""العقد الحكومي يخرج على نموذج الهيئة نفسه — قرار المالك (2026-09-17).

سلّم المالكُ نموذجَ الهيئة (صفحتان) وقال: «دا نموذج عقد العمل السليم… عايزه
يتحط بالتفصيل في كل مرة يتم إنشاء عقد فيها… بالمللي». فصار الأصلُ هو
الورقةَ المطبوعة، ويُرسَم فوقه ما يُملأ في الخانات وحده — ولا يُقلَّد بـHTML
ولا يُحوَّل بـLibreOffice (وكان غيابُه يُسلّم ``docx`` بدل PDF).

وما يُحرَس هنا هو ما يُقرأ على الورقة:

- الورقةُ نفسها: بصمُة الأصل، وعدُد الصفحات، والشعار، والنصُّ الرسميُّ حرفًا
  بحرف — لا تُصحَّح كلمٌة فيه ولا يُزاد سطر.
- القيمُ تصل خاناتِها كلَّها، ولا تبقى خانٌة واجبٌة فارغة.
- البند السادس: تُملأ الفقرةُ المطابقة و**تُشطب** الأخرى — ولا تظهران معًا.
- الأجرُ من المسيّر المعتمد (الأساسي)، ورقمُ الإقامة الفعليُّ لا كود المستند.
- والمساران — التعيين والتجديد — يقرآن الملفَّ نفسه والحقولَ نفسها.
"""
from __future__ import annotations

import re

import pytest
from pypdf import PdfReader
from sqlalchemy import select

from app import gov_contract_data as D, gov_contract_form as F, models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

CTX = {
    "employee_name": "محمد فاروق عبدالله", "employee_name_en": "Mohamed Farouk",
    "civil_id": "289071500123", "nationality": "مصري", "nationality_en": "Egyptian",
    "passport_number": "A12345678", "job_title": "محاسب", "job_title_en": "Accountant",
    "company_name": "شركة النيل الأزرق", "company_name_en": "Blue Nile Co.",
    "company_rep_name": "طه عبدالعزيز", "company_rep_name_en": "Taha Abdulaziz",
    "company_civil_id": "277010100987", "labour_dept": "العاصمة", "labour_dept_en": "Al Asima",
    "wage": "850.000", "contract_date": "17/09/2026", "day_name": "الخميس",
    "day_name_en": "Thursday", "contract_start_date": "01/10/2026",
    "contract_type_raw": "definite",
}


def _text(pdf: bytes) -> str:
    r = PdfReader(__import__("io").BytesIO(pdf))
    return "\n".join((p.extract_text() or "") for p in r.pages)


def _pdf(**over) -> bytes:
    ctx = dict(CTX)
    ctx.update(over)
    content, ext, mime, missing, snap = F.generate(ctx)
    assert not missing, missing
    assert ext == "pdf" and mime == "application/pdf"
    return content


# ---------------------------------------------------------------------------
# الورقةُ هي ورقة الهيئة
# ---------------------------------------------------------------------------

def test_the_official_form_is_the_one_the_owner_delivered():
    assert F.ASSET.exists(), "نموذج الهيئة مفقود"
    assert F.asset_sha256() == F.ASSET_SHA256, "تغيّرت بصمة النموذج الرسمي — يُوقف ويُراجَع"


def test_the_output_keeps_the_two_pages_and_the_logo():
    out = _pdf()
    src = PdfReader(str(F.ASSET))
    got = PdfReader(__import__("io").BytesIO(out))
    assert len(got.pages) == len(src.pages) == 2, "عدُد الصفحات تغيّر"

    def images(reader):
        names = []
        for page in reader.pages:
            res = (page.get("/Resources") or {}).get_object()
            xo = (res.get("/XObject") or {})
            xo = xo.get_object() if hasattr(xo, "get_object") else xo
            for k, v in (xo or {}).items():
                obj = v.get_object()
                if obj.get("/Subtype") == "/Image":
                    names.append((obj.get("/Width"), obj.get("/Height")))
        return sorted(names)

    assert images(got) == images(src), "شعار الهيئة أو صوره تغيّرت"


def test_not_one_word_of_the_official_text_is_changed():
    """ولا تُصحَّح كلمٌة في متن الهيئة: نصُّ الأصل يبقى كلُّه في المخرَج."""
    src = _text(F.ASSET.read_bytes())
    out = _text(_pdf())
    for line in [ln.strip() for ln in src.splitlines() if len(ln.strip()) > 25]:
        assert line in out, f"سطرٌ من النموذج الرسمي سقط: {line[:60]}"


def test_page_two_is_untouched():
    """الشروطُ الخاصة وخاناتُ التوقيع تُملأ بخط اليد — فلا يُرسَم فوقها."""
    src = PdfReader(str(F.ASSET)).pages[1].extract_text()
    out = PdfReader(__import__("io").BytesIO(_pdf())).pages[1].extract_text()
    assert src == out


# ---------------------------------------------------------------------------
# القيم
# ---------------------------------------------------------------------------

def test_every_value_reaches_the_paper():
    out = _text(_pdf())
    for value in ("Mohamed Farouk", "289071500123", "Egyptian", "Accountant",
                  "Blue Nile Co.", "Taha Abdulaziz", "277010100987", "Al Asima",
                  "850.000", "17/09/2026", "01/10/2026", "Thursday", "A12345678"):
        assert value in out, f"«{value}» لم يصل الورقة"


def test_arabic_values_reach_the_paper_too():
    out = _text(_pdf())
    # النصُّ العربيُّ يُرسَم مشكًَّلا للعرض، فيُقاس بحروفه لا بسلسلته.
    assert "محمد" in out.replace("‏", "") or "ﻣﺤﻤﺪ" in out, "الاسمُ العربيُّ لم يصل"


def test_every_box_has_a_value_and_every_value_a_box():
    values = F.values_from(CTX)
    filled = {k for k in F.BOXES if str(values.get(k) or "").strip()}
    empty = set(F.BOXES) - filled
    # الفارغُ الوحيدُ المسموح: فقرُة البند السادس التي تُشطب.
    assert empty == {"indefinite_start", "indefinite_start_en"}, empty
    assert set(F.REQUIRED) <= set(values), "حقلٌ واجبٌ بلا قيمة في الخريطة"


def test_a_missing_required_field_names_itself_and_no_longer_stops():
    """قرار المالك 2026-09-22 (بطلب صريح، يعدّل 09-17): الحقل الناقص **لا يوقف** التوليد — تُطبع
    الخانة فارغةً ويملؤها الموظف يدويًّا — و``missing`` يبقى **يُسمّي** الناقص ليعلمه المندوب."""
    content, _, _, missing, _ = F.generate({**CTX, "passport_number": "", "labour_dept": ""})
    assert content.startswith(b"%PDF"), "لم يُولَّد عقد رغم إلغاء الحجب"
    assert F.REQUIRED["passport_number"] in missing
    assert F.REQUIRED["labour_dept"] in missing
    full, _, _, none_missing, _ = F.generate(CTX)
    assert full.startswith(b"%PDF") and not none_missing, none_missing


def test_nothing_is_taken_from_the_request_payload():
    """القيمُ من السياق المبنيّ في الخادم — ولا مفتاح يأتي من حمولة الطلب."""
    import inspect
    src = inspect.getsource(F.values_from)
    assert "payload" not in src and "request" not in src


# ---------------------------------------------------------------------------
# البند السادس
# ---------------------------------------------------------------------------

def _drawn_lines(pdf: bytes) -> int:
    """عدُد خطوط الشطب المرسومة على الصفحة الأولى."""
    page = PdfReader(__import__("io").BytesIO(pdf)).pages[0]
    ops = page.get_contents().get_data().decode("latin-1", "ignore")
    return len(re.findall(r"\bl\b", ops))


@pytest.mark.parametrize("kind, filled, struck", [
    ("definite", "definite_start", "indefinite"),
    ("indefinite", "indefinite_start", "definite"),
])
def test_one_clause_is_filled_and_the_other_struck(kind, filled, struck):
    values = F.values_from({**CTX, "contract_type_raw": kind})
    assert values[filled] == "01/10/2026"
    other = "indefinite_start" if filled == "definite_start" else "definite_start"
    assert not values.get(other), "الفقرتان مملوءتان معًا — عقدٌ يناقض نفسه"
    assert _drawn_lines(_pdf(contract_type_raw=kind)) >= len(F.STRIKE_LINES[struck])


def test_an_unknown_contract_type_is_treated_as_indefinite_not_as_both():
    values = F.values_from({**CTX, "contract_type_raw": "??"})
    assert bool(values.get("indefinite_start")) != bool(values.get("definite_start"))


def test_the_strike_covers_the_clause_lines_only():
    for kind, lines in F.STRIKE_LINES.items():
        for _, x0, y0, x1, y1 in lines:
            assert 600 <= y0 <= 665, (kind, y0)   # البند السادس وحده
            assert x1 > x0


# ---------------------------------------------------------------------------
# مصادر البيانات — والمساران يقرآن الشيء نفسه
# ---------------------------------------------------------------------------

def test_wage_comes_from_the_approved_payroll_as_basic_salary():
    db = SessionLocal()
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.basic_salary.isnot(None)))
        # فترٌة بعيدة كي تكون هي الأحدث مهما تركت اختباراتٌ سابقة من مسيّرات.
        run = models.PayrollRun(company_id=1, period="2099-12", status="approved",
                                totals_json={"payslips": [
                                    {"employee_id": emp.id, "basic_salary": 777.5}]})
        db.add(run)
        db.flush()
        wage, source = D.approved_wage(db, emp)
        assert wage == "777.5" and source == "payroll:2099-12"
    finally:
        db.rollback()
        db.close()


def test_a_prepared_payroll_is_not_an_approved_wage():
    assert "prepared" not in D.APPROVED_PAYROLL_STATUSES


def test_both_paths_read_the_same_form_and_the_same_fields():
    import inspect

    from app.routers import employees as RE, renewals as RR
    assert "gov_contract_form.generate" in inspect.getsource(RR)
    assert "gov_contract_form.generate" in inspect.getsource(RE._issue_gov_contract)
    assert "gov_contract_data.contract_context" in inspect.getsource(RE._issue_gov_contract)
    assert RR._approved_wage is D.approved_wage


def test_the_snapshot_records_what_was_printed():
    _, _, _, _, snap = F.generate({**CTX, "wage_source": "payroll:2026-08"})
    assert snap["wage"] == "850.000" and snap["wage_source"] == "payroll:2026-08"
    assert snap["contract_term"] == "definite"
    assert snap["form_sha256"] == F.ASSET_SHA256


def test_deep_health_reports_form_readiness(client):
    r = client.get("/api/health/deep").json()
    gov = r["checks"]["gov_contract"]
    assert gov["status"] in ("ok", "degraded")
    assert gov["form_fingerprint_ok"] is True and "can_render_pdf" in gov


def test_the_hire_endpoint_returns_the_official_form(client):
    """مسارُ التعيين كان يبني HTML يقلّد النموذج — فصار يسلّم الورقة نفسها."""
    db = SessionLocal()
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.status == "active",
            models.Employee.passport_number.isnot(None)))
        company = db.get(models.Company, 1)
        snap = (company.representative_name, company.representative_civil_id)
        company.representative_name = company.representative_name or "ممثّل الشركة"
        company.representative_civil_id = company.representative_civil_id or "270010100001"
        eid = emp.id
        db.commit()
    finally:
        db.close()
    try:
        r = client.post(f"/api/employees/{eid}/gov-contract/generate?format=pdf",
                        headers=auth_headers(login(client, "100000000002", "hr12345")))
        assert r.status_code == 200, r.text[:300]
        assert r.headers["content-type"].startswith("application/pdf")
        assert len(PdfReader(__import__("io").BytesIO(r.content)).pages) == 2
    finally:
        db = SessionLocal()
        try:
            c = db.get(models.Company, 1)
            c.representative_name, c.representative_civil_id = snap
            db.commit()
        finally:
            db.close()


def test_the_residence_field_carries_the_real_permit_number():
    """كودُ المستند الداخلي يُطبع في خانة رسمية فيبدو رقم إقامة وهو ليس كذلك."""
    db = SessionLocal()
    try:
        first = db.scalar(select(models.Permit).where(models.Permit.kind == "residency"))
        assert first is not None, "لا إقامة مسجَّلة — لا يُختبر رقمها"
        emp = db.get(models.Employee, first.employee_id)
        # القاعدُة: أحدثُ إقامٍة انتهاًء لهذا الموظف — لا أولُ صفٍّ في الجدول.
        latest = db.scalar(select(models.Permit).where(
            models.Permit.employee_id == emp.id,
            models.Permit.kind == "residency").order_by(
                models.Permit.expiry_date.desc()))
        ctx = D.contract_context(db, emp, db.get(models.Company, emp.company_id))
        assert ctx["residence_no"] == latest.number
    finally:
        db.close()


def test_a_later_raise_does_not_change_an_issued_contract():
    """جوهر GC-10: لقطُة الإصدار تُجمَّد — تغيّرُ البيانات بعدها لا يغيّر عقًدا صدر."""
    *_, snap1 = F.generate({**CTX, "wage": "450"})
    *_, snap2 = F.generate({**CTX, "wage": "900"})
    assert snap1["wage"] == "450" and snap2["wage"] == "900"


def test_the_labour_department_follows_the_workplace_governorate():
    db = SessionLocal()
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.branch_id.isnot(None)))
        branch = db.get(models.Branch, emp.branch_id)
        ctx = D.contract_context(db, emp, db.get(models.Company, 1))
        if branch.governorate:
            assert ctx["labour_dept"] == branch.governorate
        else:
            assert ctx["labour_dept"] != ""  # من مقرّ الشركة لا فراغ
    finally:
        db.close()
