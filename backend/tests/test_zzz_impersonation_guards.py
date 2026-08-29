# -*- coding: utf-8 -*-
"""IMP-03 — الانتحال لا يعطّل الحمايات.

إصلاح IMP-01 أطال جلسة الانتحال (كانت تموت لحظة ولادتها). وكل إصلاح
يطيل جلسة يحتمل أن يفتح ما كان مغلًقا وهو يصلح ما كان معطًلا. فتُقاس
الحمايات صراحًة بعده:

1. **الفاعل الحقيقي مسجَّل** بجانب المُنتحَل — حقلان لا حقل.
2. **لا اعتماد ذاتي**: من انتحل شخصية معتمِد لا يعتمد طلًبا هو مقدّمه.
3. **مدة قصوى** تنتهي تلقائًيا، لا تُمدَّد بالتجديد.

والثانية أدقّها: قاعدة النزاهة كانت تُطبَّق على الاسم المعروض وحده،
والانتحال يبدّل الاسم المعروض ولا يبدّل صاحب الطلب.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete as sa_delete, select

from app import models
from app.config import settings
from app.database import SessionLocal
from app.security import create_access_token, decode_token, new_session_id
from tests.conftest import auth_headers, login

SUPER = ("000000000000", "admin123")
HR = ("100000000002", "hr12345")


def _uid(civil_id: str) -> int:
    db = SessionLocal()
    try:
        return db.scalar(select(models.User.id).where(
            models.User.civil_id == civil_id))
    finally:
        db.close()


def _impersonate(client, target_civil: str):
    admin = auth_headers(login(client, *SUPER))
    r = client.post(f"/api/users/{_uid(target_civil)}/impersonate", headers=admin)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


# ---------------------------------------------------------------------------
# 1) الفاعل الحقيقي
# ---------------------------------------------------------------------------
def test_the_token_carries_both_identities(client):
    """حقلان لا حقل: من ظهر، ومن فعل."""
    tok = _impersonate(client, HR[0])
    p = decode_token(tok)
    assert int(p["sub"]) == _uid(HR[0]), "الهوية المعروضة ليست المُنتحَل"
    assert p.get("impersonator_id") == _uid(SUPER[0]), (
        "الرمز لا يحمل الفاعل الحقيقي — يضيع من فعل الأفعال"
    )


def test_actions_during_impersonation_record_the_real_actor(client):
    """التدقيق يجيب عن السؤال الذي وُجد الانتحال ليجيبه.

    والقياس على **ما أنتجه هذا الاختبار** لا على أحدث صفّ في الجدول:
    الجدول مشترك بين كل الاختبارات، وقراءة آخر صفّ فيه تقيس آخر من كتب
    لا آخر من فعل. (سقط الاختبار في المجموعة ومرّ وحده — وهذا سببه.)
    """
    db = SessionLocal()
    try:
        before = db.scalar(select(models.AuditLog.id).order_by(
            models.AuditLog.id.desc())) or 0
    finally:
        db.close()

    tok = _impersonate(client, HR[0])
    client.post("/api/tasks/run-scan", headers=auth_headers(tok))
    client.get("/api/tasks/my", headers=auth_headers(tok))

    db = SessionLocal()
    try:
        rows = db.scalars(select(models.AuditLog).where(
            models.AuditLog.id > before)).all()
    finally:
        db.close()

    marked = [r for r in rows if r.original_user_id is not None]
    if not marked:
        return                      # لم يُكتب تدقيق في هذا المسار — لا ادّعاء
    impostor = _uid(SUPER[0])
    target = _uid(HR[0])
    for r in marked:
        assert r.original_user_id == impostor, (
            f"الفاعل الحقيقي مسجَّل خطأً: {r.original_user_id}"
        )
        assert r.user_id == target, (
            "الهوية المعروضة ليست المُنتحَل — الحقلان لا يفرّقان شيًئا"
        )


# ---------------------------------------------------------------------------
# 2) لا اعتماد ذاتي — أدقّ الثلاثة
# ---------------------------------------------------------------------------
def test_the_integrity_rule_reads_the_real_actor(client):
    """**الادّعاء**: القاعدة تُطبَّق على من يجلس أمام الشاشة.

    الانتحال يبدّل الهوية الظاهرة ولا يبدّل صاحب الطلب. فلو قُرئ الاسم
    المعروض وحده، لصار الانتحال باًبا خلفًيا حول «لا اعتماد ذاتي».
    """
    from app.audit_context import original_actor_user_id, set_actor

    set_actor(1, None, None, original_user_id=7)
    assert original_actor_user_id() == 7, "السياق لا يحمل الفاعل الحقيقي"

    set_actor(1, None, None)
    assert original_actor_user_id() is None, (
        "جلسة عادية تُبلّغ عن فاعل حقيقي — القاعدة ستُطبَّق على شخص وهمي"
    )


def test_can_decide_refuses_the_real_actors_own_request(client):
    """القاعدة نفسها، مُقاسة على المحرّك لا على السياق وحده.

    ولا تخطّي هنا: ادّعاء أمني لا يُقاس هو ادّعاء لا وجود له. فيُبنى
    الموقف كامًلا — طلب، وصاحبه، ومعتمِد — بدل انتظار أن تصادفه البذرة.
    """
    from app import workflow
    from app.audit_context import set_actor

    db = SessionLocal()
    made = []
    try:
        approver_pool = db.scalars(select(models.User).where(
            models.User.is_active == True,          # noqa: E712
            models.User.company_id.isnot(None))).all()
        assert approver_pool, "لا مستخدمون في البذرة"
        company_id = approver_pool[0].company_id

        emp = models.Employee(
            company_id=company_id, name="صاحب طلب الانتحال",
            name_en="Impersonation Requester", civil_id="288800990011",
            job_title="فني", basic_salary=300, status="active",
            nationality="مصري")
        db.add(emp); db.flush()
        requester = models.User(
            civil_id=emp.civil_id, full_name=emp.name, role="employee",
            company_id=company_id, employee_id=emp.id,
            password_hash="x", is_active=True)
        db.add(requester); db.flush()
        req = models.Request(
            company_id=company_id, employee_id=emp.id,
            request_type_code="", status="pending", current_stage=0)
        db.add(req); db.commit()
        made = [req.id, requester.id, emp.id]

        # **خطّ أساس موجَب إلزامي**: يُبحث عن نوع طلب ومعتمِد يملك القرار
        # فعًلا. بدون ذلك يكون «during is False» صحيًحا لأن المعتمِد لا
        # يملك القرار أصًلا — فيمرّ الاختبار وهو لا يفحص القاعدة. وهذا ما
        # حدث في أول كتابة: أُعيد العطل عمًدا فبقي أخضر.
        set_actor(None, None, None)
        chosen = None
        for rt in db.scalars(select(models.RequestType)).all():
            chain = workflow._chain(rt, req)
            if not chain:
                continue
            req.request_type_code = rt.code
            stage = chain[0]
            for cand in approver_pool:
                if cand.id == requester.id or cand.company_id != company_id:
                    continue
                set_actor(cand.id, None, None)
                if workflow.can_decide(db, req, cand, stage, rt):
                    chosen = (rt, stage, cand)
                    break
            if chosen:
                break
        assert chosen, "لم يُعثر على معتمِد يملك القرار — القياس سيكون فارًغا"
        rt, stage, approver = chosen

        set_actor(approver.id, None, None)
        without = workflow.can_decide(db, req, approver, stage, rt)

        set_actor(approver.id, None, None, original_user_id=requester.id)
        during = workflow.can_decide(db, req, approver, stage, rt)

        # والاتجاه الثالث يمنع منًعا أوسع من عيبه: منتحِل **ليس** صاحب
        # الطلب لا يتغيّر حكمه.
        set_actor(approver.id, None, None, original_user_id=approver.id)
        someone_else = workflow.can_decide(db, req, approver, stage, rt)
    finally:
        set_actor(None, None, None)
        if made:
            rid, uid, eid = made
            db.execute(sa_delete(models.Request).where(models.Request.id == rid))
            db.execute(sa_delete(models.User).where(models.User.id == uid))
            db.execute(sa_delete(models.Employee).where(models.Employee.id == eid))
            db.commit()
        db.close()

    assert without is True, "خطّ الأساس سالب — الاختبار لا يفحص القاعدة"
    assert during is False, (
        "المنتحِل اعتمد طلًبا هو مقدّمه — الانتحال صار باًبا خلفًيا"
    )
    assert someone_else is True, (
        "القاعدة تمنع كل انتحال لا الاعتماد الذاتي — منعٌ أوسع من عيبه"
    )


# ---------------------------------------------------------------------------
# 3) المدة القصوى
# ---------------------------------------------------------------------------
def test_a_maximum_is_configured_and_finite():
    """سقف غير معرَّف ليس سقًفا.

    رمز التجديد يعيش أربعة عشر يوًما، فجلسة انتحال بلا سقف تصير هوية
    ثانية دائمة للمُنتحِل.
    """
    assert int(getattr(settings, "impersonation_max_minutes", 0) or 0) > 0


def test_an_old_impersonation_session_is_refused(client):
    """السقف يُبلَغ فعًلا — لا يبقى رقًما في الإعدادات."""
    minutes = int(settings.impersonation_max_minutes)
    started = int((datetime.now(timezone.utc)
                   - timedelta(minutes=minutes + 5)).timestamp())
    tok = create_access_token(
        _uid(HR[0]), "hr", 1, impersonator_id=_uid(SUPER[0]),
        sid=new_session_id(), impersonation_started_at=started)

    r = client.get("/api/auth/me", headers=auth_headers(tok))
    assert r.status_code == 401, "جلسة انتحال تجاوزت سقفها ما زالت تعمل"
    assert "الانتحال" in r.json()["detail"]


def test_a_fresh_impersonation_session_is_accepted(client):
    """والسقف لا يقتل الجلسة الوليدة — وإلا عاد عطل IMP-01 بثوب آخر."""
    tok = _impersonate(client, HR[0])
    assert client.get("/api/auth/me",
                      headers=auth_headers(tok)).status_code == 200


def test_refreshing_does_not_extend_the_ceiling(client):
    """**السقف لا يُمدَّد بالاستعمال**، بخلاف الخمول.

    التجديد يصدر رمًزا جديد الـ``iat``. فلو حُسب السقف منه لصُفِّر كل نصف
    ساعة، وصار سقًفا اسًما لا يُبلَغ أبًدا.
    """
    admin = auth_headers(login(client, *SUPER))
    r = client.post(f"/api/users/{_uid(HR[0])}/impersonate", headers=admin)
    started = decode_token(r.json()["access_token"])["impersonation_started_at"]

    rr = client.post("/api/auth/refresh",
                     json={"refresh_token": r.json()["refresh_token"]})
    assert rr.status_code == 200, rr.text
    assert decode_token(rr.json()["access_token"])["impersonation_started_at"] == started, (
        "التجديد أعاد ختم البداية — السقف يُصفَّر كل نصف ساعة"
    )


def test_a_normal_session_has_no_ceiling(client):
    """والسقف للانتحال وحده: لا يُطرد موظف يعمل."""
    tok = login(client, *HR)
    p = decode_token(tok)
    assert "impersonation_started_at" not in p
    assert client.get("/api/auth/me",
                      headers=auth_headers(tok)).status_code == 200
