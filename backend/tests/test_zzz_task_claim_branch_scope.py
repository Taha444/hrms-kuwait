# -*- coding: utf-8 -*-
"""التقاُط المهمة بنطاق الفرع — قرار المالك (2026-09-18).

كان الالتقاُط يُقيَّد بالشركة وحدها: مسؤوُل الفرع الأول يلتقط مهمًة عن
موظٍف في الفرع الثاني، فتصير «جارية» باسمه ويُمنَع مسؤولُها بـ409.
وHR/المدير بلا نطاق فروع — يلتقطان كما كانا.
"""
from __future__ import annotations

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from app.deps import resolve_scope
from tests.conftest import auth_headers, login

SUP1 = ("100000000005", "sup12345")
HR = ("100000000002", "hr12345")


def _task(in_scope: bool, entity="employee"):
    db = SessionLocal()
    try:
        sup = db.scalar(select(models.User).where(models.User.civil_id == SUP1[0]))
        mine = resolve_scope(sup, db).branch_ids or set()
        cond = (models.Employee.branch_id.in_(mine) if in_scope
                else models.Employee.branch_id.notin_(mine))
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.branch_id.isnot(None), cond))
        t = models.Task(company_id=1, type="manual", title="guard task",
                        status="open", related_entity_type=entity,
                        related_entity_id=emp.id if entity == "employee" else None)
        db.add(t)
        db.commit()
        return t.id
    finally:
        db.close()


def _drop(tid):
    db = SessionLocal()
    try:
        db.delete(db.get(models.Task, tid))
        db.commit()
    finally:
        db.close()


def test_supervisor_cannot_claim_a_task_of_another_branch(client):
    tid = _task(in_scope=False)
    try:
        r = client.post(f"/api/tasks/{tid}/claim", headers=auth_headers(login(client, *SUP1)))
        assert r.status_code == 403, (r.status_code, r.text[:150])
    finally:
        _drop(tid)


def test_supervisor_cannot_claim_a_company_level_task(client):
    tid = _task(in_scope=False, entity="license")
    try:
        r = client.post(f"/api/tasks/{tid}/claim", headers=auth_headers(login(client, *SUP1)))
        assert r.status_code == 403, (r.status_code, r.text[:150])
    finally:
        _drop(tid)


def test_supervisor_still_claims_in_his_branch(client):
    tid = _task(in_scope=True)
    try:
        r = client.post(f"/api/tasks/{tid}/claim", headers=auth_headers(login(client, *SUP1)))
        assert r.status_code == 200, r.text[:150]
    finally:
        _drop(tid)


def test_hr_claims_any_branch(client):
    tid = _task(in_scope=False)
    try:
        r = client.post(f"/api/tasks/{tid}/claim", headers=auth_headers(login(client, *HR)))
        assert r.status_code == 200, r.text[:150]
    finally:
        _drop(tid)
