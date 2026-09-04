# -*- coding: utf-8 -*-
"""حرّاس بنود P0 التي وُجدت مطبَّقة — كي تبقى.

كيت التشغيل مبنيّ على تقرير مراجعة لا على فحص شيفرة، فبعض بنوده كان
مطبًَّقا قبل أن يُكتب. وإغلاق بند بلا حارس يجعله يعود بلا أن يلاحظ أحد:
لا شيء يقول إن السلوك كان مطلوًبا.

- ``P2-06`` — محرّك الانتهاء يراقب **النسخة السارية وحدها**
- ``P4-19`` — قراءة المستند مسار عادي بثلاث نتائج، لا حاجز
"""
from __future__ import annotations

import inspect
import re

from app import notifications
from app.routers import renewals


# ---------------------------------------------------------------------------
# P2-06 — النسخة السارية وحدها
# ---------------------------------------------------------------------------
def test_the_expiry_scan_filters_on_the_current_version():
    """**لماذا يهمّ**: مستند له خمس نسخ، وأربع منها منتهية بطبيعتها.

    مسحٌ لا يقصر على السارية يُنشئ تنبيًها لكل نسخة قديمة — فيغرق صندوق
    المندوب بتواريخ انتهت قبل سنة، ويضيع بينها ما ينتهي غًدا.
    """
    src = inspect.getsource(notifications.daily_scan)
    doc_query = [ln for ln in src.splitlines()
                 if "models.Document" in ln and "select(" in ln]
    assert doc_query, "لم يُعثر على استعلام المستندات — راجع الفحص"
    assert any("is_current" in ln for ln in doc_query), (
        f"مسح الانتهاء لا يقصر على النسخة السارية: {doc_query}"
    )


def test_the_scan_still_looks_at_expiry_dates():
    """والحدّ المقابل: قصرٌ على السارية بلا تاريخ انتهاء لا يمسح شيًئا."""
    src = inspect.getsource(notifications.daily_scan)
    assert "expiry_date" in src, "المسح لا يقرأ تواريخ الانتهاء"


# ---------------------------------------------------------------------------
# P4-19 — ثلاث نتائج لا حاجز
# ---------------------------------------------------------------------------
#: مكتوبة هنا مستقلّة عن الشيفرة: قراءتها منها تجعل حذف حالة يُفرغ الفحص.
OCR_OUTCOMES = ("failed", "low_confidence", "high_confidence")


def test_document_reading_has_three_named_outcomes():
    """**القاعدة**: القراءة الفاشلة حالة تُعرض، لا حاجز يوقف المعاملة.

    ومن قبلُ كان الفشل يمرّ صامًتا فيمضي النظام كأن شيًئا لم يحدث. والحالات
    الثلاث تجعل المراجع يرى ما قرأه النظام وبأي ثقة، ويؤكّد أو يُدخل يدًوا.
    """
    src = inspect.getsource(renewals)
    for outcome in OCR_OUTCOMES:
        assert f'"{outcome}"' in src, f"حالة «{outcome}» غير موجودة"


def test_low_confidence_requires_confirmation_and_high_does_not():
    """التمييز عملي لا تسمية: ما دون العتبة يُطلب تأكيده."""
    src = inspect.getsource(renewals)
    block = re.search(r'status, needs = "low_confidence", (\w+)', src)
    high = re.search(r'status, needs = "high_confidence", (\w+)', src)
    failed = re.search(r'status, needs = "failed", (\w+)', src)
    assert block and high and failed, "لم تُقرأ نتائج القراءة الثلاث"
    assert block.group(1) == "True", "ثقة منخفضة بلا طلب تأكيد"
    assert failed.group(1) == "True", "قراءة فاشلة بلا طلب تأكيد"
    assert high.group(1) == "False", "ثقة عالية تطلب تأكيًدا — حاجز بلا سبب"


def test_the_threshold_is_a_documented_number_not_a_magic_one():
    """والعتبة معلَنة: رقم في الشيفرة بلا سبب يُغيَّر بلا سبب."""
    assert hasattr(renewals, "LOW_CONFIDENCE"), "لا عتبة معلَنة"
    assert 0 < renewals.LOW_CONFIDENCE < 1, renewals.LOW_CONFIDENCE
    doc = inspect.getsource(renewals)
    idx = doc.find("LOW_CONFIDENCE = ")
    around = doc[max(0, idx - 400):idx]
    assert "#" in around, "العتبة بلا تعليل مكتوب"
