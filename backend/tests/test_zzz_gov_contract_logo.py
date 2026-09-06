# -*- coding: utf-8 -*-
"""شعار الهيئة يبقى في العقد المولَّد — بصمًة وموضًعا.

**والقياس سبق الإصلاح**: طُلب استخراج الشعار من الأصل ووضعه في
المولَّد، فقِستُ الاثنين فإذا هو موجود في المولَّد أصًلا — في موضعيه،
وبالبايتات نفسها. فلا شيء يُضاف، والذي يلزم أن **يبقى**.

ومسار التوليد يفكّ ملف الوورد ويُعيد بناءه بعد ملء الحقول. وإعادة بناء
أرشيف ZIP هي بالضبط ما يُسقط ملًفا غير نصّي بصمت: يخرج العقد سليم
النصّ بلا شعار، فيُقدَّم إلى الهيئة ورقًة لا تحمل ختمها.

**ولذلك يُقاس الشعار لا يُفترَض**: بصمته، وعدد مواضعه، وعلاقته في
``document.xml.rels``. أي واحد منها يسقط ⇒ الاختبار يسقط.
"""
from __future__ import annotations

import hashlib
import re
import zipfile
from io import BytesIO
from pathlib import Path

from app import gov_contract_docx as G

MEDIA = "word/media/image1.jpeg"
EMBED = 'r:embed="rId5"'

#: سياق كامل — التوليد يرفض الناقص، فالقياس يحتاج عقًدا يُولَّد فعًلا.
CTX = {
    "employee_name": "أحمد محمود علي", "employee_name_en": "Ahmed Mahmoud Ali",
    "civil_id": "290010112345", "nationality": "مصري",
    "nationality_en": "Egyptian", "passport_number": "A12345678",
    "residence_no": "123456789", "job_title": "بائع", "job_title_en": "Salesman",
    "company_name": "شركة الخليج للتجارة", "company_name_en": "Gulf Trading Co.",
    "company_rep_name": "عبدالله ناصر المطيري",
    "company_rep_name_en": "Abdullah Al-Mutairi",
    "company_civil_id": "270010112345",
    "labour_dept": "العاصمة", "labour_dept_en": "Al Asima",
    "wage": "450", "contract_date": "07/09/2026",
    "contract_start_date": "01/10/2026", "day_name_en": "Monday",
    "probation_days": "100", "annual_leave_days": "30",
    "contract_term_ar": "سنة واحدة", "contract_term_en": "One Year",
    "contract_type_raw": "definite",
}


def _docx_bytes() -> bytes:
    """المستند المولَّد كـdocx — لا PDF، فالمقارنة على بنية الوورد."""
    values, missing = G.build_values(CTX)
    assert not missing, f"سياق القياس ناقص: {missing}"
    return G.fill(values, definite=True)


def _zip(data: bytes) -> zipfile.ZipFile:
    return zipfile.ZipFile(BytesIO(data))


def _original() -> bytes:
    return Path(G.ASSET).read_bytes()


def test_the_logo_file_survives_generation():
    """**جوهر القياس**: الصورة نفسها في المولَّد، لا صورة تشبهها."""
    with _zip(_original()) as z:
        want = z.read(MEDIA)
    with _zip(_docx_bytes()) as z:
        assert MEDIA in z.namelist(), f"سقط الشعار: {z.namelist()}"
        got = z.read(MEDIA)
    assert hashlib.sha256(got).hexdigest() == hashlib.sha256(want).hexdigest(), (
        "الشعار في المولَّد يخالف شعار الهيئة"
    )
    assert len(got) == len(want) > 1000, (len(got), len(want))


def test_the_logo_keeps_both_of_its_places():
    """وفي موضعيه: ترويسة كل صفحة من صفحتَي الجدول.

    وسقوط موضع واحد يخرج عقًدا نصفه مختوم — أصعب اكتشاًفا من سقوطه كلّه.
    """
    with _zip(_original()) as z:
        o = z.read("word/document.xml").decode("utf-8")
    with _zip(_docx_bytes()) as z:
        m = z.read("word/document.xml").decode("utf-8")
    for label, needle in (("كتل الرسم", "<w:drawing>"),
                          ("مرجع الصورة", EMBED),
                          ("اسم ملف الصورة", "image1.jpeg")):
        assert m.count(needle) == o.count(needle), (
            f"{label}: الأصل {o.count(needle)} والمولَّد {m.count(needle)}"
        )


def test_the_relationship_that_binds_them_survives():
    """والعلاقة التي تربط الرسم بالملف: بلا ``rId5`` يبقى إطار فارغ."""
    rels = "word/_rels/document.xml.rels"
    with _zip(_docx_bytes()) as z:
        assert rels in z.namelist()
        xml = z.read(rels).decode("utf-8")
    found = re.findall(r'Id="(rId\d+)"[^>]*Target="(media/[^"]+)"', xml)
    assert ("rId5", "media/image1.jpeg") in found, found


def test_no_part_of_the_package_is_lost():
    """**وإعادة بناء الأرشيف تُسقط الأجزاء بصمت** — فتُعدّ كلّها.

    الأصل أربعة عشر جزًءا: المستند، والعلاقات، والأنماط، والخطوط،
    والصورة. ونقص أيّها يفتح ملًفا تالًفا أو بلا تنسيق.
    """
    with _zip(_original()) as z:
        want = set(z.namelist())
    with _zip(_docx_bytes()) as z:
        got = set(z.namelist())
    assert not (want - got), f"أجزاء مفقودة: {sorted(want - got)}"


def test_the_source_template_is_still_the_official_one():
    """ويبقى المصدر ملف الهيئة ببصمته — وإلا فما نُسخ ليس شعارها."""
    assert hashlib.sha256(_original()).hexdigest() == G.OFFICIAL_SHA256
