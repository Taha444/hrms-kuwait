# -*- coding: utf-8 -*-
"""M16 #6 — رفعُ إذن العمل/البطاقة الجديدة في التجديد يُغلق تنبيهَ انتهاءِ نسختها القديمة."""
import asyncio
import io
from datetime import date, timedelta

from sqlalchemy import select
from starlette.datastructures import Headers, UploadFile

from app import models
from app.database import SessionLocal
from app.routers import renewals
from tests.conftest import plain_employee_clause, purge


def test_replacing_the_work_permit_closes_the_old_versions_expiry_task():
    db = SessionLocal()
    ids = {}
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.status == "active",
            plain_employee_clause(models)))
        old = models.Document(company_id=1, entity_type="employee", entity_id=emp.id,
                              document_type_code="work_permit", title="old", file_path="x/old.pdf",
                              version=1, is_current=True, uploaded_by=1,
                              expiry_date=date.today() + timedelta(days=10))
        db.add(old); db.flush()
        task = models.Task(company_id=1, type="doc_expiring", title="t", status="open",
                           related_entity_type="document", related_entity_id=old.id)
        db.add(task); db.flush()
        ids.update(old=old.id, task=task.id)

        up = UploadFile(io.BytesIO(b"%PDF-1.4 new"), filename="new.pdf",
                        headers=Headers({"content-type": "application/pdf"}))
        user = db.get(models.User, 1)
        new = asyncio.run(renewals._save_doc(db, user, None, "employee", emp.id, 1,
                                             "work_permit", "new", up))
        ids["new"] = new.id
        db.flush()
        assert db.get(models.Document, ids["old"]).is_current is False
        assert db.get(models.Task, ids["task"]).status == "done"
    finally:
        db.rollback()
        db.close()
