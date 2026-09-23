# -*- coding: utf-8 -*-
"""الشركات: CRUD + تفعيل/تعطيل/أرشفة (الإدارة العليا)."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from .. import permissions
from ..deps import (audit, get_current_user, require_owner_or_admin, require_perm,
                    require_super_admin)

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=list[schemas.CompanyOut])
def list_companies(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    from ..permissions import CROSS_COMPANY_ROLES

    q = select(models.Company)
    if user.role not in CROSS_COMPANY_ROLES:
        # المستخدم العادي يرى شركته فقط
        q = q.where(models.Company.id == user.company_id)
    return list(db.scalars(q.order_by(models.Company.name)).all())


def _check_commercial_reg_unique(db: Session, cr: str | None, exclude_id: int | None = None):
    """PILOT-P0-11: منع تكرار السجل التجاري بين شركتين (كان ممكن قبل الفحص)."""
    if not cr or not cr.strip():
        return
    cr = cr.strip()
    q = select(models.Company).where(models.Company.commercial_reg == cr)
    if exclude_id is not None:
        q = q.where(models.Company.id != exclude_id)
    existing = db.scalar(q)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"السجل التجاري '{cr}' مستخدم بالفعل في شركة '{existing.name}'",
        )


@router.post("", response_model=schemas.CompanyOut, status_code=201)
def create_company(data: schemas.CompanyIn, request: Request,
                   user: models.User = Depends(require_owner_or_admin),
                   db: Session = Depends(get_db)):
    _check_commercial_reg_unique(db, data.commercial_reg)
    company = models.Company(**data.model_dump())
    db.add(company)
    # **والفحُص أعاله ال يرى الطلَب الموازي.** ``uq_companies_commercial_reg``
    # يُغلق النافذَة في القاعدة — **ويُترجَم إلى الرسالة نفسها**: قيٌد يردّ
    # خمسمئة بادَل تسابًقا بانهيار، والمستخدُم ال يفرّق بين اثنين.
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(f"السجل التجاري '{(data.commercial_reg or '').strip()}' "
                    "مستخدم بالفعل في شركة أخرى"))
    audit(db, user, "create_company", "company", company.id, request=request)
    db.commit()
    db.refresh(company)
    return company


@router.put("/{company_id}", response_model=schemas.CompanyOut)
def update_company(company_id: int, data: schemas.CompanyUpdate, request: Request,
                   user: models.User = Depends(require_perm("manage_company")),
                   db: Session = Depends(get_db)):
    """CO-EDIT — تعديل شركة. **وما لا يُرسَل لا يُمسّ.**

    كان يكتب النموذج كامًلا بقيمه الافتراضية، فتعديل الاسم وحده يُصفّر
    ``eos_day_divisor`` و``eos_max_months`` ومهلة التنبيه وأيام الإجازة
    إلى قيم المصنع — **وهي أرقاٌم تُحسب بها مستحقات نهاية خدمة الموظفين**.
    """
    # **قرار المالك (2026-09-11)** — التعديل بـ``manage_company`` لا
    # بـ``super_admin``: كانت بيانات الشركة لا يعدّلها أحٌد في الإنتاج، لأن
    # القاعدة المعلَنة تمنع منح ``super_admin`` لأيّ شخص.
    #
    # **والنطاق يُحرَس هنا** لأن المعرّف في المسار لا في الاستعلام: فلا
    # يمرّ عليه ``scope_company_id`` الذي يُجبِر غير العابرين على شركتهم.
    # وبلا هذا الفحص يصير مدير شركٍة قادًرا على تعديل شركٍة أخرى بتبديل
    # رقٍم في العنوان — وهي أوسع مما طُلب. والإنشاء والتعطيل يبقيان
    # للإدارة العليا بقرار المالك نفسه.
    if user.role not in permissions.CROSS_COMPANY_ROLES \
            and user.company_id != company_id:
        raise HTTPException(status_code=403, detail="لا تملك تعديل بيانات شركة أخرى")

    company = db.get(models.Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="الشركة غير موجودة")
    payload = data.model_dump(exclude_unset=True)
    if "commercial_reg" in payload:
        _check_commercial_reg_unique(db, payload["commercial_reg"], exclude_id=company_id)
    for k, v in payload.items():
        setattr(company, k, v)
    audit(db, user, "update_company", "company", company.id, request=request)
    db.commit()
    db.refresh(company)
    return company


@router.get("/{company_id}/representatives", response_model=list[schemas.CompanyRepresentativeOut])
def list_representatives(company_id: int, user: models.User = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    """GC-11 — قائمة الممثّلين المفوَّضين بالتوقيع عن الشركة، لاختيار "الطرف
    الأول" وقت توليد العقد الحكومي. نفس نطاق ``list_companies``: شركته وحدها
    لغير العابرين — رقمها المدني بيانٌ شخصي يُطبع في مستند رسمي."""
    from ..permissions import CROSS_COMPANY_ROLES

    if user.role not in CROSS_COMPANY_ROLES and user.company_id != company_id:
        raise HTTPException(status_code=403, detail="لا تملك الاطلاع على ممثّلي شركة أخرى")
    q = select(models.CompanyRepresentative).where(
        models.CompanyRepresentative.company_id == company_id,
        models.CompanyRepresentative.status == "active",
    ).order_by(models.CompanyRepresentative.id)
    return list(db.scalars(q).all())


@router.post("/{company_id}/status")
def set_status(company_id: int, status: str, request: Request,
               user: models.User = Depends(require_owner_or_admin),
               db: Session = Depends(get_db)):
    if status not in ("active", "inactive", "archived"):
        raise HTTPException(status_code=400, detail="حالة غير صالحة")
    company = db.get(models.Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="الشركة غير موجودة")
    company.status = status
    audit(db, user, f"company_status_{status}", "company", company.id, request=request)
    db.commit()
    return {"ok": True, "status": status}
