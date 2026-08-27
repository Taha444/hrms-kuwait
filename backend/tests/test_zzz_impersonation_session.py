# -*- coding: utf-8 -*-
"""جلسة الانتحال — هل تبقى موسومة طوال عمرها؟

الانتحال موجود ليجيب سؤاًلا واحًدا: **من فعل هذا حًقا؟** فإن ضاع وسم
الانتحال في منتصف الجلسة، صارت الأفعال مقيَّدة على المُنتحَل وحده — وهذا
أسوأ من غياب الميزة، لأن السجل يبدو سليًما وهو مضلِّل.

رمز الدخول يعيش 30 دقيقة، والواجهة تجدّده تلقائيًّا عند أول 401. فأي جلسة
انتحال تتجاوز نصف ساعة تمرّ بالتجديد حتًما.
"""
from __future__ import annotations

from .conftest import auth_headers, login

SUPER = ("000000000000", "admin123")


def _impersonate(client, civil_id="100000000101"):
    tok = login(client, *SUPER)
    from app import models
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        target = db.query(models.User).filter(
            models.User.civil_id == civil_id).one()
        tid = target.id
    finally:
        db.close()
    r = client.post(f"/api/users/{tid}/impersonate", headers=auth_headers(tok),
                    params={"reason": "فحص بلاغ"})
    assert r.status_code == 200, r.text
    return r.json()


def test_impersonation_marker_survives_token_refresh(client):
    """التجديد لا يحوّل جلسة انتحال إلى جلسة عادية بصمت."""
    imp = _impersonate(client)

    # الوسم موجود في أول رمز
    assert client.post("/api/users/impersonate-end",
                       headers=auth_headers(imp["access_token"])).status_code == 200

    # ثم تمرّ 30 دقيقة وتُجدِّد الواجهة الرمز تلقائيًّا
    r = client.post("/api/auth/refresh",
                    json={"refresh_token": imp["refresh_token"]})
    assert r.status_code == 200, r.text
    refreshed = r.json()["access_token"]

    from app.security import decode_token
    assert decode_token(refreshed).get("impersonator_id") is not None, (
        "التجديد جرّد الجلسة من وسم الانتحال: كل فعل بعده يُقيَّد على "
        "المُنتحَل وحده، ولا أثر لمن فعله حًقا"
    )

    # وأثر ذلك العملي: إنهاء الانتحال يصير مستحيًلا
    assert client.post("/api/users/impersonate-end",
                       headers=auth_headers(refreshed)).status_code == 200, (
        "بعد التجديد لم يعد الرمز رمز انتحال، فتعذّر إنهاؤه"
    )


def test_impersonation_marker_survives_company_selection(client):
    """اختيار الشركة داخل جلسة انتحال لا يجرّدها من وسمها.

    هذا المسار أسرع وقوًعا من التجديد: الواجهة تمسح الشركة النشطة عند بدء
    الانتحال، فمُنتحَلٌ متعدّد الشركات يُوجَّه إلى شاشة الاختيار فوًرا.
    """
    from app import models
    from app.database import SessionLocal
    from app.security import decode_token

    db = SessionLocal()
    try:
        owner = db.query(models.User).filter(
            # المشروع يمنح رؤية الشركات بالدور لا بعلَم is_cross_company
            models.User.role == "company_owner",
        ).first()
        if not owner:
            import pytest
            pytest.fail("لا مالك شركات في بيانات الاختبار — المسار غير مغطى")
        oid, ocid = owner.id, owner.civil_id
    finally:
        db.close()

    imp = _impersonate(client, ocid)
    cos = client.get("/api/auth/my-companies",
                     headers=auth_headers(imp["access_token"]))
    assert cos.status_code == 200, cos.text
    companies = cos.json()
    cid = (companies[0]["id"] if isinstance(companies, list)
           else companies["companies"][0]["id"])

    r = client.post("/api/auth/select-company", params={"company_id": cid},
                    headers=auth_headers(imp["access_token"]))
    assert r.status_code == 200, r.text
    after = r.json()["access_token"]
    assert decode_token(after).get("impersonator_id") is not None, (
        "اختيار الشركة جرّد الجلسة من وسم الانتحال من أول خطوة"
    )
    assert client.post("/api/users/impersonate-end",
                       headers=auth_headers(after)).status_code == 200


def test_audit_records_the_real_actor_after_refresh(client):
    """السجل يحفظ من فعل حًقا، لا من انتُحلت هويته.

    هذه غاية الميزة كلها: بلا هذا القيد يبدو السجل سليًما وهو مضلِّل — وهذا
    أسوأ من غياب الانتحال أصًلا.
    """
    from app import models
    from app.database import SessionLocal
    from app.security import decode_token

    imp = _impersonate(client)
    r = client.post("/api/auth/refresh",
                    json={"refresh_token": imp["refresh_token"]})
    refreshed = r.json()["access_token"]
    actor_id = decode_token(refreshed)["impersonator_id"]

    client.post("/api/users/impersonate-end", headers=auth_headers(refreshed))

    db = SessionLocal()
    try:
        row = db.query(models.AuditLog).filter(
            models.AuditLog.action == "impersonate_end"
        ).order_by(models.AuditLog.id.desc()).first()
        assert row is not None, "إنهاء الانتحال لم يُسجَّل"
        assert row.user_id == actor_id, (
            f"السجل قيّد الفعل على {row.user_id} بدل الفاعل الحقيقي {actor_id}"
        )
    finally:
        db.close()


def test_impersonation_dies_when_impersonator_loses_authority(client):
    """من سُحبت منه الإدارة العليا لا تستمر جلسة انتحاله أسبوعين.

    رمز التجديد يعيش 14 يوًما. بلا مراجعة الصلاحية عند كل تجديد، يبقى من
    عُزل يتصرّف باسم غيره حتى انتهاء الرمز.
    """
    from app import models
    from app.database import SessionLocal

    imp = _impersonate(client)
    db = SessionLocal()
    try:
        admin = db.query(models.User).filter(
            models.User.civil_id == SUPER[0]).one()
        admin.is_active = False
        db.commit()
        r = client.post("/api/auth/refresh",
                        json={"refresh_token": imp["refresh_token"]})
        assert r.status_code == 401, (
            "جلسة انتحال استمرّت بعد تعطيل حساب المُنتحِل"
        )
    finally:
        admin = db.query(models.User).filter(
            models.User.civil_id == SUPER[0]).one()
        admin.is_active = True
        db.commit()
        db.close()
