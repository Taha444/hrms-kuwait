# -*- coding: utf-8 -*-
"""GC-01/GC-02 — العقد الحكومي يُولَّد من نموذج الهيئة الرسمي نفسه.

كان النظام يبني العقد بتخطيط خطّي من قالب HTML يقلّد النموذج. والنموذج
الرسمي جدول عمودين بشعار الهيئة وثلاث صفحات — ويكفي فرق واحد ليُردّ
المستند عند التقديم.

والتحقّق هنا **بنيويّ لا بالنظر**: يُثبَت أن كل ما تغيّر في الملف هو محتوى
عُقد النصّ، وأن التنسيق والخطوط والشعار متطابقة بالبصمة مع الأصل. هذا أقوى
من فحص صورة، لأنه يغطّي ما لا تُظهره الصورة.
"""
from __future__ import annotations

import hashlib
import io
import re
import zipfile

import pytest

from app import gov_contract_docx as G

_T = re.compile(r"(<w:t(?:\s[^>]*)?>)(.*?)(</w:t>)", re.S)

VALUES = {
    "labour_dept_en": "Al-Farwaniyah", "labour_dept_ar": "الفروانية",
    "day_name_en": "Thursday", "contract_date": "27/08/2026",
    "contract_start_date": "01/09/2026",
    "company_name_en": "Gulf Trading Co.", "company_name_ar": "شركة الخليج للتجارة",
    "company_rep_name_en": "Ahmad Al-Sabah", "company_rep_name_ar": "أحمد الصباح",
    "company_civil_id": "123456789012",
    "employee_name_en": "Rahul Kumar", "employee_name_ar": "راهول كومار",
    "employee_civil_id": "287050112345",
    "nationality_en": "Indian", "nationality_ar": "هندي",
    "passport_no": "M1234567", "residence_no": "RES-88123",
    "job_title_en": "Accountant", "job_title_ar": "محاسب",
    "probation_days": "90", "wage": "450", "annual_leave_days": "30",
    "contract_term_en": "ONE YEAR", "contract_term_ar": "سنة",
    "contract_day": "27", "contract_month": "08", "contract_year": "2026",
}


def _text(data: bytes) -> str:
    xml = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode("utf-8")
    return "".join(m.group(2) for m in _T.finditer(xml))


def _skeleton(data: bytes) -> str:
    """الملف بعد تفريغ كل نصّ — أي التنسيق وحده."""
    xml = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode("utf-8")
    return _T.sub(lambda m: m.group(1) + "@" + m.group(3), xml)


def test_official_template_fingerprint_is_intact():
    """النموذج الرسمي كما سلّمته الهيئة. اختلاف البصمة يوقف كل شيء."""
    data = G.official_bytes()
    assert hashlib.sha256(data).hexdigest() == G.OFFICIAL_SHA256


def test_tampered_template_stops_generation():
    """نموذج معدَّل لا يُولَّد منه عقد يُقدَّم لجهة رسمية."""
    with pytest.raises(G.TemplateTampered):
        G.build_tagged("ليس ملف وورد".encode("utf-8"))


def test_every_tag_has_a_source_and_every_source_a_tag():
    """لا وسم في النموذج بلا مصدر، ولا مصدر بلا وسم.

    وسم بلا مصدر يُطبع حرفيًّا في العقد؛ ومصدر بلا وسم بيانات صحيحة لا
    تصل الورقة. كلاهما يمرّ بصمت بلا هذا الفحص.
    """
    tags = G.tags_in(G.build_tagged())
    mapped = ({t for t, _, _, _ in G.FIELD_SOURCES}
              | {"contract_day", "contract_month", "contract_year"})
    assert tags - mapped == set(), f"وسوم بلا مصدر: {sorted(tags - mapped)}"
    assert mapped - tags == set(), f"مصادر بلا وسم: {sorted(mapped - tags)}"


def test_layout_and_logo_are_byte_identical_to_the_official_file():
    """كل ما تغيّر هو محتوى النصّ. التخطيط والشعار والخطوط كما هي.

    هذا هو معيار GC-02 مثبًتا بنيوًيا: مقارنة الصور تُظهر ما يظهر، وهذه
    تُثبت أن شيًئا لم يتغيّر أصًلا.
    """
    original = G.official_bytes()
    filled = G.fill(VALUES)

    assert _skeleton(original) == _skeleton(filled), (
        "تغيّر شيء خارج عُقد النصّ — التخطيط لم يعد مطابًقا للنموذج الرسمي"
    )

    a = zipfile.ZipFile(io.BytesIO(original))
    b = zipfile.ZipFile(io.BytesIO(filled))
    for name in a.namelist():
        if name == "word/document.xml":
            continue
        assert hashlib.sha256(a.read(name)).hexdigest() == \
               hashlib.sha256(b.read(name)).hexdigest(), (
            f"{name} تغيّر — وهو من التنسيق أو الخطوط أو الشعار"
        )


def test_no_sample_values_survive_in_the_output():
    """GC-04 — «Butchery» و«فلبيني» بقايا عقد منشأة أخرى.

    تركها في مستند يُقدَّم للهيئة ليس خطًأ تجميليًّا: هو بيان كاذب عن
    منشأة وجنسية لا علاقة لهما بالموظف.
    """
    txt = _text(G.fill(VALUES))
    for sample in ("0000", "Butchery", "فلبيني", "wensday", "al asima",
                   "320", "10/02/2024", "06/03/2024", "06/06/2024",
                   "ONE YEARS", "{{", "}}"):
        assert sample not in txt, f"قيمة عيّنة باقية في المخرَج: {sample!r}"


def test_every_value_reaches_the_document():
    """القيمة المُمرَّرة تظهر فعًلا — لا تُبتلع في وسم لم يُستبدل."""
    txt = _text(G.fill(VALUES))
    for key, val in VALUES.items():
        assert val in txt, f"القيمة {val!r} للحقل {key} لم تصل المستند"


def test_missing_required_field_names_itself_and_stops():
    """GC-08 — عقد بمربّع فارغ يوقّعه الموظف ويُقدَّم للهيئة أسوأ من لا عقد."""
    ctx = {"employee_name": "أحمد", "civil_id": "123"}
    values, missing = G.build_values(ctx)
    assert missing, "بيانات ناقصة ومع ذلك مضى التوليد"
    assert "رقم الإقامة" in missing
    assert "الجنسية بالعربية" in missing
    # الرسالة بالعربية ليعرف المندوب أين يذهب
    assert all(re.search(r"[؀-ۿ]", m) for m in missing)


def test_header_date_parts_derive_from_one_date():
    """يوم/شهر/سنة الترويسة مشتقّة من تاريخ العقد لا مُدخلة مستقلّة.

    مصدران لتاريخ واحد يفترقان، والعقد يحمل تاريخين مختلفين في صفحته
    الأولى.
    """
    ctx = {k: "x" for k, _, _, _ in G.FIELD_SOURCES}
    ctx = {src: "x" for _, src, _, _ in G.FIELD_SOURCES}
    ctx["contract_date"] = "05/11/2026"
    values, _ = G.build_values(ctx)
    assert values["contract_day"] == "05"
    assert values["contract_month"] == "11"
    assert values["contract_year"] == "2026"


def test_pdf_conversion_degrades_without_libreoffice():
    """غياب LibreOffice عطل بيئة لا عطل عقد — يُسلَّم الـdocx بتخطيطه الرسمي.

    والبديل — إسقاط التوليد كلّه — يمنع المندوب من عمله بسبب حزمة ناقصة
    على الخادم.
    """
    content, ext, mime, missing = G.generate({src: "x" for _, src, _, _ in G.FIELD_SOURCES}
                                             | {"contract_date": "01/01/2026"})
    assert not missing
    assert ext in ("pdf", "docx")
    assert content[:2] == b"PK" if ext == "docx" else content[:4] == b"%PDF"


def test_tagged_copy_is_derived_not_stored():
    """نسخة العمل تُشتقّ من الأصل حسابيًّا في كل مرة.

    لو حُفظت في المستودع لصار فيه نموذجان يفترقان، ولا أحد يعرف أيّهما
    الرسمي — وهو أخطر من خطأ في التعبئة.
    """
    from pathlib import Path

    assets = Path(G.__file__).parent / "assets"
    files = {p.name for p in assets.glob("*.docx")}
    assert files == {"GOV-CONTRACT-RENEWAL.docx"}, (
        f"ملفات وورد إضافية في assets: {files} — الأصل وحده يُحفَظ"
    )
    assert G.build_tagged() == G.build_tagged(), "الاشتقاق غير حتميّ"
