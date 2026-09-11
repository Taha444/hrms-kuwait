# -*- coding: utf-8 -*-
"""طريقان إلى الحقيقة نفسها، وأحدهما بلا ضمانات.

``/api/pro/deprecation-notice`` يعلن بنصّه: «صفحة PRO Transactions القديمة
موقوفة… **الاستخدام الوحيد المُعتمد** للإقامة/الإذن هو Residency Renewals».
والواجهُة محقٌّة في تجاهل العنقود كلّه — سبعُة مسارات لا تناديها.

**لكنّ المسارات ما زالت حيًّة تكتب.** و``POST /pro/permits/{id}/renew``
يكتب ``Permit.expiry_date`` مباشرًة: لا عقَد حكومي، ولا توقيَع طرفين، ولا
فحَص اكتمال، ولا قراءَة مستنٍد نهائي — وهي الضماناُت التي بُنيت دورُة
التجديد لأجلها.

و``manage_permits`` يحملها **المندوب**: الفاعُل الذي وُضعت الدورة لتحكمه.
فمندوٌب له معاملٌة مفتوحة يجدّد الإقامة من الباب القديم، **فتبقى المعاملة
مفتوحًة على بياناٍت بطلت** — والمعاملة وإقامتُها يتناقضان، وهو عين ما
يمنعه ``hrms-renewal-propagation``: «ولا يبقى جزٌء من النظام شايف التاريخ
القديم وجزٌء آخر شايف الجديد».

**والإعلاُن لا يُغني عن الفرض**: قاعدٌة مكتوبٌة في إشعاٍر ولا يحرسها شيء
ليست قاعدة.

والشرُط من ``_open_case_for_permit`` نفسها — المصدُر الواحد الذي يحتكم
إليه حارُس الإنشاء وقائمُة المستحقّين — لا نسخٌة ثالثة منه. ولا يُسَدّ
الباب حيث لا معاملة: تصحيُح إقامٍة لا ملّف لها يبقى ممكًنا.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import delete as sa_delete, select

from app import models
from app.clock import today as kuwait_today
from app.database import SessionLocal
from tests.conftest import auth_headers, login

PRO = ("100000000003", "deleg123")


def _a_permit() -> models.Permit | None:
    db = SessionLocal()
    try:
        return db.scalar(select(models.Permit).where(
            models.Permit.company_id == 1,
            models.Permit.kind == "residency"))
    finally:
        db.close()


def _open_case(permit: models.Permit) -> int:
    from app.routers import renewals as R

    db = SessionLocal()
    try:
        rn = models.ResidencyRenewal(
            company_id=permit.company_id, employee_id=permit.employee_id,
            permit_id=permit.id, status=R.R.PENDING_MANAGER)
        db.add(rn)
        db.commit()
        return rn.id
    finally:
        db.close()


def _drop_case(rid: int) -> None:
    db = SessionLocal()
    try:
        db.execute(sa_delete(models.ResidencyRenewal).where(
            models.ResidencyRenewal.id == rid))
        db.commit()
    finally:
        db.close()


def _expiry(permit_id: int):
    db = SessionLocal()
    try:
        return db.get(models.Permit, permit_id).expiry_date
    finally:
        db.close()


# ---------------------------------------------------------------------------
# الباب القديم لا يفتح على معاملٍة مفتوحة
# ---------------------------------------------------------------------------

def test_the_legacy_path_refuses_while_a_case_is_open(client):
    """**جوهر البند**: لا تجديَد مباشٌر لإقامٍة لها معاملٌة مفتوحة."""
    permit = _a_permit()
    if permit is None:
        pytest.skip("لا إقامَة في هذه القاعدة")

    was = _expiry(permit.id)
    rid = _open_case(permit)
    try:
        target = (kuwait_today() + timedelta(days=700)).isoformat()
        r = client.post(f"/api/pro/permits/{permit.id}/renew",
                        params={"expiry_date": target},
                        headers=auth_headers(login(client, *PRO)))
        assert r.status_code == 409, (r.status_code, r.text[:300])
        assert str(rid) in r.text, "لا يسمّي المعاملة التي يُحال إليها"
        assert _expiry(permit.id) == was, "كُتب التاريخ رغم الرفض"
    finally:
        _drop_case(rid)


def test_the_refusal_names_where_to_go(client):
    """**ورفٌض لا يقول أين المسار ليس إرشاًدا.**

    فالرسالُة تسمّي المعاملة وشاشَتها، لا تقول «غير مسموح» وتسكت.
    """
    permit = _a_permit()
    if permit is None:
        pytest.skip("لا إقامَة في هذه القاعدة")

    rid = _open_case(permit)
    try:
        r = client.post(f"/api/pro/permits/{permit.id}/renew",
                        params={"expiry_date":
                                (kuwait_today() + timedelta(days=700)).isoformat()},
                        headers=auth_headers(login(client, *PRO)))
        assert "تجديد الإقامات" in r.text, r.text[:300]
    finally:
        _drop_case(rid)


def test_a_permit_with_no_case_can_still_be_corrected(client):
    """**والحارس لا يسدّ ما لا يتفرّق**: إقامٌة بلا ملّف تبقى قابلًة للتصحيح.

    فالمنُع لعلٍّة — تناقُض المعاملة مع إقامتها — لا لذات المسار.
    """
    permit = _a_permit()
    if permit is None:
        pytest.skip("لا إقامَة في هذه القاعدة")

    # لا معاملَة مفتوحة: يُتحقَّق بالقياس لا بالافتراض.
    from app.routers.renewals import _open_case_for_permit

    db = SessionLocal()
    try:
        if _open_case_for_permit(db, permit.id) is not None:
            pytest.skip("لهذه الإقامة معاملٌة مفتوحة في هذه القاعدة")
    finally:
        db.close()

    was = _expiry(permit.id)
    target = (kuwait_today() + timedelta(days=365))
    try:
        r = client.post(f"/api/pro/permits/{permit.id}/renew",
                        params={"expiry_date": target.isoformat()},
                        headers=auth_headers(login(client, *PRO)))
        assert r.status_code == 200, r.text[:300]
        assert _expiry(permit.id) == target
    finally:
        db = SessionLocal()
        try:
            db.get(models.Permit, permit.id).expiry_date = was
            db.commit()
        finally:
            db.close()


def test_the_condition_comes_from_its_one_source():
    """والشرُط من ``_open_case_for_permit`` لا نسخٌة ثالثة منه."""
    import inspect

    from app.routers import pro as P

    src = inspect.getsource(P.renew_permit)
    assert "_open_case_for_permit" in src, "شرٌط مكتوٌب بالي;د للمعاملة المفتوحة"
    assert "ResidencyRenewal" not in src, "استعلاٌم ثاٍن عن المعاملات"


def test_the_deprecation_notice_still_declares_one_approved_path():
    """**وحارٌس يفرض إعلاًنا يُقاس أن الإعلان باٍق.**

    فلو رُفع الإيقاف وعاد المسار معتمًدا، سقط الحارس معلًنا أنه يُراجَع —
    لا أن يفرض قاعدًة لم تبقَ.
    """
    from app.routers.pro import deprecation_notice

    out = deprecation_notice()
    assert out["deprecated"] is True
    assert "/api/renewals/*" in out["recommended_endpoints"]
