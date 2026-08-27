# -*- coding: utf-8 -*-
"""حارس تخطيط RTL — منع عودة الفيض الأفقي الفارغ.

كان رابط «تخطّي إلى المحتوى الرئيسي» يُخفى بـ ``left: -9999px``. الحيلة
صحيحة في الإنجليزية: اتجاه الفيض هناك يمين، فالصندوق خارج مساحة التمرير
ولا أثر له. أما في العربية فاتجاه الفيض يسار — فصار الرابط **داخل** مساحة
التمرير، ومنح كل صفحة 9999 بكسًلا من الفراغ يُكشف بأول تمرير لليسار.

عيب لا يظهر إلا في اللغة التي يعمل بها العميل، ولهذا مرّ. ولا يوجد مشغّل
اختبارات للواجهة، فالحارس هنا: مصدر الواجهة يُفحص نًصا. الفحص على المصدر لا
على المتصفح يعني أنه يعمل في كل تشغيل بلا بيئة إضافية.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "frontend" / "src"

#: إزاحة سالبة كبيرة على محور أفقي — الحيلة التي تكسر RTL.
OFFSCREEN = re.compile(r"(left|right|inset-inline-\w+|insetInline\w*)\s*[:=]\s*[\"']?-\s*\d{3,}")


def _sources():
    if not SRC.is_dir():
        pytest.skip("مصدر الواجهة غير موجود في هذه البيئة")
    return [p for p in SRC.rglob("*")
            if p.suffix in {".ts", ".tsx", ".css", ".jsx", ".js"}]


def test_no_offscreen_negative_offset():
    """لا إخفاء بإزاحة أفقية سالبة — في RTL يصير فيًضا فارًغا لا إخفاء."""
    hits = []
    for p in _sources():
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith(("*", "//", "/*")):
                continue          # الشرح يذكر الحيلة قصًدا
            if OFFSCREEN.search(line):
                hits.append(f"{p.relative_to(SRC)}:{i}: {line.strip()[:90]}")
    assert not hits, (
        "إخفاء بإزاحة أفقية سالبة يمنح الصفحة فيًضا أفقيًّا فارًغا في العربية.\n"
        "البديل: صنف .skip-link (نمط clip) — يخفي بلا أي أثر على مساحة التمرير.\n"
        + "\n".join(hits)
    )


def test_skip_link_uses_clip_pattern():
    """الرابط يبقى موجوًدا ويظهر عند التركيز — إخفاؤه لا يعني إلغاءه."""
    css = (SRC / "styles.css").read_text(encoding="utf-8")
    assert ".skip-link {" in css, "قاعدة .skip-link مفقودة"
    assert "clip-path: inset(50%)" in css, "الإخفاء يجب أن يكون بنمط clip"
    assert ".skip-link:focus {" in css, (
        "الرابط أداة من يتنقّل بلوحة المفاتيح وحدها؛ "
        "إخفاؤه عند التركيز يجعله عديم الفائدة"
    )
