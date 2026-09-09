# -*- coding: utf-8 -*-
"""ثلاثة أعطال كشفتها **المراجعة بعد الإدخال** لا الإدخال نفسه.

أُدخلت ثلاث شركات فمرّت كلها بلا خطأ، ثم قُرئ ما في القاعدة فإذا:

1. **حقول الشركة فارغة**: رقم الملف والسجل التجاري والكيان القانوني
   تُقرأ من المستندات ثم **تُتخطّى صمًتا** في وضع الواجهة البرمجية —
   فتدخل الفروع والمستندات وتبقى هويّة الشركة خالية.
2. **مستٌند مخصَّص بلا تنبيه انتهاء**: المسح اليومي يتخطّى ``custom:``
   ما لم يُفعَّل ``notify_on_expiry``، ولم يكن للحقل مدخل في الرفع.
   فترخيص المصنع يدخل بتاريخ انتهائه **ولا ينبّه أحًدا** — وهو أخطر ما
   يصمت عنه النظام: تاريٌخ مسجَّل وتنبيٌه لا يأتي.
3. **بصمة المحتوى لا تُحفَظ**: «هل هذا هو الملف الذي رُفع؟» سؤاٌل بلا
   جواب في مستندات تُقدَّم لجهات رسمية.

**وعطٌل رابع** ظهر في الطريق: ``PUT /companies/{id}`` كان يكتب النموذج
كامًلا بقيمه الافتراضية، فتعديل الاسم وحده **يُصفّر معاملات نهاية
الخدمة** — وهي أرقام تُحسب بها مستحقات الموظفين.

> والدرس: **الإدخال بلا خطأ ليس إدخاًلا صحيًحا.** ما مرّ صامًتا هنا كان
> يمرّ صامًتا على الإنتاج لولا أن قُرئ ما استقرّ في القاعدة.
"""
from __future__ import annotations

import inspect

from sqlalchemy import delete as sa_delete, select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

MANAGER = ("100000000001", "manager123")
SUPER = ("000000000000", "admin123")


def test_a_custom_document_can_be_told_to_alert(client):
    """**تاريٌخ مسجَّل وتنبيٌه لا يأتي** — أخطر ما يصمت عنه النظام."""
    hdr = auth_headers(login(client, *MANAGER))
    db = SessionLocal()
    try:
        cid = db.scalar(select(models.User).where(
            models.User.civil_id == MANAGER[0])).company_id
    finally:
        db.close()

    r = client.post("/api/documents/upload", headers=hdr,
                    data={"entity_type": "company", "entity_id": str(cid),
                          "document_type_code": "custom:قياس التنبيه",
                          "title": "ترخيص قياس", "expiry_date": "2027-01-01",
                          "notify_on_expiry": "true"},
                    files={"file": ("a.pdf", b"%PDF-1.4 alert", "application/pdf")})
    assert r.status_code in (200, 201), r.text

    db = SessionLocal()
    try:
        doc = db.scalar(select(models.Document).where(
            models.Document.document_type_code == "custom:قياس التنبيه"))
        got = (doc.notify_on_expiry, bool(doc.checksum_sha256))
        db.execute(sa_delete(models.Document).where(models.Document.id == doc.id))
        db.commit()
    finally:
        db.close()
    assert got[0] is True, "رُفع مستند مخصَّص بلا تنبيه انتهاء"
    # **وبصمة المحتوى تُحفَظ**: مستندات هذه الشاشة تُقدَّم لجهات رسمية.
    assert got[1], "رُفع بلا بصمة محتوى"


def test_updating_a_company_does_not_reset_its_eos_numbers(client):
    """**أرقاٌم تُحسب بها مستحقات الموظفين لا تُصفَّر بتعديل اسم.**"""
    hdr = auth_headers(login(client, *SUPER))
    db = SessionLocal()
    try:
        c = db.scalars(select(models.Company)).first()
        cid, before = c.id, (c.eos_day_divisor, c.eos_max_months,
                             c.alert_lead_days, c.annual_leave_days)
        c.eos_day_divisor = 30
        db.commit()
    finally:
        db.close()

    r = client.put(f"/api/companies/{cid}", headers=hdr,
                   json={"name_en": "Partial Update Only"})
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        c = db.get(models.Company, cid)
        after = (c.eos_day_divisor, c.eos_max_months,
                 c.alert_lead_days, c.annual_leave_days)
        assert c.name_en == "Partial Update Only"
        c.eos_day_divisor = before[0]
        c.name_en = None
        db.commit()
    finally:
        db.close()
    assert after[0] == 30, f"صُفّر قاسم نهاية الخدمة: {after}"
    assert after[1:] == before[1:], f"صُفّرت معاملات أخرى: {before} ← {after}"


def test_the_company_file_number_can_be_set_through_the_api(client):
    """ورقم ملف صاحب العمل يُطبع في العقد الحكومي — ولم يكن يُقبل هنا."""
    hdr = auth_headers(login(client, *SUPER))
    db = SessionLocal()
    try:
        c = db.scalars(select(models.Company)).first()
        cid, original = c.id, c.file_number
    finally:
        db.close()

    assert client.put(f"/api/companies/{cid}", headers=hdr,
                      json={"file_number": "TEST-FILE-99"}).status_code == 200
    db = SessionLocal()
    try:
        c = db.get(models.Company, cid)
        got = c.file_number
        c.file_number = original
        db.commit()
    finally:
        db.close()
    assert got == "TEST-FILE-99", got


def test_the_api_mode_writes_the_company_fields_at_all():
    """**وحقول الشركة كانت تُتخطّى صمًتا**: تُقرأ من المستندات ولا تُكتب."""
    import app.import_company_package as M

    src = inspect.getsource(M.run_api)
    assert "/companies/" in src, "وضع الواجهة لا يكتب حقول الشركة"
    assert "file_number" in src and "commercial_reg" in src
    # ولا يُستبدَل ما على الموقع: الفارق يُعرَض ويُترَك القرار لصاحبه.
    assert "لم يُغيَّر" in src, "يستبدل قيمة قائمة بلا عرض"
    # والمستند المخصَّص يُرفع بتنبيهه.
    assert "notify_on_expiry" in src, "يرفع مستنًدا مخصًَّصا بلا تنبيه"


def test_the_three_datasets_are_readable_and_declare_their_gaps():
    """وملفات الشركات الثلاث تُقرأ، وكلٌّ يقول ما نقص منه."""
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "docs" / "data"
    expect = {"blue_nile_import.json": (11, 14),
              "qimat_al_nile_import.json": (7, 7),
              "mohamed_ibrahim_import.json": (3, 2)}
    for name, (nb, nd) in expect.items():
        d = json.loads((root / name).read_text(encoding="utf-8"))
        assert len(d["branches"]) == nb, (name, len(d["branches"]))
        assert len(d["documents"]) == nd, (name, len(d["documents"]))
        assert d.get("review"), f"{name}: ملف بيانات بلا قائمة مراجعة يدّعي اليقين"
        codes = [b["code"] for b in d["branches"]]
        assert len(set(codes)) == len(codes), f"{name}: كوٌد مكرَّر"
        assert all(x.get("issuing_authority") for x in d["documents"]), name
