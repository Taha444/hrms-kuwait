# -*- coding: utf-8 -*-
"""مركز العمليات والامتثال (Operations & Compliance Center): يجمع كل ما يحتاج متابعة."""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import get_current_user, scope_company_id

router = APIRouter(prefix="/operations", tags=["operations"])


def _urgency(days: int | None) -> str:
    if days is None:
        return "ok"
    if days < 0:
        return "expired"
    if days <= 30:
        return "critical"
    if days <= 90:
        return "warning"
    return "ok"


@router.get("")
def operations_center(company_id: int | None = None, branch_id: int | None = None,
                      user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """كل العناصر التي تتطلّب إجراءً: إقامات/تراخيص قرب الانتهاء، طلبات معلّقة، مهام مفتوحة."""
    cid = scope_company_id(user, company_id)
    today = date.today()

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
        if days > 90:
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
        if days > 90:
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
    tq = select(func.count()).select_from(models.Task).where(
        models.Task.status == "open",
        models.Task.type.in_(["renew_residency", "renew_work_permit", "license_expiring",
                              "doc_expiring", "transfer_info", "exit_permit", "capacity_exceeded"]))
    if cid is not None:
        tq = tq.where(models.Task.company_id == cid)
    open_gov_tasks = db.scalar(tq) or 0

    # ملخّص الامتثال
    all_items = permits + licenses
    compliance = {
        "expired": sum(1 for x in all_items if x["urgency"] == "expired"),
        "critical": sum(1 for x in all_items if x["urgency"] == "critical"),
        "warning": sum(1 for x in all_items if x["urgency"] == "warning"),
    }

    return {
        "compliance": compliance,
        "permits": permits,
        "licenses": licenses,
        "pending_requests": pending_requests,
        "open_gov_tasks": open_gov_tasks,
    }
