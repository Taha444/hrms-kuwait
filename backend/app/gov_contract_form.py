# -*- coding: utf-8 -*-
"""العقد الحكومي — نموذج الهيئة الرسمي يُملأ كما هو (قرار المالك 2026-09-17).

**الأصل لا يُمسّ**: ``assets/GOV-CONTRACT-PAM.pdf`` هو الملف الذي سلّمه
المالك (نموذج عقد عمل استرشادي في القطاع الأهلي — صفحتان). لا يُعاد بناء
تخطيطه ولا تُصاغ بنوده ولا تُصحَّح كلمة فيه: **الصفحةُ نفسها تُطبع**،
ويُرسَم فوقها ما يُملأ في الخانات وحده. فما يخرج من النظام هو ورقة الهيئة
حرفًا بحرف، لا محاكاةً لها.

**ولماذا لا docx ولا HTML**: القالبُ السابق كان يُحوَّل بـLibreOffice، فإن
غاب عن الخادم سُلّم ``docx`` بدل PDF؛ ومسارُ التعيين كان يبني HTML يقلّد
النموذج. وكلاهما يخرج ورقًة ليست ورقة الهيئة. والرسمُ فوق الأصل لا يحتاج
إلا ``reportlab`` و``pypdf`` — وكلاهما مثبَّت.

**قرارات المالك المطبَّقة هنا** (2026-09-17):

- الأجر في البند الرابع: **الراتب الأساسي** (من آخر مسيّر معتمد — ``_approved_wage``).
- البند السادس: تُملأ الفقرةُ المطابقة لنوع العقد و**تُشطب** الأخرى، كما
  يُفعل بالورقة.
- وما عدا ذلك يُطبع كما في الملف الرسمي — ومنه «30 يومًا» في البند السابع.

**وحقلٌ ناقص** (تعديل 2026-09-22): لم يعد يوقف التوليد — الخانة تُطبع
فارغة والعقد يصدر، والموظف يملؤها يدويًا. استكمال البيانات في النظام
مهمة لاحقة (ترقية)، لا شرط لإصدار الورقة.
"""
from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path

ASSET = Path(__file__).parent / "assets" / "GOV-CONTRACT-PAM.pdf"
FONT = Path(__file__).parent / "assets" / "fonts" / "Amiri-Regular.ttf"

#: بصمةُ الملف الذي سلّمه المالك. تغيُّرها يعني أن أحًدا بدّل النموذج.
ASSET_SHA256 = "879aa5874078426e4fb60b8cb227450edc6f9e6a267a839bb4d2864e779fa8b2"

PAGE_H = 841.92

#: الخاناتُ بإحداثياتها في الأصل (أعلى-اليسار، كما يقرؤها مستخرِج النصّ)،
#: وكلُّ حقلٍ خانتان: الإنجليزيةُ يسارًا والعربيةُ يمينًا.
#: ``(page, x0, y0, x1, y1)``
BOXES: dict[str, tuple[int, float, float, float, float]] = {
    "labour_dept_en":       (0, 123.5, 105.2, 227.1, 115.1),
    "labour_dept":          (0, 390.4, 105.1, 512.0, 115.7),
    "day_name_en":          (0, 61.4, 120.2, 115.3, 130.1),
    "contract_date_en":     (0, 185.0, 120.2, 238.9, 130.1),
    "day_name":             (0, 451.0, 120.2, 514.4, 130.8),
    "contract_date":        (0, 355.1, 120.2, 418.5, 130.8),
    "company_name_en":      (0, 87.9, 166.5, 191.3, 176.4),
    "company_name":         (0, 401.5, 166.5, 522.9, 177.1),
    "company_rep_name_en":  (0, 74.3, 195.5, 177.8, 205.5),
    "company_rep_name":     (0, 405.7, 195.6, 527.2, 206.1),
    "company_civil_id_en":  (0, 98.1, 209.9, 201.5, 219.9),
    "company_civil_id":     (0, 385.4, 209.8, 506.9, 220.4),
    "employee_name_en":     (0, 74.3, 241.9, 177.8, 251.8),
    "employee_name":        (0, 405.7, 241.9, 527.2, 252.5),
    "nationality_en":       (0, 93.3, 256.4, 196.8, 266.4),
    "nationality":          (0, 398.8, 256.4, 520.4, 267.0),
    "passport_number_en":   (0, 98.8, 270.9, 202.2, 280.9),
    "passport_number":      (0, 388.4, 271.0, 509.9, 281.5),
    "civil_id_en":          (0, 98.1, 285.3, 201.5, 295.3),
    "civil_id":             (0, 385.4, 285.2, 506.9, 295.8),
    "facility_name_en":     (0, 178.3, 315.3, 250.2, 325.3),
    "facility_name":        (0, 344.4, 316.0, 444.8, 326.5),
    "job_title_en":         (0, 45.8, 335.6, 108.8, 345.6),
    "job_title":            (0, 348.6, 326.6, 422.5, 337.2),
    "job_title2_en":        (0, 45.8, 425.3, 108.8, 435.2),
    "job_title2":           (0, 304.0, 415.6, 378.0, 426.1),
    "wage_en":              (0, 76.1, 516.3, 112.1, 526.3),
    "wage":                 (0, 348.2, 506.8, 390.4, 517.3),
    "start_date_en":        (0, 190.3, 566.2, 246.6, 576.1),
    "start_date":           (0, 410.6, 566.7, 474.1, 577.3),
    # البند السادس — خانتان لكل صيغة، تُملأ واحدةٌ وتُشطب الأخرى.
    "definite_start_en":    (0, 45.8, 617.6, 99.8, 627.6),
    "definite_start":       (0, 396.7, 608.1, 460.2, 618.7),
    "indefinite_start_en":  (0, 77.8, 650.6, 134.0, 660.6),
    "indefinite_start":     (0, 356.7, 632.0, 422.7, 642.5),
}

#: أسطرُ كل فقرةٍ في البند السادس — يُشطب ما لا يطابق نوع العقد.
STRIKE_LINES: dict[str, list[tuple[int, float, float, float, float]]] = {
    "definite": [
        (0, 45.8, 607.6, 294.3, 617.5),
        (0, 45.8, 617.6, 294.3, 627.6),
        (0, 45.8, 627.8, 283.3, 637.8),
        (0, 301.4, 608.1, 550.3, 618.7),
        (0, 361.9, 618.8, 550.4, 629.3),
    ],
    "indefinite": [
        (0, 45.8, 640.4, 294.4, 650.4),
        (0, 45.8, 650.6, 136.3, 660.6),
        (0, 352.5, 632.0, 550.5, 642.5),
    ],
}

#: الحقولُ التي لا يصدر العقد بدونها — بأسمائها العربية كما يقرؤها من يُصلحها.
REQUIRED: dict[str, str] = {
    "employee_name": "اسم الموظف",
    "civil_id": "الرقم المدني للموظف",
    "nationality": "الجنسية",
    "passport_number": "رقم الجواز",
    "job_title": "المسمّى الوظيفي",
    "company_name": "اسم الشركة",
    "company_rep_name": "اسم ممثّل الشركة في التوقيع",
    "company_civil_id": "الرقم المدني لممثّل الشركة",
    "labour_dept": "إدارة العمل (محافظة مقرّ العمل)",
    "wage": "الأجر (من المسيّر المعتمد أو ملف الموظف)",
    "start_date": "تاريخ بدء نفاذ العقد",
    "contract_date": "تاريخ تحرير العقد",
}

_ARABIC = re.compile("[؀-ۿ]")


def asset_sha256() -> str:
    return hashlib.sha256(ASSET.read_bytes()).hexdigest()


def _shape(text: str) -> str:
    """يشكّل العربية للرسم: وصلُ الحروف ثم ترتيبُ العرض (RTL)."""
    import arabic_reshaper
    from bidi.algorithm import get_display
    return get_display(arabic_reshaper.reshape(text))


def values_from(ctx: dict) -> dict:
    """يقرأ قيمَ الخانات من سياق التوليد — لا شيء منها من حمولة الطلب."""
    def g(*keys: str) -> str:
        for k in keys:
            v = ctx.get(k)
            if v not in (None, ""):
                return str(v).strip()
        return ""

    company = g("company_name")
    company_en = g("company_name_en")
    job = g("job_title")
    job_en = g("job_title_display_en", "job_title_en") or job
    out = {
        "labour_dept": g("labour_dept"),
        "labour_dept_en": g("labour_dept_en") or g("labour_dept"),
        "day_name": g("day_name"),
        "day_name_en": g("day_name_en"),
        "contract_date": g("contract_date", "date_today"),
        "contract_date_en": g("contract_date", "date_today"),
        "company_name": company,
        "company_name_en": company_en or company,
        "company_rep_name": g("company_rep_name"),
        "company_rep_name_en": g("company_rep_name_en") or g("company_rep_name"),
        "company_civil_id": g("company_civil_id"),
        "company_civil_id_en": g("company_civil_id"),
        "employee_name": g("employee_name"),
        "employee_name_en": g("employee_name_display_en", "employee_name_en") or g("employee_name"),
        "nationality": g("nationality"),
        "nationality_en": g("nationality_en") or g("nationality"),
        "passport_number": g("passport_number"),
        "passport_number_en": g("passport_number"),
        "civil_id": g("civil_id"),
        "civil_id_en": g("civil_id"),
        # «منشأة باسم» هي الشركة نفسها في هذا النموذج.
        "facility_name": company,
        "facility_name_en": company_en or company,
        "job_title": job,
        "job_title_en": job_en,
        "job_title2": job,
        "job_title2_en": job_en,
        "wage": g("wage", "basic_salary"),
        "wage_en": g("wage", "basic_salary"),
        "start_date": g("contract_start_date", "hire_date"),
        "start_date_en": g("contract_start_date", "hire_date"),
    }
    # البند السادس: المطابقُ يُملأ، والآخر يبقى فارًغا ويُشطب.
    definite = (g("contract_type_raw", "contract_type") or "").strip().lower() == "definite"
    if definite:
        out["definite_start"] = out["start_date"]
        out["definite_start_en"] = out["start_date"]
    else:
        out["indefinite_start"] = out["start_date"]
        out["indefinite_start_en"] = out["start_date"]
    out["_definite"] = definite
    return out


def missing_fields(values: dict) -> list[str]:
    return [label for key, label in REQUIRED.items() if not str(values.get(key) or "").strip()]


def fill(values: dict) -> bytes:
    """يرسم القيم فوق النموذج الأصلي ويعيد PDF."""
    from pypdf import PdfReader, PdfWriter
    from reportlab.lib.colors import black
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    font_name = "Amiri"
    try:
        pdfmetrics.getFont(font_name)
    except KeyError:
        pdfmetrics.registerFont(TTFont(font_name, str(FONT)))

    reader = PdfReader(str(ASSET))
    overlays: dict[int, io.BytesIO] = {}
    per_page: dict[int, list] = {}
    for key, (page, x0, y0, x1, y1) in BOXES.items():
        text = str(values.get(key) or "").strip()
        if text:
            per_page.setdefault(page, []).append((key, text, x0, y0, x1, y1))
    strike = "indefinite" if values.get("_definite") else "definite"
    for page, x0, y0, x1, y1 in STRIKE_LINES[strike]:
        per_page.setdefault(page, []).append((None, None, x0, y0, x1, y1))

    for page, items in per_page.items():
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(595.32, PAGE_H))
        c.setFillColor(black)
        c.setStrokeColor(black)
        for key, text, x0, y0, x1, y1 in items:
            is_arabic_column = not str(key or "").endswith("_en")
            if text is None:                       # خطُّ الشطب
                mid = PAGE_H - (y0 + y1) / 2
                c.setLineWidth(0.8)
                c.line(x0, mid, x1, mid)
                continue
            size = 9.0
            shaped = _shape(text) if _ARABIC.search(text) else text
            width = x1 - x0
            while size > 5.5 and pdfmetrics.stringWidth(shaped, font_name, size) > width - 2:
                size -= 0.5
            c.setFont(font_name, size)
            baseline = PAGE_H - y1 + 2.0
            # العمودُ العربيُّ يُحاذى يمينًا ولو كانت القيمةُ أرقامًا لاتينية،
            # والعمودُ الإنجليزيُّ يسارًا — كما تُملأ الورقة بخط اليد.
            if is_arabic_column:
                c.drawRightString(x1 - 1, baseline, shaped)
            else:
                c.drawString(x0 + 1, baseline, shaped)
        c.save()
        buf.seek(0)
        overlays[page] = buf

    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        if i in overlays:
            page.merge_page(PdfReader(overlays[i]).pages[0])
        writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def generate(ctx: dict) -> tuple[bytes, str, str, list[str], dict]:
    """يعيد ``(bytes, ext, mime, missing, snapshot)``.

    **تعديل 2026-09-22 (بطلب صريح، يعدّل قرار 2026-09-17 أعلاه):** الحقل
    الناقص لم يعد يوقف التوليد — ``fill()`` أصًلا يرسم الخانة فارغة إن
    غاب مفتاحها (انظر ``if text:`` في الحلقة أعلاه)، فالتوليد يمضي دائًما
    ويعود العقد كما هو، والناقص يُعاد في ``missing`` كتنبيه معلوماتي فقط
    يعرضه المستدعي دون أن يمنع به الطباعة. استكمال البيانات صار مهمة
    لاحقة (ترقية) لا شرط توليد.
    """
    values = values_from(ctx)
    missing = missing_fields(values)
    content = fill(values)
    snapshot = {k: v for k, v in values.items() if not k.startswith("_")}
    snapshot["contract_term"] = "definite" if values["_definite"] else "indefinite"
    snapshot["form_sha256"] = ASSET_SHA256
    snapshot["wage_source"] = ctx.get("wage_source") or ""
    snapshot["missing_fields"] = missing
    return (content, "pdf", "application/pdf", missing, snapshot)


def environment_report() -> dict:
    """ما يحتاجه التوليد — ويُقرأ في ``/api/health/deep``."""
    ok_asset = ASSET.exists() and asset_sha256() == ASSET_SHA256
    ok_font = FONT.exists()
    # **كلُّ ما تستورده ``fill()`` يُفحَص هنا** — ومنه ``pypdf``. كان الفحص يقرأ ثلاث مكتباتٍ
    # ويترك الرابعة، فقالت لوحة الصحة «جاهز» (``can_render_pdf: true``) على الإنتاج بينما
    # ``ModuleNotFoundError: No module named 'pypdf'`` يُسقط كلَّ عقدٍ بـ500 (2026-09-24).
    # وفحصُ جاهزيةٍ ينقصه ما يحتاجه المولِّد أسوأ من غيابه: يطمئن حيث يجب أن يُنذر.
    import importlib

    missing_libs = []
    for mod in ("arabic_reshaper", "reportlab", "bidi.algorithm", "pypdf"):
        try:
            importlib.import_module(mod)
        except Exception:  # noqa: BLE001 — الغيابُ بأيّ سبب غيابٌ
            missing_libs.append(mod)
    libs = not missing_libs
    return {
        "form_present": ASSET.exists(),
        "form_fingerprint_ok": ok_asset,
        "arabic_font": FONT.name if ok_font else None,
        "libs": libs,
        "missing_libs": missing_libs,
        "can_render_pdf": bool(ok_asset and ok_font and libs),
        "status": "ok" if (ok_asset and ok_font and libs) else "degraded",
        "note": ("" if ok_asset and libs else
                 (f"مكتبة ناقصة على الخادم: {', '.join(missing_libs)} — لا يُولَّد عقد "
                  "حتى تُثبَّت (requirements.txt)" if not libs else
                  "نموذج الهيئة مفقود أو تغيّرت بصمته — لا يُولَّد عقد حتى يُراجَع")),
    }
