# -*- coding: utf-8 -*-
"""مسار إلغاء الإقامة — قرار المالك (2026-09-18).

لم يكن في النظام: إقامُة من غادر تبقى «نشطة»، فتصل تنبيهاُت تجديدها
ويُعَدّ على الترخيص. والقرار:

    طلٌب من HR ← اعتماد المدير ← المندوب ينفّذ ويرفع الإثبات الحكومي
    ← الإقامة «ملغاة» وتتوقف تنبيهاُت تجديدها.

والمندوب **لا يعتمد مرحلته بلا إثباٍت رفعه هو** — فإلغاٌء يُسجَّل بلا
ورقٍة حكومية ادّعاٌء لا إجراء.
"""
from __future__ import annotations

import io
from datetime import timedelta

from sqlalchemy import select

from app import models
from app.clock import today as kuwait_today
from app.database import SessionLocal
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")
MGR = ("100000000001", "manager123")
DELEGATE = ("100000000003", "deleg123")
EMP = ("100000000101", "emp12345")

CODE = "ADMRESCXL"


def _employee_with_fresh_residency():
    """موظٌف في الشركة الأولى، تُستبدل إقاماتُه النشطة بإقامٍة واحدة للاختبار."""
    db = SessionLocal()
    try:
        # لا أحَد من حسابات الاختبار: المعتمِد لا يعتمد ما يخصّه (منع الاعتماد الذاتي).
        mine = [u.employee_id for u in db.scalars(select(models.User).where(
            models.User.civil_id.in_([HR[0], MGR[0], DELEGATE[0], EMP[0]]))).all()
                if u.employee_id]
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.status == "active",
            models.Employee.id.notin_(mine or [-1])))
        old = []
        for p in db.scalars(select(models.Permit).where(
                models.Permit.employee_id == emp.id, models.Permit.kind == "residency",
                models.Permit.status == "active")).all():
            old.append(p.id)
            p.status = "guard_parked"
        permit = models.Permit(company_id=1, employee_id=emp.id, kind="residency",
                               number="GUARD-RES", status="active",
                               expiry_date=kuwait_today() + timedelta(days=40))
        db.add(permit)
        db.commit()
        return emp.id, permit.id, old
    finally:
        db.close()


def _restore(emp_id, permit_id, old, *req_ids):
    db = SessionLocal()
    try:
        for rid in req_ids:
            for d in db.scalars(select(models.RequestDocument).where(
                    models.RequestDocument.request_id == rid)).all():
                db.delete(d)
            for a in db.scalars(select(models.RequestApproval).where(
                    models.RequestApproval.request_id == rid)).all():
                db.delete(a)
            for t in db.scalars(select(models.Task).where(
                    models.Task.related_entity_type == "request",
                    models.Task.related_entity_id == rid)).all():
                db.delete(t)
            r = db.get(models.Request, rid)
            if r:
                db.delete(r)
        for t in db.scalars(select(models.Task).where(
                models.Task.related_entity_type == "permit",
                models.Task.related_entity_id == permit_id)).all():
            db.delete(t)
        p = db.get(models.Permit, permit_id)
        if p:
            db.delete(p)
        for pid in old:
            db.get(models.Permit, pid).status = "active"
        db.commit()
    finally:
        db.close()


def _create(client, emp_id):
    return client.post("/api/requests", headers=auth_headers(login(client, *HR)), json={
        "request_type_code": CODE, "employee_id": emp_id,
        "payload_json": {"reason": "final_exit", "notes": "مغادرة نهائية"}})


def _decide(client, who, rid):
    return client.post(f"/api/requests/{rid}/decide", headers=auth_headers(login(client, *who)),
                       json={"decision": "approved"})


def _upload(client, who, rid):
    return client.post(f"/api/requests/{rid}/documents", headers=auth_headers(login(client, *who)),
                       data={"kind": "attachment"},
                       files={"file": ("proof.pdf", io.BytesIO(b"%PDF-1.4 proof"), "application/pdf")})


def test_the_full_path_cancels_the_residency_and_silences_its_alerts(client):
    emp_id, permit_id, old = _employee_with_fresh_residency()
    rid = None
    try:
        # تنبيه تجديٍد قائم على الإقامة — يجب أن يُغلق بإلغائها.
        db = SessionLocal()
        try:
            db.add(models.Task(company_id=1, type="renew_residency", title="guard renew",
                               status="open", related_entity_type="permit",
                               related_entity_id=permit_id))
            db.commit()
        finally:
            db.close()

        r = _create(client, emp_id)
        assert r.status_code in (200, 201), r.text[:200]
        rid = r.json()["id"]
        assert _decide(client, MGR, rid).status_code == 200

        # المندوب لا يعتمد بلا إثباٍت رفعه هو
        d = _decide(client, DELEGATE, rid)
        assert d.status_code in (400, 409), (d.status_code, d.text[:200])
        assert "الإثبات" in d.text
        # وإثباٌت رفعه غيُره لا يكفي
        assert _upload(client, HR, rid).status_code in (200, 201)
        assert _decide(client, DELEGATE, rid).status_code in (400, 409)

        assert _upload(client, DELEGATE, rid).status_code in (200, 201)
        d = _decide(client, DELEGATE, rid)
        assert d.status_code == 200, d.text[:200]

        db = SessionLocal()
        try:
            assert db.get(models.Request, rid).status == "completed"
            assert db.get(models.Permit, permit_id).status == "cancelled"
            open_alerts = db.scalars(select(models.Task).where(
                models.Task.related_entity_type == "permit",
                models.Task.related_entity_id == permit_id,
                models.Task.status == "open")).all()
            assert not open_alerts, "بقي تنبيُه تجديٍد لإقامٍة ملغاة"
        finally:
            db.close()
    finally:
        _restore(emp_id, permit_id, old, *([rid] if rid else []))


def test_no_active_residency_means_nothing_to_cancel(client):
    emp_id, permit_id, old = _employee_with_fresh_residency()
    db = SessionLocal()
    try:
        db.get(models.Permit, permit_id).status = "expired"
        db.commit()
    finally:
        db.close()
    try:
        r = _create(client, emp_id)
        assert r.status_code in (400, 409), (r.status_code, r.text[:200])
    finally:
        _restore(emp_id, permit_id, old)


def test_an_open_renewal_blocks_the_cancellation(client):
    emp_id, permit_id, old = _employee_with_fresh_residency()
    db = SessionLocal()
    try:
        case = models.ResidencyRenewal(company_id=1, employee_id=emp_id, permit_id=permit_id,
                                       renewal_type="normal", status="new")
        db.add(case)
        db.commit()
        case_id = case.id
    finally:
        db.close()
    try:
        r = _create(client, emp_id)
        assert r.status_code == 409, (r.status_code, r.text[:200])
        assert "تجديد" in r.text
    finally:
        db = SessionLocal()
        try:
            db.delete(db.get(models.ResidencyRenewal, case_id))
            db.commit()
        finally:
            db.close()
        _restore(emp_id, permit_id, old)


def test_the_employee_cannot_file_it(client):
    """والنوع داخلٌي: لا يُعرض للموظف — ولا يقبله الخادم منه بنداٍء مباشر."""
    r = client.post("/api/requests", headers=auth_headers(login(client, *EMP)), json={
        "request_type_code": CODE, "payload_json": {"reason": "final_exit"}})
    if r.status_code in (200, 201):
        db = SessionLocal()
        try:
            db.delete(db.get(models.Request, r.json()["id"]))
            db.commit()
        finally:
            db.close()
    assert r.status_code in (400, 403, 404, 409), (r.status_code, r.text[:200])
