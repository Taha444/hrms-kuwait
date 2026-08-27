# -*- coding: utf-8 -*-
"""لا تُكشف حالة حساب قبل إثبات معرفة كلمته.

كان الردّ 423 «مقفل» و403 «موقوف» يسبق فحص كلمة المرور، بينما يردّ 401 لرقم
غير موجود. فمن يجرّب أرقاًما مدنية بأي كلمة يعرف أيّها يخصّ حساًبا قائًما —
والأرقام المدنية الكويتية منظَّمة يسهل توليدها، فيُبنى كشف موظفي الشركة من
الخارج.

والحلّ ليس إخفاء الحالة عن الجميع: موقوفٌ يقرأ «الرقم أو كلمة المرور غير
صحيحة» يظنّ العطل في كلمته ويستنزف محاولاته حتى القفل. الحلّ كشفها لمن
أثبت أنه صاحبها.
"""
from __future__ import annotations

import contextlib

import pytest

EMP = ("100000000101", "emp12345")


def _login(client, civil_id, password):
    return client.post("/api/auth/login",
                       json={"civil_id": civil_id, "password": password})


@contextlib.contextmanager
def _suspended(civil_id):
    from app import models
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        u = db.query(models.User).filter(models.User.civil_id == civil_id).one()
        was_status, was_active = u.status, u.is_active
        u.status, u.is_active = "suspended", False
        db.commit()
        yield
    finally:
        u = db.query(models.User).filter(models.User.civil_id == civil_id).one()
        u.status, u.is_active = was_status, was_active
        db.commit()
        db.close()


def test_wrong_password_hides_the_account_state(client):
    """كلمة خاطئة على حساب موقوف تردّ ما يردّه رقم غير موجود بالضبط."""
    with _suspended(EMP[0]):
        real = _login(client, EMP[0], "كلمة-خاطئة")
        ghost = _login(client, "999999999997", "كلمة-خاطئة")
        assert real.status_code == ghost.status_code == 401, (
            f"الحساب الموقوف ردّ {real.status_code} والوهمي {ghost.status_code} — "
            "الفارق وحده يبني كشف الموظفين"
        )
        assert real.json()["detail"] == ghost.json()["detail"], (
            "الرسالتان مختلفتان، فالفرق يُقرأ"
        )


def test_correct_password_reveals_the_state_to_its_owner(client):
    """من أثبت أنه صاحب الحساب يستحقّ سبب المنع بدقّة، لا رسالة مضلِّلة."""
    with _suspended(EMP[0]):
        r = _login(client, *EMP)
        assert r.status_code == 403, (
            f"صاحب الحساب الموقوف تلقّى {r.status_code} بدل 403 — "
            "سيظنّ العطل في كلمته ويستنزف محاولاته حتى القفل"
        )
        assert "موقوف" in r.json()["detail"]


def test_unknown_account_costs_the_same_time_as_a_real_one(client):
    """الزمن يكشف كما يكشف الردّ.

    حساب قائم يمرّ بـPBKDF2 (‏240 ألف دورة) ورقم غير موجود كان يردّ فوًرا —
    فرق يُقاس بساعة يد فيبقى التعداد ممكًنا وإن توحّدت الرسائل.
    """
    import time

    def _elapsed(civil_id):
        best = 10.0
        for _ in range(3):            # الأدنى أقلّ تأثًرا بضجيج الجهاز
            t0 = time.perf_counter()
            _login(client, civil_id, "كلمة-خاطئة")
            best = min(best, time.perf_counter() - t0)
        return best

    real = _elapsed(EMP[0])
    ghost = _elapsed("999999999996")
    assert ghost > real * 0.5, (
        f"رقم غير موجود ردّ في {ghost * 1000:.0f}ms مقابل {real * 1000:.0f}ms "
        "لحساب قائم — الفارق وحده يميّز الموجود من غيره"
    )


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
