# -*- coding: utf-8 -*-
"""الهيكل التنظيمي: الفروع/المواقع، الورديات، التراخيص، مسؤولو الفروع، ورمز QR الحيّ."""
import secrets
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import assert_same_company, audit, get_current_user, require_perm, scope_company_id
from ..qr import current_code, seconds_remaining

router = APIRouter(tags=["org"])


# ----------------------------- الفروع -----------------------------

@router.get("/branches", response_model=list[schemas.BranchOut])
def list_branches(company_id: int | None = None,
                  user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    cid = scope_company_id(user, company_id)
    q = select(models.Branch)
    if cid is not None:
        q = q.where(models.Branch.company_id == cid)
    return list(db.scalars(q).all())


@router.post("/branches", response_model=schemas.BranchOut, status_code=201)
def create_branch(data: schemas.BranchIn, request: Request,
                  user: models.User = Depends(require_perm("manage_branches")),
                  db: Session = Depends(get_db)):
    cid = user.company_id
    if cid is None:
        raise HTTPException(status_code=400, detail="يجب أن يكون المستخدم تابعًا لشركة")
    branch = models.Branch(company_id=cid, qr_secret=secrets.token_hex(16), **data.model_dump())
    db.add(branch)
    db.flush()
    audit(db, user, "create_branch", "branch", branch.id, request=request)
    db.commit()
    db.refresh(branch)
    return branch


@router.get("/org/structure")
def org_structure(company_id: int | None = None,
                  user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """هيكل الشركة: الفروع وعدد موظفي كل فرع ومسؤوليه (Company → Branches)."""
    cid = scope_company_id(user, company_id)
    if cid is None:
        raise HTTPException(status_code=400, detail="اختر شركة لعرض هيكلها")
    company = db.get(models.Company, cid)
    if not company:
        raise HTTPException(status_code=404, detail="الشركة غير موجودة")

    def emp_count(*conds):
        q = select(func.count()).select_from(models.Employee).where(
            models.Employee.company_id == cid, models.Employee.status == "active")
        for c in conds:
            q = q.where(c)
        return db.scalar(q) or 0

    branches = db.scalars(select(models.Branch).where(models.Branch.company_id == cid)
                          .order_by(models.Branch.name)).all()
    sup_rows = db.scalars(select(models.BranchSupervisor).where(
        models.BranchSupervisor.company_id == cid)).all()
    user_names = {u.id: u.full_name for u in db.scalars(select(models.User)).all()}
    sup_by_branch: dict[int, list[str]] = {}
    for s in sup_rows:
        sup_by_branch.setdefault(s.branch_id, []).append(user_names.get(s.user_id, "—"))

    out = [{
        "id": b.id, "name": b.name, "address": b.address,
        "geofence_radius_m": b.geofence_radius_m,
        "employee_count": emp_count(models.Employee.branch_id == b.id),
        "supervisors": sup_by_branch.get(b.id, []),
    } for b in branches]

    return {
        "company": {"id": company.id, "name": company.name},
        "branches": out,
        "unassigned_employees": emp_count(models.Employee.branch_id.is_(None)),
        "total_employees": emp_count(),
    }


@router.get("/branches/{branch_id}/stats")
def branch_stats(branch_id: int, user: models.User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """إحصائيات فرع واحد: الموظفون، حضور اليوم، في إجازة، إقامات قرب الانتهاء."""
    branch = db.get(models.Branch, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="الفرع غير موجود")
    assert_same_company(user, branch.company_id)
    today = date.today()
    emp_ids = select(models.Employee.id).where(models.Employee.branch_id == branch_id,
                                               models.Employee.status == "active")

    employees = db.scalar(select(func.count()).select_from(emp_ids.subquery())) or 0
    present_today = db.scalar(select(func.count(func.distinct(models.AttendanceRecord.employee_id)))
                              .where(models.AttendanceRecord.branch_id == branch_id,
                                     models.AttendanceRecord.check_in_at >= datetime(today.year, today.month, today.day))) or 0
    on_leave = db.scalar(select(func.count()).select_from(models.Leave).where(
        models.Leave.employee_id.in_(emp_ids), models.Leave.status == "approved",
        models.Leave.start_date <= today, models.Leave.end_date >= today)) or 0
    expiring_permits = db.scalar(select(func.count()).select_from(models.Permit).where(
        models.Permit.employee_id.in_(emp_ids), models.Permit.status == "active",
        models.Permit.expiry_date.isnot(None),
        models.Permit.expiry_date <= today + timedelta(days=90))) or 0

    return {"branch_id": branch_id, "branch_name": branch.name, "employees": employees,
            "present_today": present_today, "on_leave": on_leave,
            "expiring_permits": expiring_permits}


@router.get("/branches/{branch_id}/qr")
def branch_qr(branch_id: int, user: models.User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    """الرمز الحيّ المتغيّر للفرع (يُعرض على شاشة الفرع ويتجدد كل 60 ثانية)."""
    branch = db.get(models.Branch, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="الفرع غير موجود")
    assert_same_company(user, branch.company_id)
    return {
        "branch_id": branch.id, "branch_name": branch.name,
        "code": current_code(branch.qr_secret),
        "expires_in": seconds_remaining(), "period": 60,
    }


@router.post("/branches/{branch_id}/kiosk-key/rotate")
def rotate_kiosk_key(branch_id: int, request: Request,
                     user: models.User = Depends(require_perm("manage_branches")),
                     db: Session = Depends(get_db)):
    """يولّد/يدوّر مفتاح شاشة العرض ويعيد رابط الشاشة الكامل (يُبطل القديم فورًا)."""
    branch = db.get(models.Branch, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="الفرع غير موجود")
    assert_same_company(user, branch.company_id)
    branch.kiosk_key = secrets.token_urlsafe(24)
    audit(db, user, "rotate_kiosk_key", "branch", branch.id, request=request)
    db.commit()
    return {
        "branch_id": branch.id,
        "kiosk_key": branch.kiosk_key,
        "kiosk_path": f"/kiosk/qr/{branch.id}?key={branch.kiosk_key}",
    }


@router.get("/branches/{branch_id}/kiosk-url")
def get_kiosk_url(branch_id: int,
                  user: models.User = Depends(require_perm("manage_branches")),
                  db: Session = Depends(get_db)):
    branch = db.get(models.Branch, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="الفرع غير موجود")
    assert_same_company(user, branch.company_id)
    if not branch.kiosk_key:
        return {"branch_id": branch.id, "kiosk_path": None}
    return {"branch_id": branch.id, "kiosk_key": branch.kiosk_key,
            "kiosk_path": f"/kiosk/qr/{branch.id}?key={branch.kiosk_key}"}


@router.post("/branches/{branch_id}/supervisors/{user_id}")
def add_supervisor(branch_id: int, user_id: int, request: Request,
                   user: models.User = Depends(require_perm("manage_branches")),
                   db: Session = Depends(get_db)):
    branch = db.get(models.Branch, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="الفرع غير موجود")
    assert_same_company(user, branch.company_id)
    target = db.get(models.User, user_id)
    if not target or target.company_id != branch.company_id:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    exists = db.scalar(select(models.BranchSupervisor).where(
        models.BranchSupervisor.branch_id == branch_id,
        models.BranchSupervisor.user_id == user_id))
    if not exists:
        db.add(models.BranchSupervisor(company_id=branch.company_id, branch_id=branch_id,
                                       user_id=user_id))
        audit(db, user, "add_supervisor", "branch", branch_id, detail=str(user_id), request=request)
        db.commit()
    return {"ok": True}


# ----------------------------- الورديات -----------------------------

@router.get("/shifts")
def list_shifts(company_id: int | None = None,
                user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    cid = scope_company_id(user, company_id)
    q = select(models.Shift)
    if cid is not None:
        q = q.where(models.Shift.company_id == cid)
    rows = db.scalars(q).all()
    return [{"id": s.id, "name": s.name, "start_time": str(s.start_time),
             "end_time": str(s.end_time), "work_days": s.work_days,
             "grace_minutes": s.grace_minutes} for s in rows]


@router.post("/shifts", status_code=201)
def create_shift(data: schemas.ShiftIn, request: Request,
                 user: models.User = Depends(require_perm("manage_attendance")),
                 db: Session = Depends(get_db)):
    if user.company_id is None:
        raise HTTPException(status_code=400, detail="يجب أن يكون المستخدم تابعًا لشركة")
    shift = models.Shift(company_id=user.company_id, **data.model_dump())
    db.add(shift)
    db.flush()
    audit(db, user, "create_shift", "shift", shift.id, request=request)
    db.commit()
    return {"ok": True, "id": shift.id}


# ----------------------------- التراخيص -----------------------------

@router.get("/licenses")
def list_licenses(company_id: int | None = None,
                  user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    cid = scope_company_id(user, company_id)
    q = select(models.License)
    if cid is not None:
        q = q.where(models.License.company_id == cid)
    rows = db.scalars(q).all()
    out = []
    for lic in rows:
        actual = len(db.scalars(select(models.Employee.id).where(
            models.Employee.license_id == lic.id,
            models.Employee.status == "active")).all())
        out.append({
            "id": lic.id, "name": lic.name, "license_no": lic.license_no,
            "issuing_authority": lic.issuing_authority, "status": lic.status,
            "expiry_date": lic.expiry_date, "allowed_workers": lic.allowed_workers,
            "actual_workers": actual, "over_capacity": actual > (lic.allowed_workers or 0),
        })
    return out


@router.post("/licenses", status_code=201)
def create_license(name: str, license_no: str | None = None, issuing_authority: str | None = None,
                   allowed_workers: int = 0, request: Request = None,
                   user: models.User = Depends(require_perm("manage_licenses")),
                   db: Session = Depends(get_db)):
    if user.company_id is None:
        raise HTTPException(status_code=400, detail="يجب أن يكون المستخدم تابعًا لشركة")
    lic = models.License(company_id=user.company_id, name=name, license_no=license_no,
                         issuing_authority=issuing_authority, allowed_workers=allowed_workers)
    db.add(lic)
    db.flush()
    audit(db, user, "create_license", "license", lic.id, request=request)
    db.commit()
    return {"ok": True, "id": lic.id}
