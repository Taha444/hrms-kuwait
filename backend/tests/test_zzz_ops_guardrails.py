# -*- coding: utf-8 -*-
"""البنود الحارسة — سلوك قائم يُمنع كسره.

هذه ليست أعطاًلا تُصلَح بل **قرارات مقصودة** ينصّ الكيت على حمايتها:
«جولة تنظيف تكسر قرارات متفق عليها أسوأ من ألّا تحدث».

- ``P1-04`` — إصدارات المستند: الجديد يصير السارية والقديم يبقى تاريًخا
- ``P5-25`` — النظام لا يُصدر مستنًدا حكومًيا بدل الجهة (``OD-013``)
- ``P7-30`` — نقص البيانات يُعرض «إعداد مطلوب» لا نموذًجا مكسوًرا

وحمايتها باختبار لا بتعليق: التعليق يُقرأ يوم يُكتب، والاختبار يسقط يوم
يُكسر.
"""
from __future__ import annotations

import inspect

from app import v15_registry as R
from app.routers import documents


# ---------------------------------------------------------------------------
# P1-04 — الإصدارات
# ---------------------------------------------------------------------------
def test_uploading_a_version_demotes_the_previous_one_without_deleting_it():
    """الجديد يصير السارية، والقديم **يبقى**.

    والفرق جوهري: مستند صدر ووُقّع عليه لا يُمحى بترقية نسخة. ومن يفتّش
    بعد سنة يحتاج أن يقرأ ما كان سارًيا حينها لا ما هو ساٍر اليوم.
    """
    src = inspect.getsource(documents)
    assert "is_current = False" in src, (
        "لا يُنزَّل الإصدار السابق — نسختان ساريتان معًا"
    )
    assert "version=new_version" in src or "new_version" in src, (
        "لا ترقيم للإصدارات"
    )
    # ولا حذف: البحث عن مسح الصفوف القديمة
    for bad in ("db.delete(d)", "delete(models.Document).where"):
        assert bad not in src, f"الإصدار القديم يُحذف بدل أن يُحفظ: {bad}"


def test_history_remains_queryable():
    """والتاريخ يبقى مقروًءا — وإلا كان الحفظ بلا فائدة."""
    src = inspect.getsource(documents)
    assert "is_current" in src and "version" in src


# ---------------------------------------------------------------------------
# P5-25 — لا مستند حكومي بدل الجهة
# ---------------------------------------------------------------------------
def test_the_government_cover_sheet_declares_it_is_not_the_original():
    """``OD-013`` غلاف متابعة **داخلي**، والأصل يُرفع من الجهة.

    والملاحظة القانونية مكتوبة في السجلّ نفسه، لا في تعليق جانبي: من
    يقرأ التعريف يعرف حدّه قبل أن يبني عليه.
    """
    od = R.CANONICAL_DOCUMENTS.get("OD-013")
    assert od, "OD-013 غير معرَّف"
    note = od.get("legal_note_ar") or ""
    assert note, "غلاف المعاملة الحكومية بلا ملاحظة قانونية"
    assert "لا يُصدر" in note or "لا يصدر" in note, note
    assert "الأصل يُرفع من الجهة" in note or "الجهة" in note, note


def test_the_cover_sheet_is_not_marked_as_an_official_government_output():
    """ولا يُوصف بأنه بديل: اسمه «غلاف متابعة» لا «شهادة» ولا «إذن»."""
    od = R.CANONICAL_DOCUMENTS["OD-013"]
    name = od.get("name_ar") or ""
    assert "غلاف" in name, f"اسم يوحي بأنه المستند الحكومي نفسه: {name}"


def test_no_other_document_claims_to_replace_a_government_original():
    """والقاعدة على السجلّ كلّه لا على مستند واحد.

    مستند يُضاف غًدا ويدّعي إصدار ورقة حكومية يسقط هنا.
    """
    suspicious = []
    for od, body in R.CANONICAL_DOCUMENTS.items():
        name = (body.get("name_ar") or "") + " " + (body.get("name_en") or "")
        note = body.get("legal_note_ar") or ""
        looks_government = any(k in name for k in ("إقامة", "إذن عمل", "ترخيص"))
        if looks_government and not note:
            suspicious.append((od, name.strip()))
    assert not suspicious, (
        f"مستندات تبدو حكومية بلا ملاحظة تحدّ صفتها: {suspicious}"
    )


# ---------------------------------------------------------------------------
# P7-30 — نقص البيانات ليس عطًلا في المنتج
# ---------------------------------------------------------------------------
def test_an_empty_reference_list_says_what_is_missing():
    """«لا ورديات معرَّفة» أنفع من خانة صامتة أو نموذج مكسور.

    والقاعدة من سكيل الحماية §3: نقص البيانات يُعرَض «إعداد مطلوب»
    موجًَّها للدور المناسب، لا رسالة خطأ عامة.
    """
    from app.ref_options import fill_schema_options
    from app.database import SessionLocal

    schema = {"fields": [{"code": "requested_shift_id", "type": "shift_ref",
                          "label": "الوردية المطلوبة"}]}
    db = SessionLocal()
    try:
        filled = fill_schema_options(db, schema, 999999)   # شركة بلا بيانات
    finally:
        db.close()

    field = filled["fields"][0]
    assert not field.get("options")
    msg = field.get("setup_required") or ""
    assert msg, "فراغ صامت بلا تفسير"
    # المقارنة على المعنى لا على التشكيل: «أوًلا» و«أولًا» و«أولا» نصوص
    # مختلفة بايتًيا ومعنى واحد، ومقارنة حرفية تسقط على رسالة سليمة.
    bare = "".join(ch for ch in msg if not ("ً" <= ch <= "ْ"))
    assert "أولا" in bare, f"لا يقول ما يُفعل: {msg}"
    assert "ورديات" in bare, f"لا يسمّي الناقص: {msg}"


def test_the_setup_message_does_not_replace_a_working_field():
    """ولا يظهر «إعداد مطلوب» على شركة بياناتها كاملة."""
    from sqlalchemy import select

    from app import models
    from app.database import SessionLocal
    from app.ref_options import fill_schema_options

    db = SessionLocal()
    try:
        cid = db.scalar(select(models.Shift.company_id).where(
            models.Shift.company_id.isnot(None)))
        assert cid, "لا ورديات في البذرة — القياس فارغ"
        filled = fill_schema_options(
            db, {"fields": [{"code": "requested_shift_id",
                             "type": "shift_ref", "label": "الوردية"}]}, cid)
    finally:
        db.close()

    field = filled["fields"][0]
    assert field.get("options"), "شركة لها ورديات ولا خيارات"
    assert not field.get("setup_required"), "رسالة إعداد على بيانات كاملة"
