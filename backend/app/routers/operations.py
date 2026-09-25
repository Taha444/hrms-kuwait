# -*- coding: utf-8 -*-
"""مركز العمليات والامتثال (Operations & Compliance Center): يجمع كل ما يحتاج متابعة."""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fastapi import HTTPException

from .. import models
from ..database import get_db
from ..deps import get_current_user, get_user_perms, scope_company_id
from ..permissions import has_permission
from ..clock import today as kuwait_today
from ..expiry_windows import WINDOW_DAYS

router = APIRouter(prefix="/operations", tags=["operations"])

# مركز العمليات يعرض إقامات/أذونات/تراخيص (معاملات حكومية) — للـ PRO/الإدارة العليا فقط.
_OPS_MANAGEMENT_ROLES = {"super_admin"}


def require_operations(user: models.User = Depends(get_current_user),
                       db: Session = Depends(get_db)) -> models.User:
    """يسمح بمركز العمليات للإدارة العليا أو من يملك صلاحية إقامات/تراخيص (PRO)."""
    if user.role in _OPS_MANAGEMENT_ROLES:
        return user
    assigned = get_user_perms(user, db)
    if has_permission(user.role, assigned, "manage_permits") or \
       has_permission(user.role, assigned, "manage_licenses"):
        return user
    raise HTTPException(status_code=403, detail="مركز العمليات غير متاح لدورك")


def _urgency(days: int | None) -> str:
    from ..expiry_windows import urgency
    return urgency(days)


@router.get("")
def operations_center(company_id: int | None = None, branch_id: int | None = None,
                      user: models.User = Depends(require_operations), db: Session = Depends(get_db)):
    """كل العناصر التي تتطلّب إجراءً: إقامات/تراخيص قرب الانتهاء، طلبات معلّقة، مهام مفتوحة."""
    cid = scope_company_id(user, company_id)
    today = kuwait_today()

    emp_map = {e.id: e for e in db.scalars(
        select(models.Employee).where(*( [models.Employee.company_id == cid] if cid is not None else []))).all()}
    branch_of = lambda eid: emp_map.get(eid).branch_id if emp_map.get(eid) else None  # noqa: E731

    # الإقامات وأذونات العمل
    pq = select(models.Permit).where(models.Permit.status == "active",
                                     models.Permit.expiry_date.isnot(None))
    if cid is not None:
        pq = pq.where(models.Permit.company_id == cid)
    permits = []
    for p in db.scalars(pq).all():
        if branch_id and branch_of(p.employee_id) != branch_id:
            continue
        days = (p.expiry_date - today).days
        if days > WINDOW_DAYS:
            continue
        permits.append({"id": p.id, "type": "residency" if p.kind == "residency" else "work_permit",
                        "number": p.number, "employee": emp_map.get(p.employee_id).name if emp_map.get(p.employee_id) else None,
                        "expiry_date": p.expiry_date.isoformat(), "days_left": days, "urgency": _urgency(days)})
    permits.sort(key=lambda x: x["days_left"])

    # التراخيص
    lq = select(models.License).where(models.License.status == "active", models.License.expiry_date.isnot(None))
    if cid is not None:
        lq = lq.where(models.License.company_id == cid)
    licenses = []
    for l in db.scalars(lq).all():
        days = (l.expiry_date - today).days
        if days > WINDOW_DAYS:
            continue
        licenses.append({"id": l.id, "name": l.name, "license_no": l.license_no,
                         "expiry_date": l.expiry_date.isoformat(), "days_left": days, "urgency": _urgency(days)})
    licenses.sort(key=lambda x: x["days_left"])

    # الطلبات المعلّقة
    rq = select(func.count()).select_from(models.Request).where(models.Request.status == "pending")
    if cid is not None:
        rq = rq.where(models.Request.company_id == cid)
    pending_requests = db.scalar(rq) or 0

    # المهام الحكومية المفتوحة
    # QA-20/BKL-06 — التعريف **والنطاق** من مصدر واحد، والقائمة تُبنى من
    # الاستعلام الذي يُشتقّ منه العدّاد. فالرقم الظاهر هو طول القائمة التي
    # تُفتح تحته حرفيًّا — لا رقم يقول 29 وقائمة تعرض 12.
    from ..gov_tasks import count_gov_tasks, list_gov_tasks
    open_gov_tasks = count_gov_tasks(db, company_id=cid)
    gov_task_rows = [
        {"id": tk.id, "type": tk.type, "title": tk.title, "detail": tk.detail,
         "severity": tk.severity, "due_date": tk.due_date,
         "assignee_user_id": tk.assignee_user_id,
         "related_entity_type": tk.related_entity_type,
         "related_entity_id": tk.related_entity_id,
         "created_at": tk.created_at}
        for tk in list_gov_tasks(db, company_id=cid)
    ]

    # ملخّص الامتثال
    all_items = permits + licenses
    compliance = {
        "expired": sum(1 for x in all_items if x["urgency"] == "expired"),
        "critical": sum(1 for x in all_items if x["urgency"] == "critical"),
        "warning": sum(1 for x in all_items if x["urgency"] == "warning"),
    }

    # قرار المالك (2026-09-17) — من يعمل على غير ترخيص تسجيله.
    from ..license_mismatch import mismatches
    license_mismatch = [m for m in mismatches(db, cid)
                        if not branch_id or m["branch_id"] == branch_id]
    # من لن يصدر له عقدٌ حكومي — بقاعدة المولِّد نفسها (gov_contract_form).
    from ..gov_contract_readiness import readiness
    scope_ids = ([cid] if cid is not None else
                 [c.id for c in db.scalars(select(models.Company)).all()])
    contract_readiness = []
    for company_id in scope_ids:
        r = readiness(db, company_id)
        if branch_id:
            r["employees"] = [e for e in r["employees"] if e["branch_id"] == branch_id]
        if r["company_missing"] or r["employees"]:
            contract_readiness.append(r)
    return {
        "gov_contract_readiness": contract_readiness,
        "license_mismatch": license_mismatch,
        "compliance": compliance,
        "permits": permits,
        "licenses": licenses,
        "pending_requests": pending_requests,
        "open_gov_tasks": open_gov_tasks,
        # القائمة نفسها، لا عدداً فقط: رقم بلا وجهة تعرضه يبقى ادّعاءً
        "gov_tasks": gov_task_rows,
    }
