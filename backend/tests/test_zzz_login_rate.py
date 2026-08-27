# -*- coding: utf-8 -*-
"""حدّ محاولات الدخول — يبطئ من يخمّن لا من يعرف كلمته.

خلف وكيل يتقاسم مكتب كامل عنوانًا واحًدا. وكان العدّاد يحسب المحاولات
الناجحة أيًضا: أحد عشر موظًفا يدخلون في دقيقة صباًحا — كلهم بكلمات صحيحة —
فيُمنع الحادي عشر برسالة «محاولات كثيرة». عيب لا يظهر في اختبار مستخدم
واحد، ويظهر كل صباح عند العميل.
"""
from __future__ import annotations

import pytest

from app.routers import auth as auth_router

EMP = ("100000000101", "emp12345")


@pytest.fixture(autouse=True)
def _rate_limit_on():
    """المجموعة تعطّل حدّ المعدّل عمًدا (conftest) كي تُكرِّر بقية الاختبارات
    الدخول بحرّية. فتشغيله هنا وحده هو ما يجعل هذه الاختبارات تقيس شيًئا."""
    from app.config import settings
    was = settings.rate_limit_enabled
    settings.rate_limit_enabled = True
    auth_router._login_fails.clear()
    yield
    auth_router._login_fails.clear()
    settings.rate_limit_enabled = was

def _login(client, civil_id, password):
    return client.post("/api/auth/login",
                       json={"civil_id": civil_id, "password": password})


def test_successful_logins_do_not_consume_the_budget(client):
    """مكتب كامل يدخل صباًحا بكلمات صحيحة — لا يُمنع أحد."""
    for i in range(_limit() + 5):
        r = _login(client, *EMP)
        assert r.status_code == 200, (
            f"مُنع دخول صحيح رقم {i + 1} برسالة: {r.text[:120]}"
        )


def test_failed_logins_are_throttled(client):
    """التخمين يُبطأ: بعد الحصّة يردّ 429 لا 401."""
    seen_429 = False
    for _ in range(_limit() + 3):
        r = _login(client, EMP[0], "كلمة-خاطئة")
        if r.status_code == 429:
            seen_429 = True
            break
        assert r.status_code in (401, 423), r.text
    assert seen_429, "التخمين المتكرّر لم يُبطأ إطلاًقا"


def test_unknown_account_probes_are_throttled(client):
    """تعداد الحسابات ليس بلا تكلفة — الفحص على رقم غير موجود يُحسب."""
    for _ in range(_limit()):
        _login(client, "999999999999", "أي-شيء")
    r = _login(client, "999999999998", "أي-شيء")
    assert r.status_code == 429, "تعداد الأرقام المدنية مرّ بلا حدّ"


def test_counter_does_not_grow_without_bound():
    """قاموس العدّاد يُنظَّف: خدمة تعمل شهوًرا لا تحتفظ بكل عنوان زارها."""
    import time
    old = time.time() - auth_router._RATE_WINDOW - 10
    for i in range(2100):
        auth_router._login_fails[f"10.0.{i // 256}.{i % 256}"] = [old]
    auth_router._rate_check("1.2.3.4")
    assert len(auth_router._login_fails) < 2100, (
        "العناوين الخاملة لم تُنظَّف — القاموس ينمو بلا حدّ"
    )


def _limit() -> int:
    return auth_router._RATE_MAX


@pytest.fixture(autouse=True)
def _unlock_probed_accounts():
    """يُعيد عدّاد الإخفاق والقفل بعد كل اختبار.

    هذه الاختبارات تُخفق الدخول عمًدا، والإخفاق يقفل الحساب بعد خمس مرات.
    فبلا إعادة الحالة تسقط كل اختبارات ما بعدها لسبب لا علاقة له بها —
    وهو أسوأ نوع من الإخفاق: يشير إلى المكان الخطأ.
    """
    yield
    from app import models
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        from sqlalchemy import or_
        for u in db.query(models.User).filter(or_(
                models.User.failed_attempts > 0,
                models.User.locked_until.isnot(None))).all():
            u.failed_attempts = 0
            u.locked_until = None
        db.commit()
    finally:
        db.close()
