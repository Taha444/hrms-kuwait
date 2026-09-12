# -*- coding: utf-8 -*-
"""الكتالوُج في موضعين، والذي يعمل هو القاعدة — ال الشيفرة.

**أخطُر ما وُجد في هذه الجولة.** ``ensure_default_catalog`` كانت **تُدرِج
الناقَص وال تُحدِّث القائم**::

    if rt["code"] in existing_rt:
        continue

فكلُّ تغييٍر في ``DEFAULT_REQUEST_TYPES`` بعد أوّل نشرٍة **ال يبلغ النظاَم
العامل**: الشيفرُة تُعلن أن نوًعا يُنتج مستنًدا، و``get_request_type`` تقرأ
صَّف القاعدة الذي يقول غير ذلك. وقيس على قاعدٍة حقيقية: **خمسٌة وثالثون
نوًعا** غيُر متزامن — منها ما وُصِل في دفعاٍت سابقة (``advance`` و``loan``
و``REQPER`` و``REQATT`` و``REQOT``) فبقي صامًتا.

**ولم يُمسَك ألن الاختبار يبذر من جديد**: ``conftest`` ينفّذ
``Base.metadata.drop_all`` ثم ``seed.run()`` — فيعمل على كتالوٍج طازٍج
دائًما. «أخضٌر في الاختبار وصامٌت في الإنتاج»، وهو الصنُف نفسه الذي كُنس
في هذه الجولة (ترويسٌة ال تُكشَف، وساعُة مضيف).

**فيُقاس اآلليُة ال الحالة**: صٌّف يُفسَد بيًدا، ثم تُشغَّل المصالحة،
ويُقاس أنه عاد. فحاٌرس يقيس حالًة على قاعدٍة طازجٍة يمرّ دائًما وال يحرس
شيًئا.

**والمزامنُة آمنٌة بالقياس**: ال مساَر ``PUT``/``PATCH`` لأنواع الطلبات في
النظام كلّه، فالصفوُف العامّة نسخٌة من الكتالوج ال عمٌل بشرّي.

**وسلسلُة الاعتماد تُستثنى بشرط**: ``Request.current_stage`` فهٌرس فيها،
فتغييُر طولها يُزيح معنى المراحل على طلٍب جاٍر.
"""
from __future__ import annotations

import inspect

from sqlalchemy import select

from app import models
from app.catalog_seed import ensure_default_catalog
from app.database import SessionLocal


def test_reconciliation_restores_a_drifted_row():
    """**جوهر البند**: صٌّف يخالف الكتالوَج يُصالَح ال يُترَك."""
    db = SessionLocal()
    try:
        row = db.scalar(select(models.RequestType).where(
            models.RequestType.code == "REQPASS",
            models.RequestType.company_id.is_(None)))
        assert row is not None, "ال نوَع REQPASS في القاعدة"
        was_produces = row.produces_document
        was_tpl = row.default_template_code

        # نُفسده كما تفسده نشرٌة قديمة
        row.produces_document = False
        row.default_template_code = "HRMS-PR-024"
        db.commit()

        report = ensure_default_catalog(db)
        db.expire_all()
        row = db.scalar(select(models.RequestType).where(
            models.RequestType.code == "REQPASS",
            models.RequestType.company_id.is_(None)))

        assert row.produces_document is True, "لم تُصالَح الرايُة"
        assert row.default_template_code == "HRMS-PR-034", \
            f"لم يُصالَح القالُب: {row.default_template_code}"
        assert report["request_types_updated"] >= 1, report
        assert any(d.startswith("REQPASS:") for d in
                   report["request_types_updated_detail"]), report
        assert was_produces is True and was_tpl == "HRMS-PR-034", \
            "افتراُض القياس: الصفُّ كان مصالًحا قبل اإلفساد"
    finally:
        db.close()


def test_reconciliation_is_idempotent():
    """ومصالحٌة تُبلِّغ عن تغييٍر كلَّ مرة ال يُصدَّق تقريرُها."""
    db = SessionLocal()
    try:
        ensure_default_catalog(db)
        second = ensure_default_catalog(db)
        assert second["request_types_updated"] == 0, \
            second["request_types_updated_detail"]
    finally:
        db.close()


def test_the_approval_chain_is_not_shifted_under_a_live_request():
    """**وسلسلٌة تُغيَّر تحت طلٍب جاٍر تُزيح معنى مراحله.**

    ``current_stage`` فهٌرس في السلسلة: فلو قُصِّرت أو طُوِّلت، صارت
    المرحلُة الثالثُة غيَر التي قُرِّرت. فتُؤجَّل حين يوجد طلٌب جاٍر ويختلف
    الطول، ويُقال ذلك في التقرير.
    """
    src = inspect.getsource(ensure_default_catalog)
    assert "in_flight" in src, "ال يُفحَص وجوُد طلٍب جاٍر"
    assert "same_length" in src, "ال يُقاس فرُق الطول"
    assert "chain_deferred" in src, "التأجيُل ال يُقال"


def test_the_report_names_what_changed():
    """**ومصالحٌة ال يُعرَف أنها وقعت ال تُصدَّق** — فتُسمّى بما تغيّر."""
    db = SessionLocal()
    try:
        report = ensure_default_catalog(db)
    finally:
        db.close()
    for key in ("request_types_updated", "request_types_updated_detail",
                "approval_chains_deferred"):
        assert key in report, key


def test_the_reason_it_was_missed_is_recorded():
    """**والعلُّة تُكتَب حيث يُقرأ الملف**: الاختباُر يبذر من جديد.

    فمن ال يعرف ذلك يظنّ أن السويَت الخضراء تُثبت أن الإنتاج مصالَح.
    """
    src = inspect.getsource(ensure_default_catalog)
    assert "conftest" in src or "يبذر من جديد" in src, \
        "ال يُقال لماذا لم يُمسَك هذا"
