# -*- coding: utf-8 -*-
"""لوحات التحكم: مؤشرات مختلفة حسب الدور (إدارة عليا / مدير / PRO / HR / عامل)."""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
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

    # ----- المالك: لوحة رقابية للاطلاع فقط (موظفون/فروع/إقامات/تراخيص/أداء/إشعارات) -----
    if role == "company_owner":
        active_emps = count(models.Employee, models.Employee.status == "active")
        day_start = datetime(today.year, today.month, today.day)
        pq = select(func.count(func.distinct(models.AttendanceRecord.employee_id))).where(
            models.AttendanceRecord.check_in_at >= day_start)
        if cid is not None:
            pq = pq.where(models.AttendanceRecord.company_id == cid)
        present_today = db.scalar(pq) or 0

        total_licenses = count(models.License)
        valid_licenses = count(models.License, models.License.status == "active",
                               or_(models.License.expiry_date.is_(None),
                                   models.License.expiry_date >= today))
        expired_licenses = count(models.License, models.License.expiry_date.isnot(None),
                                 models.License.expiry_date < today)
        pct = lambda n, d: round(n / d * 100) if d else 0  # noqa: E731

        data.update({
            "employees": active_emps,
            "branches": count(models.Branch),
            "residencies": count(models.Permit, models.Permit.kind == "residency",
                                 models.Permit.status == "active"),
            "residencies_expiring": count(models.Permit, models.Permit.kind == "residency",
                                          models.Permit.status == "active",
                                          models.Permit.expiry_date.isnot(None),
                                          models.Permit.expiry_date <= soon),
            "licenses": valid_licenses,
            "licenses_expiring": count(models.License, models.License.status == "active",
                                       models.License.expiry_date.isnot(None),
                                       models.License.expiry_date <= soon),
            "performance": {
                "attendance_rate": pct(present_today, active_emps),
                "valid_licenses_pct": pct(valid_licenses, total_licenses),
                "expired_licenses_pct": pct(expired_licenses, total_licenses),
            },
            "notifications": my_open_tasks,
            "owner_view": True,
        })
        return data

    # ----- مؤشرات مشتركة -----
    expiring_permits = count(models.Permit, models.Permit.status == "active",
                             models.Permit.expiry_date.isnot(None), models.Permit.expiry_date <= soon)
    data["open_tasks"] = my_open_tasks

    if role == "super_admin":
        data["companies"] = db.scalar(select(func.count()).select_from(models.Company)) or 0

    # ----- PRO / المندوب: المعاملات الحكومية فقط -----
    if role == "delegate":
        soon30 = today + timedelta(days=30)
        crit_tasks = db.scalar(select(func.count()).select_from(models.Task).where(
            models.Task.assignee_user_id == user.id, models.Task.status == "open",
            models.Task.severity == "critical")) or 0
        data.update({
            "expired_residencies": count(models.Permit, models.Permit.kind == "residency",
                                         models.Permit.status == "active",
                                         models.Permit.expiry_date.isnot(None),
                                         models.Permit.expiry_date < today),
            "residencies_expiring_30": count(models.Permit, models.Permit.kind == "residency",
                                             models.Permit.status == "active",
                                             models.Permit.expiry_date.isnot(None),
                                             models.Permit.expiry_date >= today,
                                             models.Permit.expiry_date <= soon30),
            "expiring_work_permits": count(models.Permit, models.Permit.kind == "work_permit",
                                           models.Permit.status == "active",
                                           models.Permit.expiry_date.isnot(None),
                                           models.Permit.expiry_date <= soon),
            "expiring_licenses": count(models.License, models.License.status == "active",
                                       models.License.expiry_date.isnot(None),
                                       models.License.expiry_date <= soon),
            "open_transactions": count(models.Request, models.Request.status == "awaiting_delegate"),
            "gov_tasks": my_open_tasks,
            "notifications": crit_tasks,
        })
        return data

    # ----- مسؤول الفرع: فرعه فقط (موظفو الفرع/مهام/طلبات/إشعارات) -----
    if role == "branch_supervisor":
        from ..deps import resolve_scope
        bids = resolve_scope(user, db).branch_ids or {-1}
        crit_tasks = db.scalar(select(func.count()).select_from(models.Task).where(
            models.Task.assignee_user_id == user.id, models.Task.status == "open",
            models.Task.severity == "critical")) or 0
        emp_ids = select(models.Employee.id).where(models.Employee.branch_id.in_(bids))
        if cid is not None:
            emp_ids = emp_ids.where(models.Employee.company_id == cid)
        branch_emps = db.scalar(select(func.count()).select_from(models.Employee).where(
            models.Employee.status == "active", models.Employee.branch_id.in_(bids))) or 0
        pending = db.scalar(select(func.count()).select_from(models.Request).where(
            models.Request.status == "pending", models.Request.employee_id.in_(emp_ids))) or 0
        data.update({
            "branch_employees": branch_emps,
            "open_tasks": my_open_tasks,
            "pending_requests": pending,
            "notifications": crit_tasks,
        })
        return data

    # ----- HR: الموظفون/الإجازات/العقود/الإنذارات/طلبات الموظفين (لا حكومة) -----
    if role == "hr":
        data.update({
            "employees": count(models.Employee, models.Employee.status == "active"),
            "on_leave": count(models.Leave, models.Leave.status == "approved",
                              models.Leave.start_date <= today, models.Leave.end_date >= today),
            "contracts": count(models.Employee, models.Employee.status == "active"),
            "warnings": count(models.EmployeeEvent, models.EmployeeEvent.kind == "warning"),
            "pending_requests": count(models.Request, models.Request.status == "pending"),
        })
        return data

    # ----- مدير الشركة: تشغيل يومي (موظفون/فروع/طلبات/إجازات/تنبيهات/عقود) -----
    if role == "company_manager":
        data.update({
            "employees": count(models.Employee, models.Employee.status == "active"),
            "branches": count(models.Branch),
            "pending_requests": count(models.Request, models.Request.status == "pending"),
            "on_leave": count(models.Leave, models.Leave.status == "approved",
                              models.Leave.start_date <= today, models.Leave.end_date >= today),
            "notifications": my_open_tasks,
            "contracts": count(models.Employee, models.Employee.status == "active"),
        })
        return data

    # ----- الإدارة العليا / أدوار أخرى -----
    data.update({
        "employees": count(models.Employee, models.Employee.status == "active"),
        "branches": count(models.Branch),
        "expiring_permits": expiring_permits,
        "pending_requests": count(models.Request, models.Request.status == "pending"),
    })
    return data
