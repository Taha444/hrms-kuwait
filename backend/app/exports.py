# -*- coding: utf-8 -*-
"""تصدير البيانات إلى CSV و Excel بترميز يدعم العربية."""
import csv
import io

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill


def to_csv(headers: list[str], rows: list[list]) -> bytes:
    """CSV بترميز UTF-8 مع BOM ليُفتح بالعربية في Excel مباشرة."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for r in rows:
        writer.writerow(r)
    return ("﻿" + buf.getvalue()).encode("utf-8")


def to_xlsx(title: str, headers: list[str], rows: list[list]) -> bytes:
    """ملف Excel منسّق مع رأس ملوّن."""
    wb = Workbook()
    ws = wb.active
    ws.title = title[:31] or "Sheet"
    ws.sheet_view.rightToLeft = True  # اتجاه عربي
    header_fill = PatternFill("solid", fgColor="0E5A54")
    header_font = Font(color="FFFFFF", bold=True)
    ws.append(headers)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
    for r in rows:
        ws.append(r)
    # عرض الأعمدة تلقائيًا (تقديري)
    for i, h in enumerate(headers, start=1):
        width = max(len(str(h)), *(len(str(r[i - 1])) for r in rows)) if rows else len(str(h))
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = min(width + 4, 40)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
