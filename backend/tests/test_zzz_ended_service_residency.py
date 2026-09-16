# -*- coding: utf-8 -*-
"""إقامةُ من انتهت خدمته لا تُجدَّد — ولا يُقال عنها «تجديد».

**القياس**: لا مسارَ إنهاءٍ يمسّ حالةَ الإقامة (``Permit.status``) — لا
``terminate/execute`` ولا ``settle_case``. فتبقى ``active`` بعد المغادرة، و:

- ``daily_scan`` يُرسل للمندوب «**تجديد** الإقامة» ويُرسل للموظف السابق
  «سيتم البدء في إجراءات التجديد».
- و``POST /renewals`` **يفتح ملفَّ تجديدٍ** له — بابٌ ثالثٌ لا يقرأ
  ``INACTIVE_EMPLOYMENT`` (``create_request`` والبصمُ يقرآنها). والتجديدُ
  معاملةٌ حكوميةٌ برسومها، وإقامةُ من غادر تُحسم بالإلغاء أو التحويل.

**والإصلاحُ لا يُسكت**: الإقامةُ ما زالت تنتهي والشركةُ كفيلُها، فيبقى
الإنذارُ للمندوب بصياغةٍ صادقة وبالنوع نفسه (ليبقى في صندوقه).

**وما ليس هنا**: لا مسارَ **إلغاء** إقامةٍ في النظام أصلًا — وبناؤه قرارٌ
يُترك لصاحبه.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import delete as sa_delete, select

from app import models, notifications as N
from app.clock import today as kuwait_today
from app.database import SessionLocal
from tests.conftest import auth_headers, login

DELEGATE1 = ("100000000004", "deleg123")


def _setup(status: str):
    """موظفٌ بحالةٍ معيّنة، وإقامةٌ نشطةٌ له تنتهي بعد ثلاثين يومًا."""
    db = SessionLocal()
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.status == "active"))
        old = emp.status
        emp.status = status
        p = models.Permit(company_id=1, employee_id=emp.id, kind="residency",
                          number="ZZZ-RES-ENDED", status="active",
                          expiry_date=kuwait_today() + timedelta(days=30))
        db.add(p)
        db.commit()
        return emp.id, old, p.id
    finally:
        db.close()


def _teardown(emp_id: int, old: str, permit_id: int) -> None:
    db = SessionLocal()
    try:
        db.execute(sa_delete(models.Task).where(
            models.Task.related_entity_type == "permit",
            models.Task.related_entity_id == permit_id))
        db.execute(sa_delete(models.ResidencyRenewal).where(
            models.ResidencyRenewal.permit_id == permit_id))
        db.execute(sa_delete(models.Permit).where(models.Permit.id == permit_id))
        db.get(models.Employee, emp_id).status = old
        db.commit()
    finally:
        db.close()


def _tasks(permit_id: int) -> list[models.Task]:
    db = SessionLocal()
    try:
        return db.scalars(select(models.Task).where(
            models.Task.related_entity_type == "permit",
            models.Task.related_entity_id == permit_id)).all()
    finally:
        db.close()


def test_a_renewal_case_is_not_opened_for_an_ended_service(client):
    emp_id, old, pid = _setup("terminated")
    try:
        r = client.post("/api/renewals",
                        data={"employee_id": emp_id, "permit_id": pid},
                        headers=auth_headers(login(client, *DELEGATE1)))
        assert r.status_code == 409, (r.status_code, r.text[:250])
        assert "الإلغاء أو التحويل" in r.text
    finally:
        _teardown(emp_id, old, pid)


def test_the_scan_does_not_say_renew_for_an_ended_service():
    """**والإنذارُ باقٍ بصياغةٍ صادقة** — ولا رسالةَ للموظف السابق."""
    emp_id, old, pid = _setup("terminated")
    try:
        db = SessionLocal()
        try:
            N.daily_scan(db)
        finally:
            db.close()
        tasks = _tasks(pid)
        assert tasks, "سكت الإنذار — والإقامةُ ما زالت تنتهي والشركةُ كفيلُها"
        db = SessionLocal()
        try:
            for t in tasks:
                u = db.get(models.User, t.assignee_user_id)
                assert u.employee_id != emp_id, (
                    "أُرسل للموظف السابق «سيتم البدء في إجراءات التجديد»")
                assert "تجديد" not in (t.title or ""), t.title
                assert "انتهت خدمته" in (t.title or ""), t.title
        finally:
            db.close()
    finally:
        _teardown(emp_id, old, pid)


def test_an_active_employee_still_gets_the_renewal_wording():
    """ومن خدمتُه قائمة يُقال له «تجديد» كما كان."""
    emp_id, old, pid = _setup("vacation")
    try:
        db = SessionLocal()
        try:
            N.daily_scan(db)
        finally:
            db.close()
        titles = [t.title for t in _tasks(pid)]
        assert any("تجديد" in (x or "") for x in titles), titles
    finally:
        _teardown(emp_id, old, pid)
