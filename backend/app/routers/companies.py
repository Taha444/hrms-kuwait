# -*- coding: utf-8 -*-
"""الشركات: CRUD + تفعيل/تعطيل/أرشفة (الإدارة العليا)."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import audit, get_current_user, require_super_admin

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=list[schemas.CompanyOut])
def list_companies(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    from ..permissions import CROSS_COMPANY_ROLES

    q = select(models.Company)
    if user.role not in CROSS_COMPANY_ROLES:
        # المستخدم العادي يرى شركته فقط
        q = q.where(models.Company.id == user.company_id)
    return list(db.scalars(q.order_by(models.Company.name)).all())


@router.post("", response_model=schemas.CompanyOut, status_code=201)
def create_company(data: schemas.CompanyIn, request: Request,
                   user: models.User = Depends(require_super_admin), db: Session = Depends(get_db)):
    company = models.Company(**data.model_dump())
    db.add(company)
    db.flush()
    audit(db, user, "create_company", "company", company.id, request=request)
    db.commit()
    db.refresh(company)
    return company


@router.put("/{company_id}", response_model=schemas.CompanyOut)
def update_company(company_id: int, data: schemas.CompanyIn, request: Request,
                   user: models.User = Depends(require_super_admin), db: Session = Depends(get_db)):
    company = db.get(models.Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="الشركة غير موجودة")
    for k, v in data.model_dump().items():
        setattr(company, k, v)
    audit(db, user, "update_company", "company", company.id, request=request)
    db.commit()
    db.refresh(company)
    return company


@router.post("/{company_id}/status")
def set_status(company_id: int, status: str, request: Request,
               user: models.User = Depends(require_super_admin), db: Session = Depends(get_db)):
    if status not in ("active", "inactive", "archived"):
        raise HTTPException(status_code=400, detail="حالة غير صالحة")
    company = db.get(models.Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="الشركة غير موجودة")
    company.status = status
    audit(db, user, f"company_status_{status}", "company", company.id, request=request)
    db.commit()
    return {"ok": True, "status": status}
