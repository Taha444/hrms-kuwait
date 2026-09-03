# -*- coding: utf-8 -*-
"""V-F — الحقل المرجعي يُملأ من الخادم، لا من ذاكرة المستخدم.

**التحقيق**: قالت المراجعة إن ``REQSHIFT`` «لا يعمل» ورجّحت إعداًدا
ناقًصا. والفحص أظهر أن الإعداد قائم: ورديتان في البذرة، ومخطّط كامل،
وأثر تشغيلي يكتب الوردية عند الاعتماد.

**والعطل الحقيقي في مكان آخر**: سبعة حقول من نوع ``*_ref`` كانت تُعرض
حقل رقم. أي أن النموذج يسأل الموظف: «الوردية المطلوبة: ___» وينتظر منه
معرّف قاعدة البيانات — رقًما لا يعرفه ولا تعرضه أي شاشة.

فالنموذج غير صالح للاستعمال مهما اكتمل الإعداد خلفه. وهذا فرق جوهري:
«إعداد ناقص» يُحَل بإدخال بيانات، و«حقل يسأل عمّا لا يُسأل عنه إنسان»
يُحَل بشيفرة.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")
HR_C2 = ("200000000002", "hr12345")

#: الأنواع المرجعية التي يملؤها الخادم، وحقولها في المخطّطات.
REF_TYPES = ("branch_ref", "shift_ref", "license_ref")


def _schema(client, creds, code):
    hdr = auth_headers(login(client, *creds))
    r = client.get(f"/api/requests/types/{code}/schema", headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["schema"]


def _ref_fields(schema):
    return [f for f in (schema.get("fields") or [])
            if str(f.get("type", "")).endswith("_ref")]


def test_the_shift_request_actually_has_a_reference_field():
    """الادّعاءات كلها فارغة لو لم يعد النوع يحمل حقًلا مرجعًيا."""
    from app import form_schemas

    fields = form_schemas.get_schema("REQSHIFT")["fields"]
    assert any(f["type"] == "shift_ref" for f in fields), (
        "REQSHIFT لم يعد فيه حقل وردية — راجع الاختبار لا الشيفرة"
    )


def test_a_reference_field_arrives_with_named_options(client):
    """**جوهر الإصلاح**: خيارات بأسماء، لا خانة رقم."""
    schema = _schema(client, HR, "REQSHIFT")
    refs = _ref_fields(schema)
    assert refs, "لا حقول مرجعية في المخطّط"

    shift = next(f for f in refs if f["type"] == "shift_ref")
    opts = shift.get("options") or []
    assert opts, f"الحقل المرجعي بلا خيارات: {shift}"
    for o in opts:
        assert isinstance(o.get("value"), int), o
        assert o.get("label") and not str(o["label"]).isdigit(), (
            f"التسمية رقم لا اسم: {o}"
        )


def test_every_reference_type_is_filled_not_just_one(client):
    """الفرع والترخيص كالوردية — العلاج على النوع لا على حقل بعينه."""
    hdr = auth_headers(login(client, *HR))
    all_schemas = client.get("/api/requests/types-schemas", headers=hdr).json()

    seen = set()
    for code, schema in all_schemas.items():
        for f in _ref_fields(schema):
            ftype = f["type"]
            if ftype not in REF_TYPES:
                continue          # employee_ref له مصدره الخاص
            seen.add(ftype)
            assert "options" in f, f"{code}.{f['code']} ({ftype}) بلا خيارات"
    assert seen, "لم يُفحص أي نوع مرجعي — القياس فارغ"


def test_options_do_not_cross_company_lines(client):
    """**خيارات شركة لا تظهر لأخرى.**

    والخطر هنا بنيويّ لا عرَضيّ: ``SCHEMAS`` قاموس على مستوى الوحدة
    مشترك بين كل الطلبات. فحقن الخيارات فيه مباشرًة يجعل الطلب التالي —
    من شركة أخرى — يقرأ فروع الأولى. ولهذا تُبنى نسخة لا يُعدَّل الأصل.
    """
    c1 = _schema(client, HR, "REQTRANS")
    c2 = _schema(client, HR_C2, "REQTRANS")

    def branch_ids(schema):
        for f in _ref_fields(schema):
            if f["type"] == "branch_ref":
                return {o["value"] for o in (f.get("options") or [])}
        return set()

    a, b = branch_ids(c1), branch_ids(c2)
    assert a and b, f"إحدى الشركتين بلا فروع: {a} / {b}"
    assert not (a & b), f"فروع مشتركة بين شركتين: {a & b}"


def test_the_shared_schema_dict_is_not_mutated(client):
    """والدليل المباشر: الأصل يبقى بلا خيارات بعد النداءات."""
    from app import form_schemas

    _schema(client, HR, "REQSHIFT")
    raw = form_schemas.SCHEMAS["REQSHIFT"]
    shift = next(f for f in raw["fields"] if f["type"] == "shift_ref")
    assert "options" not in shift, (
        "حُقنت خيارات شركة في القاموس المشترك — الطلب التالي يقرؤها"
    )


def test_an_empty_reference_says_setup_required_not_nothing(client):
    """الحماية §3 — «إعداد مطلوب» مفهوم بدل نموذج مكسور.

    شركة بلا ورديات: الحقل يقول ما ينقص ولمن، ولا يترك خانة صامتة.
    """
    from app.ref_options import fill_schema_options

    db = SessionLocal()
    try:
        empty_company = db.scalar(select(models.Company.id).where(
            ~models.Company.id.in_(select(models.Shift.company_id))))
        schema = {"fields": [{"code": "requested_shift_id", "type": "shift_ref",
                              "label": "الوردية المطلوبة"}]}
        # شركة غير موجودة تُعطي الحالة نفسها: لا خيارات
        filled = fill_schema_options(db, schema, empty_company or 999999)
    finally:
        db.close()

    field = filled["fields"][0]
    assert not field.get("options")
    assert field.get("setup_required"), "لا رسالة تشرح الفراغ"
    assert "ورديات" in field["setup_required"], field["setup_required"]
