# -*- coding: utf-8 -*-
"""الخدمة الذاتية للموظف (/me): ملفه ومستنداته وإنذاراته وعقوده — بياناته هو فقط.

لا تتطلّب صلاحية view_employee/view_documents — العزل مضمون لأن كل استعلام
مقيّد بـ user.employee_id (سجل المستخدم نفسه لا غير).
"""
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user

router = APIRouter(prefix="/me", tags=["self-service"])


def _own_employee(user: models.User, db: Session) -> models.Employee:
    if not user.employee_id:
        raise HTTPException(status_code=404, detail="لا يوجد ملف موظف مرتبط بحسابك")
    emp = db.get(models.Employee, user.employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="الملف غير موجود")
    return emp


@router.get("/profile")
def my_profile(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """ملف الموظف الشخصي: بياناته + العقد + المستندات + الإجازات + الإنذارات (بدون إقامات حكومية)."""
    emp = _own_employee(user, db)
    docs = db.scalars(select(models.Document).where(
        models.Document.entity_type == "employee",
        models.Document.entity_id == emp.id,
        models.Document.is_current == True,  # noqa: E712
    )).all()
    leaves = db.scalars(select(models.Leave).where(
        models.Leave.employee_id == emp.id).order_by(models.Leave.start_date.desc())).all()
    warnings = db.scalars(select(models.EmployeeEvent).where(
        models.EmployeeEvent.employee_id == emp.id,
        models.EmployeeEvent.kind == "warning",
    ).order_by(models.EmployeeEvent.created_at.desc())).all()
    return {
        "employee": schemas.EmployeeOut.model_validate(emp),
        "documents": [{"id": d.id, "type": d.document_type_code, "title": d.title,
                       "expiry_date": d.expiry_date, "version": d.version} for d in docs],
        "leaves": [{"id": l.id, "type": l.leave_type, "start_date": l.start_date,
                    "end_date": l.end_date, "days": l.days, "status": l.status} for l in leaves],
        "warnings": [{"id": w.id, "title": w.title, "detail": w.detail,
                      "date": (w.date or w.created_at.date())} for w in warnings],
    }


@router.get("/document/{document_type_code}")
def my_document(document_type_code: str,
                user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """تنزيل أحدث نسخة من مستند للموظف نفسه فقط."""
    emp = _own_employee(user, db)
    doc = db.scalar(select(models.Document).where(
        models.Document.entity_type == "employee",
        models.Document.entity_id == emp.id,
        models.Document.document_type_code == document_type_code,
        models.Document.is_current == True,  # noqa: E712
    ))
    if not doc or not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="لا توجد نسخة محفوظة")
    return FileResponse(doc.file_path, filename=os.path.basename(doc.file_path),
                        media_type=doc.mime or "application/octet-stream")
