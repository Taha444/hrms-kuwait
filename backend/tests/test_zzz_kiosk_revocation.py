# -*- coding: utf-8 -*-
"""زٌر يَعِد بالإبطال ولا يُبطل — ورمُز فرٍع دائم.

**العطل المقيس**: ``make_static_qr_token`` كان ``deterministic`` بلا
انتهاء ولا مُعرِّف ولا صلة بمفتاح الشاشة — «لا يتغيّر إطلاقًا» بنصّ شرحه.

فتدويُر مفتاح الشاشة (``rotate_kiosk_key``) يمنع **جلَب رمٍز جديد** من
الرابط، **ولا يمسّ ما خرج**: من صوّر الشاشة مرًّة يبصم بها إلى الأبد.
ووصُف الزرّ يقول «القديم يُبطل فورًا؛ أي شاشة تستخدمه ستنقطع» — وهو يصف
المفتاح لا الرمز.

**والدفاع المعلَن كان الـgeofence**، وشرُح الرمز يحيل إليه صراحًة:
«الحماية من الاستخدام عن بُعد تعتمد على الـgeofence لا على تغيّر الرمز».
والقياس: ``_check_geofence`` يقيس المسافة **إن أرسل العميل إحداثيات**،
وموظُف نمط ``qr`` غير مُلزَم بإرسالها. فالدفاع الذي يُبرِّر دواَم الرمز
**اختيارٌي بيد المتّصل**.
"""
from __future__ import annotations

import inspect

import pytest
from sqlalchemy import select

from app import models, qr_token
from app.database import SessionLocal
from app.routers import attendance as A
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
MGR = ("100000000001", "manager123")


def _branch_of_employee() -> tuple[int, str | None]:
    db = SessionLocal()
    try:
        user = db.scalar(select(models.User).where(models.User.civil_id == EMP[0]))
        emp = db.get(models.Employee, user.employee_id)
        br = db.get(models.Branch, emp.branch_id) if emp.branch_id else None
        if br is None:
            br = db.scalar(select(models.Branch).where(
                models.Branch.company_id == emp.company_id))
        return br.id, br.kiosk_key
    finally:
        db.close()


def _set_key(branch_id: int, key: str | None) -> None:
    db = SessionLocal()
    try:
        db.get(models.Branch, branch_id).kiosk_key = key
        db.commit()
    finally:
        db.close()


def test_the_token_carries_the_key_fingerprint():
    """الرمز يحمل بصمة المفتاح — **ولا يحمل المفتاح نفسه**.

    فالرمز يُعرَض على شاشٍة ويُصوَّر، وحمُله فيه تسريٌب له.
    """
    token = qr_token.make_static_qr_token(7, "مفتاٌح-سرّي")
    payload = qr_token.decode(token, "qr")
    assert payload.get("kv"), "الرمز بلا بصمة — فلا يُبطله تدوير"
    assert "مفتاٌح-سرّي" not in token, "المفتاح نفسه في الرمز"
    assert payload["kv"] == qr_token.kiosk_key_fingerprint("مفتاٌح-سرّي")


def test_rotating_the_key_changes_the_fingerprint():
    """ومفتاٌح جديد بصمٌة جديدة — وإلا لم يُبطل شيًئا."""
    assert (qr_token.kiosk_key_fingerprint("أ")
            != qr_token.kiosk_key_fingerprint("ب"))


def test_a_token_issued_before_rotation_is_refused(client):
    """**جوهر البند**: رمٌز صُوِّر قبل التدوير لا يعمل بعده.

    وهذا هو معنى «الإبطال» الذي كان الزرّ يَعِد به ولا يفعله.
    """
    branch_id, was = _branch_of_employee()
    _set_key(branch_id, "المفتاح-القديم")
    old_token = qr_token.make_static_qr_token(branch_id, "المفتاح-القديم")
    try:
        _set_key(branch_id, "المفتاح-الجديد")
        r = client.post("/api/attendance/validate-qr",
                        headers=auth_headers(login(client, *EMP)),
                        json={"qr_token": old_token, "lat": 29.3, "lng": 47.9})
        assert r.status_code == 403, (r.status_code, r.text[:200])
        assert "أُبطل" in r.text, r.text[:200]
    finally:
        _set_key(branch_id, was)


def test_the_current_token_still_works(client):
    """والرمز الحالي يعمل — الإبطال لا يُعطّل الشاشة القائمة."""
    branch_id, was = _branch_of_employee()
    _set_key(branch_id, "مفتاٌح-حالّي")
    token = qr_token.make_static_qr_token(branch_id, "مفتاٌح-حالّي")
    try:
        r = client.post("/api/attendance/validate-qr",
                        headers=auth_headers(login(client, *EMP)),
                        json={"qr_token": token, "lat": 29.3, "lng": 47.9})
        # قد يُردّ لأسباب أخرى (نمط الحضور، النطاق) — المهمّ ألّا يكون سبُبه
        # الإبطال، وإلا كان الحارس يُعطّل الشاشة الحيّة.
        assert "أُبطل" not in r.text, r.text[:200]
    finally:
        _set_key(branch_id, was)


def test_a_legacy_token_without_a_fingerprint_is_refused(client):
    """**ورمٌز قديٌم بلا بصمة لا يُقبَل تسامًحا.**

    فقبوُله يُبقي الثغرة مفتوحًة لكل ما صدر قبل هذا الإصلاح — وهو بالضبط
    ما جئنا نُبطله. وشاشُة الفرع تجلب رمًزا جديًدا عند تحميلها، فالكلفة
    إعادُة فتح الشاشة لا تعطُّل الحضور.
    """
    branch_id, was = _branch_of_employee()
    _set_key(branch_id, "مفتاح")
    import jwt as _jwt

    from app.config import settings

    legacy = _jwt.encode({"branch_id": branch_id, "type": "qr", "static": True},
                         settings.secret_key, algorithm=settings.algorithm)
    try:
        r = client.post("/api/attendance/validate-qr",
                        headers=auth_headers(login(client, *EMP)),
                        json={"qr_token": legacy, "lat": 29.3, "lng": 47.9})
        assert r.status_code == 403, (r.status_code, r.text[:200])
        assert "أُبطل" in r.text, r.text[:200]
    finally:
        _set_key(branch_id, was)


def test_the_declared_defence_is_still_optional_for_qr_mode():
    """**وما لم يُصلَح يُقال لا يُسكَت عنه.**

    شرُح الرمز كان يحيل حمايته إلى الـgeofence، وهو يقيس المسافة **إن
    أرسل العميل إحداثيات**. فموظُف نمط ``qr`` يُسقطها فلا تُقاس مسافة.

    ولم تُجعَل الإحداثيات إلزامية هنا: فروٌع كثيرة بلا إحداثيات مسجَّلة
    (أحٌد وعشرون في بيانات العميل)، وإلزاُمها يوقف الحضور فيها كلّها. وهو
    قراٌر للمالك لا أثٌر جانبيّ لإصلاح الإبطال.
    """
    src = inspect.getsource(A._check_geofence)
    assert "needs_gps" in src, "تغيّرت بنية الفحص — يُعاد تقييم هذا الحارس"
    # يبقى الشرط قائًما: القياس معلٌَّق على وصول الإحداثيات.
    assert "if lat is not None and lng is not None" in src
