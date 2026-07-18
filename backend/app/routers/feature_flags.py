# -*- coding: utf-8 -*-
"""V1.5 Phase 5 — API إدارة feature flags (super_admin فقط)."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import feature_flags as ff
from .. import models
from ..database import get_db
from ..deps import audit, require_super_admin

router = APIRouter(prefix="/feature-flags", tags=["feature-flags"])


class FlagIn(BaseModel):
    key: str
    value: str
    company_id: int | None = None
    note: str | None = None


@router.get("/registry")
def registry(user: models.User = Depends(require_super_admin)):
    """قائمة الـ flags المعروفة + وصف كل واحد + القيمة الافتراضية."""
    return ff.REGISTRY


@router.get("")
def list_flags(company_id: int | None = None,
               user: models.User = Depends(require_super_admin),
               db: Session = Depends(get_db)):
    """يعرض الحالة الفعّالة لكل الـ flags لشركة محددة (أو للتفعيل العام إن كان company_id=None).
    كل مدخل يبيّن مصدر القيمة (company/global/default)."""
    return ff.list_effective(db, company_id)


@router.get("/raw")
def list_raw_rows(user: models.User = Depends(require_super_admin),
                  db: Session = Depends(get_db)):
    """كل صفوف الـ feature_flags الخام (للتدقيق فقط)."""
    rows = db.scalars(select(models.FeatureFlag).order_by(
        models.FeatureFlag.key, models.FeatureFlag.company_id.nulls_first(),
    )).all()
    return [
        {"id": r.id, "key": r.key, "company_id": r.company_id, "value": r.value,
         "note": r.note, "updated_at": r.updated_at,
         "updated_by_user_id": r.updated_by_user_id}
        for r in rows
    ]


@router.post("", status_code=201)
def set_flag(data: FlagIn, request: Request,
             user: models.User = Depends(require_super_admin),
             db: Session = Depends(get_db)):
    """ضبط قيمة flag لشركة أو للجميع (upsert). يفشل بمفتاح غير معروف."""
    try:
        row = ff.set_flag(
            db, data.key, data.value, company_id=data.company_id,
            note=data.note, updated_by_user_id=user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    scope = f"شركة #{data.company_id}" if data.company_id else "عام"
    audit(db, user, "feature_flag_set", "feature_flag", row.id,
          detail=f"{data.key} = {data.value} ({scope})", request=request)
    db.commit()
    return {"ok": True, "id": row.id, "key": row.key, "value": row.value,
            "company_id": row.company_id}


@router.delete("/{flag_id}")
def delete_flag(flag_id: int, request: Request,
                user: models.User = Depends(require_super_admin),
                db: Session = Depends(get_db)):
    """يحذف تفويض flag (يرجّع للسلوك الأعلى في الأولوية: global أو default)."""
    row = db.get(models.FeatureFlag, flag_id)
    if not row:
        raise HTTPException(status_code=404, detail="غير موجود")
    key = row.key
    db.delete(row)
    audit(db, user, "feature_flag_delete", "feature_flag", flag_id, detail=key,
          request=request)
    db.commit()
    return {"ok": True}
