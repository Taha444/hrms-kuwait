# -*- coding: utf-8 -*-
"""إدخال حزمة مستندات شركة: يُقرأ قبل أن يُكتب، ويُعاد بلا ضرر.

**لماذا أداة لا إدخال بيد**: أربعة عشر مستنًدا رسمًيا وأحد عشر فرًعا،
لكلٍّ رقم ترخيص وتاريخا إصدار وانتهاء. والخطأ في تاريخ انتهاء واحد يعني
**تنبيه تجديد لا يأتي** — أو معاملة تُفتَح لترخيص ساري.

وما يقيسه هذا الملف هو **القواعد** لا البيانات:

- بلا ``--apply`` لا يُكتب صٌف واحد.
- التشغيل الثاني لا يُضاعف فرًعا ولا مستنًدا.
- **بصمة الملف تُوزَن قبل حفظه**: مستٌند رسمي لا يطابق بصمته المعلنة لا
  يدخل النظام — الفارق إمّا تلٌف وإمّا نسخٌة أخرى، وكلاهما يوقفه.
- حقٌل له قيمة لا يُستبدَل بصمت؛ يُعرَض الفارق ويُترَك القرار لصاحبه.
- الشركة لا تُنشأ من هنا: هويّتها قراٌر يُتَّخذ مرّة، وخطٌأ فيها يسري
  على كل ما تحتها.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from sqlalchemy import delete as sa_delete, select

from app import models
from app.database import SessionLocal
from app.import_company_package import run

MANIFEST = "HRMS_Document_Upload_Mapping.txt"


@pytest.fixture
def package(tmp_path):
    """حزمٌة صغيرة مبنيّة هنا: القياس على القواعد لا على ملفات العميل."""
    (tmp_path / "01_Company").mkdir()
    (tmp_path / "03_Index_and_Mapping").mkdir()
    blob = b"%PDF-1.4 fake company licence"
    doc = tmp_path / "01_Company" / "Company_License.pdf"
    doc.write_bytes(blob)
    sha = hashlib.sha256(blob).hexdigest()
    (tmp_path / "03_Index_and_Mapping" / MANIFEST).write_text(
        "Company: قياس\n"
        "Destination: 01_Company/Company_License.pdf\n"
        f"SHA256: {sha}\n" + "-" * 72 + "\n", encoding="utf-8")
    return tmp_path, doc, sha


@pytest.fixture
def data():
    return {
        "company": {"match_by": {"name_contains": "الخليج"},
                    "name_en": "Gulf Trading Co.", "file_number": "TEST-FILE-1"},
        "branches": [{"no": "01", "code": "ZZTEST01", "name": "فرع القياس",
                      "governorate": "العاصمة", "governorate_en": "Al Asima",
                      "address": "عنوان القياس"}],
        "documents": [{"file": "Company_License.pdf", "entity": "company",
                       "type_code": "custom:قياس الاستيراد",
                       "title": "ترخيص قياس", "number": "1/1",
                       "issued": "2025-01-01", "expiry": "2027-01-01"}],
    }


@pytest.fixture(autouse=True)
def cleanup():
    """يُعيد ما مسّه القياس إلى ما كان — لا إلى الفراغ.

    وكان يُصفّر ``file_number`` بعد كل قياس، فيمحو ما ضبطه اختباٌر قبله.
    **والتنظيف الذي يُصفّر بدل أن يُعيد يُفسد جاره** — وهو نفس ما وقع
    فيه أول قياس هنا حين افترض الفراغ.
    """
    db = SessionLocal()
    try:
        c = db.scalar(select(models.Company).where(
            models.Company.name.contains("الخليج")))
        original = c.file_number
        # **وحالٌة معلومة قبل القياس**: بعض ما هنا يقيس أن المستورِد
        # يملأ الفارغ، وبعضه يقيس أنه لا يستبدل الممتلئ. فلو بدأ القياس
        # على ما تركه غيره، اختلط الشرطان وسقط أحدهما بحسب الترتيب —
        # وهو ما وقع مرّتين. تُصفَّر هنا وتُعاد إلى ما كانت بعده.
        c.file_number = None
        db.commit()
    finally:
        db.close()

    yield

    db = SessionLocal()
    try:
        br = db.scalars(select(models.Branch).where(
            models.Branch.code == "ZZTEST01")).all()
        for b in br:
            db.execute(sa_delete(models.Document).where(
                models.Document.entity_type == "branch",
                models.Document.entity_id == b.id))
            db.delete(b)
        db.execute(sa_delete(models.Document).where(
            models.Document.document_type_code == "custom:قياس الاستيراد"))
        c = db.scalar(select(models.Company).where(
            models.Company.name.contains("الخليج")))
        if c:
            c.file_number = original
        db.commit()
    finally:
        db.close()


def _run(data, package, apply):
    db = SessionLocal()
    try:
        return run(data, package[0], apply=apply, db=db)
    finally:
        db.close()


def test_a_dry_run_writes_nothing(data, package):
    """**التقرير أوًلا والقرار بعده** — والافتراضي ألّا يُكتب شيء.

    والقياس على **عدم التغيّر** لا على قيمة بعينها: كتبتُه أوًلا يشترط
    أن يكون الحقل فارًغا، فسقط في السويت الكاملة ومرّ وحده — لأن اختباًرا
    قبله يملؤه. والشرط الصحيح هو ما يدّعيه هذا الاختبار فعًلا: أن التشغيل
    الجافّ لا يغيّر شيًئا، أًيا كان ما وجده.
    """
    db = SessionLocal()
    try:
        before = db.scalar(select(models.Company).where(
            models.Company.name.contains("الخليج"))).file_number
    finally:
        db.close()

    report = _run(data, package, apply=False)
    assert any("فرع جديد" in x for x in report["branches"]), report

    db = SessionLocal()
    try:
        assert db.scalar(select(models.Branch).where(
            models.Branch.code == "ZZTEST01")) is None, "كُتب في تشغيل جافّ"
        after = db.scalar(select(models.Company).where(
            models.Company.name.contains("الخليج"))).file_number
    finally:
        db.close()
    assert after == before, f"غُيّر حقل في تشغيل جافّ: {before!r} ← {after!r}"


def test_applying_creates_then_repeats_without_doubling(data, package):
    """**وتُعاد بلا ضرر**: تشغيٌل ثانٍ لا يُضاعف فرًعا ولا مستنًدا."""
    _run(data, package, apply=True)
    db = SessionLocal()
    try:
        b = db.scalar(select(models.Branch).where(models.Branch.code == "ZZTEST01"))
        assert b is not None and b.governorate == "العاصمة"
        n1 = db.scalar(select(models.Company).where(
            models.Company.name.contains("الخليج"))).file_number
        docs1 = db.scalars(select(models.Document).where(
            models.Document.document_type_code == "custom:قياس الاستيراد")).all()
    finally:
        db.close()
    assert n1 == "TEST-FILE-1" and len(docs1) == 1

    second = _run(data, package, apply=True)
    db = SessionLocal()
    try:
        branches = db.scalars(select(models.Branch).where(
            models.Branch.code == "ZZTEST01")).all()
        docs2 = db.scalars(select(models.Document).where(
            models.Document.document_type_code == "custom:قياس الاستيراد")).all()
    finally:
        db.close()
    assert len(branches) == 1, f"تضاعف الفرع: {len(branches)}"
    assert len(docs2) == 1, f"تضاعف المستند: {len(docs2)}"
    assert any("موجود" in x for x in second["documents"])


def test_a_file_that_does_not_match_its_hash_is_refused(data, package):
    """**مستٌند رسمي لا يطابق بصمته لا يدخل** — تلٌف أو نسخٌة أخرى."""
    tmp, doc, _sha = package
    doc.write_bytes(b"%PDF-1.4 a different file entirely")

    report = _run(data, package, apply=True)
    assert any("بصمة مخالفة" in x for x in report["blocked"]), report["blocked"]

    db = SessionLocal()
    try:
        docs = db.scalars(select(models.Document).where(
            models.Document.document_type_code == "custom:قياس الاستيراد")).all()
    finally:
        db.close()
    assert not docs, "دخل مستند لا يطابق بصمته"


def test_an_existing_value_is_not_overwritten_silently(data, package):
    """**وقيمٌة قائمة لا تُستبدَل بصمت**: قد تكون هي الأصحّ."""
    db = SessionLocal()
    try:
        c = db.scalar(select(models.Company).where(
            models.Company.name.contains("الخليج")))
        c.file_number = "الرقم القديم"
        db.commit()
    finally:
        db.close()

    report = _run(data, package, apply=True)
    assert any("file_number" in x and "لم يُغيَّر" in x for x in report["blocked"]), (
        report["blocked"]
    )
    db = SessionLocal()
    try:
        c = db.scalar(select(models.Company).where(
            models.Company.name.contains("الخليج")))
        assert c.file_number == "الرقم القديم", "استُبدلت قيمة قائمة"
    finally:
        db.close()


def test_it_refuses_to_invent_a_company(data, package):
    """**والشركة لا تُنشأ من هنا**: هويّتها قراٌر يُتَّخذ مرّة."""
    data = {**data, "company": {**data["company"],
                                "match_by": {"name_contains": "لا شركة بهذا الاسم"}}}
    with pytest.raises(SystemExit) as e:
        _run(data, package, apply=True)
    assert "أنشئها" in str(e.value)


def test_the_shipped_dataset_is_readable_and_declares_its_gaps():
    """وملف بيانات النيل الأزرق يُقرأ، ويقول ما لم يُقرأ منه."""
    p = Path(__file__).resolve().parents[2] / "docs" / "data" / "blue_nile_import.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    assert len(d["branches"]) == 11 and len(d["documents"]) == 14
    # **ما تعذّر تأكيده يُذكر ولا يُملأ بتخمين.**
    assert d["review"], "ملف بيانات بلا قائمة مراجعة يدّعي اليقين"
    assert all(b.get("code") for b in d["branches"]), "فرع بلا كود — لا هوية ثابتة"
    codes = [b["code"] for b in d["branches"]]
    assert len(set(codes)) == len(codes), "كوٌد مكرَّر بين فرعين"


def test_the_number_and_authority_reach_the_screen():
    """**بياٌن يُكتَب ولا يُقرأ عطٌل بذاته.**

    رقم الترخيص وجهته المصدِرة يُحفظان مع كل مستند، وكانت شاشة الأرشيف
    تقرؤهما **للمستند المخصَّص وحده** — فترفع الشركة ترخيصها التجاري
    برقمه وجهته ثم لا يظهر منهما شيء. ورقم الترخيص أول ما يُسأل عنه في
    ورقة رسمية.
    """
    import inspect

    from app.routers import archive as A

    src = inspect.getsource(A._docs_for)
    assert 'item["doc_number"]' in src, "الرقم لا يخرج إلا للمخصَّص"
    assert 'item["issuing_authority"]' in src, "الجهة لا تخرج إلا للمخصَّص"

    page = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages"
            / "Archive.tsx").read_text(encoding="utf-8")
    assert "cur?.doc_number" in page, "البطاقة لا تعرض رقم الترخيص"
    assert 'cur?.status === "expired"' in page, "المنتهي لا يُقال صراحًة"
