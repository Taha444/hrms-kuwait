# -*- coding: utf-8 -*-
"""وحدة المندوب (PRO): متابعة الإقامات/أذونات العمل والتراخيص، التجديد،
الجهات الحكومية، الملاحظات، ومتابعة الانتهاء."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import assert_same_company, audit, get_current_user, require_perm, scope_company_id
from ..notifications import create_task

router = APIRouter(prefix="/pro", tags=["pro"])

# جهات حكومية كويتية شائعة (لتصنيف التراخيص)
GOV_ENTITIES = ["بلدية الكويت", "وزارة التجارة والصناعة", "الإطفاء (المطافي)",
                "الهيئة العامة للقوى العاملة", "وزارة الداخلية"]


def _urgency(days_left: int | None) -> str:
    if days_left is None:
        return "none"
    if days_left < 0:
        return "expired"
    if days_left <= 30:
        return "critical"
    if days_left <= 90:
        return "warning"
    return "ok"


@router.get("/permits")
def list_permits(company_id: int | None = None, kind: str | None = None,
                 status: str | None = None, branch_id: int | None = None,
                 user: models.User = Depends(require_perm("manage_permits")),
                 db: Session = Depends(get_db)):
    """متابعة الإقامات وأذونات العمل مع أيام الانتهاء والأولوية."""
    cid = scope_company_id(user, company_id)
    q = select(models.Permit)
    if cid is not None:
        q = q.where(models.Permit.company_id == cid)
    if kind:
        q = q.where(models.Permit.kind == kind)
    if status:
        q = q.where(models.Permit.status == status)
    permits = db.scalars(q).all()
    emp_map = {e.id: e for e in db.scalars(select(models.Employee)).all()}
    today = date.today()
    out = []
    for p in permits:
        emp = emp_map.get(p.employee_id)
        if branch_id and (not emp or emp.branch_id != branch_id):
            continue
        days_left = (p.expiry_date - today).days if p.expiry_date else None
        out.append({
            "id": p.id, "kind": p.kind, "number": p.number,
            "employee_id": p.employee_id, "employee_name": emp.name if emp else None,
            "branch_id": emp.branch_id if emp else None,
            "start_date": p.start_date, "expiry_date": p.expiry_date,
            "status": p.status, "days_left": days_left, "urgency": _urgency(days_left),
        })
    out.sort(key=lambda x: (x["days_left"] is None, x["days_left"] if x["days_left"] is not None else 1e9))
    return out


@router.post("/permits/{permit_id}/renew")
def renew_permit(permit_id: int, expiry_date: date, request: Request,
                 number: str | None = None, start_date: date | None = None, note: str | None = None,
                 user: models.User = Depends(require_perm("manage_permits")),
                 db: Session = Depends(get_db)):
    """تجديد إقامة/إذن عمل: تحديث التاريخ + تسجيل في سجلّ المندوب + إغلاق مهام التجديد."""
    p = db.get(models.Permit, permit_id)
    if not p:
        raise HTTPException(status_code=404, detail="السجل غير موجود")
    assert_same_company(user, p.company_id, db=db)
    old_expiry = p.expiry_date
    p.expiry_date = expiry_date
    if number:
        p.number = number
    if start_date:
        p.start_date = start_date
    p.status = "active"
    db.add(models.GovLog(company_id=p.company_id, entity_type="permit", entity_id=p.id,
                         action="renew", created_by=user.id,
                         note=f"تجديد حتى {expiry_date} (كان {old_expiry}). {note or ''}".strip()))
    # إغلاق مهام التجديد المرتبطة
    for task_type in ("renew_residency", "renew_work_permit"):
        for tk in db.scalars(select(models.Task).where(
                models.Task.related_entity_type == "permit",
                models.Task.related_entity_id == p.id,
                models.Task.type == task_type,
                models.Task.status.in_(["open", "in_progress"]))).all():
            tk.status = "done"
    audit(db, user, "renew_permit", "permit", p.id, detail=str(expiry_date), request=request)
    db.commit()
    return {"ok": True, "id": p.id, "expiry_date": p.expiry_date}


@router.post("/licenses/{license_id}/renew")
def renew_license(license_id: int, expiry_date: date, request: Request, note: str | None = None,
                  user: models.User = Depends(require_perm("manage_licenses")),
                  db: Session = Depends(get_db)):
    lic = db.get(models.License, license_id)
    if not lic:
        raise HTTPException(status_code=404, detail="الترخيص غير موجود")
    assert_same_company(user, lic.company_id, db=db)
    old = lic.expiry_date
    lic.expiry_date = expiry_date
    lic.status = "active"
    db.add(models.GovLog(company_id=lic.company_id, entity_type="license", entity_id=lic.id,
                         action="renew", created_by=user.id,
                         note=f"تجديد حتى {expiry_date} (كان {old}). {note or ''}".strip()))
    audit(db, user, "renew_license", "license", lic.id, detail=str(expiry_date), request=request)
    db.commit()
    return {"ok": True, "id": lic.id, "expiry_date": lic.expiry_date}


@router.post("/notes")
def add_note(entity_type: str, entity_id: int, note: str, request: Request,
             user: models.User = Depends(require_perm("process_delegate_tasks")),
             db: Session = Depends(get_db)):
    """تسجيل ملاحظة على معاملة (إقامة/ترخيص)."""
    if entity_type not in ("permit", "license"):
        raise HTTPException(status_code=400, detail="نوع غير صالح")
    entity = db.get(models.Permit if entity_type == "permit" else models.License, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="السجل غير موجود")
    assert_same_company(user, entity.company_id, db=db)
    log = models.GovLog(company_id=entity.company_id, entity_type=entity_type,
                        entity_id=entity_id, action="note", note=note, created_by=user.id)
    db.add(log)
    db.commit()
    return {"ok": True}


@router.get("/notes")
def list_notes(entity_type: str, entity_id: int,
               user: models.User = Depends(require_perm("manage_permits")),
               db: Session = Depends(get_db)):
    rows = db.scalars(select(models.GovLog).where(
        models.GovLog.entity_type == entity_type, models.GovLog.entity_id == entity_id)
        .order_by(models.GovLog.created_at.desc())).all()
    names = {u.id: u.full_name for u in db.scalars(select(models.User)).all()}
    return [{"action": r.action, "note": r.note, "by": names.get(r.created_by),
             "at": r.created_at} for r in rows]


@router.get("/government")
def government_overview(company_id: int | None = None,
                        user: models.User = Depends(require_perm("manage_licenses")),
                        db: Session = Depends(get_db)):
    """نظرة على الجهات الحكومية: التراخيص مجمّعة حسب الجهة المُصدِرة + المنتهية قريبًا."""
    cid = scope_company_id(user, company_id)
    q = select(models.License)
    if cid is not None:
        q = q.where(models.License.company_id == cid)
    licenses = db.scalars(q).all()
    today = date.today()
    groups: dict[str, list] = {}
    for lic in licenses:
        authority = lic.issuing_authority or "غير محدّد"
        days_left = (lic.expiry_date - today).days if lic.expiry_date else None
        groups.setdefault(authority, []).append({
            "id": lic.id, "name": lic.name, "license_no": lic.license_no,
            "license_type": lic.license_type, "status": lic.status,
            "expiry_date": lic.expiry_date, "days_left": days_left,
            "urgency": _urgency(days_left),
        })
    return {"entities": [{"authority": a, "licenses": ls} for a, ls in groups.items()],
            "known_authorities": GOV_ENTITIES}
