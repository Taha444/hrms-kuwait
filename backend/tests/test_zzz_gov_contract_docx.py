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


# ---------------------------------------------------------------------------
# GC-07 — البند السادس: فقرة واحدة تبقى والأخرى تُشطب
# ---------------------------------------------------------------------------
def _paragraph_texts(data: bytes) -> list[str]:
    xml = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode("utf-8")
    paras = re.findall(r"<w:p[ >].*?</w:p>", xml, re.S)
    return ["".join(m.group(2) for m in _T.finditer(p)) for p in paras]


def _paragraph_is_struck(data: bytes, index: int) -> bool:
    xml = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode("utf-8")
    para = re.findall(r"<w:p[ >].*?</w:p>", xml, re.S)[index]
    runs = re.findall(r"<w:r(?:\s[^>]*)?>.*?</w:r>", para, re.S)
    texted = [r for r in runs if "<w:t" in r]
    return bool(texted) and all("<w:strike/>" in r for r in texted)


def test_definite_contract_strikes_the_indefinite_clause():
    """عقد محدد المدة: تبقى فقرته وتُشطب فقرة «غير محدد»."""
    out = G.fill(VALUES, definite=True)
    for i in G.CLAUSE_PARAGRAPHS["indefinite"]:
        assert _paragraph_is_struck(out, i), f"فقرة «غير محدد» {i} لم تُشطب"
    for i in G.CLAUSE_PARAGRAPHS["definite"]:
        assert not _paragraph_is_struck(out, i), f"فقرة «محدد» {i} شُطبت بالخطأ"


def test_indefinite_contract_strikes_the_definite_clause():
    """والعكس — القرار يتبع نوع العقد المسجَّل لا افتراًضا ثابًتا."""
    out = G.fill(VALUES, definite=False)
    for i in G.CLAUSE_PARAGRAPHS["definite"]:
        assert _paragraph_is_struck(out, i), f"فقرة «محدد» {i} لم تُشطب"
    for i in G.CLAUSE_PARAGRAPHS["indefinite"]:
        assert not _paragraph_is_struck(out, i), f"فقرة «غير محدد» {i} شُطبت بالخطأ"


def test_the_two_clauses_are_never_both_active():
    """جوهر GC-07: عقد يقول إنه محدد وغير محدد في آن لا يُحتجّ به.

    بند المدة هو ما يُحتكم إليه عند إنهاء العلاقة.
    """
    for definite in (True, False):
        out = G.fill(VALUES, definite=definite)
        active = [i for group in G.CLAUSE_PARAGRAPHS.values() for i in group
                  if not _paragraph_is_struck(out, i)]
        both = {"definite": all(i in active for i in G.CLAUSE_PARAGRAPHS["definite"]),
                "indefinite": all(i in active for i in G.CLAUSE_PARAGRAPHS["indefinite"])}
        assert not (both["definite"] and both["indefinite"]), (
            "الفقرتان المتعارضتان نشطتان معًا"
        )


def test_struck_clause_keeps_its_text():
    """الشطب لا الحذف: النصّ الرسمي يبقى كامًلا ويُقرأ الاستبعاد.

    حذف فقرة من نموذج رسمي تغيير لمحتواه لا تعبئة له.
    """
    original_paras = _paragraph_texts(G.official_bytes())
    out_paras = _paragraph_texts(G.fill(VALUES, definite=True))
    assert len(original_paras) == len(out_paras), "عدد الفقرات تغيّر — حُذفت فقرة"
    for i in G.CLAUSE_PARAGRAPHS["indefinite"]:
        assert out_paras[i].strip(), f"فقرة {i} المشطوبة فُرّغت من نصّها"


def test_striking_touches_only_the_target_paragraphs():
    """لا يتسرّب الشطب إلى بقيّة المستند."""
    out = G.fill(VALUES, definite=True)
    target = set(G.CLAUSE_PARAGRAPHS["indefinite"])
    xml = zipfile.ZipFile(io.BytesIO(out)).read("word/document.xml").decode("utf-8")
    paras = re.findall(r"<w:p[ >].*?</w:p>", xml, re.S)
    for i, para in enumerate(paras):
        if i in target:
            continue
        assert "<w:strike/>" not in para, f"شطب تسرّب إلى الفقرة {i}"


def test_generate_follows_the_recorded_contract_type():
    """المسار الكامل: النوع المسجَّل يصل الورقة.

    اختبار الوحدة يثبت أن الشطب يعمل؛ وهذا يثبت أنه **يُستدعى** بالقيمة
    الصحيحة. الفجوة بينهما هي التي تُنتج عقًدا صحيح الآلية خاطئ المحتوى.
    """
    base = {src: "x" for _, src, _, _ in G.FIELD_SOURCES} | {
        "contract_date": "01/01/2026"}

    out_def, *_ = G.generate(base | {"contract_type_raw": "definite"})
    out_indef, *_ = G.generate(base | {"contract_type_raw": "indefinite"})
    assert out_def != out_indef, "نوع العقد لم يغيّر المخرَج إطلاًقا"

    if out_def[:2] == b"PK":            # docx — نفحص الشطب مباشرة
        for i in G.CLAUSE_PARAGRAPHS["indefinite"]:
            assert _paragraph_is_struck(out_def, i)
        for i in G.CLAUSE_PARAGRAPHS["definite"]:
            assert _paragraph_is_struck(out_indef, i)


def test_unknown_contract_type_defaults_to_definite_not_to_both():
    """نوع غير معروف لا يعني «اطبع الفقرتين».

    الافتراض الصامت الذي يترك العقد متناقًضا هو العيب الأصلي نفسه.
    """
    base = {src: "x" for _, src, _, _ in G.FIELD_SOURCES} | {
        "contract_date": "01/01/2026", "contract_type_raw": "شيء غير معروف"}
    out, *_ = G.generate(base)
    if out[:2] == b"PK":
        struck = [i for group in G.CLAUSE_PARAGRAPHS.values() for i in group
                  if _paragraph_is_struck(out, i)]
        assert struck, "لم تُشطب أي فقرة — العقد يحمل بندين متعارضين"


# ---------------------------------------------------------------------------
# «لا يتغيّر حرف واحد في العقد» — الحارس الحرفيّ
# ---------------------------------------------------------------------------
#: المواضع المسموح باختلافها، وسببُ كلٍّ منها. أي اختلاف خارج هذه القائمة
#: يُسقط الاختبار: هذا هو الفرق بين «نملأ الحقول» و«نعدّل العقد».
#:
#: القرار (مالك العمل): النصّ يبقى كما ورد من الهيئة حرًفا بحرف — بما فيه
#: الأخطاء الإملائية في المتن (GC-11). لا تُصحَّح.
ALLOWED_TEXT_CHANGES = {
    # خانات التعبئة: سلاسل أصفار في النموذج
    73, 79, 83, 89, 95, 104, 111, 116, 118, 138,
    470, 489, 495, 506, 514, 528, 555, 576, 664,
    # قيم عيّنة من عقد سابق تُستبدل ببيانات الموظف والمنشأة
    46, 47, 50, 55, 147, 183, 315, 316, 317, 318,
    436, 513, 699, 737, 924, 1363,
    # «Butchery» — اسم منشأة أخرى ملتصق بخانة اسم المنشأة
    117,
    # مقاطع التواريخ المجزّأة (تُدمج في العنصر الأول ويُفرَّغ الباقي)
    258, 259, 260, 261, 262, 263,
    302, 303, 304, 305, 306,
    378, 379, 380, 381, 382,
    438, 440, 451,
    802, 803, 804, 805, 806,
    845, 846, 847, 848, 849,
    853, 854,
    893, 894, 895, 896, 897,
}


def test_not_a_single_character_changes_outside_the_filled_fields():
    """القرار الصريح: العقد كما هو، والتعبئة وحدها هي ما يتغيّر.

    الحارس يعدّ الاختلافات موضًعا موضًعا. إضافة موضع جديد هنا قرار واعٍ
    يمرّ بمراجعة، لا تعديل يتسلّل مع تغيير آخر.
    """
    a = re.findall(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>",
                   zipfile.ZipFile(io.BytesIO(G.official_bytes()))
                   .read("word/document.xml").decode("utf-8"), re.S)
    b = re.findall(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>",
                   zipfile.ZipFile(io.BytesIO(G.fill(VALUES)))
                   .read("word/document.xml").decode("utf-8"), re.S)
    assert len(a) == len(b), "عدد عناصر النصّ تغيّر — أُضيف أو حُذف نصّ"

    changed = {i for i in range(len(a)) if a[i] != b[i]}
    intruders = changed - ALLOWED_TEXT_CHANGES
    assert not intruders, (
        "تغيّر نصّ خارج خانات التعبئة — العقد يجب أن يبقى كما ورد من الهيئة:\n"
        + "\n".join(f"  [{i}] {a[i]!r} ← {b[i]!r}" for i in sorted(intruders))
    )


def test_official_spelling_is_left_exactly_as_received():
    """GC-11 — قرار مالك العمل: الأخطاء الإملائية في المتن **لا تُصحَّح**.

    قد تكون منقولة من نموذج الهيئة نفسه، وتغيير نصّ نموذج رسمي بلا إذن
    أسوأ من الخطأ الإملائي. والحارس هنا يمنع «تحسيًنا» حسن النيّة يُقدَّم
    بعد شهور فيُغيّر مستنًدا رسميًّا بلا قرار.
    """
    txt = _text(G.fill(VALUES))
    for word in ("تسععرى", "القطالأ", "تخت", "طبقعا", "القعانون",
                 "اجرا مقدراه", "لا تقلعن", "يتجزا"):
        assert word in txt, (
            f"«{word}» صُحِّحت — والقرار المسجَّل هو إبقاء النصّ كما ورد"
        )


# ---------------------------------------------------------------------------
# المسار الكامل: ما يصل يد المندوب فعًلا
# ---------------------------------------------------------------------------
def test_the_delivered_file_carries_the_authority_logo():
    """شعار الهيئة يصل الملف المُسلَّم — لا يُعاد بناء العقد في صفحة.

    كان المخرَج صفحة HTML بترويسة الشركة: شعار الهيئة يختفي، والعمودان
    يصيران سطوًرا، والصفحات الثلاث تصير ستًّا. والصورة داخل الملف هي الدليل
    الوحيد على أن المُسلَّم هو نموذج الهيئة لا تقليًدا له.
    """
    original = zipfile.ZipFile(io.BytesIO(G.official_bytes()))
    logo_name = next(n for n in original.namelist() if n.startswith("word/media/"))
    logo_hash = hashlib.sha256(original.read(logo_name)).hexdigest()

    delivered = zipfile.ZipFile(io.BytesIO(G.fill(VALUES, definite=True)))
    assert logo_name in delivered.namelist(), "شعار الهيئة غائب عن الملف المُسلَّم"
    assert hashlib.sha256(delivered.read(logo_name)).hexdigest() == logo_hash, (
        "الشعار تغيّر — الملف لم يعد نموذج الهيئة"
    )


def test_renewal_endpoint_returns_a_downloadable_official_file(client):
    """التوليد من الواجهة يُنتج مستنًدا يُنزَّل، لا HTML يُعاد بناؤه.

    الواجهة كانت تقرأ ``r.data.html`` وتفتحه في نافذة طباعة — فحتى لو
    ولّد الخادم النموذج الرسمي، ما يراه المستخدم صفحة أخرى. الفجوة بين
    ما يُولَّد وما يُسلَّم هي ما يجعل الإصلاح يبدو ناجًحا وهو غير واصل.
    """
    from .conftest import auth_headers, login

    tok = login(client, "100000000003", "deleg123")     # مندوب
    due = client.get("/api/renewals/due/permits", headers=auth_headers(tok))
    if due.status_code != 200 or not due.json():
        pytest.skip("لا إقامات مستحقّة في بيانات الاختبار")
    item = due.json()[0]
    started = client.post("/api/renewals", headers=auth_headers(tok),
                          data={"employee_id": str(item["employee_id"]),
                                "permit_id": str(item["permit_id"])})
    if started.status_code != 201:
        pytest.skip(f"تعذّر فتح معاملة: {started.text[:120]}")
    rid = started.json()["id"]

    gen = client.post(f"/api/renewals/{rid}/gov-contract/generate",
                      headers=auth_headers(tok))
    assert gen.status_code == 200, gen.text
    body = gen.json()
    assert "html" not in body, (
        "ما زال يُعاد HTML — الواجهة ستبني العقد بنفسها وتفقد الشعار والتخطيط"
    )
    assert body["format"] in ("pdf", "docx")
    assert body.get("document_id"), "لا مستند يُنزَّل"

    dl = client.get(f"/api/documents/{body['document_id']}/download",
                    headers=auth_headers(tok))
    assert dl.status_code == 200, dl.text
    assert dl.content[:2] == b"PK" or dl.content[:4] == b"%PDF", (
        "المُنزَّل ليس ملف وورد ولا PDF"
    )
    if dl.content[:2] == b"PK":
        z = zipfile.ZipFile(io.BytesIO(dl.content))
        assert any(n.startswith("word/media/") for n in z.namelist()), (
            "الملف المُنزَّل بلا شعار الهيئة"
        )
