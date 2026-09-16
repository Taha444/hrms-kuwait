# -*- coding: utf-8 -*-
"""«من انتهت خدمته لا يبدأ معاملة» — قاعدةٌ واحدة كانت قائمتين.

**القياس**: قائمتان، وكلٌّ منهما يقول تعليقُها إنها «القاعدة الواحدة»:

==================================  ======  ======  ======  ======
                                    مؤرشف  منتهية  مستقيل  متقاعد
==================================  ======  ======  ======  ======
``deps.INACTIVE_EMPLOYMENT``         ✔       ✔       ✘       ✘
``workflow.BLOCKED_EMPLOYEE_…``      ✔       ✔       ✔       ✘
==================================  ======  ======  ======  ======

فالمستقيلُ ممنوعٌ من فتح طلبٍ ومن البصم، ومسموحٌ له باستبدال توقيعه —
والتوقيعُ ما يُختَم على الورق الرسمي. **والمتقاعدُ لم تمنعه أيٌّ منهما.**

فصارت قائمةً واحدة في ``deps``، و``workflow`` يقرؤها باسمه القديم (البصمُ
ونهايةُ الخدمة يقرآنه). ولا تُمنَع «في إجازة» ولا «موقوف»: الخدمةُ قائمة.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app import deps, models, workflow as W
from app.database import SessionLocal


def test_there_is_one_list_not_two():
    """**الاسمان كائنٌ واحد** — فلا تنحرف نسخةٌ عن أختها مرّةً أخرى."""
    assert W.BLOCKED_EMPLOYEE_STATUSES is deps.INACTIVE_EMPLOYMENT
    for st in ("archived", "terminated", "resigned", "retired"):
        assert st in deps.INACTIVE_EMPLOYMENT, st
    for st in ("active", "vacation", "suspended"):
        assert st not in deps.INACTIVE_EMPLOYMENT, (
            f"«{st}» خدمتُه قائمة — لا يُمنع من المعاملات")


@pytest.mark.parametrize("status", ["retired", "resigned"])
def test_an_ended_service_cannot_open_a_request(status):
    """**والمتقاعدُ كان يفتح طلبًا** — يُقاس بالنداء نفسه."""
    db = SessionLocal()
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.status == "active"))
        hr = db.scalar(select(models.User).where(
            models.User.role == "hr", models.User.company_id == 1))
        emp.status = status
        db.flush()
        rt = W.get_request_type(db, 1, "leave")
        assert rt is not None
        with pytest.raises(HTTPException) as ei:
            W.create_request(db, emp, hr, rt, {})
        assert ei.value.status_code == 409, ei.value.detail
        assert status in str(ei.value.detail)
    finally:
        db.rollback()
        db.close()


@pytest.mark.parametrize("status", ["retired", "resigned"])
def test_an_ended_service_cannot_replace_a_signature(status):
    """**والمستقيلُ كان يستبدل توقيعه** — وهو ما يُختَم على الورق الرسمي."""
    db = SessionLocal()
    try:
        user = db.scalar(select(models.User).where(
            models.User.employee_id.isnot(None), models.User.company_id == 1))
        emp = db.get(models.Employee, user.employee_id)
        emp.status = status
        db.flush()
        with pytest.raises(HTTPException) as ei:
            deps.assert_employment_active(db, user, action="استبدال التوقيع")
        assert ei.value.status_code == 409
    finally:
        db.rollback()
        db.close()


def test_a_vacation_does_not_block_a_request():
    """ومن في إجازةٍ يطلب — التوحيدُ لا يمنع ما كان يعمل."""
    db = SessionLocal()
    try:
        user = db.scalar(select(models.User).where(
            models.User.employee_id.isnot(None), models.User.company_id == 1))
        emp = db.get(models.Employee, user.employee_id)
        emp.status = "vacation"
        db.flush()
        deps.assert_employment_active(db, user)   # لا يرفع
    finally:
        db.rollback()
        db.close()
