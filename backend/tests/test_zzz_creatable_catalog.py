# -*- coding: utf-8 -*-
"""BKL-05 — ما تعرضه شاشة «طلب جديد» هو ما يقبله الخادم.

البلاغ: الواجهة تعرض أكواًدا قديمة (V1.3) والخادم يرفضها. والمستخدم يملأ
نموذًجا كامًلا ثم يُردّ برسالة عن «كود مهجور» لا يعرف ما هو ولا كيف يتجنّبه.

والأنواع القديمة تبقى في الكتالوج الكامل — الطلبات التاريخية مبنيّة عليها
ولا تُقرأ بدونها. الممنوع أن تظهر في **الإنشاء** وحده.

والفحص هنا **بالمقارنة الفعلية**: يُقرأ الكتالوج المعروض، ثم يُسأل الخادم
عن كل كود فيه. أي كود يُعرض ويُرفض هو العطل بعينه.
"""
from __future__ import annotations

import pytest

from app import models
from app.database import SessionLocal
from app.routers.requests import superseded_by

from .conftest import auth_headers, login

EMPLOYEE = ("100000000101", "emp12345")
HR = ("100000000002", "hr12345")


def _catalog(client, creds, **params):
    hdr = auth_headers(login(client, *creds))
    r = client.get("/api/requests/types", headers=hdr, params=params)
    assert r.status_code == 200, r.text
    return r.json(), hdr


def _codes(payload) -> list[str]:
    """الكتالوج قد يعود مسطًَّحا أو مجمًَّعا حسب الوسيط."""
    if isinstance(payload, dict):
        out = []
        for group in payload.values():
            if isinstance(group, list):
                out += [x.get("code") for x in group if isinstance(x, dict)]
        return [c for c in out if c]
    return [x.get("code") for x in payload if isinstance(x, dict) and x.get("code")]


def test_creatable_catalog_contains_no_superseded_code(client):
    """جوهر البند: لا كود مهجور في شاشة الإنشاء.

    والفحص بنفس الدالة التي يستعملها POST للرفض — لا بنسخة منها.
    """
    payload, _ = _catalog(client, HR, creatable_only=True)
    codes = _codes(payload)
    assert codes, "كتالوج الإنشاء فارغ — تغيّر شكل الرد"

    db = SessionLocal()
    try:
        offenders = []
        for code in codes:
            replacement = superseded_by(db, 1, code)
            if replacement:
                offenders.append(f"{code} → مهجور لصالح {replacement}")
        assert not offenders, (
            "أكواد مهجورة معروضة للإنشاء:\n" + "\n".join(offenders)
        )
    finally:
        db.close()


def test_full_catalog_still_carries_the_old_codes(client):
    """القديم يبقى للقراءة: طلبات تاريخية مبنيّة عليه لا تُقرأ بدونه.

    إخفاؤه من كل مكان يحلّ عطل الإنشاء ويخلق عطًلا أسوأ — سجلّ لا يُفسَّر.
    """
    creatable, _ = _catalog(client, HR, creatable_only=True)
    full, _ = _catalog(client, HR)
    assert len(_codes(full)) >= len(_codes(creatable)), (
        "الكتالوج الكامل أضيق من كتالوج الإنشاء"
    )


def test_every_offered_type_is_accepted_by_the_server(client):
    """المقارنة الفعلية: ما يُعرض يُقبل.

    لا يكفي أن تتفق الدالتان في الشيفرة — الاختبار يسأل الخادم نفسه، لأن
    المستخدم يسأله لا يسأل الشيفرة.
    """
    payload, hdr = _catalog(client, EMPLOYEE, creatable_only=True)
    codes = _codes(payload)
    assert codes, "الموظف لا يرى أي نوع قابل للإنشاء"

    rejected_as_legacy = []
    for code in codes:
        r = client.post("/api/requests", headers=hdr, json={
            "request_type_code": code, "payload_json": {}})
        # 400 لبيانات ناقصة مقبول — نحن نختبر رفض **النوع** لا رفض الحقول
        text = r.text or ""
        if r.status_code in (400, 409, 422) and (
                "LEGACY" in text.upper() or "مهجور" in text
                or "غير معرّف" in text or "غير معرف" in text):
            rejected_as_legacy.append(f"{code}: {text[:120]}")
    assert not rejected_as_legacy, (
        "أنواع معروضة للإنشاء ويرفضها الخادم:\n" + "\n".join(rejected_as_legacy)
    )


def test_employee_only_sees_types_marked_for_employees(client):
    """الموظف لا يرى النماذج الإدارية الداخلية في شاشته."""
    payload, _ = _catalog(client, EMPLOYEE, creatable_only=True)
    codes = set(_codes(payload))
    db = SessionLocal()
    try:
        for code in codes:
            rt = db.query(models.RequestType).filter(
                models.RequestType.code == code).first()
            if rt is not None:
                assert rt.visible_to_employee, (
                    f"{code} معروض للموظف وهو غير موسوم له"
                )
    finally:
        db.close()


def test_creatable_catalog_has_no_duplicate_codes(client):
    """كود يظهر مرتين يجعل المستخدم يختار بين نسختين من شيء واحد."""
    payload, _ = _catalog(client, HR, creatable_only=True)
    codes = _codes(payload)
    dupes = {c for c in codes if codes.count(c) > 1}
    assert not dupes, f"أكواد مكرّرة في شاشة الإنشاء: {sorted(dupes)}"


@pytest.fixture
def superseded_pair(client):
    """يصنع حالة استبدال حقيقية: نوع قديم وبديله النشط.

    بلا هذه الحالة تمرّ الاختبارات فراًغا — لا يوجد في بيانات البذرة نوع
    مهجور، فالفلتر لا يُختبر أصًلا ويبدو أخضر. واختبار لا يميّز الإصلاح
    من غيابه ليس اختباًرا.
    """
    from app import v15_registry

    db = SessionLocal()
    created = []
    try:
        # نوع له canonical مختلف عن كوده
        legacy = None
        for rt in db.query(models.RequestType).filter(
                models.RequestType.is_active == True).all():   # noqa: E712
            canon = v15_registry.resolve_request(rt.code).get("canonical")
            if canon and canon != rt.code:
                legacy = rt
                canonical_code = canon
                break
        assert legacy is not None, "لا نوع له canonical مختلف — تغيّر السجلّ"

        # البديل غير موجود عادًة (WF-* معرّفات مسار لا أنواع)، فننشئه
        existing = db.query(models.RequestType).filter(
            models.RequestType.code == canonical_code).first()
        if existing is None:
            repl = models.RequestType(
                code=canonical_code, name=f"بديل {legacy.name}",
                category=legacy.category, is_active=True,
                company_id=None, visible_to_employee=legacy.visible_to_employee)
            db.add(repl)
            db.commit()
            created.append(repl.id)
        yield legacy.code, canonical_code
    finally:
        for rid in created:
            obj = db.get(models.RequestType, rid)
            if obj:
                db.delete(obj)
        db.commit()
        db.close()


def test_a_superseded_type_disappears_from_the_create_screen(client,
                                                             superseded_pair):
    """الحالة الفعلية: وُجد بديل نشط ⇒ القديم يختفي من الإنشاء.

    وهذا ما يُثبت أن الفلتر يعمل — لا مجرّد أن الشيفرة تقرأ صحيحة.
    """
    legacy_code, canonical_code = superseded_pair
    db = SessionLocal()
    try:
        assert superseded_by(db, 1, legacy_code) == canonical_code, (
            "لم تتحقّق حالة الاستبدال — الفكستشر لم يصنع ما يزعم"
        )
    finally:
        db.close()

    payload, _ = _catalog(client, HR, creatable_only=True)
    codes = _codes(payload)
    assert legacy_code not in codes, (
        f"الكود المهجور {legacy_code} ما زال معروًضا للإنشاء"
    )


def test_the_superseded_type_is_still_readable_in_the_full_catalog(
        client, superseded_pair):
    """القديم يبقى للقراءة: طلبات تاريخية مبنيّة عليه."""
    legacy_code, _ = superseded_pair
    payload, _ = _catalog(client, HR)
    assert legacy_code in _codes(payload), (
        f"{legacy_code} اختفى من الكتالوج الكامل — الطلبات التاريخية لا تُفسَّر"
    )


def test_server_refuses_the_superseded_type_it_no_longer_offers(
        client, superseded_pair):
    """الطرفان متّسقان في الاتجاهين: ما لا يُعرض لا يُقبل."""
    legacy_code, _ = superseded_pair
    hdr = auth_headers(login(client, *HR))
    r = client.post("/api/requests", headers=hdr, json={
        "request_type_code": legacy_code, "payload_json": {}})
    assert r.status_code != 201, (
        f"الخادم قبل نوًعا مهجوًرا لا يعرضه الكتالوج: {legacy_code}"
    )
