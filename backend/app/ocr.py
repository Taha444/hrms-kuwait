# -*- coding: utf-8 -*-
"""واجهة OCR قابلة للتوصيل + قارئ MRZ حقيقي لجوازات السفر + قارئ البطاقة المدنية الكويتية.

- قراءة MRZ: منفّذة فعليًا كدالة تحليل نصّية (TD3 من سطرين، 44 خانة) مع التحقق من
  أرقام الضبط (check digits).
- قراءة البطاقة المدنية الكويتية: Tesseract (eng+ara) + regex لاستخراج:
  Civil ID (12 خانة)، Name (English+Arabic)، Passport No، Nationality،
  Sex، Birth Date، Expiry Date.
- استخراج النص من الصورة: خلف واجهة قابلة للتوصيل (Tesseract/خدمة سحابية).

القاعدة الذهبية: النتيجة *اقتراح* يؤكّده المستخدم قبل الحفظ.
"""
from __future__ import annotations

import os
import re
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
    def image_to_text(self, file_path: str, lang: str = "eng") -> str: ...


class NullImageOcr:
    """لا محرّك صور مُفعّل — يُرجع نصًّا فارغًا."""
    def image_to_text(self, file_path: str, lang: str = "eng") -> str:
        return ""


class TesseractOcr:
    """محرّك OCR فعلي عبر Tesseract (pytesseract). يدعم قراءة نص MRZ من الجواز،
    والبطاقة المدنية الكويتية باللغتين (eng+ara).

    Preprocessing المطبَّق:
    - EXIF exif_transpose: تصحيح دوران صور الموبايل
    - Upscale: تكبير الصور الصغيرة لعرض 2000px (Tesseract يعمل أفضل على 300+ DPI)
    - Grayscale + autocontrast: زيادة التباين
    - Sharpen: حواف أوضح للأحرف
    - Config PSM 6: يفترض كتلة نص موحّدة (مناسب للبطاقات)
    """
    def image_to_text(self, file_path: str, lang: str = "eng") -> str:
        import pytesseract
        from PIL import Image, ImageOps, ImageFilter

        img = Image.open(file_path)
        img = ImageOps.exif_transpose(img)
        # تكبير الصور الصغيرة (Tesseract يعمل أفضل على دقة أعلى)
        w, h = img.size
        if w < 2000:
            scale = 2000 / w
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        img = img.convert("L")
        img = ImageOps.autocontrast(img, cutoff=2)
        img = img.filter(ImageFilter.SHARPEN)
        # PSM 6 = Assume a single uniform block of text
        return pytesseract.image_to_string(img, lang=lang, config="--psm 6")


# ============================================================================
# اكتشاف المحرّك — كل استدعاء يعيد الفحص (بلا cache) عشان لو الـbinary
# اتثبت بعد إقلاع التطبيق يتم استخدامه فورًا. يُرجع أيضًا تفاصيل التشخيص.
# ============================================================================
def _tesseract_status() -> dict:
    """يفحص حالة Tesseract الحقيقية على النظام ويُرجع تفاصيل التشخيص."""
    status: dict = {"available": False, "version": None, "languages": [], "error": None}
    try:
        import pytesseract
        status["version"] = str(pytesseract.get_tesseract_version())
        status["available"] = True
        try:
            status["languages"] = list(pytesseract.get_languages(config=""))
        except Exception as le:
            status["languages_error"] = str(le)
    except Exception as e:
        status["error"] = f"{type(e).__name__}: {e}"
    return status


def _get_provider() -> OcrProvider:
    """يُرجع Tesseract إن كان مثبَّتًا، وإلا Null."""
    if _tesseract_status()["available"]:
        return TesseractOcr()
    return NullImageOcr()


# متغيّر للتوافق مع الاستدعاءات القديمة (يُقيَّم لحظيًا)
provider: OcrProvider = _get_provider()


def _read_text_source(file_path: str, lang: str = "eng") -> str:
    """يقرأ نصًّا: من ملف .txt مباشرة، أو من الصورة عبر محرّك OCR إن توفّر."""
    if file_path.lower().endswith(".txt") and os.path.exists(file_path):
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            return f.read()
    return _get_provider().image_to_text(file_path, lang=lang)


# ============================================================================
# قارئ البطاقة المدنية الكويتية (Tesseract eng+ara)
# ============================================================================
_DATE_RE = re.compile(r"(\d{2})[/\-\.](\d{2})[/\-\.](\d{4})")
_CIVIL_RE = re.compile(r"\b(\d{12})\b")
_PASSPORT_RE = re.compile(r"\b([A-Z]\d{7,9})\b")
_NATIONALITY_RE = re.compile(r"Nationality[\s:]*([A-Z]{3})\b", re.IGNORECASE)
_SEX_RE = re.compile(r"\bSex[\s:]*([MFmf])\b")


def _norm_date(m: re.Match) -> str | None:
    dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
    try:
        return datetime.strptime(f"{yyyy}-{mm}-{dd}", "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


def parse_kuwait_civil_id(text_en: str, text_ar: str = "") -> dict:
    """يستخرج حقول بطاقة الهوية الكويتية من نصوص Tesseract:
    civil_id (12 خانة)، full_name (English)، full_name_ar، passport_number،
    nationality (3-letter)، gender، date_of_birth، expiry_date.
    """
    result: dict = {
        "_provider": "tesseract_civil_id",
        "civil_id": None, "full_name": None, "full_name_ar": None,
        "passport_number": None, "nationality": None, "gender": None,
        "date_of_birth": None, "expiry_date": None,
    }
    if not text_en.strip() and not text_ar.strip():
        result["_confidence"] = 0.0
        result["_note"] = "لم يستخرج Tesseract أي نص — تأكد من وضوح الصورة."
        return result

    if (m := _CIVIL_RE.search(text_en)):
        result["civil_id"] = m.group(1)
    if (m := _PASSPORT_RE.search(text_en)):
        result["passport_number"] = m.group(1)
    if (m := _NATIONALITY_RE.search(text_en)):
        result["nationality"] = m.group(1).upper()
    if (m := _SEX_RE.search(text_en)):
        result["gender"] = "male" if m.group(1).upper() == "M" else "female"

    # التواريخ: الأحدث = انتهاء، الأقدم = ميلاد
    dates = [d for d in (_norm_date(x) for x in _DATE_RE.finditer(text_en)) if d]
    if len(dates) >= 2:
        srt = sorted(dates)
        result["date_of_birth"] = srt[0]
        result["expiry_date"] = srt[-1]
    elif len(dates) == 1:
        result["expiry_date"] = dates[0]

    # الاسم الإنجليزي — بعد كلمة "Name"
    nm = re.search(
        r"Name[\s:]+([A-Z][A-Z\s]{2,60}?)(?:\s*(?:Passport|Nationality|Sex|Birth|Expiry|\n|$))",
        text_en, re.IGNORECASE | re.DOTALL)
    if nm:
        result["full_name"] = re.sub(r"\s+", " ", nm.group(1)).strip()

    # الاسم العربي — نتفحّص كل سطر منفصلاً بعد استبعاد العناوين الثابتة
    if text_ar:
        _LABELS = ("البطاقة المدنية", "دولة الكويت", "الرقم المدني", "الاسم",
                   "الجنسية", "الجنس", "تاريخ الميلاد", "تاريخ الانتهاء",
                   "رقم الجواز", "ذكر", "أنثى", "مصرى", "كويتى")
        # split على newlines أولاً — لا نسمح للـregex بعبور السطور
        candidates = []
        for raw_line in text_ar.splitlines():
            # نستخرج تسلسلات عربية + مسافات فقط ضمن السطر الواحد
            for m in re.finditer(r"[ء-ي][ء-ي ]{5,60}", raw_line):
                clean = re.sub(r"\s+", " ", m.group(0)).strip()
                if any(lbl in clean for lbl in _LABELS):
                    continue
                # نطلب على الأقل كلمتين (اسم + عائلة أدنى)
                if len(clean) >= 6 and " " in clean:
                    candidates.append(clean)
        if candidates:
            result["full_name_ar"] = max(candidates, key=len)

    # ثقة تعتمد على عدد الحقول المستخرجة
    extracted = sum(1 for k, v in result.items() if v and not k.startswith("_"))
    result["_confidence"] = round(min(0.5 + extracted * 0.08, 0.95), 2)
    if extracted == 0:
        result["_note"] = ("لم يُستخرج أي حقل — الصورة قد تكون ضبابية أو بحاجة "
                          "لتشذيب. جرّب صورة أوضح أو أدخل البيانات يدويًا.")
    return result


def extract(document_type_code: str, file_path: str) -> dict:
    """يستخرج بيانات مقترحة حسب نوع المستند (يؤكّدها المستخدم قبل الحفظ).

    عند فشل القراءة يُرجع diagnostics صريحة (Tesseract غير مثبت / حزمة عربية ناقصة
    / نص فارغ) بدل رسائل غامضة، عشان المشرف يعرف السبب الفعلي.
    """
    tess = _tesseract_status()

    if document_type_code == "passport":
        if not tess["available"]:
            return {"_provider": "mrz", "_confidence": 0.0,
                    "_note": f"محرّك OCR غير متاح على الخادم ({tess['error']}). "
                             "ارفع نص MRZ كملف .txt أو ثبّت tesseract-ocr.",
                    "_diag": tess,
                    "full_name": None, "passport_number": None, "nationality": None,
                    "date_of_birth": None, "expiry_date": None}
        text = _read_text_source(file_path, lang="eng")
        if text.strip():
            r = parse_mrz_td3(text)
            r["_diag"] = {"text_length": len(text), **tess}
            return r
        return {"_provider": "mrz", "_confidence": 0.0,
                "_note": "Tesseract مثبَّت لكن لم يُستخرج نص MRZ — جودة صورة الجواز منخفضة. "
                         "جرّب صورة أوضح أو ارفع نص MRZ كملف .txt.",
                "_diag": tess,
                "full_name": None, "passport_number": None, "nationality": None,
                "date_of_birth": None, "expiry_date": None}

    # QA-05 — الإقامة وإذن العمل يُقرآن بقارئ البطاقة نفسه.
    # ROOT CAUSE: extract كانت تعالج passport و civil_id فقط، وكل ما عداهما
    # يسقط إلى {"_provider": "null", "_confidence": 0.0} — بلا سبب ظاهر.
    # فرفع صورة إقامة كان يعطي "ثقة 0.0" دائًما مهما كانت الصورة واضحة، ولا
    # يُستخرج تاريخ انتهاء، فيبقى سجل الإقامة بلا تاريخ ولا يظهر في التجديدات.
    # الإقامة الكويتية بطاقة عربية/إنجليزية بتواريخ — نفس ما يقرأه هذا المحلّل.
    if document_type_code in ("civil_id", "residency", "work_permit"):
        if not tess["available"]:
            return {
                "_provider": "tesseract_civil_id", "_confidence": 0.0,
                "_note": f"محرّك OCR غير مثبَّت على الخادم ({tess['error']}). "
                         "المطلوب: apt-get install tesseract-ocr tesseract-ocr-ara.",
                "_diag": tess,
                "civil_id": None, "full_name": None, "full_name_ar": None,
                "passport_number": None, "nationality": None, "gender": None,
                "date_of_birth": None, "expiry_date": None,
            }

        langs = tess.get("languages", [])
        has_ara = "ara" in langs
        has_eng = "eng" in langs or not langs  # لو ما قدرناش نقرأ القائمة نجرّب

        text_en = ""
        text_ar = ""
        en_err = ar_err = None
        if has_eng:
            try:
                text_en = _read_text_source(file_path, lang="eng")
            except Exception as e:
                en_err = f"{type(e).__name__}: {e}"
        if has_ara:
            try:
                text_ar = _read_text_source(file_path, lang="ara")
            except Exception as e:
                ar_err = f"{type(e).__name__}: {e}"

        r = parse_kuwait_civil_id(text_en, text_ar)
        r["_diag"] = {
            **tess,
            "text_length_en": len(text_en),
            "text_length_ar": len(text_ar),
            "en_error": en_err,
            "ar_error": ar_err,
            "arabic_pack_installed": has_ara,
        }
        # لو الحزمة العربية مفقودة — نضيف تحذير واضح
        if not has_ara and r.get("_confidence", 0) < 0.9:
            note = r.get("_note", "")
            r["_note"] = (note + " | " if note else "") + \
                         "حزمة اللغة العربية (tesseract-ocr-ara) غير مثبَّتة — الاسم العربي لن يُقرأ."
        # لو Tesseract مثبَّت لكن ما قدرش يقرأ أي نص — رسالة أوضح
        if not text_en.strip() and not text_ar.strip():
            r["_note"] = (f"Tesseract v{tess['version']} مثبَّت لكن لم يقرأ أي نص من الصورة. "
                         "الأسباب المحتملة: (1) الصورة ضبابية أو منخفضة الدقة، "
                         "(2) الإضاءة سيئة، (3) البطاقة مائلة جدًا. "
                         "جرّب تصويرها من مسافة أقرب مع إضاءة أفضل، "
                         "أو أدخل البيانات يدويًا.")
        return r

    # نوع لا قارئ له بعد — نقول ذلك صراحًة بدل صفر صامت يُقرأ كفشل قراءة
    return {"_provider": "null", "_confidence": 0.0, "text": "",
            "_note": f"لا يوجد قارئ آلي لنوع المستند «{document_type_code}» — "
                     "أدخل البيانات يدوًيا.",
            "_diag": {"unsupported_type": document_type_code, **tess}}
