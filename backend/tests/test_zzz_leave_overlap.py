# -*- coding: utf-8 -*-
"""M12 — إجازتان متداخلتان لا تُفتحان معًا.

لا حارس تداخل كان في أيّ موضع: تُعتمد إجازة 5–10 وأخرى 7–12 فتُسجَّلان وتُخصم أيامُهما
معًا عن أيامٍ مشتركة. والحارس في ``create_request`` (نقطة الاختناق)، بعد حماية الضغط
المزدوج حتى تبقى إعادة المحاولة المتطابقة تُرجع الطلب القائم لا 409.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import delete as sa_delete, select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login, purge

EMP = ("100000000101", "emp12345")


def _leave(client, start, end, days):
    emp = auth_headers(login(client, *EMP))
    return client.post("/api/requests", headers=emp, json={
        "request_type_code": "leave",
        "payload_json": {"leave_type": "annual", "reason": "M12",
                         "start_date": start, "end_date": end, "days": days}})


def test_a_live_leave_request_blocks_an_overlapping_one_but_not_a_disjoint_one(client):
    made = []
    try:
        a = _leave(client, "2027-09-01", "2027-09-05", 5)
        assert a.status_code == 201, a.text
        made.append(a.json()["id"])
        overlapping = _leave(client, "2027-09-03", "2027-09-07", 5)
        assert overlapping.status_code == 409, f"إجازتان متداخلتان قُبلتا: {overlapping.status_code}"
        assert f"#{made[0]}" in overlapping.text
        disjoint = _leave(client, "2027-09-20", "2027-09-22", 3)
        assert disjoint.status_code == 201, disjoint.text
        made.append(disjoint.json()["id"])
        # ضغطةٌ مزدوجة بالحمولة نفسها تُرجع الطلب القائم لا 409
        again = _leave(client, "2027-09-01", "2027-09-05", 5)
        assert again.status_code == 201 and again.json()["id"] == made[0], again.text
    finally:
        db = SessionLocal()
        try:
            purge(db, "requests", made)
            db.commit()
        finally:
            db.close()


def test_an_approved_leave_row_blocks_an_overlapping_request(client):
    db = SessionLocal()
    try:
        emp_id = db.scalar(select(models.User.employee_id).where(models.User.civil_id == EMP[0]))
        row = models.Leave(company_id=1, employee_id=emp_id, leave_type="annual",
                           start_date=date(2027, 11, 1), end_date=date(2027, 11, 10),
                           days=10, status="approved")
        db.add(row)
        db.commit()
        lid = row.id
    finally:
        db.close()
    try:
        r = _leave(client, "2027-11-08", "2027-11-12", 5)
        assert r.status_code == 409, f"تداخل مع إجازة معتمَدة قُبل: {r.status_code}"
        assert f"#{lid}" in r.text
    finally:
        db = SessionLocal()
        try:
            db.execute(sa_delete(models.Leave).where(models.Leave.id == lid))
            db.commit()
        finally:
            db.close()
