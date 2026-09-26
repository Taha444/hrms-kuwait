# -*- coding: utf-8 -*-
"""M18 #3 — الأرشفة التلقائية تُرقّم الإصدارات تصاعديًا: كانت ``len(prev)+1`` على النسخ **الحالية** فيخرج كلُّ ما بعد الثاني «إصدار 2»."""
from types import SimpleNamespace

from sqlalchemy import select

from app import doc_archive, models
from app.database import SessionLocal
from tests.conftest import plain_employee_clause


def test_repeated_generated_documents_get_ascending_versions_and_one_current(monkeypatch):
    monkeypatch.setattr(doc_archive, "is_confidential_output", lambda r, d: False)
    db = SessionLocal()
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.status == "active",
            plain_employee_clause(models)))
        real_req = db.scalar(select(models.Request.id).where(models.Request.company_id == 1))
        req = SimpleNamespace(id=real_req, employee_id=emp.id, company_id=1, request_type_code="M18VER")
        rows = []
        for i in range(4):
            doc = SimpleNamespace(file_path=f"x/m18ver{i}.pdf", reference_no=f"M18VER-{i}",
                                  checksum_sha256=None, signature_version=None)
            rows.append(doc_archive.archive_request_document(db, req, doc, title=f"شهادة {i}", actor_id=1))
        assert all(rows)
        versions = [r.version for r in rows]
        assert versions == [1, 2, 3, 4], versions
        db.flush()
        current = [r.version for r in rows if r.is_current]
        assert current == [4], current
    finally:
        db.rollback()
        db.close()
