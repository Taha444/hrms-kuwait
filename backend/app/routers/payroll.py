# -*- coding: utf-8 -*-
"""مسيّر الرواتب: حساب شهري + حفظ المسيّر + عرض القسائم."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, payroll as payroll_engine
from ..database import get_db
from ..deps import audit, require_perm, scope_company_id

router = APIRouter(prefix="/payroll", tags=["payroll"])


def _parse_period(period: str) -> tuple[int, int]:
    try:
        y, m = (int(x) for x in period.split("-"))
        if not (1 <= m <= 12):
            raise ValueError
        return y, m
    except Exception:
        raise HTTPException(status_code=400, detail="صيغة الفترة يجب أن تكون YYYY-MM")


def _company(user: models.User, company_id: int | None) -> int:
    cid = scope_company_id(user, company_id)
    if cid is None:
        raise HTTPException(status_code=400, detail="يجب تحديد الشركة لتشغيل المسيّر")
    return cid


@router.get("/preview")
def preview(period: str, request: Request, company_id: int | None = None,
            user: models.User = Depends(require_perm("view_payroll")),
            db: Session = Depends(get_db)):
    y, m = _parse_period(period)
    cid = _company(user, company_id)
    result = payroll_engine.compute_payroll(db, cid, y, m)
    audit(db, user, "view_payroll_preview", "company", cid, detail=result["period"], request=request)
    db.commit()
    return result


@router.post("/run")
def run(period: str, request: Request, company_id: int | None = None,
        user: models.User = Depends(require_perm("run_payroll")),
        db: Session = Depends(get_db)):
    y, m = _parse_period(period)
    cid = _company(user, company_id)
    result = payroll_engine.compute_payroll(db, cid, y, m)

    existing = db.scalar(select(models.PayrollRun).where(
        models.PayrollRun.company_id == cid, models.PayrollRun.period == result["period"]))
    if existing:
        existing.totals_json = result
        existing.status = "finalized"
        run_id = existing.id
    else:
        pr = models.PayrollRun(company_id=cid, period=result["period"],
                               status="finalized", totals_json=result)
        db.add(pr)
        db.flush()
        run_id = pr.id
    audit(db, user, "run_payroll", "payroll_run", run_id, detail=result["period"], request=request)
    db.commit()
    return {"ok": True, "run_id": run_id, **result}


@router.get("/runs")
def list_runs(company_id: int | None = None,
              user: models.User = Depends(require_perm("view_payroll")),
              db: Session = Depends(get_db)):
    cid = scope_company_id(user, company_id)
    q = select(models.PayrollRun)
    if cid is not None:
        q = q.where(models.PayrollRun.company_id == cid)
    rows = db.scalars(q.order_by(models.PayrollRun.period.desc())).all()
    return [{"id": r.id, "period": r.period, "status": r.status,
             "totals": (r.totals_json or {}).get("totals"),
             "employees_count": (r.totals_json or {}).get("employees_count"),
             "created_at": r.created_at} for r in rows]


@router.get("/runs/{run_id}")
def get_run(run_id: int, user: models.User = Depends(require_perm("view_payroll")),
            db: Session = Depends(get_db)):
    pr = db.get(models.PayrollRun, run_id)
    if not pr:
        raise HTTPException(status_code=404, detail="المسيّر غير موجود")
    from ..deps import assert_same_company
    assert_same_company(user, pr.company_id, db=db)
    return pr.totals_json or {}
