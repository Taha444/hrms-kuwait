# -*- coding: utf-8 -*-
"""R8 §1 — Government Portals CRUD.

روابط المواقع الحكومية المستخدمة في شغل المندوب (PACI, Sahel, MOCI, PAM...).
- عرض: PRO + الأدوار الإدارية.
- إدارة (إضافة/تعديل/حذف/إخفاء): super_admin + company_manager.
- الترتيب داخل كل فئة يتحكم فيه sort_order.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import audit, get_current_user, require_super_admin

router = APIRouter(prefix="/gov-portals", tags=["gov-portals"])


CATEGORY_LABELS = {
    "residency": "الإقامات",
    "work_permits": "تصاريح العمل",
    "civil_id": "البطاقة المدنية",
    "moci": "وزارة التجارة",
    "municipality": "البلدية",
    "insurance": "التأمينات",
    "other": "أخرى",
}


class PortalIn(BaseModel):
    name_ar: str = Field(min_length=2, max_length=200)
    name_en: str | None = Field(default=None, max_length=200)
    description_ar: str | None = None
    description_en: str | None = None
    url: str = Field(min_length=5, max_length=500)
    category: str = "other"
    icon: str | None = Field(default=None, max_length=60)
    sort_order: int = 100
    is_active: bool = True


def _can_view_portals(user: models.User) -> bool:
    """PRO + كل الإدارة يشوفوا الروابط. الموظف العادي لا."""
    return user.role in (
        "super_admin", "company_owner", "company_manager",
        "hr", "accountant", "delegate", "admin_employee",
    )


def _can_manage_portals(user: models.User) -> bool:
    """إدارة الروابط لـsuper_admin + company_manager فقط."""
    return user.role in ("super_admin", "company_manager")


@router.get("")
def list_portals(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """قائمة الروابط الفعّالة، مجمّعة حسب الفئة."""
    if not _can_view_portals(user):
        raise HTTPException(status_code=403, detail="لا تملك صلاحية عرض الروابط الحكومية")

    show_hidden = _can_manage_portals(user)
    q = select(models.GovernmentPortal)
    if not show_hidden:
        q = q.where(models.GovernmentPortal.is_active == True)  # noqa: E712
    rows = db.scalars(q.order_by(models.GovernmentPortal.category,
                                 models.GovernmentPortal.sort_order,
                                 models.GovernmentPortal.name_ar)).all()

    # جمِّع حسب الفئة
    groups: dict[str, list[dict]] = {}
    for p in rows:
        item = {
            "id": p.id,
            "name_ar": p.name_ar, "name_en": p.name_en,
            "description_ar": p.description_ar, "description_en": p.description_en,
            "url": p.url, "category": p.category,
            "icon": p.icon, "sort_order": p.sort_order,
            "is_active": p.is_active,
        }
        groups.setdefault(p.category, []).append(item)

    return {
        "can_manage": _can_manage_portals(user),
        "category_labels": CATEGORY_LABELS,
        "groups": [{"category": cat, "label": CATEGORY_LABELS.get(cat, cat), "portals": items}
                   for cat, items in sorted(groups.items(),
                                            key=lambda kv: min(p["sort_order"] for p in kv[1]))],
    }


@router.post("", status_code=201)
def create_portal(data: PortalIn, request: Request,
                  user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not _can_manage_portals(user):
        raise HTTPException(status_code=403, detail="إضافة الروابط لـsuper_admin/company_manager فقط")
    if data.category not in CATEGORY_LABELS:
        raise HTTPException(status_code=400,
                          detail=f"فئة غير معروفة — استخدم: {list(CATEGORY_LABELS.keys())}")
    p = models.GovernmentPortal(**data.model_dump(), created_by=user.id)
    db.add(p)
    db.flush()
    audit(db, user, "create_gov_portal", "gov_portal", p.id,
          detail=f"{p.name_ar} — {p.category}", request=request)
    db.commit()
    return {"ok": True, "id": p.id}


@router.put("/{portal_id}")
def update_portal(portal_id: int, data: PortalIn, request: Request,
                  user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not _can_manage_portals(user):
        raise HTTPException(status_code=403, detail="تعديل الروابط لـsuper_admin/company_manager فقط")
    p = db.get(models.GovernmentPortal, portal_id)
    if not p:
        raise HTTPException(status_code=404, detail="الرابط غير موجود")
    if data.category not in CATEGORY_LABELS:
        raise HTTPException(status_code=400,
                          detail=f"فئة غير معروفة — استخدم: {list(CATEGORY_LABELS.keys())}")
    for k, v in data.model_dump().items():
        setattr(p, k, v)
    audit(db, user, "update_gov_portal", "gov_portal", p.id, request=request)
    db.commit()
    return {"ok": True}


@router.delete("/{portal_id}")
def delete_portal(portal_id: int, request: Request,
                  user: models.User = Depends(require_super_admin), db: Session = Depends(get_db)):
    """حذف نهائي — لـsuper_admin فقط. للإخفاء المؤقت استخدم is_active=false عبر PUT."""
    p = db.get(models.GovernmentPortal, portal_id)
    if not p:
        raise HTTPException(status_code=404, detail="الرابط غير موجود")
    db.delete(p)
    audit(db, user, "delete_gov_portal", "gov_portal", portal_id,
          detail=p.name_ar, request=request)
    db.commit()
    return {"ok": True}
