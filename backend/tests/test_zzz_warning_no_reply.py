# -*- coding: utf-8 -*-
"""مهلة الرد على الإنذار تنقضي فيُخطَر HR — قرار المالك (2026-09-18).

الحقُل إلزامٌي ولم يكن يقرؤه شيء. والقرار: بانقضاء المهلة بلا رد من
الموظف تُنشأ مهمةٌ لـHR «انقضت مهلة الرد بلا رد» — **ولا قراَر آليّ**:
الإنذاُر لا يُغلَق ولا يُبنى عليه شيء، وHR يقرّر.

والردُّ (``REQWARN``) يشير إلى الإنذار بنّص حّر (``warning_ref``) لا بمعرِّف؛
فيُعَدّ ردًّا كلُّ ``REQWARN`` من الموظف نفسه بعد صدور الإنذار — فلا يُقال
«بلا رد» عمّن ردّ.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app import models
from app.clock import today as kuwait_today
from app.database import SessionLocal
from app.notifications import daily_scan


def _employee():
    db = SessionLocal()
    try:
        return db.scalar(select(models.Employee.id).where(
            models.Employee.company_id == 1, models.Employee.status == "active"))
    finally:
        db.close()


def _warning(emp_id, deadline, status="completed"):
    db = SessionLocal()
    try:
        r = models.Request(company_id=1, employee_id=emp_id, request_type_code="ADMWARN",
                           status=status,
                           payload_json={"response_deadline": deadline.isoformat()})
        db.add(r)
        db.commit()
        return r.id
    finally:
        db.close()


def _reply(emp_id):
    db = SessionLocal()
    try:
        r = models.Request(company_id=1, employee_id=emp_id, request_type_code="REQWARN",
                           status="pending", payload_json={"warning_ref": "x"})
        db.add(r)
        db.commit()
        return r.id
    finally:
        db.close()


def _tasks(req_id):
    db = SessionLocal()
    try:
        return db.scalars(select(models.Task).where(
            models.Task.type == "warning_no_reply",
            models.Task.related_entity_id == req_id)).all()
    finally:
        db.close()


def _scan():
    db = SessionLocal()
    try:
        daily_scan(db)
        db.commit()
    finally:
        db.close()


def _cleanup(*ids):
    db = SessionLocal()
    try:
        for t in db.scalars(select(models.Task).where(
                models.Task.type == "warning_no_reply")).all():
            db.delete(t)
        for i in ids:
            db.delete(db.get(models.Request, i))
        db.commit()
    finally:
        db.close()


def test_a_passed_deadline_without_reply_reaches_hr_once(client):
    wid = _warning(_employee(), kuwait_today() - timedelta(days=1))
    try:
        _scan()
        tasks = _tasks(wid)
        assert tasks, "انقضت المهلة بلا رد ولم يُخطَر أحد"
        db = SessionLocal()
        try:
            roles = {db.get(models.User, t.assignee_user_id).role for t in tasks}
        finally:
            db.close()
        assert roles == {"hr"}, roles
        n = len(tasks)
        # ولا يعود كل يوم — ولا بعد أن يُغلقه HR.
        db = SessionLocal()
        try:
            for t in db.scalars(select(models.Task).where(
                    models.Task.type == "warning_no_reply")).all():
                t.status = "done"
            db.commit()
        finally:
            db.close()
        _scan()
        assert len(_tasks(wid)) == n, "أُعيد إنشاء المهمة بعد إغلاقها"
        # ولا قراَر آليًّا: الإنذار كما هو.
        db = SessionLocal()
        try:
            assert db.get(models.Request, wid).status == "completed"
        finally:
            db.close()
    finally:
        _cleanup(wid)


def test_a_reply_after_the_warning_means_no_task(client):
    emp = _employee()
    wid = _warning(emp, kuwait_today() - timedelta(days=1))
    rid = _reply(emp)
    try:
        _scan()
        assert not _tasks(wid)
    finally:
        _cleanup(wid, rid)


def test_a_deadline_not_yet_passed_means_no_task(client):
    wid = _warning(_employee(), kuwait_today() + timedelta(days=2))
    try:
        _scan()
        assert not _tasks(wid)
    finally:
        _cleanup(wid)
