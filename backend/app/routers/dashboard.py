# -*- coding: utf-8 -*-
"""لوحات التحكم: مؤشرات مختلفة حسب الدور (إدارة عليا / مدير / HR / عامل)."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import get_current_user, scope_company_id

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(company_id: int | None = None,
             user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    cid = scope_company_id(user, company_id)
    today = date.today()
    soon = today + timedelta(days=90)

    def _count(model, *conds):
        q = select(func.count()).select_from(model)
        if cid is not None and hasattr(model, "company_id"):
            q = q.where(model.company_id == cid)
        for c in conds:
            q = q.where(c)
        return db.scalar(q) or 0

    open_tasks = db.scalar(
        select(func.count()).select_from(models.Task)
        .where(models.Task.assignee_user_id == user.id, models.Task.status == "open")
    ) or 0

    expiring_permits = _count(models.Permit, models.Permit.status == "active",
                              models.Permit.expiry_date.isnot(None),
                              models.Permit.expiry_date <= soon)

    data = {
        "role": user.role,
        "companies": db.scalar(select(func.count()).select_from(models.Company)) or 0
        if user.role == "super_admin" else None,
        "employees": _count(models.Employee, models.Employee.status == "active"),
        "branches": _count(models.Branch),
        "expiring_permits": expiring_permits,
        "open_tasks": open_tasks,
        "pending_requests": _count(models.Request, models.Request.status == "pending"),
    }

    # مؤشرات خاصة بالعامل
    if user.role == "employee" and user.employee_id:
        my_open = db.scalar(
            select(func.count()).select_from(models.Request)
            .where(models.Request.employee_id == user.employee_id,
                   models.Request.status.notin_(["completed", "rejected", "cancelled"]))
        ) or 0
        data["my_active_requests"] = my_open
    return data
