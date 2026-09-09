# -*- coding: utf-8 -*-
"""الفرع يُولَد ناقًصا ولا يُكمَّل — وما كشفه بناء وضع الواجهة البرمجية.

**العطل**: ``BranchIn`` كان يقبل الاسم والإحداثيات والعنوان، ويحجب
ثلاثة يبني عليها النظام:

- ``code`` يدخل **الرقم الوظيفي** لكل موظف في الفرع (``GTC-SLM-00042``).
- ``governorate`` هي **إدارة العمل المختصّة** في العقد الحكومي — وبلا
  محافظة على أي فرع يقف التوليد برسالة «إدارة العمل ناقصة».

**ولا نقطة تحديث للفروع أصًلا**: فرٌع بخطأ في اسمه يبقى به إلى الأبد،
وفرٌع بلا إحداثيات لا يُضبَط فلا يعمل البصم بالموقع فيه. أي أن الحقول
الثلاثة محجوبٌة عند الإنشاء **ولا باب لها بعده**.

ولم يظهر هذا في مسح «نقطة بلا طريق» لأن المشكلة ليست نقطًة بلا طريق بل
**حقًلا بلا مدخل**: النقطة موجودة، وصيغتها هي الناقصة.

**ووضع الواجهة البرمجية** يمرّ من الباب نفسه الذي تمرّ منه الشاشة:
الخادم هو من يكتب، فيحفظ الملف في مخزنه ويقيّد في التدقيق باسم من رفع.
وبديله — الكتابة في القاعدة من جهاز بعيد — يحفظ الملفات على الجهاز
وصفوف الموقع تشير إلى ما لا يجده خادمه.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete, select

from app import models
from app.database import SessionLocal
from app.main import app
from tests.conftest import auth_headers, login

MANAGER = ("100000000001", "manager123")


@pytest.fixture
def made(client):
    """فرٌع يُنشأ بالحقول الثلاثة — ويُزال بعد القياس."""
    hdr = auth_headers(login(client, *MANAGER))
    r = client.post("/api/branches", headers=hdr, json={
        "name": "فرع قياس الحقول", "code": "ZZBR9", "name_en": "Test Branch",
        "governorate": "الأحمدي", "governorate_en": "Al Ahmadi",
        "address": "عنوان أوّلي"})
    assert r.status_code == 201, r.text
    bid = r.json()["id"]
    yield hdr, bid

    db = SessionLocal()
    try:
        db.execute(sa_delete(models.Branch).where(models.Branch.id == bid))
        db.commit()
    finally:
        db.close()


def test_a_branch_is_born_with_its_code_and_governorate(made):
    """**جوهر العطل**: حقول يبني عليها النظام وكانت محجوبة عن الإنشاء."""
    hdr, bid = made
    db = SessionLocal()
    try:
        b = db.get(models.Branch, bid)
        got = (b.code, b.governorate, b.governorate_en, b.name_en)
    finally:
        db.close()
    assert got == ("ZZBR9", "الأحمدي", "Al Ahmadi", "Test Branch"), got


def test_a_branch_can_be_corrected_after_birth(client, made):
    """**ولم يكن للفروع تعديٌل أصًلا** — خطٌأ في الاسم يبقى إلى الأبد."""
    hdr, bid = made
    r = client.put(f"/api/branches/{bid}", headers=hdr,
                   json={"name": "الاسم بعد التصحيح",
                         "latitude": 29.0769, "longitude": 48.0838})
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        b = db.get(models.Branch, bid)
        assert b.name == "الاسم بعد التصحيح"
        # **والإحداثيات صارت قابلة للضبط**: بدونها لا يعمل البصم بالموقع.
        assert b.latitude and b.longitude
        # وما لم يُرسَل لا يُمسّ.
        assert b.code == "ZZBR9" and b.governorate == "الأحمدي"
    finally:
        db.close()


def test_a_partial_update_does_not_wipe_the_rest(client, made):
    """``exclude_unset`` — الفارق بين «لم يُذكر» و«أُفرِغ عمًدا».

    وهو العطل نفسه الذي قِيس في تعديل الموظفين: طلٌب بأربعة حقول محا
    أحد عشر.
    """
    hdr, bid = made
    assert client.put(f"/api/branches/{bid}", headers=hdr,
                      json={"address": "عنوان جديد فقط"}).status_code == 200
    db = SessionLocal()
    try:
        b = db.get(models.Branch, bid)
        assert b.address == "عنوان جديد فقط"
        assert b.name == "فرع قياس الحقول", "مُحي الاسم بتعديل العنوان"
        assert b.governorate == "الأحمدي", "مُحيت المحافظة"
    finally:
        db.close()


def test_the_edit_is_written_in_the_audit_trail(client, made):
    """وتعديٌل بلا أثر في السجل لا يُسأل عنه أحد."""
    hdr, bid = made
    client.put(f"/api/branches/{bid}", headers=hdr, json={"name": "اسم ثالث"})
    db = SessionLocal()
    try:
        # الأحدث لا الأول: سجل التدقيق يبقى بعد حذف الفرع، وSQLite تُعيد
        # استعمال المعرّف — فأول صفّ قد يكون لقياس سابق لا لهذا.
        row = db.scalars(select(models.AuditLog).where(
            models.AuditLog.action == "update_branch",
            models.AuditLog.entity_id == bid
        ).order_by(models.AuditLog.id.desc())).first()
    finally:
        db.close()
    assert row is not None, "التعديل لم يُقيَّد"
    assert "اسم ثالث" in (row.detail or ""), row.detail


def test_a_document_upload_can_carry_its_number(client):
    """ARC-03 — رقم المستند وجهته: تعرضهما البطاقة ولم يكن لهما مدخل.

    فترفع الشركة ترخيًصا رسمًيا ولا سبيل إلى تسجيل رقمه — وهو أول ما
    يُسأل عنه في ورقة رسمية.
    """
    hdr = auth_headers(login(client, *MANAGER))
    db = SessionLocal()
    try:
        cid = db.scalar(select(models.User).where(
            models.User.civil_id == MANAGER[0])).company_id
    finally:
        db.close()

    r = client.post("/api/documents/upload", headers=hdr,
                    data={"entity_type": "company", "entity_id": str(cid),
                          "document_type_code": "custom:قياس الرقم",
                          "title": "ورقة قياس", "doc_number": "9/2026",
                          "issuing_authority": "جهة القياس"},
                    files={"file": ("x.pdf", b"%PDF-1.4 test", "application/pdf")})
    assert r.status_code in (200, 201), r.text

    db = SessionLocal()
    try:
        doc = db.scalar(select(models.Document).where(
            models.Document.document_type_code == "custom:قياس الرقم"))
        meta = doc.extracted_data_json or {}
        db.execute(sa_delete(models.Document).where(models.Document.id == doc.id))
        db.commit()
    finally:
        db.close()
    assert meta.get("doc_number") == "9/2026", meta
    assert meta.get("issuing_authority") == "جهة القياس", meta


# ---------------------------------------------------------------------------
# وضع الواجهة البرمجية
# ---------------------------------------------------------------------------

def test_the_api_mode_goes_through_the_same_door_as_the_screen(client):
    """**الخادم هو من يكتب** — لا الأداة في قاعدة بعيدة.

    والبديل يحفظ الملفات على جهاز المشغّل بينما صفوف الموقع تشير إلى
    مفاتيح لا يجدها خادمه: مستٌند مسجَّل وتنزيله «غير موجود».
    """
    import app.import_company_package as M

    src = inspect_src(M.run_api)
    assert "/documents/upload" in src, "لا يرفع عبر واجهة الموقع"
    assert "/branches" in src, "لا يُنشئ الفروع عبر الواجهة"
    # ولا يُعاد رفع الموجود: إعادةٌ تُنتج إصدارات وهمية لمستند لم يتغيّر.
    assert "_current_types" in src, "يُعيد رفع ما هو موجود"
    # والبصمة قبل الرفع هنا أيًضا.
    assert "sha256" in src.lower(), "يرفع بلا وزن بصمة"


def test_the_password_never_reaches_the_command_line():
    """**وكلمة المرور لا تُمرَّر في سطر الأوامر**: يبقى في تاريخ الصدفة.

    فتُطلَب بـ``getpass`` ولا تُطبَع ولا تُحفَظ.
    """
    import app.import_company_package as M

    src = inspect_src(M.main)
    assert "getpass" in src, "كلمة المرور تُقرأ بلا إخفاء"
    assert "--password" not in src, "كلمة مرور في سطر الأوامر"


def inspect_src(fn) -> str:
    import inspect

    return inspect.getsource(fn)


def test_the_shipped_dataset_still_matches_the_package():
    """وملف البيانات يبقى مطابًقا لعدد ما في الحزمة."""
    p = Path(__file__).resolve().parents[2] / "docs" / "data" / "blue_nile_import.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    assert len(d["documents"]) == 14 and len(d["branches"]) == 11
    assert all(x.get("issuing_authority") for x in d["documents"]), (
        "مستند بلا جهة مصدِرة — والشهادة تسمّيها لكلٍّ"
    )


def test_the_branch_screen_can_create_and_edit():
    """**والنقطة بلا شاشة لا تُستعمَل**: الفروع كانت تُنشأ بالواجهة
    البرمجية وحدها، وشاشتها تعرض مفاتيح الكشك ولا تُنشئ فرًعا ولا تعدّله.
    """
    page = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages"
            / "Branches.tsx").read_text(encoding="utf-8")
    assert 'api.post("/branches"' in page, "لا إنشاء من الشاشة"
    assert "api.put(`/branches/${editing}`" in page, "لا تعديل من الشاشة"
    for field in ("code", "governorate", "latitude"):
        assert f'"{field}"' in page, f"الحقل {field} ليس في النموذج"
    # وما ينقص الفرع يُقال قبل أن يقف به عمل.
    assert "br_no_gov" in page and "br_no_geo" in page, "النقص لا يُعرَض"


def test_the_owner_of_all_companies_can_create_a_branch(client):
    """**ومن يملك كل الشركات كان لا يستطيع إنشاء فرع في أيٍّ منها.**

    ``create_branch`` يقرأ ``user.company_id`` وحده، والإدارة العليا
    وصاحب الشركات بلا شركة بحكم دورهما — فيردّهما بـ400 «يجب أن يكون
    المستخدم تابًعا لشركة». وهو بابٌ مغلق في وجه من له كل المفاتيح.
    """
    from sqlalchemy import select as _select

    hdr = auth_headers(login(client, "000000000000", "admin123"))
    db = SessionLocal()
    try:
        cid = db.scalars(_select(models.Company)).first().id
    finally:
        db.close()

    # بلا تحديد الشركة: يُردّ، والرسالة تقول ما ينقص.
    blind = client.post("/api/branches", headers=hdr,
                        json={"name": "فرع بلا شركة", "code": "ZZNOC"})
    assert blind.status_code == 400, blind.text
    assert "company_id" in blind.json()["detail"], blind.json()

    r = client.post(f"/api/branches?company_id={cid}", headers=hdr,
                    json={"name": "فرع الإدارة العليا", "code": "ZZSUP1",
                          "governorate": "العاصمة"})
    assert r.status_code == 201, r.text
    bid = r.json()["id"]
    db = SessionLocal()
    try:
        b = db.get(models.Branch, bid)
        assert b.company_id == cid and b.code == "ZZSUP1"
        db.execute(sa_delete(models.Branch).where(models.Branch.id == bid))
        db.commit()
    finally:
        db.close()


def test_a_scoped_user_cannot_aim_at_another_company(client):
    """**ونطاق من له شركته يحكمه لا اختياره**: ``company_id`` يُتجاهَل."""
    from sqlalchemy import select as _select

    hdr = auth_headers(login(client, *MANAGER))
    db = SessionLocal()
    try:
        mine = db.scalar(_select(models.User).where(
            models.User.civil_id == MANAGER[0])).company_id
        other = db.scalars(_select(models.Company).where(
            models.Company.id != mine)).first()
        other_id = other.id if other else None
    finally:
        db.close()
    if other_id is None:
        import pytest as _pt
        _pt.skip("لا شركة ثانية للقياس")

    r = client.post(f"/api/branches?company_id={other_id}", headers=hdr,
                    json={"name": "فرع موجَّه لشركة أخرى", "code": "ZZAIM1"})
    assert r.status_code == 201, r.text
    bid = r.json()["id"]
    db = SessionLocal()
    try:
        b = db.get(models.Branch, bid)
        landed = b.company_id
        db.execute(sa_delete(models.Branch).where(models.Branch.id == bid))
        db.commit()
    finally:
        db.close()
    assert landed == mine, "أنشأ فرًعا في شركة خارج نطاقه"
