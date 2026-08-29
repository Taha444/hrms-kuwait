# -*- coding: utf-8 -*-
"""LBL-01..04 — لا تسرّب لقيمة داخلية إلى ما يقرؤه المستخدم.

**العَرَضان الموثَّقان**: «طلب شهادة راتب (V1.3)» في كتالوج الطلبات،
و``indefinite`` خامًّا في شاشة عربية.

**والجذر واحد**: طبقة العرض تطبع القيمة المخزَّنة بلا ترجمة. والقيمة
المخزَّنة تقنية بطبيعتها — ``indefinite`` و``qr`` و``V1.3`` كلها صحيحة في
مكانها وخاطئة في عين القارئ.

**ولماذا الفحص هنا لا في الواجهة**: النصّ يخرج من ثلاثة أفواه — الشاشة،
والتصدير (CSV/XLSX/PDF)، والإشعارات ورسائل الخطأ. وترجمة في الواجهة
وحدها تترك التقرير المصدَّر بأكواده. فيُفحص **ما يصل المستخدم** أًيا كان
مخرجه، لا ما تعرضه شاشة بعينها.
"""
from __future__ import annotations

import re

import pytest
from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")

#: وسم إصدار داخلي: «(V1.3)» وأخواته.
VERSION_MARKER = re.compile(r"\(\s*[Vv]\d+(?:\.\d+)*\s*\)")

#: قيم enum خام لا يجوز أن تصل القارئ كما هي. مكتوبة هنا صراحًة لا
#: مقروءة من الشيفرة: قائمة تُشتقّ من المصدر تُفرَّغ معه فيمرّ الفحص فراًغا.
RAW_ENUMS = ("indefinite", "definite", "pending_hr_verify",
             "awaiting_civil_card", "with_delegate", "in_progress")


def _catalogue_names(db):
    """كل ما يظهر اسًما في كتالوج الطلبات والقوالب."""
    out = []
    for model, fields in ((models.RequestType, ("name", "name_en")),
                          (models.DocumentTemplate, ("name", "name_en"))):
        for row in db.scalars(select(model)).all():
            for f in fields:
                v = getattr(row, f, None)
                if v:
                    out.append((model.__name__, getattr(row, "code", None), f, v))
    return out


def test_no_internal_version_marker_reaches_the_catalogue():
    """LBL-01 — «(V1.3)» لا تعني للمستخدم شيًئا.

    وتوحي بأن ثمّة نسخة أخرى من الطلب عليه أن يختار بينها.
    """
    db = SessionLocal()
    try:
        hits = [x for x in _catalogue_names(db) if VERSION_MARKER.search(x[3])]
    finally:
        db.close()
    assert not hits, f"وسم إصدار داخلي في الكتالوج: {hits[:5]}"


def test_the_marker_check_is_not_vacuous():
    """الكاشف نفسه يُقاس: لو لم يطابق شيًئا لمرّ الفحص دائًما."""
    assert VERSION_MARKER.search("طلب شهادة راتب (V1.3)")
    assert VERSION_MARKER.search("Something (v2.2)")
    assert not VERSION_MARKER.search("طلب شهادة راتب")


def test_the_catalogue_has_no_raw_enum_as_a_name():
    """LBL-02 — الاسم المعروض لا يكون قيمة تقنية."""
    db = SessionLocal()
    try:
        bad = [x for x in _catalogue_names(db)
               if x[3].strip().lower() in RAW_ENUMS]
    finally:
        db.close()
    assert not bad, f"قيمة خام كاسم معروض: {bad[:5]}"


def test_arabic_names_do_not_carry_latin_codes():
    """اسم عربي فيه كود لاتيني بحروف صغيرة = قيمة مخزَّنة تسرّبت.

    والأسماء الإنجليزية مستثناة بطبيعتها، والاختصارات الكبيرة (QR، GPS،
    PDF) ليست تسرًُّبا بل هي ما يقرؤه الناس فعًلا.
    """
    db = SessionLocal()
    try:
        rows = [x for x in _catalogue_names(db) if x[2] == "name"]
    finally:
        db.close()
    bad = []
    for model, code, _f, value in rows:
        if not re.search(r"[؀-ۿ]", value):
            continue                       # ليس اسًما عربًيا
        for token in re.findall(r"[A-Za-z_]{4,}", value):
            if token.islower():
                bad.append((code, value, token))
    assert not bad, f"كود لاتيني داخل اسم عربي: {bad[:5]}"


# ---------------------------------------------------------------------------
# LBL-03 — الفحص يشمل ما يخرج من الـAPI لا الشاشات وحدها
# ---------------------------------------------------------------------------
def _walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


#: حقول تحمل القيمة التقنية **عمًدا** — الواجهة تترجمها، والتصدير يقرأ
#: الحقل المترجَم بجانبها. وجودها ليس تسرًُّبا.
TECHNICAL_FIELDS = ("status", "type", "code", "kind", "severity", "role",
                    "contract_type", "attendance_mode", "category",
                    "entity_type", "related_entity_type", "stage",
                    "decision", "channel", "source", "document_type_code")


def _leaks(payload):
    out = []
    for path, value in _walk(payload):
        leaf = path.rsplit(".", 1)[-1].split("[")[0]
        if leaf in TECHNICAL_FIELDS or leaf.endswith("_code"):
            continue
        if VERSION_MARKER.search(value):
            out.append((path, value))
        elif value.strip().lower() in RAW_ENUMS:
            out.append((path, value))
    return out


@pytest.mark.parametrize("endpoint", [
    "/api/requests/types",
    "/api/tasks/my",
    "/api/renewals",
    "/api/templates",
])
def test_no_raw_value_leaks_through_the_api(client, endpoint):
    """ما يخرج من الـAPI يصل التقرير والتصدير كما يصل الشاشة.

    فالفحص عليه لا على شاشة بعينها: ترجمة في الواجهة وحدها تترك الملف
    المصدَّر بأكواده.
    """
    hdr = auth_headers(login(client, *HR))
    r = client.get(endpoint, headers=hdr)
    if r.status_code == 404:
        pytest.fail(f"{endpoint} غير موجود — حدّث قائمة الفحص")
    assert r.status_code == 200, r.text
    leaks = _leaks(r.json())
    assert not leaks, f"قيم خام في {endpoint}: {leaks[:5]}"


def test_the_leak_detector_catches_a_planted_value():
    """الكاشف يُقاس بقيمة مزروعة — وإلا مرّ على كل شيء."""
    planted = {"title": "طلب شهادة راتب (V1.3)",
               "contract_type": "indefinite",     # حقل تقني: يُتجاهَل
               "label": "indefinite"}             # تسرّب حقيقي
    found = dict(_leaks(planted))
    assert ".title" in found, "لم يلتقط وسم الإصدار"
    assert ".label" in found, "لم يلتقط القيمة الخام"
    assert ".contract_type" not in found, "أبلغ عن حقل تقني مقصود"
