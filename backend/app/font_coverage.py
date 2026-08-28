# -*- coding: utf-8 -*-
"""هل يرسم هذا الخط حروًفا عربية؟ — يُقرأ من الملف لا من اسمه.

**العطل الذي أنتج هذه الوحدة**: فحص الجاهزية كان يعدّ الخط عربًيا إن حمل
اسمه إحدى كلمات ``noto/dejavu/arial/...``. وحين ثُبِّتت ``fonts-noto-core``
على الخادم ردّ الفحص ``status: ok`` وقال «جاهز لإخراج PDF بعربية سليمة»،
والدليل الذي عرضه بنفسه كان::

    NotoSansSinhala…  NotoSansMalayalam…  NotoSansLao…

سنهالية وماليالامية ولاوية — ولا خطّ عربي واحد. الاسم يطابق، والحروف لا.
وهذا أسوأ من الفشل: العقد يخرج بمربّعات فارغة، والتوليد يعود بنجاح،
وتُحسب بصمته، ويصل الموظف ليوقّع ورقة لا تُقرأ.

فالسؤال الصحيح ليس «ما اسم الخط» بل «أفيه ألف ولام وميم؟» — ويُجاب
بقراءة جدول ``cmap`` من الملف. لا اعتمادية جديدة: بضع عشرات من الأسطر
تقرأ ما تقرأه أي أداة خطوط، وتعمل على لينكس وويندوز معًا.
"""
from __future__ import annotations

import struct
from pathlib import Path

#: حروف عربية أساسية لا يخلو منها خط يدعم العربية فعًلا. تُطلب كلها:
#: تغطية حرف واحد قد تأتي عرًضا في خط رموز، وأربعة معًا لا تأتي عرًضا.
ARABIC_PROBES = (0x0627, 0x0644, 0x0645, 0x0629)   # ا ل م ة

_FONT_SUFFIXES = (".ttf", ".otf", ".ttc")


def _u16(b: bytes, i: int) -> int:
    return struct.unpack_from(">H", b, i)[0]


def _u32(b: bytes, i: int) -> int:
    return struct.unpack_from(">I", b, i)[0]


def _cmap_offset(data: bytes) -> int | None:
    """موضع جدول cmap داخل الملف، مع فكّ حاويات ttc."""
    if len(data) < 12:
        return None
    base = 0
    if data[:4] == b"ttcf":                       # حاوية خطوط متعددة
        if len(data) < 16:
            return None
        base = _u32(data, 12)                     # أول خط فيها يكفي
        if base + 12 > len(data):
            return None
    num_tables = _u16(data, base + 4)
    rec = base + 12
    for _ in range(num_tables):
        if rec + 16 > len(data):
            return None
        if data[rec:rec + 4] == b"cmap":
            return _u32(data, rec + 8)
        rec += 16
    return None


def _covered_by_format4(data: bytes, off: int, cp: int) -> bool:
    """الشكل 4 — التقسيم إلى مقاطع، وهو الأشيع.

    لا يكفي أن يقع الحرف داخل مقطع: المقطع قد يعيد المعرّف 0 أي «لا رسم».
    ولهذا يُحسب معرّف الرسم كامًلا كما تحسبه أداة العرض.
    """
    seg_x2 = _u16(data, off + 6)
    seg_count = seg_x2 // 2
    ends = off + 14
    starts = ends + seg_x2 + 2
    deltas = starts + seg_x2
    ranges = deltas + seg_x2
    for i in range(seg_count):
        end = _u16(data, ends + i * 2)
        if cp > end:
            continue
        start = _u16(data, starts + i * 2)
        if cp < start:
            return False                          # المقاطع مرتّبة
        ro = _u16(data, ranges + i * 2)
        if ro == 0:
            delta = _u16(data, deltas + i * 2)
            return ((cp + delta) & 0xFFFF) != 0
        idx = ranges + i * 2 + ro + (cp - start) * 2
        if idx + 2 > len(data):
            return False
        gid = _u16(data, idx)
        return gid != 0
    return False


def _covered_by_format12(data: bytes, off: int, cp: int) -> bool:
    """الشكل 12 — مجموعات متّصلة، يستعمله ما يتجاوز النطاق الأساسي."""
    n = _u32(data, off + 12)
    grp = off + 16
    for _ in range(n):
        if grp + 12 > len(data):
            return False
        s = _u32(data, grp)
        e = _u32(data, grp + 4)
        if s <= cp <= e:
            return True
        grp += 12
    return False


def font_supports_arabic(path: str | Path) -> bool:
    """هل يرسم هذا الملف الحروف العربية الأساسية؟

    يُقرأ ``cmap`` ويُسأل عن كل حرف في :data:`ARABIC_PROBES`. وأي خلل في
    الملف يُقرأ «لا» — فالمجهول هنا ليس جاهزية.
    """
    p = Path(path)
    try:
        data = p.read_bytes()
    except OSError:
        return False

    try:
        cmap = _cmap_offset(data)
        if cmap is None or cmap + 4 > len(data):
            return False
        n_sub = _u16(data, cmap + 2)
        subtables: list[int] = []
        for i in range(n_sub):
            rec = cmap + 4 + i * 8
            if rec + 8 > len(data):
                break
            plat = _u16(data, rec)
            enc = _u16(data, rec + 2)
            # جداول اليونيكود وحدها: (3,1) و(3,10) و(0,*)
            if plat == 0 or (plat == 3 and enc in (1, 10)):
                subtables.append(cmap + _u32(data, rec + 4))
        if not subtables:
            return False

        for cp in ARABIC_PROBES:
            found = False
            for off in subtables:
                if off + 4 > len(data):
                    continue
                fmt = _u16(data, off)
                if fmt == 4:
                    ok = _covered_by_format4(data, off, cp)
                elif fmt == 12:
                    ok = _covered_by_format12(data, off, cp)
                else:
                    continue                      # أشكال نادرة: لا تُفترض
                if ok:
                    found = True
                    break
            if not found:
                return False                      # حرف ناقص = لا عربية
        return True
    except (struct.error, IndexError, ValueError):
        return False


def find_arabic_fonts(roots: list[str] | None = None,
                      limit: int = 5) -> list[str]:
    """أسماء الخطوط المثبَّتة التي تدعم العربية **فعًلا**.

    تتوقّف عند ``limit`` — الغرض إثبات الوجود لا الجرد.
    """
    if roots is None:
        roots = ["/usr/share/fonts", "/usr/local/share/fonts",
                 str(Path.home() / ".fonts"), r"C:\Windows\Fonts"]
    out: list[str] = []
    for root in roots:
        d = Path(root)
        if not d.is_dir():
            continue
        try:
            for f in sorted(d.rglob("*")):
                if f.suffix.lower() not in _FONT_SUFFIXES:
                    continue
                if font_supports_arabic(f):
                    out.append(f.name)
                    if len(out) >= limit:
                        return out
        except OSError:
            continue
    return out
