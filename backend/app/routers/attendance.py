# -*- coding: utf-8 -*-
"""الحضور والانصراف — تدفّق من خطوتين: مسح QR (تحقّق) → تذكرة → سيلفي → تسجيل.

التحقّق كله على الخادم: توقيع الرمز، نطاق الشركة/الفرع، أهلية الموظف، الـ Geofence،
ومنع إعادة الاستخدام (jti). السيلفي إلزامي ويُرسَل كملف (multipart).
"""
import calendar
import os
from datetime import date, datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import settings
from ..database import get_db
from ..deps import assert_same_company, audit, get_current_user, require_perm, scope_company_id
from ..qr import haversine_m
from ..safe_files import read_limited
from .. import qr_token

router = APIRouter(prefix="/attendance", tags=["attendance"])


def _resolve_employee(db: Session, user: models.User) -> models.Employee:
    if not user.employee_id:
        raise HTTPException(status_code=400, detail="حسابك غير مرتبط بملف موظف")
    emp = db.get(models.Employee, user.employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="ملف الموظف غير موجود")
    return emp


def _check_geofence(emp: models.Employee, branch: models.Branch,
                    lat: float | None, lng: float | None):
    needs_gps = emp.attendance_mode in ("gps", "both")
    if needs_gps:
        if lat is None or lng is None or branch.latitude is None:
            raise HTTPException(status_code=400, detail="إحداثيات GPS مطلوبة لهذا النمط")
    if lat is not None and lng is not None and branch.latitude is not None:
        dist = haversine_m(lat, lng, branch.latitude, branch.longitude)
        if dist > branch.geofence_radius_m:
            raise HTTPException(
                status_code=400,
                detail=f"أنت خارج نطاق الفرع ({int(dist)}م > {branch.geofence_radius_m}م)",
            )


@router.post("/validate-qr")
def validate_qr(data: schemas.ValidateQrIn, request: Request,
                user: models.User = Depends(require_perm("record_attendance")),
                db: Session = Depends(get_db)):
    """الخطوة 1: التحقق من رمز QR الممسوح وإصدار تذكرة تسجيل قصيرة."""
    emp = _resolve_employee(db, user)
    if emp.attendance_mode == "none":
        raise HTTPException(status_code=400, detail="الحضور غير مفعّل لهذا الموظف")
    if emp.attendance_mode not in ("qr", "both"):
        raise HTTPException(status_code=400, detail="نمط حضورك لا يعتمد على رمز QR")

    try:
        payload = qr_token.decode(data.qr_token, "qr")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="انتهت صلاحية الرمز، أعد المسح")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="رمز غير صالح")

    branch = db.get(models.Branch, int(payload["branch_id"]))
    if not branch:
        raise HTTPException(status_code=404, detail="الفرع غير موجود")
    # العزل + أهلية الموظف لهذا الفرع
    assert_same_company(user, branch.company_id)
    if emp.branch_id not in (None, branch.id):
        raise HTTPException(status_code=403, detail="أنت غير مُسجَّل على هذا الفرع")

    _check_geofence(emp, branch, data.lat, data.lng)

    # منع إعادة الاستخدام للرموز المتغيّرة فقط؛ الرمز الثابت يُقبل دومًا (يحميه الـ geofence)
    if not payload.get("static"):
        if not qr_token.consume_jti(db, payload["jti"], "qr", payload["exp"]):
            db.commit()
            raise HTTPException(status_code=409, detail="هذا الرمز استُخدم بالفعل، انتظر تجدّده")

    ticket, ticket_exp = qr_token.make_checkin_ticket(emp.id, branch.id)
    audit(db, user, "validate_qr", "branch", branch.id, request=request)
    db.commit()
    return {
        "ok": True,
        "branch": {"id": branch.id, "name": branch.name},
        "checkin_ticket": ticket,
        "ticket_expires_in": qr_token.TICKET_TTL_SECONDS,
    }


@router.post("/check-in")
async def check_in(request: Request, checkin_ticket: str = Form(...),
                   action: str = Form(...), selfie: UploadFile = File(...),
                   user: models.User = Depends(require_perm("record_attendance")),
                   db: Session = Depends(get_db)):
    """الخطوة 2: تسجيل الحضور/الانصراف بالتذكرة + السيلفي الإلزامي."""
    if action not in ("in", "out"):
        raise HTTPException(status_code=400, detail="إجراء غير صالح")
    emp = _resolve_employee(db, user)

    try:
        payload = qr_token.decode(checkin_ticket, "checkin_ticket")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="انتهت صلاحية التذكرة، أعد مسح الرمز")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="تذكرة غير صالحة")

    if int(payload["employee_id"]) != emp.id:
        raise HTTPException(status_code=403, detail="التذكرة لا تخصّك")
    branch = db.get(models.Branch, int(payload["branch_id"]))
    if not branch:
        raise HTTPException(status_code=404, detail="الفرع غير موجود")

    # السيلفي إلزامي (مع حدّ أقصى للحجم)
    raw = await read_limited(selfie)
    if not raw or len(raw) < 200:
        raise HTTPException(status_code=400, detail="صورة السيلفي إلزامية لتسجيل الحضور")
    folder = os.path.join(settings.upload_dir, "selfies")
    os.makedirs(folder, exist_ok=True)
    fname = f"{action}_{emp.id}_{int(datetime.now().timestamp()*1000)}.jpg"
    fpath = os.path.join(folder, fname)
    with open(fpath, "wb") as f:
        f.write(raw)

    # منع إعادة استخدام التذكرة (لمرة واحدة)
    if not qr_token.consume_jti(db, payload["jti"], "checkin_ticket", payload["exp"]):
        db.commit()
        raise HTTPException(status_code=409, detail="هذه التذكرة استُخدمت بالفعل")

    now = datetime.now(timezone.utc)

    if action == "in":
        open_rec = db.scalar(select(models.AttendanceRecord).where(
            models.AttendanceRecord.employee_id == emp.id,
            models.AttendanceRecord.check_out_at.is_(None)))
        if open_rec:
            raise HTTPException(status_code=409, detail="لديك تسجيل حضور مفتوح بالفعل")
        status = _compute_in_status(db, emp, now)
        rec = models.AttendanceRecord(
            company_id=emp.company_id, employee_id=emp.id, branch_id=branch.id,
            check_in_at=now, method=("gps" if emp.attendance_mode == "gps" else "qr"),
            selfie_in_path=fpath, status=status)
        db.add(rec)
        audit(db, user, "check_in", "attendance", emp.id, detail=status, request=request)
        db.commit()
        db.refresh(rec)
        return {"ok": True, "action": "in", "status": status, "check_in_at": rec.check_in_at}

    # action == out
    rec = db.scalar(select(models.AttendanceRecord).where(
        models.AttendanceRecord.employee_id == emp.id,
        models.AttendanceRecord.check_out_at.is_(None)
    ).order_by(models.AttendanceRecord.check_in_at.desc()))
    if not rec:
        raise HTTPException(status_code=404, detail="لا يوجد تسجيل حضور مفتوح")
    rec.check_out_at = now
    rec.selfie_out_path = fpath
    _finalize_out(db, emp, rec, now)
    audit(db, user, "check_out", "attendance", emp.id, request=request)
    db.commit()
    return {"ok": True, "action": "out", "worked_minutes": rec.worked_minutes,
            "overtime_minutes": rec.overtime_minutes, "status": rec.status,
            "check_out_at": rec.check_out_at}


def _compute_in_status(db: Session, emp: models.Employee, now: datetime) -> str:
    if not emp.shift_id:
        return "present"
    shift = db.get(models.Shift, emp.shift_id)
    if not shift:
        return "present"
    cutoff = datetime.combine(now.date(), shift.start_time).replace(tzinfo=timezone.utc)
    if now > cutoff and (now - cutoff).total_seconds() / 60 > shift.grace_minutes:
        return "late"
    return "present"


def _finalize_out(db: Session, emp: models.Employee, rec: models.AttendanceRecord, now: datetime):
    # SQLite لا يحفظ tzinfo عند إعادة القراءة — نطبّع الطرفين دومًا لتفادي مقارنة naive/aware
    check_in = rec.check_in_at.replace(tzinfo=timezone.utc) if rec.check_in_at.tzinfo is None else rec.check_in_at
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    rec.worked_minutes = max(int((now - check_in).total_seconds() // 60), 0)
    if emp.shift_id:
        shift = db.get(models.Shift, emp.shift_id)
        if shift:
            shift_minutes = int((datetime.combine(now.date(), shift.end_time)
                                 - datetime.combine(now.date(), shift.start_time)).total_seconds() // 60)
            end_cutoff = datetime.combine(now.date(), shift.end_time).replace(tzinfo=timezone.utc)
            if now < end_cutoff and rec.status == "present":
                rec.status = "early_leave"
            if rec.worked_minutes > shift_minutes:
                rec.overtime_minutes = rec.worked_minutes - shift_minutes


@router.get("/my")
def my_attendance(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    emp = _resolve_employee(db, user)
    rows = db.scalars(
        select(models.AttendanceRecord)
        .where(models.AttendanceRecord.employee_id == emp.id)
        .order_by(models.AttendanceRecord.check_in_at.desc()).limit(60)
    ).all()
    return [{"id": r.id, "check_in_at": r.check_in_at, "check_out_at": r.check_out_at,
             "status": r.status, "worked_minutes": r.worked_minutes,
             "overtime_minutes": r.overtime_minutes, "method": r.method} for r in rows]


@router.put("/{record_id}/correct")
def correct_attendance(record_id: int, request: Request, reason: str,
                       check_in_at: datetime | None = None,
                       check_out_at: datetime | None = None,
                       status: str | None = None,
                       user: models.User = Depends(require_perm("manage_attendance")),
                       db: Session = Depends(get_db)):
    """تصحيح سجل حضور (FIX-015): يعيد احتساب دقائق العمل/الإضافي ويسجّل السبب في التدقيق."""
    if not reason.strip():
        raise HTTPException(status_code=400, detail="سبب التصحيح إلزامي")
    rec = db.get(models.AttendanceRecord, record_id)
    if not rec:
        raise HTTPException(status_code=404, detail="السجل غير موجود")
    assert_same_company(user, rec.company_id, db=db, request=request)

    before = {"check_in_at": str(rec.check_in_at), "check_out_at": str(rec.check_out_at),
             "status": rec.status, "worked_minutes": rec.worked_minutes}
    if check_in_at is not None:
        rec.check_in_at = check_in_at if check_in_at.tzinfo else check_in_at.replace(tzinfo=timezone.utc)
    if check_out_at is not None:
        rec.check_out_at = check_out_at if check_out_at.tzinfo else check_out_at.replace(tzinfo=timezone.utc)
    if status is not None:
        rec.status = status
    if rec.check_in_at and rec.check_out_at:
        emp = db.get(models.Employee, rec.employee_id)
        rec.overtime_minutes = 0
        _finalize_out(db, emp, rec, rec.check_out_at)

    audit(db, user, "correct_attendance", "attendance", rec.id,
         detail=f"{reason} | before={before}", request=request)
    db.commit()
    db.refresh(rec)
    return {"ok": True, "check_in_at": rec.check_in_at, "check_out_at": rec.check_out_at,
            "status": rec.status, "worked_minutes": rec.worked_minutes,
            "overtime_minutes": rec.overtime_minutes}


@router.get("/review")
def attendance_review(month: str | None = None, branch_id: int | None = None,
                      company_id: int | None = None,
                      user: models.User = Depends(require_perm("view_attendance")),
                      db: Session = Depends(get_db)):
    """مراجعة الحضور الشهري لموظفي الشركة المختارة (للمدير/المالك/الإدارة العليا).

    يبني مصفوفة (موظف × يوم) بحالات: حاضر/متأخر/غائب/إجازة/عطلة، مع ملخّص شهري.
    """
    cid = scope_company_id(user, company_id)
    today = date.today()
    try:
        y, m = (int(p) for p in month.split("-")) if month else (today.year, today.month)
    except Exception:
        y, m = today.year, today.month
    days_in_month = calendar.monthrange(y, m)[1]
    first, last = date(y, m, 1), date(y, m, days_in_month)
    days = [date(y, m, i + 1) for i in range(days_in_month)]

    emp_q = select(models.Employee).where(
        models.Employee.status == "active", models.Employee.attendance_mode != "none")
    if cid is not None:
        emp_q = emp_q.where(models.Employee.company_id == cid)
    if branch_id:
        emp_q = emp_q.where(models.Employee.branch_id == branch_id)
    employees = db.scalars(emp_q.order_by(models.Employee.name)).all()

    out_emps = []
    for e in employees:
        recs = db.scalars(select(models.AttendanceRecord).where(
            models.AttendanceRecord.employee_id == e.id,
            models.AttendanceRecord.check_in_at >= datetime(y, m, 1),
            models.AttendanceRecord.check_in_at < datetime(y, m, days_in_month) + timedelta(days=1),
        )).all()
        rec_by_day, overtime = {}, 0
        for r in recs:
            ci = r.check_in_at
            rec_by_day[ci.date()] = r
            overtime += r.overtime_minutes or 0
        leaves = db.scalars(select(models.Leave).where(
            models.Leave.employee_id == e.id, models.Leave.status == "approved",
            models.Leave.start_date <= last, models.Leave.end_date >= first)).all()
        shift = db.get(models.Shift, e.shift_id) if e.shift_id else None
        workset = set((shift.work_days if shift else "0,1,2,3,4").split(","))

        cells, summary = {}, {"present": 0, "late": 0, "absent": 0, "leave": 0, "off": 0}
        for d in days:
            ds = d.isoformat()
            our_idx = str((d.weekday() + 1) % 7)  # 0=الأحد
            is_workday = our_idx in workset
            r = rec_by_day.get(d)
            if r:
                st = "late" if r.status == "late" else "present"
                cells[ds] = st
                summary[st] += 1
            elif any(lv.start_date <= d <= lv.end_date for lv in leaves):
                cells[ds] = "leave"; summary["leave"] += 1
            elif is_workday and d <= today:
                cells[ds] = "absent"; summary["absent"] += 1
            elif is_workday:
                cells[ds] = "future"
            else:
                cells[ds] = "off"; summary["off"] += 1
        out_emps.append({
            "employee_id": e.id, "name": e.name, "job_title": e.job_title,
            "branch_id": e.branch_id, "attendance_mode": e.attendance_mode,
            "cells": cells, "summary": summary, "overtime_minutes": overtime,
        })

    return {
        "period": {"year": y, "month": m, "from": first.isoformat(), "to": last.isoformat()},
        "days": [d.isoformat() for d in days],
        "employees": out_emps,
        "total_employees": len(out_emps),
    }


@router.get("/branch/{branch_id}")
def branch_attendance(branch_id: int,
                      user: models.User = Depends(require_perm("view_attendance")),
                      db: Session = Depends(get_db)):
    branch = db.get(models.Branch, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="الفرع غير موجود")
    assert_same_company(user, branch.company_id)
    rows = db.scalars(
        select(models.AttendanceRecord)
        .where(models.AttendanceRecord.branch_id == branch_id)
        .order_by(models.AttendanceRecord.check_in_at.desc()).limit(200)
    ).all()
    return [{"id": r.id, "employee_id": r.employee_id, "check_in_at": r.check_in_at,
             "check_out_at": r.check_out_at, "status": r.status,
             "selfie_in": bool(r.selfie_in_path)} for r in rows]
