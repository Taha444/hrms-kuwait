# -*- coding: utf-8 -*-
"""خزنة المستندات: رفع بنُسخ (versioning) + اقتراح OCR + تنزيل الأحدث + مهام متسلسلة."""
import logging
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

logger = logging.getLogger(__name__)


def _as_date(v):
    """قراءة OCR تعود نًصا (ISO غالًبا) وعمود expiry_date من نوع Date."""
    from datetime import date as _date
    if not v or isinstance(v, _date):
        return v or None
    try:
        return _date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


# أنواع المستندات التي تُمثَّل أيًضا كتصاريح (permits) — العدادات وشاشات
# التجديد تقرأ من permits لا من documents.
DOC_TYPE_TO_PERMIT_KIND = {
    "residency": "residency",
    "work_permit": "work_permit",
}


def _sync_permit_from_document(db: Session, doc: models.Document) -> None:
    """QA-06/QA-19 — يُبقي سجل التصريح متوافًقا مع أحدث مستند.

    ROOT CAUSE للعدادات الصفرية: المستند والتصريح مخزنان منفصلان. رفع صورة
    الإقامة يكتب صف Document ولا يمسّ Permit، بينما لوحة التحكم ومركز العمليات
    وشاشة التجديدات كلها تقرأ Permit. فتُرفع الإقامات ويبقى العدّاد صفًرا.

    المستند هو المصدر (فيه الصورة والتاريخ المقروء)، والتصريح انعكاس له.
    """
    kind = DOC_TYPE_TO_PERMIT_KIND.get(doc.document_type_code)
    if not kind or doc.entity_type != "employee" or not doc.expiry_date:
        return
    permit = db.scalar(select(models.Permit).where(
        models.Permit.employee_id == doc.entity_id,
        models.Permit.kind == kind,
    ).order_by(models.Permit.expiry_date.desc()))
    today = date.today()
    status = "active" if doc.expiry_date >= today else "expired"
    if permit:
        # لا نتراجع بتاريخ أقدم: رفع نسخة قديمة للأرشفة يجب ألا يُبطل السارية
        if permit.expiry_date and permit.expiry_date > doc.expiry_date:
            return
        permit.expiry_date = doc.expiry_date
        permit.start_date = doc.issue_date or permit.start_date
        permit.status = status
    else:
        db.add(models.Permit(
            company_id=doc.company_id, employee_id=doc.entity_id, kind=kind,
            start_date=doc.issue_date, expiry_date=doc.expiry_date, status=status,
        ))


router = APIRouter(prefix="/documents", tags=["documents"])


def _close_expiry_tasks_for(db: Session, doc_id: int) -> int:
    """P0-#10 — يقفل كل open/in_progress expiry tasks المرتبطة بمستند معين.
    يُستدعى عند: استبدال المستند بنسخة جديدة، حذفه، أو تجديده.
    Returns: عدد المهام اللي اتقفلت."""
    from datetime import datetime, timezone
    closed = db.scalars(select(models.Task).where(
        models.Task.related_entity_type == "document",
        models.Task.related_entity_id == doc_id,
        models.Task.type == "doc_expiring",
        models.Task.status.in_(("open", "in_progress")),
    )).all()
    for t in closed:
        t.status = "done"
        t.completed_at = datetime.now(timezone.utc)
    # audit trail — نسجل event لكل task مُغلَق
    for t in closed:
        db.add(models.AuditLog(
            company_id=t.company_id, user_id=None,
            action="expiry_task_auto_closed", entity_type="task",
            entity_id=t.id, detail=f"document #{doc_id} replaced/renewed",
            correlation_id=f"doc:{doc_id}",
        ))
    return len(closed)


# ==============================================================================
# V1.5 Phase 4 — Canonical Documents catalog (public, no auth needed)
# ==============================================================================
@router.get("/canonical")
def canonical_catalog():
    """يعرض 9 layouts + 25 canonical documents (OD-001..OD-025) + خريطة الأكواد
    القديمة (PRN → OD) — يستخدمه الفرونت لعرض التسمية الرسمية بجانب الكود القديم."""
    from .. import v15_registry
    return {
        "layouts": v15_registry.LAYOUTS,
        "canonical_documents": v15_registry.CANONICAL_DOCUMENTS,
        "reports": v15_registry.REPORTS,
        "system_records": v15_registry.SYSTEM_RECORDS,
        "legacy_prn_aliases": v15_registry.LEGACY_PRN_ALIASES,
        "counts": v15_registry.summary(),
    }


@router.get("/canonical/{od_code}")
def canonical_document_detail(od_code: str):
    """تفاصيل OD واحد + معلومات الـ layout المرتبط + قائمة الحقول الإلزامية."""
    from .. import v15_registry
    od = v15_registry.resolve_canonical_document(od_code)
    if not od:
        raise HTTPException(status_code=404, detail="canonical document not found")
    layout = v15_registry.LAYOUTS.get(od["layout"])
    return {**od, "layout_info": layout}


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


@router.get("/ocr-status")
def ocr_status(user: models.User = Depends(require_perm("upload_documents"))):
    """تشخيص محرّك OCR على الخادم: هل Tesseract مثبَّت؟ إصداره؟ اللغات المتاحة؟
    مفيد للإدارة عشان تعرف لو حزمة العربية ناقصة قبل ما يشتكي المستخدمون."""
    return ocr._tesseract_status()


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
        # P0-#10 — عند استبدال النسخة (تجديد/رفع جديد): اقفل أي open expiry tasks
        # لهذا الـdocument تلقائيًا. النسخة الجديدة هتلقى tasks جديدة من daily_scan
        # بناءً على expiry_date الجديد.
        _close_expiry_tasks_for(db, d.id)

    # QA-06 — تاريخ الانتهاء يُقرأ من المستند نفسه حين لا يُدخله الرافع.
    #
    # ROOT CAUSE: كان expiry_date حقل نموذج يدوي بحت. الـOCR موجود لكنه في
    # endpoint منفصل (ocr-preview) يقترح على **الموظف** لا على المستند، فلا
    # شيء يكتب التاريخ على سجل المستند تلقائيًا. ومن يرفع بلا إدخاله يترك
    # الحقل فارغًا، فمحرك الانتهاء والعدادات تقرأ فراًغا — ومن هنا "الإقامات
    # السارية = 0" رغم وجود المستندات.
    #
    # SKILL-6: القراءة هي القاعدة والإدخال اليدوي تصحيح. ما أدخله الرافع
    # يفوز دائًما — لا نصحّح إنسانًا بآلة.
    expiry_source = "manual" if expiry_date else None
    if not expiry_date:
        try:
            read = ocr.extract(document_type_code, fpath) or {}
            guess = read.get("expiry_date")
            if guess:
                expiry_date = _as_date(guess)
                expiry_source = "ocr" if expiry_date else None
        except Exception as exc:  # noqa: BLE001 — القراءة مساعدة لا شرط للرفع
            logger.warning("OCR expiry extraction failed for %s: %s",
                           document_type_code, exc)

    doc = models.Document(
        company_id=company_id, entity_type=entity_type, entity_id=entity_id,
        document_type_code=document_type_code, title=title or document_type_code,
        file_path=fpath, mime=file.content_type, issue_date=issue_date,
        expiry_date=expiry_date, version=new_version, is_current=True,
        uploaded_by=user.id,
    )
    db.add(doc)
    db.flush()
    _sync_permit_from_document(db, doc)

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
                    request: Request,
                    user: models.User = Depends(require_perm("view_documents")),
                    db: Session = Depends(get_db)):
    """تنزيل أحدث نسخة لنوع مستند معيّن. R9 §4: كل تنزيل يظهر في Audit."""
    doc = db.scalar(select(models.Document).where(
        models.Document.entity_type == entity_type,
        models.Document.entity_id == entity_id,
        models.Document.document_type_code == document_type_code,
        models.Document.is_current == True,  # noqa: E712
    ))
    if not doc or not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="لا توجد نسخة محفوظة")
    assert_same_company(user, doc.company_id, db=db)
    audit(db, user, "download_document", entity_type, entity_id,
          detail=f"{document_type_code} v{doc.version}",
          request=request, company_id=doc.company_id)
    db.commit()
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


@router.get("/{doc_id}/download")
def download_document_version(doc_id: int, request: Request,
                              user: models.User = Depends(require_perm("view_documents")),
                              db: Session = Depends(get_db)):
    """QA-28 — تنزيل نسخة بعينها من مستند (لا الأحدث وحدها).

    ROOT CAUSE: ``/documents/history`` كانت تُرجع كل الإصدارات، لكن لا نقطة
    تنزيل تقبل معرّف إصدار — و``/documents/latest`` تُرجع الحالي فقط. فالنسخ
    السابقة كانت "محفوظة" ولا سبيل إلى فتحها: وجودها في القاعدة لا يكفي.
    """
    doc = db.get(models.Document, doc_id)
    if not doc or not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="لا توجد نسخة محفوظة")
    assert_same_company(user, doc.company_id, db=db)
    audit(db, user, "download_document_version", doc.entity_type, doc.entity_id,
          detail=f"{doc.document_type_code} v{doc.version} (id={doc.id})",
          request=request, company_id=doc.company_id)
    db.commit()
    return FileResponse(doc.file_path, filename=os.path.basename(doc.file_path),
                        media_type=doc.mime or "application/octet-stream")


@router.patch("/{doc_id}/expiry")
def correct_document_expiry(doc_id: int, request: Request,
                            expiry_date: date | None = None,
                            reason: str | None = None,
                            user: models.User = Depends(require_perm("upload_documents")),
                            db: Session = Depends(get_db)):
    """QA-06 — تصحيح تاريخ الانتهاء يدوًيا.

    ROOT CAUSE: الرفع يقبل تاريًخا يدوًيا (ويفوز على OCR)، لكن لا سبيل لتعديله
    بعد ذلك — فتصحيح تاريخ قرأه OCR خطأً كان يستلزم إعادة رفع المستند كله.
    ومعيار قبول البند يشترط "تصحيح يدوي متاح" صراحًة.

    التصحيح يُزامن سجل التصريح (Permit) بنفس الدالة التي يستخدمها الرفع، وإلا
    تفرّق العدّاد عن المستند من جديد — وهو أصل عطل "الإقامات السارية = 0".
    """
    doc = db.get(models.Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="المستند غير موجود")
    assert_same_company(user, doc.company_id, db=db)

    before = doc.expiry_date
    if before == expiry_date:
        return {"ok": True, "unchanged": True, "expiry_date": expiry_date}

    doc.expiry_date = expiry_date
    _sync_permit_from_document(db, doc)
    audit(db, user, "correct_document_expiry", doc.entity_type, doc.entity_id,
          detail=f"{doc.document_type_code}: {before} → {expiry_date}"
                 + (f" ({reason})" if reason else ""),
          before={"expiry_date": before.isoformat() if before else None},
          after={"expiry_date": expiry_date.isoformat() if expiry_date else None},
          request=request, company_id=doc.company_id)
    db.commit()
    return {"ok": True, "document_id": doc.id, "expiry_date": expiry_date}
