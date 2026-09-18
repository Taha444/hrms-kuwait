# -*- coding: utf-8 -*-
"""سجلُّ حضور الفرع بنطاق الفرع — كشاشة المراجعة التي تعرضه.

``/attendance/branch/{id}`` كانت تتحقق من الشركة وحدها، و``view_attendance``
يملكها مسؤولُ الفرع. فمسؤوُل الفرع الأول يقرأ حضوَر الفرع الثاني (من دخل
ومتى وخرج، ومن صوّر سيلفي)، بينما ``/attendance/review`` تُقيّده بفروعه
وتردّ 403 لفرٍع خارجها.
"""
from __future__ import annotations

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

SUP1 = ("100000000005", "sup12345")


def _foreign_branch():
    db = SessionLocal()
    try:
        sup = db.scalar(select(models.User).where(models.User.civil_id == SUP1[0]))
        from app.deps import resolve_scope
        mine = resolve_scope(sup, db).branch_ids or set()
        b = db.scalar(select(models.Branch).where(
            models.Branch.company_id == 1, models.Branch.id.notin_(mine)))
        return b.id, next(iter(mine))
    finally:
        db.close()


def test_a_branch_supervisor_cannot_read_another_branchs_attendance(client):
    other, _ = _foreign_branch()
    r = client.get(f"/api/attendance/branch/{other}", headers=auth_headers(login(client, *SUP1)))
    assert r.status_code in (403, 404), (r.status_code, r.text[:150])


def test_a_branch_supervisor_still_reads_his_own_branch(client):
    _, mine = _foreign_branch()
    r = client.get(f"/api/attendance/branch/{mine}", headers=auth_headers(login(client, *SUP1)))
    assert r.status_code == 200, r.text[:150]


def test_hr_reads_every_branch(client):
    other, _ = _foreign_branch()
    r = client.get(f"/api/attendance/branch/{other}",
                   headers=auth_headers(login(client, "100000000002", "hr12345")))
    assert r.status_code == 200, r.text[:150]
