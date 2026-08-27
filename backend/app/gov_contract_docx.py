# -*- coding: utf-8 -*-
"""GC-01/GC-02 — توليد العقد الحكومي من نموذج الهيئة الرسمي نفسه.

كان النظام يبني العقد بتخطيط خطّي من قالب HTML: ترويسة الشركة ثم كتلة
بيانات ثم نصّ. والنموذج الرسمي للهيئة العامة للقوى العاملة شيء آخر تماًما:
جدول عمودين — الإنجليزي يسار والعربي يمين — وشعار الهيئة في الترويسة،
وثلاث صفحات، ومنطقة توقيع «الطرف الأول / الطرف الثاني» في آخرها.

فالاستبدال ليس تعديل نصّ بل **تغيير طريقة التوليد**: يُملأ ملف الوورد
الرسمي نفسه ثم يُحوَّل إلى PDF. وهذا وحده ما يحفظ التخطيط والشعار والخطوط
العربية — إعادة بناء التصميم في HTML تعني تقليد نموذج رسمي، ويكفي فرق
واحد ليُردّ المستند.

**الأصل لا يُمسّ.** ``assets/GOV-CONTRACT-RENEWAL.docx`` مطابق لما سلّمته
الهيئة، وبصمته تُفحص قبل كل توليد. ونسخة العمل الموسومة **تُشتقّ منه
حسابيًّا** في كل مرة ولا تُحرَّر بيد: لو حُرِّرت مرة، صار في المستودع
نموذجان يفترقان ولا أحد يعرف أيّهما الرسمي.

**والوسم بالموضع لا بالنصّ.** العناصر النائبة سلاسل أصفار متطابقة، فلا
يميّزها إلا موقعها في المستند. والمواقع مثبَّتة أدناه بسياق كل واحد، فأي
تغيّر في الأصل يُسقط الفحص بدل أن يملأ الحقل الخطأ بصمت.
"""
from __future__ import annotations

import hashlib
import io
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

ASSET = Path(__file__).parent / "assets" / "GOV-CONTRACT-RENEWAL.docx"

#: بصمة النموذج الرسمي كما سلّمته الهيئة. اختلافها يعني أن أحًدا عدّله.
OFFICIAL_SHA256 = "2a9cf6e4c2098e03ceea1f6280323f1570bd3efcba612d1b84924b69809479cf"

_T_RE = re.compile(r"(<w:t(?:\s[^>]*)?>)(.*?)(</w:t>)", re.S)


class TemplateTampered(RuntimeError):
    """النموذج الرسمي تغيّر — يُوقَف التوليد ويُبلَّغ."""


def official_bytes() -> bytes:
    data = ASSET.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != OFFICIAL_SHA256:
        raise TemplateTampered(
            "نموذج العقد الحكومي لا يطابق نسخة الهيئة الرسمية.\n"
            f"  المتوقَّع: {OFFICIAL_SHA256[:16]}\n"
            f"  الموجود : {actual[:16]}\n"
            "أوقف التوليد وأبلغ: العقد يُقدَّم لجهة رسمية."
        )
    return data


# ---------------------------------------------------------------------------
# خريطة الوسم: موضع العنصر في ``word/document.xml`` ← الوسم الذي يحلّ محلّه.
# النصّ المرافق للتوثيق لا للمطابقة — المطابقة على النصّ نفسه في ``_verify``.
# ---------------------------------------------------------------------------
#: (الموضع، النصّ الأصلي المتوقَّع، البديل)
SLOTS: list[tuple[int, str, str]] = [
    # ---- العمود الإنجليزي ----
    (46, "al ", ""),                                  # جزء من "al asima"
    (47, "asima", "{{labour_dept_en}}"),
    (50, "wensday", "{{day_name_en}}"),
    (55, "10/02/2024", "{{contract_date}}"),
    (73, "000000000000000000000000", "{{company_name_en}}"),
    (79, "0000000000000000000", "{{company_rep_name_en}}"),
    (83, "00000000000000", "{{company_civil_id}}"),
    (89, "000000000000000", "{{employee_name_en}}"),
    (95, "0000000000000", "{{nationality_en}}"),
    (104, "00000000000", "{{passport_no}}"),
    (111, "0000000000000", "{{residence_no}}"),
    (116, "00000000000", "{{company_name_en}}"),
    # «Butchery» بقيّة من عقد منشأة أخرى — تُزال ويبقى نصّ النموذج كما هو
    (117,
     " Butchery Company and wishes to contract with the second party to work for it in the ",
     " Company and wishes to contract with the second party to work for it in the "),
    (118, "0000000000", "{{job_title_en}}"),
    (138, "0000000", "{{job_title_en}}"),
    (147, "term not exceeding 100 ", "term not exceeding {{probation_days}} "),
    (183, "320", "{{wage}}"),
    (315, "ONE", "{{contract_term_en}}"),
    (316, " ", ""),
    (317, "YEA", ""),
    (318, "RS", ""),
    (924,
     "a term of 30 days. It shall not be due on the first year save after",
     "a term of {{annual_leave_days}} days. It shall not be due on the first year save after"),
    # ---- العمود العربي ----
    (436, "العاصمة", "{{labour_dept_ar}}"),
    (470, "0000000000", "{{company_name_ar}}"),
    (489, "0000000000000000", "{{company_rep_name_ar}}"),
    (495, "00000000000000000000", "{{company_civil_id}}"),
    (506, "0000000000000000000", "{{employee_name_ar}}"),
    (513, "فلبيني", "{{nationality_ar}}"),
    (514, "0000000000000", "{{passport_no}}"),
    (528, "0000000000000000", "{{employee_civil_id}}"),
    (555, "000000000 ", "{{company_name_ar}} "),
    (576, "0000", "{{job_title_ar}}"),
    (664, "0000", "{{job_title_ar}}"),
    (699, " 100 ", " {{probation_days}} "),
    (737, "320", "{{wage}}"),
    # النقاط مواضع الكتابة باليد في النموذج الورقي — تبقى كما هي،
    # ويُستبدل الرقم وحده. حذفها تغيير في شكل النموذج لا تعبئة له.
    (1363, " ..... 30 .... ", " ..... {{annual_leave_days}} .... "),
]

#: مقاطع التواريخ والمدد — تُكتب مجزّأة بثلاثة أشكال مختلفة داخل الملف
#: (``06`` + ``/`` + ``0`` + ``3`` + ``/20`` + ``24`` مرة، ومتّصلة مرة،
#: ومقلوبة في العربية حيث تسبق السنةُ اليومَ). فلا يطابقها نصّ واحد ولا نمط
#: واحد. تُثبَّت بالموضع كالحقول: الوسم في أول عنصر والباقي يُفرَّغ.
#:
#: والتاريخ نفسه يتكرّر في ستّة مواضع — هذا في النموذج الرسمي لا خطأ فيه:
#: البند الخامس والسادس بفقرتيه، في العمودين. حقل واحد يملؤها كلها.
DATE_SPANS: list[tuple[int, int, str]] = [
    (258, 263, "{{contract_start_date}}"),   # الإنجليزي — البند الخامس
    (302, 306, "{{contract_start_date}}"),   # الإنجليزي — السادس/محدد
    (378, 382, "{{contract_start_date}}"),   # الإنجليزي — السادس/غير محدد
    (802, 806, "{{contract_start_date}}"),   # العربي — البند الخامس
    (845, 849, "{{contract_start_date}}"),   # العربي — السادس/محدد
    (893, 897, "{{contract_start_date}}"),   # العربي — السادس/غير محدد
    (853, 854, "{{contract_term_ar}}"),      # «سنة» — مدّة العقد بالعربية
]

#: ترويسة العمود العربي: التاريخ مفكوك عبر جملة كاملة
#: (``2024/ 03/ … إنه في يوم الموافق 06``). دمجه يكسر تخطيط النموذج،
#: فيُملأ كلٌّ في موضعه.
HEADER_DATE_PARTS: list[tuple[int, str, str]] = [
    (438, "2024", "{{contract_year}}"),
    (440, "03", "{{contract_month}}"),
    (451, "06", "{{contract_day}}"),
]


def _texts(xml: str) -> list[str]:
    return [m.group(2) for m in _T_RE.finditer(xml)]


def _rewrite(xml: str, changes: dict[int, str]) -> str:
    idx = -1

    def sub(m: re.Match) -> str:
        nonlocal idx
        idx += 1
        if idx in changes:
            return m.group(1) + changes[idx] + m.group(3)
        return m.group(0)

    return _T_RE.sub(sub, xml)


def build_tagged(original: bytes | None = None) -> bytes:
    """يشتقّ نسخة العمل الموسومة من الأصل. لا تُحرَّر بيد أبًدا."""
    data = original if original is not None else official_bytes()
    try:
        src = zipfile.ZipFile(io.BytesIO(data))
        xml = src.read("word/document.xml").decode("utf-8")
    except (zipfile.BadZipFile, KeyError) as exc:
        # ملف غير قابل للقراءة هو أيًضا «النموذج تغيّر»: يُوقَف التوليد
        # بالسبب نفسه، لا يتسرّب استثناء تقنيّ إلى المندوب.
        raise TemplateTampered(
            f"تعذّرت قراءة نموذج العقد الحكومي — الملف تالف أو ليس مستند وورد: {exc}"
        ) from exc
    texts = _texts(xml)

    changes: dict[int, str] = {}
    mismatches: list[str] = []
    for pos, expected, replacement in SLOTS:
        if pos >= len(texts) or texts[pos] != expected:
            found = texts[pos] if pos < len(texts) else "<خارج المدى>"
            mismatches.append(f"  الموضع {pos}: متوقَّع {expected!r} ووُجد {found!r}")
            continue
        changes[pos] = replacement

    # التواريخ المجزّأة — بالموضع لا بالكشف
    for start, end, tag in DATE_SPANS:
        if end >= len(texts):
            mismatches.append(f"  مقطع تاريخ {start}..{end} خارج المدى")
            continue
        changes[start] = tag
        for k in range(start + 1, end + 1):
            changes[k] = ""
    for pos, expected, replacement in HEADER_DATE_PARTS:
        if pos >= len(texts) or texts[pos] != expected:
            found = texts[pos] if pos < len(texts) else "<خارج المدى>"
            mismatches.append(f"  الموضع {pos}: متوقَّع {expected!r} ووُجد {found!r}")
            continue
        changes[pos] = replacement

    if mismatches:
        raise TemplateTampered(
            "خريطة الوسم لا تطابق النموذج — تغيّر الأصل أو تغيّرت الخريطة.\n"
            "الوسم بالموضع، فعدم المطابقة يوقف التوليد بدل أن يملأ الحقل الخطأ:\n"
            + "\n".join(mismatches)
        )

    new_xml = _rewrite(xml, changes)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            payload = (new_xml.encode("utf-8") if item.filename == "word/document.xml"
                       else src.read(item.filename))
            dst.writestr(item, payload)
    return out.getvalue()


def tags_in(data: bytes) -> set[str]:
    xml = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode("utf-8")
    return set(re.findall(r"\{\{(\w+)\}\}", xml))


# ---------------------------------------------------------------------------
# GC-07 — البند السادس: فقرتان متعارضتان في نموذج واحد
# ---------------------------------------------------------------------------
# النموذج الرسمي يحمل فقرتين لا تجتمعان: «محدد المدة» و«غير محدد المدة»،
# وتحتهما ملاحظة أن ذلك يخضع لإرادة الطرفين. في الورقة تُشطب إحداهما بالقلم.
#
# وكان المخرَج يطبعهما **معًا مملوءتين بنفس التاريخ** — عقد يقول إنه محدد
# المدة وغير محدد المدة في آن. ليس عيبًا تجميليًّا: بند المدة هو ما يُحتكم
# إليه عند إنهاء العلاقة، ومستند يقول الشيء ونقيضه لا يُحتجّ به.
#
# القرار (مالك العمل): تُملأ الفقرة المطابقة لنوع العقد المسجَّل، وتُشطب
# الأخرى — نفس ما يُفعل بالورقة، فيبقى النصّ الرسمي كامًلا ويُقرأ الاستبعاد.
# لا تُحذف: حذف فقرة من نموذج رسمي تغيير لمحتواه.
CLAUSE_PARAGRAPHS: dict[str, list[int]] = {
    "definite": [32, 33, 78, 79],      # الإنجليزي ثم العربي
    "indefinite": [34, 80],
}

_P_RE = re.compile(r"<w:p[ >].*?</w:p>", re.S)
_R_RE = re.compile(r"(<w:r(?:\s[^>]*)?>)(.*?)(</w:r>)", re.S)
_RPR_RE = re.compile(r"(<w:rPr(?:\s[^>]*)?>)(.*?)(</w:rPr>)", re.S)

#: العناصر التي يأتي ``w:strike`` قبلها في ترتيب مخطَّط OOXML. الترتيب ليس
#: تجميلًا: مستند مخالف له قد يرفضه Word ويقبله غيره — فيبدو سليًما عند من
#: ولّده ومعطوًبا عند من يفتحه.
_AFTER_STRIKE = ("<w:dstrike", "<w:outline", "<w:shadow", "<w:emboss",
                 "<w:imprint", "<w:noProof", "<w:vanish", "<w:color",
                 "<w:spacing", "<w:w ", "<w:kern", "<w:position", "<w:sz",
                 "<w:szCs", "<w:highlight", "<w:u ", "<w:effect", "<w:bdr",
                 "<w:shd", "<w:vertAlign", "<w:rtl", "<w:lang")


def _strike_rpr(inner: str) -> str:
    if "<w:strike" in inner:
        return inner
    cut = len(inner)
    for tag in _AFTER_STRIKE:
        i = inner.find(tag)
        if i != -1:
            cut = min(cut, i)
    return inner[:cut] + "<w:strike/>" + inner[cut:]


def _strike_run(m: re.Match) -> str:
    open_tag, body, close_tag = m.group(1), m.group(2), m.group(3)
    if _RPR_RE.search(body):
        body = _RPR_RE.sub(
            lambda r: r.group(1) + _strike_rpr(r.group(2)) + r.group(3), body, count=1)
    else:
        body = "<w:rPr><w:strike/></w:rPr>" + body
    return open_tag + body + close_tag


def strike_clause(xml: str, paragraphs: list[int]) -> str:
    """يشطب فقرات بعينها — لا يحذفها."""
    out, idx = [], -1
    last = 0
    for m in _P_RE.finditer(xml):
        idx += 1
        if idx not in paragraphs:
            continue
        out.append(xml[last:m.start()])
        out.append(_R_RE.sub(_strike_run, m.group(0)))
        last = m.end()
    out.append(xml[last:])
    return "".join(out)


def fill(values: dict[str, str], tagged: bytes | None = None,
         definite: bool | None = None) -> bytes:
    """يملأ نسخة العمل الموسومة بالقيم ويعيد docx جاهًزا.

    الحقل غير المُمرَّر يُترك وسًما ظاهًرا لا يُفرَّغ بصمت: عقد بمربّع فارغ
    يُوقَّع ويُقدَّم للهيئة أسوأ من عقد لا يُولَّد. والمنع الفعليّ في
    ``required_fields`` قبل الوصول إلى هنا.

    ``definite`` يحدّد أيّ فقرتَي البند السادس تبقى وأيّهما تُشطب (GC-07).
    و``None`` تعني عدم الشطب — للاختبار وحده: عقد بفقرتين متعارضتين لا
    يُسلَّم.
    """
    data = tagged if tagged is not None else build_tagged()
    src = zipfile.ZipFile(io.BytesIO(data))
    xml = src.read("word/document.xml").decode("utf-8")
    if definite is not None:
        # تُشطب الفقرة المخالفة لنوع العقد المسجَّل — لا تُحذف
        xml = strike_clause(xml, CLAUSE_PARAGRAPHS["indefinite" if definite
                                                   else "definite"])
    for key, val in values.items():
        xml = xml.replace("{{" + key + "}}", _escape(str(val)))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            payload = (xml.encode("utf-8") if item.filename == "word/document.xml"
                       else src.read(item.filename))
            dst.writestr(item, payload)
    return out.getvalue()


def _escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def soffice_path() -> str | None:
    for name in ("soffice", "libreoffice"):
        p = shutil.which(name)
        if p:
            return p
    for p in (r"C:\Program Files\LibreOffice\program\soffice.exe",
              "/usr/bin/soffice", "/usr/lib/libreoffice/program/soffice"):
        if Path(p).exists():
            return p
    return None


def to_pdf(docx_bytes: bytes, timeout: int = 120) -> bytes | None:
    """يحوّل إلى PDF عبر LibreOffice. يعيد None إن لم يكن متاًحا.

    ``None`` لا استثناء: غياب LibreOffice ليس عطًلا في العقد بل في البيئة،
    والمنادي يقرّر — يسلّم الـdocx (وهو التخطيط الرسمي نفسه) بدل أن يفشل
    التوليد كليًّا. ومن يريد PDF إلزاميًّا يفحص القيمة.
    """
    exe = soffice_path()
    if not exe:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "contract.docx"
        src.write_bytes(docx_bytes)
        try:
            subprocess.run(
                [exe, "--headless", "--norestore", "--convert-to", "pdf",
                 "--outdir", tmp, str(src)],
                check=True, timeout=timeout,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None
        pdf = Path(tmp) / "contract.pdf"
        return pdf.read_bytes() if pdf.exists() else None


# ---------------------------------------------------------------------------
# ربط بيانات النظام بحقول النموذج
# ---------------------------------------------------------------------------
#: الوسم ← (مفتاح السياق، الاسم العربي للحقل، إلزامي؟)
#:
#: الخريطة هنا لا في المنادي: من يضيف حقًلا للنموذج يضيف سطره هنا، فلا يوجد
#: وسم في الملف بلا مصدر معروف ولا مصدر بلا وسم.
FIELD_SOURCES: list[tuple[str, str, str, bool]] = [
    ("employee_name_ar", "employee_name", "اسم الموظف بالعربية", True),
    ("employee_name_en", "employee_name_en", "اسم الموظف بالإنجليزية", True),
    ("employee_civil_id", "civil_id", "الرقم المدني للموظف", True),
    ("nationality_ar", "nationality", "الجنسية بالعربية", True),
    ("nationality_en", "nationality_en", "الجنسية بالإنجليزية", True),
    ("passport_no", "passport_number", "رقم الجواز", True),
    ("residence_no", "residence_no", "رقم الإقامة", True),
    ("job_title_ar", "job_title", "المهنة بالعربية", True),
    ("job_title_en", "job_title_en", "المهنة بالإنجليزية", True),
    ("company_name_ar", "company_name", "اسم الشركة بالعربية", True),
    ("company_name_en", "company_name_en", "اسم الشركة بالإنجليزية", True),
    ("company_rep_name_ar", "company_rep_name", "اسم ممثّل الشركة بالعربية", True),
    ("company_rep_name_en", "company_rep_name_en", "اسم ممثّل الشركة بالإنجليزية", True),
    ("company_civil_id", "company_civil_id", "الرقم المدني لممثّل الشركة", True),
    ("labour_dept_ar", "labour_dept", "إدارة العمل (المحافظة) بالعربية", True),
    ("labour_dept_en", "labour_dept_en", "إدارة العمل بالإنجليزية", True),
    ("wage", "wage", "الأجر", True),
    ("contract_date", "contract_date", "تاريخ تحرير العقد", True),
    ("contract_start_date", "contract_start_date", "تاريخ نفاذ العقد", True),
    ("day_name_en", "day_name_en", "اسم اليوم بالإنجليزية", True),
    ("probation_days", "probation_days", "أيام فترة التجربة", True),
    ("annual_leave_days", "annual_leave_days", "أيام الإجازة السنوية", True),
    ("contract_term_ar", "contract_term_ar", "مدّة العقد بالعربية", True),
    ("contract_term_en", "contract_term_en", "مدّة العقد بالإنجليزية", True),
]


def build_values(ctx: dict) -> tuple[dict[str, str], list[str]]:
    """يبني قيم الحقول من سياق النظام. يعيد (القيم، أسماء الناقص).

    الناقص يُسمّى بالعربية ولا يُملأ بفراغ: عقد بمربّع فارغ يوقّعه الموظف
    ويُقدَّم للهيئة أسوأ من عقد لا يُولَّد (GC-08).
    """
    values: dict[str, str] = {}
    missing: list[str] = []
    for tag, key, label, required in FIELD_SOURCES:
        raw = str(ctx.get(key) or "").strip()
        if not raw and required:
            missing.append(label)
            continue
        values[tag] = raw

    # يوم/شهر/سنة الترويسة العربية مشتقّة من تاريخ العقد نفسه لا مُدخلة
    # مستقلّة: مصدران لتاريخ واحد يفترقان.
    date = values.get("contract_date", "")
    parts = date.split("/") if "/" in date else []
    if len(parts) == 3:
        values["contract_day"], values["contract_month"], values["contract_year"] = parts
    return values, missing


def generate(ctx: dict) -> tuple[bytes, str, str, list[str]]:
    """يولّد العقد. يعيد (المحتوى، الامتداد، نوع المحتوى، الناقص).

    يحاول PDF أوًلا؛ وإن غاب LibreOffice عن البيئة يسلّم الـdocx — وهو
    التخطيط الرسمي نفسه — بدل أن يفشل التوليد كلّه لسبب بيئيّ.
    """
    values, missing = build_values(ctx)
    if missing:
        return b"", "", "", missing
    # GC-07 — نوع العقد المسجَّل هو ما يقرّر أي فقرة تبقى. لا افتراض هنا:
    # الافتراض الصامت يُنتج عقًدا يقول غير ما اتُّفق عليه.
    definite = str(ctx.get("contract_type_raw") or "").strip().lower() != "indefinite"
    docx = fill(values, definite=definite)
    pdf = to_pdf(docx)
    if pdf:
        return pdf, "pdf", "application/pdf", []
    return (docx, "docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            [])
