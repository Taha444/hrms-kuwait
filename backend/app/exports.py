# -*- coding: utf-8 -*-
"""تصدير البيانات إلى CSV و Excel بترميز يدعم العربية."""
import csv
import io

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill


import re

_NUMERIC = re.compile(r"^[+-]?[\d\s.,]*$")


def neutralize(value):
    """نصٌّ يبدأ بما يقرؤه الجدولُ صيغةً يُسبق بفاصلةٍ عليا — والأرقامُ لا تُمسّ.

    **حقنُ الصيغ** (OWASP CSV Injection): الأسماءُ والمسمّياتُ وأسبابُ الطلبات
    يكتبها مستخدمون، والتصديرُ يُفتح في Excel عند من يملك صلاحيةً أعلى.
    و``openpyxl`` يكتب كلَّ نصٍّ يبدأ بـ``=`` **صيغةً** تُنفَّذ عند الفتح —
    ``=HYPERLINK(...)`` يسرّب، و``=cmd|...`` في CSV يُشغّل. فلا تحييدَ كان.

    ويُترك ``+965…`` و``-5`` على حالهما: رقمٌ لا صيغة، وسبقُه يُفسد هاتفًا.
    """
    if not isinstance(value, str) or not value:
        return value
    first = value[0]
    if first in ("=", "@", "\t", "\r") or (
            first in ("+", "-") and not _NUMERIC.match(value)):
        return "'" + value
    return value


_LONG_DIGITS = re.compile(r"[0-9]{11,}")


def _csv_cell(value):
    """أرقامٌ طويلة (رقم مدني/هاتف/حساب) يعرضها Excel بصيغة علمية ``2.9E+11`` ويضيع منها ما بعد الخانة 15.

    تُكتب ``="…"`` — يقرؤها Excel نصًّا كما هي. ولا خطر حقن: القيمة أرقامٌ صرفة تُتحقَّق بالتعبير قبل الإحاطة.
    """
    if isinstance(value, str) and _LONG_DIGITS.fullmatch(value):
        return f'="{value}"'
    if isinstance(value, int) and not isinstance(value, bool) and abs(value) >= 10 ** 11:
        return f'="{value}"'
    return neutralize(value)


def to_csv(headers: list[str], rows: list[list]) -> bytes:
    """CSV بترميز UTF-8 مع BOM ليُفتح بالعربية في Excel مباشرة."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([neutralize(h) for h in headers])
    for r in rows:
        writer.writerow([_csv_cell(v) for v in r])
    return ("﻿" + buf.getvalue()).encode("utf-8")


def to_xlsx(title: str, headers: list[str], rows: list[list], text_columns: set[int] | None = None) -> bytes:
    """ملف Excel منسّق مع رأس ملوّن.

    text_columns: فهارس أعمدة (0-based) تُفرض كنص صراحة (تنسيق '@') — تمنع تحويل
    Excel أرقام هوية طويلة (الرقم المدني) تلقائيًا لصيغة علمية مثل 1E+11 (QA-P1-RPT-01).
    """
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
        ws.append([neutralize(v) for v in r])
    # و``openpyxl`` يستنتج الصيغةَ من ``=`` عند الإسناد — فيُثبَّت النصُّ نصًّا.
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            if isinstance(cell.value, str):
                cell.data_type = "s"
    if text_columns:
        for col_idx in text_columns:
            col_letter = ws.cell(row=1, column=col_idx + 1).column_letter
            for row_idx in range(2, ws.max_row + 1):
                cell = ws[f"{col_letter}{row_idx}"]
                cell.number_format = "@"
                if cell.value is not None:
                    cell.value = str(cell.value)
    # عرض الأعمدة تلقائيًا (تقديري)
    for i, h in enumerate(headers, start=1):
        width = max(len(str(h)), *(len(str(r[i - 1])) for r in rows)) if rows else len(str(h))
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = min(width + 4, 40)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
