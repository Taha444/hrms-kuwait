# -*- coding: utf-8 -*-
"""محرّك PDF عربي حقيقي (FIX-007).

يبديل الاعتماد على «طباعة المتصفح» لملف HTML بملف PDF ثنائي (application/pdf)
حقيقي يُنتج على الخادم، مع إعادة تشكيل الحروف العربية (ligatures) وترتيبها
اتجاه RTL عبر arabic_reshaper + python-bidi، وخط Amiri (رخصة OFL حرة) المرفق
داخل المشروع بدل الاعتماد على خطوط النظام (لضمان عمله على أي بيئة نشر).
"""
from __future__ import annotations

import io
import os
import re

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

_FONT_NAME = "Amiri"
_FONT_PATH = os.path.join(os.path.dirname(__file__), "assets", "fonts", "Amiri-Regular.ttf")
_registered = False

_AR_RE = re.compile(r"[؀-ۿ]")


def _ensure_font() -> str:
    """يسجّل خط Amiri مرّة واحدة؛ يعود لخط Helvetica الافتراضي إن تعذّر (بيئة بلا الملف)."""
    global _registered
    if _registered:
        return _FONT_NAME
    try:
        pdfmetrics.registerFont(TTFont(_FONT_NAME, _FONT_PATH))
        _registered = True
        return _FONT_NAME
    except Exception:
        return "Helvetica"


def _shape(text: str) -> str:
    """يهيّئ نصًا مختلطًا (عربي/لاتيني/أرقام) للعرض الصحيح RTL في PDF."""
    text = text or ""
    if not _AR_RE.search(text):
        return text
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)


class ArabicPDF:
    """أداة بناء مستند PDF بسيط: عنوان، سطور معلومات، فقرات، قائمة اعتماد، توقيعات."""

    def __init__(self, title: str, subtitle: str = ""):
        self.font = _ensure_font()
        self.buf = io.BytesIO()
        self.c = canvas.Canvas(self.buf, pagesize=A4)
        self.width, self.height = A4
        self.right = self.width - 2 * cm
        self.left = 2 * cm
        self.y = self.height - 2.2 * cm
        self._header(title, subtitle)

    def _line_break(self, gap: float = 0.9 * cm) -> None:
        self.y -= gap
        if self.y < 3 * cm:
            self.c.showPage()
            self.c.setFont(self.font, 11)
            self.y = self.height - 2.2 * cm

    def _text(self, text: str, size: int = 12, bold_gap: float = 0.8 * cm, center: bool = False) -> None:
        self.c.setFont(self.font, size)
        shaped = _shape(text)
        if center:
            self.c.drawCentredString(self.width / 2, self.y, shaped)
        else:
            self.c.drawRightString(self.right, self.y, shaped)
        self._line_break(bold_gap)

    def _header(self, title: str, subtitle: str) -> None:
        self._text(title, size=16, center=True)
        if subtitle:
            self._text(subtitle, size=11, center=True, bold_gap=0.7 * cm)
        self.c.setStrokeColorRGB(0.2, 0.2, 0.2)
        self.c.line(self.left, self.y + 0.3 * cm, self.right, self.y + 0.3 * cm)
        self._line_break(0.6 * cm)

    def kv(self, label: str, value: str) -> None:
        self._text(f":{value}  {label}", size=11)

    def section(self, title: str) -> None:
        self._line_break(0.2 * cm)
        self._text(title, size=13, bold_gap=0.7 * cm)

    def paragraph(self, text: str) -> None:
        self._text(text, size=11)

    def bullet(self, text: str) -> None:
        self._text(f"• {text}", size=10.5, bold_gap=0.7 * cm)

    def signatures(self, labels: list[str]) -> None:
        self._line_break(1.2 * cm)
        self.c.setFont(self.font, 10.5)
        n = len(labels) or 1
        col_w = (self.right - self.left) / n
        for i, label in enumerate(labels):
            cx = self.right - i * col_w - col_w / 2
            self.c.drawCentredString(cx, self.y, _shape(label))
            self.c.line(cx - col_w / 2 + 0.3 * cm, self.y - 0.6 * cm, cx + col_w / 2 - 0.3 * cm, self.y - 0.6 * cm)
        self.y -= 1.4 * cm

    def bytes(self) -> bytes:
        self.c.showPage()
        self.c.save()
        return self.buf.getvalue()


def render_request_pdf(rt, req, emp, company, approvals, body_lines: list[str]) -> bytes:
    """يبني PDF فعليًا لمستند طلب معتمَد (بديل render_document_html)."""
    doc = ArabicPDF(
        title=(company.name if company else ""),
        subtitle=rt.name,
    )
    doc.kv("رقم الطلب", str(req.id))
    doc.kv("الموظف", emp.name if emp else "")
    doc.kv("الرقم المدني", getattr(emp, "civil_id", "") or "")
    doc.kv("الوظيفة", getattr(emp, "job_title", "") or "")
    if body_lines:
        doc.section("تفاصيل الطلب")
        for line in body_lines:
            doc.paragraph(line)
    doc.section("سلسلة الاعتماد")
    if approvals:
        for a in approvals:
            doc.bullet(
                f"{a.stage_label or ''} ({a.approver_role or ''}) — "
                f"{a.decided_at.strftime('%Y-%m-%d %H:%M')}"
            )
    else:
        doc.bullet("—")
    doc.signatures(["توقيع الموظف", "توقيع/ختم الشركة"])
    return doc.bytes()
