# -*- coding: utf-8 -*-
"""عددُ أيام الإجازة المُعلَن يُقارَن بما يُعفيه المسيّر — تنبيهٌ لا قاعدة.

**القياس** (محاكاة، ``rollback``): إجازةٌ سنويةٌ من 2 إلى 21 أغسطس بـ
``days=1`` — ``_apply_leave`` نقص الرصيدَ **يومًا واحدًا**، والمسيّرُ **أعفى
خمسةَ عشر يومَ عمل** من الغياب (يُعفي كلَّ يومٍ بين التاريخين أيًّا كان
``days``). أربعةَ عشر يومًا مدفوعًا لا تُخصم.

**ولا يُفرض الحساب**: العطلُ الرسمية لا تُحتسب من الإجازة السنوية، والنظامُ
بلا تقويمِ عطل. فالضابطُ القائم — المعتمِد — يرى الفرقَ محسوبًا بقاعدة المسيّر
نفسها (``shift.work_days``) بدل أن يحسبه ذهنيًا.
"""
from __future__ import annotations

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from app.routers import requests as RQ


def _req(db, days, start="2026-08-02", end="2026-08-21", leave_type="annual"):
    emp = db.scalar(select(models.Employee).where(models.Employee.company_id == 1))
    r = models.Request(company_id=1, employee_id=emp.id, request_type_code="leave",
                       status="pending", payload_json={
                           "leave_type": leave_type, "days": days,
                           "start_date": start, "end_date": end})
    db.add(r)
    db.flush()
    return r


def test_an_under_declared_leave_warns_the_approver():
    db = SessionLocal()
    try:
        w = RQ._leave_days_warning(db, _req(db, 1))
        assert w and "أقلُّ من أيام العمل" in w, w
        assert "15" in w or "١٥" in w, w
    finally:
        db.rollback()
        db.close()


def test_a_matching_declaration_is_quiet():
    db = SessionLocal()
    try:
        assert RQ._leave_days_warning(db, _req(db, 15)) is None
    finally:
        db.rollback()
        db.close()


def test_a_non_deducting_leave_is_quiet():
    """والمرضيّةُ لا تمسّ الرصيدَ السنوي — فلا تنبيه."""
    db = SessionLocal()
    try:
        assert RQ._leave_days_warning(db, _req(db, 1, leave_type="sick")) is None
    finally:
        db.rollback()
        db.close()


def test_the_warning_reaches_the_detail_response(client):
    """ويصل إلى من يعتمد — لا إلى صاحب الطلب (تواريخُه مخفيّةٌ عنه أصلًا)."""
    from tests.conftest import auth_headers, login

    db = SessionLocal()
    try:
        r = _req(db, 1)
        db.commit()
        rid = r.id
    finally:
        db.close()
    try:
        got = client.get(f"/api/requests/{rid}",
                         headers=auth_headers(login(client, "100000000002", "hr12345")))
        assert got.status_code == 200, got.text[:200]
        assert got.json().get("leave_days_warning"), got.json().keys()
    finally:
        db = SessionLocal()
        try:
            db.execute(models.Request.__table__.delete().where(models.Request.id == rid))
            db.commit()
        finally:
            db.close()
