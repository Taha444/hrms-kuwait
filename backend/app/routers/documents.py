# -*- coding: utf-8 -*-
"""خزنة المستندات: رفع بنُسخ (versioning) + اقتراح OCR + تنزيل الأحدث + مهام متسلسلة."""
import os
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..database import get_db
from ..deps import assert_same_company, audit, require_perm
from .. import ocr
from ..notifications import create_task, notify_roles
from ..safe_files import read_limited, unique_path

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/ocr-preview")
async def ocr_preview(document_type_code: str = Form(...), file: UploadFile = File(...),
                      user: models.User = Depends(require_perm("upload_documents"))):
    """يقرأ المستند ويُرجع بيانات *مقترحة* فقط — يؤكّدها المستخدم قبل الحفظ (قاعدة ذهبية)."""
    tmp = unique_path(os.path.join(settings.upload_dir, "tmp"), file.filename, prefix="ocr_")
    with open(tmp, "wb") as f:
        f.write(await read_limited(file))
    try:
        suggested = ocr.extract(document_type_code, tmp)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    return {"suggested": suggested, "note": "راجع البيانات وعدّلها قبل الحفظ."}


@router.post("/upload")
async def upload_document(
    request: Request,
    entity_type: str = Form("employee"),
    entity_id: int = Form(...),
    document_type_code: str = Form(...),
    title: str | None = Form(None),
    issue_date: date | None = Form(None),
    expiry_date: date | None = Form(None),
    file: UploadFile = File(...),
    user: models.User = Depends(require_perm("upload_documents")),
    db: Session = Depends(get_db),
):
    """يرفع نسخة جديدة: تصبح الأحدث (is_current=True) والقديمة تُحفظ في التاريخ."""
    # تحديد الشركة للعزل حسب نوع الكيان
    if entity_type == "employee":
        emp = db.get(models.Employee, entity_id)
        if not emp:
            raise HTTPException(status_code=404, detail="الموظف غير موجود")
        assert_same_company(user, emp.company_id, db=db)
        company_id = emp.company_id
    elif entity_type == "company":
        company = db.get(models.Company, entity_id)
        if not company:
            raise HTTPException(status_code=404, detail="الشركة غير موجودة")
        assert_same_company(user, company.id, db=db)
        company_id = company.id
    elif entity_type == "branch":
        branch = db.get(models.Branch, entity_id)
        if not branch:
            raise HTTPException(status_code=404, detail="الفرع غير موجود")
        assert_same_company(user, branch.company_id, db=db)
        company_id = branch.company_id
    else:
        company_id = user.company_id

    folder = os.path.join(settings.upload_dir, "documents")
    fpath = unique_path(folder, file.filename, prefix=f"{entity_type}_{entity_id}_")
    with open(fpath, "wb") as f:
        f.write(await read_limited(file))

    # تعطيل النسخ السابقة لنفس النوع
    prev = db.scalars(select(models.Document).where(
        models.Document.entity_type == entity_type,
        models.Document.entity_id == entity_id,
        models.Document.document_type_code == document_type_code,
        models.Document.is_current == True,  # noqa: E712
    )).all()
    new_version = (max((d.version for d in prev), default=0)) + 1
    for d in prev:
        d.is_current = False

    doc = models.Document(
        company_id=company_id, entity_type=entity_type, entity_id=entity_id,
        document_type_code=document_type_code, title=title or document_type_code,
        file_path=fpath, mime=file.content_type, issue_date=issue_date,
        expiry_date=expiry_date, version=new_version, is_current=True,
        uploaded_by=user.id,
    )
    db.add(doc)
    db.flush()

    # مهمة متسلسلة: رفع جواز جديد → إغلاق إشعار "الجواز قارب على الانتهاء" + مهمة نقل معلومات
    if document_type_code == "passport" and entity_type == "employee":
        db.execute(
            update(models.Task)
            .where(models.Task.related_entity_type == "document",
                   models.Task.type == "doc_expiring",
                   models.Task.status.in_(["open", "in_progress"]))
            .values(status="done", completed_at=datetime.now())
        )
        emp = db.get(models.Employee, entity_id)
        notify_roles(
            db, company_id, ["delegate"],
            type="transfer_info",
            title=f"نقل معلومات الجواز الجديد: {emp.name if emp else entity_id}",
            detail="تم رفع جواز جديد. برجاء نقل البيانات/التأشيرة من الجواز القديم إلى الجديد.",
            related_entity_type="employee", related_entity_id=entity_id,
            severity="warning", dedup_key=f"transfer_info:{entity_id}:{new_version}",
        )

    audit(db, user, "upload_document", entity_type, entity_id,
          detail=f"{document_type_code} v{new_version}", request=request)
    db.commit()
    db.refresh(doc)
    return {"ok": True, "id": doc.id, "version": new_version}


@router.get("/latest")
def latest_document(entity_type: str, entity_id: int, document_type_code: str,
                    user: models.User = Depends(require_perm("view_documents")),
                    db: Session = Depends(get_db)):
    """تنزيل أحدث نسخة لنوع مستند معيّن."""
    doc = db.scalar(select(models.Document).where(
        models.Document.entity_type == entity_type,
        models.Document.entity_id == entity_id,
        models.Document.document_type_code == document_type_code,
        models.Document.is_current == True,  # noqa: E712
    ))
    if not doc or not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="لا توجد نسخة محفوظة")
    assert_same_company(user, doc.company_id, db=db)
    return FileResponse(doc.file_path, filename=os.path.basename(doc.file_path),
                        media_type=doc.mime or "application/octet-stream")


@router.get("/history")
def document_history(entity_type: str, entity_id: int, document_type_code: str | None = None,
                     user: models.User = Depends(require_perm("view_documents")),
                     db: Session = Depends(get_db)):
    q = select(models.Document).where(
        models.Document.entity_type == entity_type,
        models.Document.entity_id == entity_id,
    )
    if document_type_code:
        q = q.where(models.Document.document_type_code == document_type_code)
    rows = db.scalars(q.order_by(models.Document.created_at.desc())).all()
    return [{"id": d.id, "type": d.document_type_code, "title": d.title,
             "version": d.version, "is_current": d.is_current,
             "expiry_date": d.expiry_date, "created_at": d.created_at} for d in rows]
