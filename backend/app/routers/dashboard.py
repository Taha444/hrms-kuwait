# -*- coding: utf-8 -*-
"""لوحات التحكم: مؤشرات مختلفة حسب الدور (إدارة عليا / مدير / PRO / HR / عامل)."""
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

    def count(model, *conds):
        q = select(func.count()).select_from(model)
        if cid is not None and hasattr(model, "company_id"):
            q = q.where(model.company_id == cid)
        for c in conds:
            q = q.where(c)
        return db.scalar(q) or 0

    my_open_tasks = db.scalar(
        select(func.count()).select_from(models.Task)
        .where(models.Task.assignee_user_id == user.id, models.Task.status == "open")) or 0

    role = user.role
    data: dict = {"role": role}

    # ----- العامل: لا إحصائيات شركة، فقط مهامه وطلباته -----
    if role == "employee":
        my_reqs = db.scalar(
            select(func.count()).select_from(models.Request).where(
                models.Request.employee_id == (user.employee_id or -1),
                models.Request.status.notin_(["completed", "rejected", "cancelled"]))) or 0
        data.update({"my_open_tasks": my_open_tasks, "my_active_requests": my_reqs,
                     "personal_only": True})
        return data

    # ----- مؤشرات مشتركة -----
    expiring_permits = count(models.Permit, models.Permit.status == "active",
                             models.Permit.expiry_date.isnot(None), models.Permit.expiry_date <= soon)
    data["open_tasks"] = my_open_tasks

    if role == "super_admin":
        data["companies"] = db.scalar(select(func.count()).select_from(models.Company)) or 0

    # ----- PRO / المندوب: إقامات وتراخيص ومهام حكومية -----
    if role == "delegate":
        data.update({
            "expiring_residencies": count(models.Permit, models.Permit.kind == "residency",
                                          models.Permit.status == "active",
                                          models.Permit.expiry_date.isnot(None),
                                          models.Permit.expiry_date <= soon),
            "expiring_work_permits": count(models.Permit, models.Permit.kind == "work_permit",
                                           models.Permit.status == "active",
                                           models.Permit.expiry_date.isnot(None),
                                           models.Permit.expiry_date <= soon),
            "expiring_licenses": count(models.License, models.License.status == "active",
                                       models.License.expiry_date.isnot(None),
                                       models.License.expiry_date <= soon),
        })
        return data

    # ----- HR: إحصائيات الموظفين فقط -----
    if role == "hr":
        data.update({
            "employees": count(models.Employee, models.Employee.status == "active"),
            "pending_requests": count(models.Request, models.Request.status == "pending"),
            "on_leave": count(models.Leave, models.Leave.status == "approved",
                              models.Leave.start_date <= today, models.Leave.end_date >= today),
        })
        return data

    # ----- المدير / المالك / الإدارة العليا -----
    data.update({
        "employees": count(models.Employee, models.Employee.status == "active"),
        "branches": count(models.Branch),
        "expiring_permits": expiring_permits,
        "pending_requests": count(models.Request, models.Request.status == "pending"),
    })
    return data
