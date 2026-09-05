# -*- coding: utf-8 -*-
"""قالب موضوعه الشركة — أول مسار في النظام لا يخصّ موظًفا.

**أمر المالك**: «ADMLIC استخدم قالب تجديد الترخيص». وقستُ قبل التنفيذ
فوجدت أنه **لا وجود له**: الاثنان والأربعون قالًبا كلّها موجَّهة
للموظف، ومحرّك العرض نفسه يطلب ``employee_id``، ويغلّف كل مستند بشبكة
بيانات موظف، ويحفظ الناتج ``entity_type="employee"``.

فتجديد ترخيص المنشأة — وهو إجراء قائم في الكتالوج — لم يكن له طريق،
فأُسنِد إليه «إنذار موظف» (HRMS-PR-022) وصار أثره يُصنَّف تأديبًيا.

**والقالب لا يُرسَم منه جسم مستند الطلب** (ذلك من ``render_request_pdf``)
— لكنه يُشتقّ منه ``od_code`` ويُختَم ``template_code``. فالخطأ كان
تصنيًفا لا طباعة، وهو ما صحّحته أوًلا قبل بناء البديل.

**وغلاف واحد لا غلافان**: الكيان يُعلَن في السياق
(``entity_kind``) ويختار الغلافُ الشبكةَ. ونسخة ثانية من الغلاف كانت
ستنحرف في الترويسة والتذييل ورمز التحقّق — فيصير للمستندات شكلان.
"""
from __future__ import annotations

import inspect

from sqlalchemy import select

from app import models, v15_registry as R, workflow
from app.database import SessionLocal
from app.routers import templates as tpl_router
from tests.conftest import auth_headers, login

SUPER = ("000000000000", "admin123")
HR = ("100000000002", "hr12345")


def _tpl_id(db, code: str) -> int | None:
    return db.scalar(select(models.DocumentTemplate.id).where(
        models.DocumentTemplate.code == code))


def test_the_company_template_exists_and_is_classified():
    """خطّ الأساس: القالب موجود، وصنفه مشتقّ لا مخمَّن.

    ``OD-013`` هو صنف المعاملات الحكومية — وإخوته في فئة البذرة نفسها
    (PR-034..PR-037) كلّها فيه.
    """
    db = SessionLocal()
    try:
        tid = _tpl_id(db, "HRMS-PR-043")
        row = db.get(models.DocumentTemplate, tid) if tid else None
    finally:
        db.close()
    assert row, "قالب تجديد ترخيص الشركة غير مبذور"
    assert row.category == "المعاملات الحكومية والمستندات", row.category
    assert R.resolve_template("HRMS-PR-043") == "OD-013"


def test_admlic_points_at_it_not_at_the_warning_notice():
    """**ما نُفِّذ من أمر المالك**: الترخيص لقالب الترخيص."""
    rt = next(r for r in workflow.DEFAULT_REQUEST_TYPES if r["code"] == "ADMLIC")
    assert rt.get("default_template_code") == "HRMS-PR-043", (
        f"ADMLIC يشير إلى {rt.get('default_template_code')}"
    )
    assert R.resolve_template(rt["default_template_code"]) == "OD-013", (
        "عاد أثر تجديد الترخيص يُصنَّف بغير صنف المعاملات الحكومية"
    )


def test_the_wrapper_shows_company_data_not_an_employee_grid(client):
    """**جوهر البناء**: مستند الشركة لا يحمل شبكة موظف فارغة."""
    db = SessionLocal()
    try:
        tid = _tpl_id(db, "HRMS-PR-043")
        cid = db.scalar(select(models.Company.id).order_by(models.Company.id))
        company = db.get(models.Company, cid)
        name = company.name
    finally:
        db.close()

    hdr = auth_headers(login(client, *SUPER))
    r = client.post(f"/api/templates/{tid}/company-preview", headers=hdr,
                    json={"company_id": cid, "extra": {"license_no": "L-991"}})
    assert r.status_code == 200, r.text[:250]
    html = r.json()["html"]

    assert "اسم الشركة" in html, "لا شبكة بيانات شركة"
    assert name in html
    assert "اسم الموظف" not in html, "شبكة الموظف ما زالت تُغلّف مستند الشركة"
    assert "L-991" in html, "ما أدخله المستخدم لم يصل المستند"


def test_the_employee_path_is_untouched(client):
    """ولم يُكسر ما كان يعمل: مستند الموظف يبقى بشبكته."""
    db = SessionLocal()
    try:
        tid = _tpl_id(db, "HRMS-PR-001")
        eid = db.scalar(select(models.Employee.id).order_by(models.Employee.id))
    finally:
        db.close()
    hdr = auth_headers(login(client, *SUPER))
    r = client.post(f"/api/templates/{tid}/preview", headers=hdr,
                    json={"employee_id": eid, "extra": {}})
    assert r.status_code == 200, r.text[:200]
    assert "اسم الموظف" in r.json()["html"]


def test_generating_files_it_under_the_company_not_a_person(client):
    """والأثر يُحفَظ في أرشيف الشركة — والسجلّ يقول «مكانه الأرشيف»."""
    db = SessionLocal()
    try:
        tid = _tpl_id(db, "HRMS-PR-043")
        cid = db.scalar(select(models.Company.id).order_by(models.Company.id))
    finally:
        db.close()

    hdr = auth_headers(login(client, *SUPER))
    r = client.post(f"/api/templates/{tid}/company-generate", headers=hdr,
                    json={"company_id": cid, "extra": {"license_no": "L-777"}})
    assert r.status_code == 200, r.text[:250]
    body = r.json()

    db = SessionLocal()
    try:
        doc = db.get(models.Document, body["document_id"])
    finally:
        db.close()
    assert doc.entity_type == "company", doc.entity_type
    assert doc.entity_id == cid
    assert doc.is_issued is True
    assert doc.reference_no and doc.checksum_sha256, (
        "مستند الشركة بلا مرجع أو بصمة — أضعف حجّية من مستند الموظف"
    )


def test_a_reissue_supersedes_and_does_not_delete(client):
    """وإعادة الإصدار تُنزّل السابقة ولا تحذفها (القاعدة 15)."""
    db = SessionLocal()
    try:
        tid = _tpl_id(db, "HRMS-PR-043")
        cid = db.scalar(select(models.Company.id).order_by(models.Company.id))
    finally:
        db.close()
    hdr = auth_headers(login(client, *SUPER))
    for _ in range(2):
        assert client.post(f"/api/templates/{tid}/company-generate", headers=hdr,
                           json={"company_id": cid}).status_code == 200

    db = SessionLocal()
    try:
        rows = db.scalars(select(models.Document).where(
            models.Document.entity_type == "company",
            models.Document.entity_id == cid,
            models.Document.document_type_code == "form_HRMS-PR-043")).all()
    finally:
        db.close()
    assert len(rows) >= 2, "لم تُحفَظ النسخة الثانية"
    assert sum(1 for d in rows if d.is_current) == 1, (
        f"أكثر من نسخة «حاليّة»: {sum(1 for d in rows if d.is_current)}"
    )


def test_the_wrapper_stayed_one_function():
    """**ولا غلافان**: الكيان يُعلَن ويختار الغلافُ الشبكة.

    نسخة ثانية من الغلاف تنحرف في الترويسة والتذييل ورمز التحقّق.
    """
    src = inspect.getsource(tpl_router)
    assert src.count("def _wrap_printable") == 1, "ظهر غلاف ثانٍ"
    wrapper = inspect.getsource(tpl_router._wrap_printable)
    assert 'ctx.get("entity_kind") == "company"' in wrapper, (
        "الغلاف لا يقرأ كيان المستند"
    )


def test_the_company_path_refuses_another_companys_data(client):
    """ولا يُصدر أحد مستنًدا لشركة ليست شركته."""
    db = SessionLocal()
    try:
        tid = _tpl_id(db, "HRMS-PR-043")
        hr = db.scalar(select(models.User).where(models.User.civil_id == HR[0]))
        other = db.scalar(select(models.Company.id).where(
            models.Company.id != hr.company_id))
    finally:
        db.close()
    assert other, "لا شركة ثانية — القياس فارغ"
    hdr = auth_headers(login(client, *HR))
    r = client.post(f"/api/templates/{tid}/company-generate", headers=hdr,
                    json={"company_id": other})
    assert r.status_code in (403, 404), r.status_code


def test_the_migration_reaches_existing_databases():
    """**والبذر يُدرج ولا يُحدِّث** (درس QA-07): بلا ترحيل لا يصل شيء."""
    from pathlib import Path

    versions = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    hits = [p for p in versions.glob("*.py")
            if "HRMS-PR-043" in p.read_text(encoding="utf-8")]
    assert hits, "لا ترحيل يوصّل القالب الجديد إلى القواعد القائمة"
    text = hits[0].read_text(encoding="utf-8")
    assert "ADMLIC" in text, "الترحيل لا يربط النوع بالقالب"
    assert "DEFAULT_TEMPLATES" in text, (
        "الترحيل يكتب نصّ القالب بنفسه — نسخة ثانية تنحرف عن البذرة"
    )
