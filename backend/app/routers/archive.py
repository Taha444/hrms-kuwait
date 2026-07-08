# -*- coding: utf-8 -*-
"""أرشيف الشركة والفرع: المستندات الرسمية (عقد التأسيس، السجل التجاري، رخص…)
مع أرشيف مستقل لكل فرع. الرفع/التنزيل عبر نقاط المستندات الموثّقة."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import assert_same_company, audit, require_perm, scope_company_id

router = APIRouter(prefix="/archive", tags=["archive"])

# أنواع المستندات الرسمية للشركة
COMPANY_DOC_TYPES = [
    ("incorporation_contract", "عقد التأسيس"),
    ("commercial_reg", "السجل التجاري"),
    ("municipality_license", "رخصة البلدية"),
    ("fire_license", "رخصة المطافي"),
    ("company_license", "ترخيص الشركة"),
    ("manpower_file", "ملف القوى العاملة"),
    ("tax_card", "البطاقة الضريبية"),
    ("other_official", "مستند رسمي آخر"),
]
BRANCH_DOC_TYPES = [
    ("branch_license", "ترخيص الفرع"),
    ("branch_municipality", "رخصة بلدية الفرع"),
    ("branch_fire", "رخصة مطافي الفرع"),
    ("branch_lease", "عقد إيجار الفرع"),
    ("other_official", "مستند رسمي آخر"),
]


def _docs_for(db: Session, entity_type: str, entity_id: int) -> list[dict]:
    rows = db.scalars(select(models.Document).where(
        models.Document.entity_type == entity_type,
        models.Document.entity_id == entity_id,
        models.Document.is_current == True,  # noqa: E712
    )).all()
    return [{"id": d.id, "type": d.document_type_code, "title": d.title,
             "expiry_date": d.expiry_date, "version": d.version,
             "created_at": d.created_at} for d in rows]


@router.get("/company")
def company_archive(company_id: int | None = None,
                    user: models.User = Depends(require_perm("view_documents")),
                    db: Session = Depends(get_db)):
    cid = scope_company_id(user, company_id)
    if cid is None:
        raise HTTPException(status_code=400, detail="اختر شركة لعرض أرشيفها")
    company = db.get(models.Company, cid)
    if not company:
        raise HTTPException(status_code=404, detail="الشركة غير موجودة")
    return {
        "company": {"id": company.id, "name": company.name,
                    "commercial_reg": company.commercial_reg, "file_number": company.file_number,
                    "entity_type": company.entity_type},
        "doc_types": [{"code": c, "name": n} for c, n in COMPANY_DOC_TYPES],
        "documents": _docs_for(db, "company", company.id),
    }


@router.put("/company/info")
def update_company_info(file_number: str | None = None, company_id: int | None = None,
                        user: models.User = Depends(require_perm("manage_company")),
                        db: Session = Depends(get_db)):
    cid = scope_company_id(user, company_id)
    if cid is None:
        raise HTTPException(status_code=400, detail="اختر شركة")
    company = db.get(models.Company, cid)
    if not company:
        raise HTTPException(status_code=404, detail="الشركة غير موجودة")
    if file_number is not None:
        company.file_number = file_number
    audit(db, user, "update_company_archive", "company", company.id)
    db.commit()
    return {"ok": True, "file_number": company.file_number}


@router.get("/branch/{branch_id}")
def branch_archive(branch_id: int,
                   user: models.User = Depends(require_perm("view_documents")),
                   db: Session = Depends(get_db)):
    branch = db.get(models.Branch, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="الفرع غير موجود")
    assert_same_company(user, branch.company_id, db=db)
    return {
        "branch": {"id": branch.id, "name": branch.name, "address": branch.address},
        "doc_types": [{"code": c, "name": n} for c, n in BRANCH_DOC_TYPES],
        "documents": _docs_for(db, "branch", branch.id),
    }
