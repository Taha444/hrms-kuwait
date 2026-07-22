# -*- coding: utf-8 -*-
"""SEC2-15 — سجل المخوّلين بالتوقيع (Authorized Signatories Registry).

نقاط النهاية:
- POST   /signatories                    — إضافة مخوّل جديد
- GET    /signatories                    — قائمة مخوّلي الشركة
- GET    /signatories/resolve            — العثور على المخوّل المناسب لمستند/رمز
- PUT    /signatories/{id}               — تعديل
- DELETE /signatories/{id}               — إلغاء (soft-delete عبر is_active=False)

القواعد:
- المستخدم مسؤول عن سجل شركته فقط (assert_same_company).
- إدارة السجل تتطلب manage_users (سلطة إدارية عليا داخل الشركة).
- resolve يفضّل الأخص (code > prefix > category > any) ويحترم الفترة الزمنية.
"""
from datetime import date, datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import assert_same_company, audit, require_perm, scope_company_id

router = APIRouter(prefix="/signatories", tags=["signatories"])


class SignatoryIn(BaseModel):
    user_id: int
    title_ar: str
    title_en: Optional[str] = None
    scope_type: Literal["any", "code", "prefix", "category"] = "any"
    scope_value: Optional[str] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    company_id: Optional[int] = None
    notes: Optional[str] = None

    @field_validator("title_ar")
    @classmethod
    def _title_required(cls, v):
        if not v or not v.strip():
            raise ValueError("العنوان الوظيفي (title_ar) مطلوب")
        return v.strip()

    @field_validator("scope_value")
    @classmethod
    def _scope_value_if_needed(cls, v, info):
        st = (info.data or {}).get("scope_type")
        if st in ("code", "prefix", "category") and not (v and v.strip()):
            raise ValueError("scope_value مطلوب مع scope_type ≠ any")
        return v.strip() if v else v


class SignatoryOut(BaseModel):
    id: int
    company_id: int
    user_id: int
    user_name: Optional[str] = None
    title_ar: str
    title_en: Optional[str] = None
    scope_type: str
    scope_value: Optional[str] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    is_active: bool


def _to_out(s: models.AuthorizedSignatory, user_name: str | None = None) -> SignatoryOut:
    return SignatoryOut(
        id=s.id, company_id=s.company_id, user_id=s.user_id, user_name=user_name,
        title_ar=s.title_ar, title_en=s.title_en, scope_type=s.scope_type,
        scope_value=s.scope_value, effective_from=s.effective_from,
        effective_to=s.effective_to, is_active=s.is_active,
    )


@router.get("")
def list_signatories(company_id: int | None = None, include_inactive: bool = False,
                     user: models.User = Depends(require_perm("view_documents")),
                     db: Session = Depends(get_db)):
    cid = scope_company_id(user, company_id)
    q = select(models.AuthorizedSignatory)
    if cid is not None:
        q = q.where(models.AuthorizedSignatory.company_id == cid)
    if not include_inactive:
        q = q.where(models.AuthorizedSignatory.is_active.is_(True))
    rows = db.scalars(q.order_by(models.AuthorizedSignatory.id.desc())).all()
    out = []
    for s in rows:
        u = db.get(models.User, s.user_id)
        out.append(_to_out(s, u.full_name if u else None))
    return out


@router.post("", status_code=201)
def create_signatory(data: SignatoryIn, request: Request,
                     user: models.User = Depends(require_perm("manage_users")),
                     db: Session = Depends(get_db)):
    cid = scope_company_id(user, data.company_id)
    if cid is None:
        raise HTTPException(status_code=400, detail="يجب تحديد الشركة")
    signer = db.get(models.User, data.user_id)
    if not signer:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    assert_same_company(user, signer.company_id, db=db)
    if signer.company_id != cid:
        raise HTTPException(status_code=400,
                            detail="المستخدم المخوّل يجب أن يكون من نفس الشركة")
    # منع التكرار الصريح (unique) — يُفرض بالتقاطع الفريد أيضًا في DB
    existing = db.scalar(select(models.AuthorizedSignatory).where(
        models.AuthorizedSignatory.company_id == cid,
        models.AuthorizedSignatory.user_id == data.user_id,
        models.AuthorizedSignatory.scope_type == data.scope_type,
        models.AuthorizedSignatory.scope_value == data.scope_value,
        models.AuthorizedSignatory.is_active.is_(True),
    ))
    if existing:
        raise HTTPException(status_code=409, detail="مخوّل مكرر بنفس النطاق")
    s = models.AuthorizedSignatory(
        company_id=cid, user_id=data.user_id,
        title_ar=data.title_ar, title_en=data.title_en,
        scope_type=data.scope_type, scope_value=data.scope_value,
        effective_from=data.effective_from, effective_to=data.effective_to,
        notes=data.notes, created_by=user.id, is_active=True,
    )
    db.add(s); db.flush()
    audit(db, user, "create_signatory", "signatory", s.id,
          detail=f"user={data.user_id} scope={data.scope_type}:{data.scope_value or '-'}",
          request=request)
    db.commit(); db.refresh(s)
    return _to_out(s, signer.full_name)


@router.put("/{sig_id}")
def update_signatory(sig_id: int, data: SignatoryIn, request: Request,
                     user: models.User = Depends(require_perm("manage_users")),
                     db: Session = Depends(get_db)):
    s = db.get(models.AuthorizedSignatory, sig_id)
    if not s:
        raise HTTPException(status_code=404, detail="غير موجود")
    assert_same_company(user, s.company_id, db=db)
    s.title_ar = data.title_ar
    s.title_en = data.title_en
    s.scope_type = data.scope_type
    s.scope_value = data.scope_value
    s.effective_from = data.effective_from
    s.effective_to = data.effective_to
    s.notes = data.notes
    audit(db, user, "update_signatory", "signatory", s.id, request=request)
    db.commit(); db.refresh(s)
    signer = db.get(models.User, s.user_id)
    return _to_out(s, signer.full_name if signer else None)


@router.delete("/{sig_id}", status_code=200)
def deactivate_signatory(sig_id: int, request: Request,
                         user: models.User = Depends(require_perm("manage_users")),
                         db: Session = Depends(get_db)):
    s = db.get(models.AuthorizedSignatory, sig_id)
    if not s:
        raise HTTPException(status_code=404, detail="غير موجود")
    assert_same_company(user, s.company_id, db=db)
    s.is_active = False
    audit(db, user, "deactivate_signatory", "signatory", s.id, request=request)
    db.commit()
    return {"ok": True, "is_active": False}


def _match_score(s: models.AuthorizedSignatory, doc_code: str, category: str | None) -> int:
    """SEC2-15 — تفضيل الأخص:
       code == exact:100 / prefix match:70 / category match:40 / any:10 / none:0
    """
    if s.scope_type == "code" and s.scope_value == doc_code:
        return 100
    if s.scope_type == "prefix" and doc_code.startswith(s.scope_value or "___"):
        return 70
    if s.scope_type == "category" and category and s.scope_value == category:
        return 40
    if s.scope_type == "any":
        return 10
    return 0


def resolve_authorized_signatory(db: Session, company_id: int, doc_code: str,
                                 category: str | None = None,
                                 as_of: date | None = None) -> models.AuthorizedSignatory | None:
    """يعيد المخوّل الأنسب لطباعة مستند برمز doc_code داخل الشركة (أو None)."""
    d = as_of or date.today()
    rows = db.scalars(select(models.AuthorizedSignatory).where(
        models.AuthorizedSignatory.company_id == company_id,
        models.AuthorizedSignatory.is_active.is_(True),
    )).all()
    valid = [s for s in rows
             if (s.effective_from is None or s.effective_from <= d)
             and (s.effective_to is None or s.effective_to >= d)]
    scored = [(s, _match_score(s, doc_code, category)) for s in valid]
    scored = [(s, sc) for s, sc in scored if sc > 0]
    if not scored:
        return None
    scored.sort(key=lambda x: (-x[1], x[0].id))  # الأعلى نقاطًا أولاً، ثم الأحدث
    return scored[0][0]


@router.get("/resolve")
def resolve_endpoint(doc_code: str, category: str | None = None,
                     company_id: int | None = None, as_of: date | None = None,
                     user: models.User = Depends(require_perm("view_documents")),
                     db: Session = Depends(get_db)):
    cid = scope_company_id(user, company_id)
    if cid is None:
        raise HTTPException(status_code=400, detail="يجب تحديد الشركة")
    s = resolve_authorized_signatory(db, cid, doc_code, category, as_of)
    if not s:
        return {"resolved": False, "reason": "لا يوجد مخوّل مطابق"}
    signer = db.get(models.User, s.user_id)
    return {"resolved": True, "signatory": _to_out(s, signer.full_name if signer else None)}
