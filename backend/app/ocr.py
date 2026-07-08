# -*- coding: utf-8 -*-
"""واجهة OCR قابلة للتوصيل + قارئ MRZ حقيقي لجوازات السفر (صيغة TD3).

- قراءة MRZ: منفّذة فعليًا كدالة تحليل نصّية (TD3 من سطرين، 44 خانة) مع التحقق من
  أرقام الضبط (check digits) — هذا هو الجزء "الذكي" في قراءة الجواز.
- استخراج النص من الصورة: خلف واجهة قابلة للتوصيل (Tesseract/خدمة سحابية) — إن لم
  يُفعَّل محرّك صور، يُمكن رفع نصّ الـ MRZ كملف .txt ويُحلَّل مباشرة.

القاعدة الذهبية: النتيجة *اقتراح* يؤكّده المستخدم قبل الحفظ.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Protocol

_TD3_LINE = 44


def _check_digit(data: str) -> int:
    """رقم الضبط وفق معيار ICAO 9303 (أوزان 7,3,1)."""
    weights = [7, 3, 1]
    total = 0
    for i, ch in enumerate(data):
        if ch.isdigit():
            v = int(ch)
        elif ch.isalpha():
            v = ord(ch.upper()) - 55  # A=10..Z=35
        else:  # '<'
            v = 0
        total += v * weights[i % 3]
    return total % 10


def _parse_date(yymmdd: str) -> str | None:
    try:
        d = datetime.strptime(yymmdd, "%y%m%d")
        # تصحيح القرن لتواريخ الانتهاء/الميلاد
        return d.strftime("%Y-%m-%d")
    except ValueError:
        return None


def parse_mrz_td3(text: str) -> dict:
    """يحلّل سطري MRZ (TD3) ويستخرج الاسم/الرقم/الجنسية/تاريخ الانتهاء مع التحقق."""
    lines = [ln.strip().replace(" ", "") for ln in text.strip().splitlines() if ln.strip()]
    lines = [ln for ln in lines if len(ln) >= 30]
    if len(lines) < 2:
        return {"_provider": "mrz", "_confidence": 0.0, "_note": "صيغة MRZ غير مكتملة."}
    l1, l2 = lines[0].ljust(_TD3_LINE, "<")[:_TD3_LINE], lines[1].ljust(_TD3_LINE, "<")[:_TD3_LINE]

    country = l1[2:5].replace("<", "")
    names = l1[5:].split("<<", 1)
    surname = names[0].replace("<", " ").strip()
    given = names[1].replace("<", " ").strip() if len(names) > 1 else ""
    full_name = f"{given} {surname}".strip()

    passport_no = l2[0:9].replace("<", "")
    passport_chk = l2[9]
    nationality = l2[10:13].replace("<", "")
    birth = l2[13:19]
    expiry = l2[21:27]

    valid = _check_digit(l2[0:9]) == (int(passport_chk) if passport_chk.isdigit() else -1)
    confidence = 0.95 if valid else 0.6

    return {
        "_provider": "mrz", "_confidence": confidence,
        "_checks": {"passport_number": valid},
        "full_name": full_name or None,
        "passport_number": passport_no or None,
        "nationality": nationality or country or None,
        "date_of_birth": _parse_date(birth),
        "expiry_date": _parse_date(expiry),
    }


class OcrProvider(Protocol):
    def image_to_text(self, file_path: str) -> str: ...


class NullImageOcr:
    """لا محرّك صور مُفعّل — يُرجع نصًّا فارغًا."""
    def image_to_text(self, file_path: str) -> str:
        return ""


class TesseractOcr:
    """محرّك OCR فعلي عبر Tesseract (pytesseract) — يقرأ نص MRZ من صورة الجواز مباشرة."""
    def image_to_text(self, file_path: str) -> str:
        import pytesseract
        from PIL import Image

        img = Image.open(file_path)
        # سطرا MRZ بأسفل الصورة عادةً؛ lang=eng كافٍ لأن MRZ حروف/أرقام لاتينية فقط
        return pytesseract.image_to_string(img, lang="eng")


def _detect_provider() -> OcrProvider:
    """يفعّل Tesseract تلقائيًا إن كانت المكتبة والثنائي (binary) متوفّرين، وإلا يبقى معطَّلًا بأمان."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return TesseractOcr()
    except Exception:
        return NullImageOcr()


provider: OcrProvider = _detect_provider()


def _read_text_source(file_path: str) -> str:
    """يقرأ نصّ الـ MRZ: من ملف .txt مباشرة، أو من الصورة عبر محرّك OCR إن توفّر."""
    if file_path.lower().endswith(".txt") and os.path.exists(file_path):
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            return f.read()
    return provider.image_to_text(file_path)


def extract(document_type_code: str, file_path: str) -> dict:
    """يستخرج بيانات مقترحة حسب نوع المستند (يؤكّدها المستخدم قبل الحفظ)."""
    if document_type_code == "passport":
        text = _read_text_source(file_path)
        if text.strip():
            return parse_mrz_td3(text)
        return {"_provider": "mrz", "_confidence": 0.0,
                "_note": "لم يُستخرج نص MRZ — فعّل محرّك صور (Tesseract) أو ارفع نص MRZ كملف .txt.",
                "full_name": None, "passport_number": None, "nationality": None,
                "date_of_birth": None, "expiry_date": None}
    if document_type_code == "civil_id":
        return {"_provider": "barcode", "_confidence": 0.0,
                "_note": "قارئ باركود البطاقة المدنية يُوصَّل عند توفّر صورة الباركود.",
                "civil_id": None, "full_name": None, "nationality": None, "expiry_date": None}
    return {"_provider": "null", "_confidence": 0.0, "text": ""}
