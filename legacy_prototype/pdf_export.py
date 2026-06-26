# -*- coding: utf-8 -*-
"""
توليد مستندات PDF (مخالصة نهاية الخدمة، شهادة راتب، قسيمة راتب).
يعتمد reportlab (+ arabic-reshaper و python-bidi لتشكيل العربية إن توفّرت).
يتدهور بلطف: إن لم تتوفر المكتبات يرفع PdfUnavailable ليتعامل معها الـ API.
"""
import io

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    _HAS_REPORTLAB = True
except Exception:
    _HAS_REPORTLAB = False

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _HAS_ARABIC = True
except Exception:
    _HAS_ARABIC = False


class PdfUnavailable(RuntimeError):
    """تُرفع عند عدم توفّر reportlab."""


def _ar(text):
    """يشكّل النص العربي ويضبط اتجاهه إن توفّرت المكتبات."""
    text = str(text or "")
    if _HAS_ARABIC:
        try:
            return get_display(arabic_reshaper.reshape(text))
        except Exception:
            return text
    return text


def _doc(title, lines):
    if not _HAS_REPORTLAB:
        raise PdfUnavailable("reportlab غير مثبّت. شغّل: pip install -r requirements.txt")
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    y = height - 30 * mm

    c.setFont("Helvetica-Bold", 16)
    c.drawRightString(width - 20 * mm, y, _ar(title))
    y -= 14 * mm
    c.setFont("Helvetica", 11)
    for label, value in lines:
        if label is None:  # فاصل
            y -= 4 * mm
            continue
        c.drawRightString(width - 20 * mm, y, _ar(f"{label}: {value}"))
        y -= 8 * mm
        if y < 25 * mm:
            c.showPage()
            y = height - 25 * mm
            c.setFont("Helvetica", 11)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue()


def eos_settlement_pdf(emp_name, company_name, result):
    """ينشئ PDF لمخالصة نهاية الخدمة من نتيجة calculate_eos."""
    s = result["service"]
    lines = [
        ("الشركة", company_name),
        ("الموظف", emp_name),
        ("سبب انتهاء الخدمة", result["inputs"]["reason_label"]),
        ("تاريخ التعيين", result["inputs"]["hire_date"]),
        ("تاريخ انتهاء الخدمة", result["inputs"]["end_date"]),
        ("مدة الخدمة", s["text"]),
        (None, None),
        ("أجر اليوم", f"{result['daily_wage']} د.ك"),
        ("المكافأة قبل النسبة", f"{result['full_indemnity']} د.ك"),
        ("نسبة الاستحقاق", f"{round(result['entitlement_factor']*100)}%"),
        ("مكافأة نهاية الخدمة", f"{result['indemnity']} د.ك"),
        ("بدل رصيد الإجازات", f"{result['leave_payout']} د.ك"),
        (None, None),
        ("إجمالي المخالصة", f"{result['total_settlement']} د.ك"),
    ]
    return _doc("مخالصة نهاية الخدمة", lines)


def salary_certificate_pdf(emp, company_name):
    """شهادة راتب لموظف."""
    lines = [
        ("الشركة", company_name),
        ("الموظف", emp.get("name")),
        ("الرقم المدني", emp.get("civil_id") or "—"),
        ("الجنسية", emp.get("nationality") or "—"),
        ("المسمى الوظيفي", emp.get("job_title") or "—"),
        ("تاريخ التعيين", emp.get("hire_date") or "—"),
        (None, None),
        ("الراتب الأساسي الشهري", f"{emp.get('basic_salary') or 0} د.ك"),
    ]
    return _doc("شهادة راتب", lines)


def payslip_pdf(slip, company_name):
    """قسيمة راتب شهرية."""
    lines = [
        ("الشركة", company_name),
        ("الموظف", slip.get("employee_name")),
        ("الشهر", slip.get("period")),
        (None, None),
        ("الراتب الأساسي", f"{slip['basic_salary']} د.ك"),
        ("البدلات", f"{slip['allowances']} د.ك"),
        ("أجر الإضافي", f"{slip['overtime_pay']} د.ك"),
        ("الإجمالي", f"{slip['gross']} د.ك"),
        ("الخصومات", f"{slip['deductions']} د.ك"),
        ("التأمينات", f"{slip['gosi']} د.ك"),
        (None, None),
        ("صافي الراتب", f"{slip['net']} د.ك"),
    ]
    return _doc("قسيمة راتب", lines)
