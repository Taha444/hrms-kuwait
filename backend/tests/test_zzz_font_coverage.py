# -*- coding: utf-8 -*-
"""GC-09 — الخط يُقرأ لا يُسمّى.

**العطل**: فحص الجاهزية عدّ كل خط يحمل ``noto`` في اسمه خًطا عربًيا. فلمّا
ثُبِّتت ``fonts-noto-core`` على الإنتاج ردّ ``status: ok`` وقال «جاهز
لإخراج PDF بعربية سليمة»، والدليل الذي عرضه بنفسه كان خطوًطا سنهالية
وماليالامية ولاوية. الاسم يطابق، والحروف لا.

وخطورته أنه لا يُكتشف من الفحص: التوليد ينجح، والبصمة تُحسب، والورقة
تصل الموظف بمربّعات فارغة مكان الحروف.

فالاختبارات هنا تبني خطوًطا حقيقية بجداول ``cmap`` مضبوطة — أحدها
**باسم الإنتاج نفسه** ``NotoSansLao-Regular.ttf`` بلا حرف عربي — ولا
تعتمد على ما هو مثبَّت على جهاز المطوّر.
"""
from __future__ import annotations

import struct

import pytest

from app.font_coverage import (ARABIC_PROBES, find_arabic_fonts,
                               font_supports_arabic)


# ---------------------------------------------------------------------------
# بناء خط حقيقي مصغَّر: جدول cmap بالشكل 4 يغطّي نطاًقا محدًَّدا
# ---------------------------------------------------------------------------
def _make_font(start: int, end: int) -> bytes:
    """ملف sfnt صالح يغطّي [start, end] وحده.

    البناء يدوي عمًدا: خط يُحمَّل من نظام المطوّر يجعل الاختبار يقيس ذلك
    النظام لا الشيفرة، ويمرّ أو يسقط لأسباب لا علاقة لها بالعطل.
    """
    # الشكل 4: مقطعان — المطلوب، ثم الخاتم الإلزامي 0xFFFF
    ends = struct.pack(">HH", end, 0xFFFF)
    starts = struct.pack(">HH", start, 0xFFFF)
    deltas = struct.pack(">HH", 1, 1)          # gid = cp+1 ≠ 0
    ranges = struct.pack(">HH", 0, 0)
    body = ends + b"\x00\x00" + starts + deltas + ranges
    sub = struct.pack(">HHHHHHH", 4, 14 + len(body), 0, 4, 4, 1, 0) + body

    cmap = struct.pack(">HH", 0, 1) + struct.pack(">HHI", 3, 1, 12) + sub
    header = struct.pack(">IHHHH", 0x00010000, 1, 16, 0, 0)
    record = b"cmap" + struct.pack(">III", 0, 12 + 16, len(cmap))
    return header + record + cmap


ARABIC_FONT = _make_font(0x0600, 0x06FF)
LATIN_ONLY_FONT = _make_font(0x0041, 0x005A)


def test_a_font_without_arabic_is_rejected(tmp_path):
    """الادّعاء الأساسي: لا حرف عربي ⇒ لا."""
    f = tmp_path / "plain.ttf"
    f.write_bytes(LATIN_ONLY_FONT)
    assert font_supports_arabic(f) is False


def test_a_font_with_arabic_is_accepted(tmp_path):
    """والعكس — وإلّا كان الفحص يرفض كل شيء ويبدو صارًما."""
    f = tmp_path / "plain.ttf"
    f.write_bytes(ARABIC_FONT)
    assert font_supports_arabic(f) is True


def test_the_exact_production_misreport_is_now_caught(tmp_path):
    """**هذا هو العطل**: الأسماء التي أدرجها الإنتاج دليًلا على العربية.

    خمسة ملفات بأسماء Noto لا يحمل أيٌّ منها حرًفا عربًيا. الفحص القديم
    كان يعدّها خمسة خطوط عربية ويردّ ``ok``.
    """
    for name in ("NotoSansSinhala-CondensedMedium.ttf",
                 "NotoSerif-SemiCondensedThin.ttf",
                 "NotoSansMalayalam-SemiCondensed.ttf",
                 "NotoSansDisplay-SemiCondensedBlack.ttf",
                 "NotoSansLao-ExtraCondensedExtraBold.ttf"):
        (tmp_path / name).write_bytes(LATIN_ONLY_FONT)

    found = find_arabic_fonts([str(tmp_path)])
    assert found == [], (
        f"أسماء Noto بلا عربية عُدّت خطوًطا عربية: {found}"
    )


def test_an_arabic_font_is_still_found_among_them(tmp_path):
    """ولا يرفض الفحص كل شيء: خط عربي بينها يُلتقط."""
    (tmp_path / "NotoSansLao-Regular.ttf").write_bytes(LATIN_ONLY_FONT)
    (tmp_path / "NotoNaskhArabic-Regular.ttf").write_bytes(ARABIC_FONT)
    assert find_arabic_fonts([str(tmp_path)]) == ["NotoNaskhArabic-Regular.ttf"]


def test_the_name_alone_never_decides(tmp_path):
    """اسم عربي صريح على ملف بلا عربية لا يمرّ.

    الاتجاه المعاكس للعطل: لو بقي أي اعتماد على الاسم لمرّ هذا.
    """
    (tmp_path / "Amiri-Regular.ttf").write_bytes(LATIN_ONLY_FONT)
    assert find_arabic_fonts([str(tmp_path)]) == []


def test_a_partial_arabic_font_is_rejected(tmp_path):
    """تغطية حرف واحد لا تكفي — قد تأتي عرًضا في خط رموز."""
    only_alef = _make_font(ARABIC_PROBES[0], ARABIC_PROBES[0])
    (tmp_path / "partial.ttf").write_bytes(only_alef)
    assert font_supports_arabic(tmp_path / "partial.ttf") is False


def test_a_corrupt_file_reads_as_no_not_as_yes(tmp_path):
    """المجهول ليس جاهزية: ملف تالف يُقرأ «لا»."""
    (tmp_path / "broken.ttf").write_bytes(b"\x00\x01\x00\x00 truncated")
    assert font_supports_arabic(tmp_path / "broken.ttf") is False
    assert font_supports_arabic(tmp_path / "missing.ttf") is False


# ---------------------------------------------------------------------------
# أثر ذلك على فحص الجاهزية الذي يقرأه المسلِّم
# ---------------------------------------------------------------------------
def test_the_bundled_font_really_carries_arabic():
    """الخطُّ المضمَّن مع النموذج هو ما يُرسَم به — فيُقاس لا يُفترَض."""
    from app import gov_contract_form as F

    assert F.FONT.exists(), "الخطُّ العربيُّ المضمَّن مفقود"
    assert font_supports_arabic(F.FONT), "الخطُّ المضمَّن لا يحمل العربية"


def test_report_is_not_ok_without_the_font(monkeypatch, tmp_path):
    """بلا خطٍّ عربيّ تخرج الورقةُ بمربّعات — و«جاهز» هنا كذب."""
    from app import gov_contract_form as F

    monkeypatch.setattr(F, "FONT", tmp_path / "missing.ttf")
    r = F.environment_report()
    assert r["status"] == "degraded" and r["can_render_pdf"] is False


def test_report_is_not_ok_when_the_official_form_changes(monkeypatch, tmp_path):
    """وبصمُة النموذج: من بدّل ورقَة الهيئة يوقف التوليد، لا يمرّ صامًتا."""
    from app import gov_contract_form as F

    fake = tmp_path / "other.pdf"
    fake.write_bytes(b"%PDF-1.4 not the official form")
    monkeypatch.setattr(F, "ASSET", fake)
    r = F.environment_report()
    assert r["status"] == "degraded" and r["form_fingerprint_ok"] is False
    assert "بصمت" in r["note"]
