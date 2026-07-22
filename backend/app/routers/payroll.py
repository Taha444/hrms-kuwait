# -*- coding: utf-8 -*-
"""مسيّر الرواتب: حساب شهري + دورة اعتماد متدرجة + قسائم.

PILOT-P0-7 — دورة الرواتب الآمنة:
    prepared → approved → finalized → locked
    (adjustment_run كبديل عند الحاجة بعد lock)

قواعد الأمان:
- company_id إلزامي — لا "All Companies" لتشغيل الرواتب
- المُجَهِّز ≠ المُعتمِد النهائي (فصل السلطات)
- مسيّر واحد لكل (شركة، فترة) — لا تكرار
- Archived employees مستبعدون تلقائيًا في compute_payroll
- بعد قفل الفترة لا يُعدَّل عليها — يجب adjustment_run منفصل
"""
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, payroll as payroll_engine
from ..database import get_db
from ..deps import audit, require_perm, scope_company_id

router = APIRouter(prefix="/payroll", tags=["payroll"])

# دورة الرواتب — الترتيب المسموح فقط:
# prepared → approved → finalized → locked
# adjustment_run دخول جانبي بعد lock (تسويات لاحقة)
STATUS_ORDER = {"prepared": 0, "approved": 1, "finalized": 2, "locked": 3, "adjustment_run": 3}
LOCKED_STATUS = "locked"


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
def run(period: str, request: Request, company_id: int | None = None, force_future: bool = False,
        user: models.User = Depends(require_perm("run_payroll")),
        db: Session = Depends(get_db)):
    """PILOT-P0-7 — تجهيز مسيّر جديد بحالة `prepared` (مش finalized مباشرة).
    يحتاج للاعتماد المنفصل عبر `/runs/{id}/approve` من مستخدم مختلف."""
    y, m = _parse_period(period)
    cid = _company(user, company_id)

    # منع الشهر المستقبلي بدون استثناء صريح
    today = date.today()
    if (y, m) > (today.year, today.month) and not force_future:
        raise HTTPException(status_code=400,
                            detail="لا يمكن تشغيل مسيّر لشهر مستقبلي دون تأكيد صريح (force_future)")

    result = payroll_engine.compute_payroll(db, cid, y, m)

    existing = db.scalar(select(models.PayrollRun).where(
        models.PayrollRun.company_id == cid, models.PayrollRun.period == result["period"]))
    if existing:
        # لا نسمح بإعادة التجهيز فوق مسيّر متقدّم عن prepared — يحتاج adjustment_run صريح
        if existing.status in ("approved", "finalized", "locked"):
            raise HTTPException(
                status_code=409,
                detail=(f"مسيّر هذه الفترة في حالة '{existing.status}' — يجب adjustment_run "
                        "بدل إعادة التجهيز فوقه"))
        existing.totals_json = result
        existing.status = "prepared"
        existing.prepared_by_user_id = user.id
        existing.prepared_at = datetime.utcnow()
        run_id = existing.id
    else:
        pr = models.PayrollRun(
            company_id=cid, period=result["period"],
            status="prepared", totals_json=result,
            prepared_by_user_id=user.id, prepared_at=datetime.utcnow(),
        )
        db.add(pr)
        db.flush()
        run_id = pr.id
    audit(db, user, "prepare_payroll", "payroll_run", run_id,
          detail=result["period"], request=request)
    db.commit()
    return {"ok": True, "run_id": run_id, "status": "prepared", **result}


@router.post("/runs/{run_id}/approve")
def approve_run(run_id: int, request: Request,
                user: models.User = Depends(require_perm("run_payroll")),
                db: Session = Depends(get_db)):
    """PILOT-P0-7 — اعتماد المسيّر (prepared → approved) بشرط مختلف المُجَهِّز."""
    from ..deps import assert_same_company
    pr = db.get(models.PayrollRun, run_id)
    if not pr:
        raise HTTPException(status_code=404, detail="المسيّر غير موجود")
    assert_same_company(user, pr.company_id, db=db)
    if pr.status != "prepared":
        raise HTTPException(status_code=409,
                            detail=f"لا يمكن اعتماد مسيّر في حالة '{pr.status}' — يجب أن يكون prepared")
    if pr.prepared_by_user_id == user.id and user.role != "super_admin":
        raise HTTPException(status_code=403,
                            detail="لا يمكنك اعتماد مسيّر جهّزته بنفسك — فصل السلطات إلزامي")
    pr.status = "approved"
    pr.approved_by_user_id = user.id
    pr.approved_at = datetime.utcnow()
    audit(db, user, "approve_payroll_run", "payroll_run", pr.id,
          detail=pr.period, request=request)
    db.commit()
    return {"ok": True, "status": "approved"}


@router.post("/runs/{run_id}/finalize")
def finalize_run(run_id: int, request: Request,
                 user: models.User = Depends(require_perm("run_payroll")),
                 db: Session = Depends(get_db)):
    """PILOT-P0-7 — finalize بعد الاعتماد (approved → finalized). قابل للـlock بعده.
    SEC2-17: يمنع finalize في وضع STRICT فقط (SEC2_17_STRICT_FINALIZE=true)."""
    import os
    from ..deps import assert_same_company
    from sqlalchemy import or_
    pr = db.get(models.PayrollRun, run_id)
    if not pr:
        raise HTTPException(status_code=404, detail="المسيّر غير موجود")
    assert_same_company(user, pr.company_id, db=db)
    if pr.status != "approved":
        raise HTTPException(status_code=409,
                            detail=f"يجب أن يكون المسيّر approved قبل finalize (الحالي: {pr.status})")
    if os.environ.get("SEC2_17_STRICT_FINALIZE", "").lower() in ("1", "true", "yes"):
        unresolved = db.scalar(select(models.Employee).where(
            models.Employee.company_id == pr.company_id,
            models.Employee.status == "active",
            models.Employee.attendance_mode == "none",
            or_(models.Employee.attendance_exempt.is_(False),
                models.Employee.attendance_exempt.is_(None)),
        ).limit(1))
        if unresolved:
            raise HTTPException(
                status_code=409,
                detail=(f"لا finalize قبل توثيق سياسة حضور كل الموظفين (مثال: {unresolved.name}). "
                        "راجع /employees/attendance-policy/pending")
            )
    pr.status = "finalized"
    pr.finalized_by_user_id = user.id
    pr.finalized_at = datetime.utcnow()
    audit(db, user, "finalize_payroll_run", "payroll_run", pr.id,
          detail=pr.period, request=request)
    db.commit()
    return {"ok": True, "status": "finalized"}


@router.post("/runs/{run_id}/lock")
def lock_run(run_id: int, request: Request,
            user: models.User = Depends(require_perm("run_payroll")),
            db: Session = Depends(get_db)):
    """يقفل المسيّر نهائًيا (finalized → locked). بعد Lock يجب adjustment_run بدل إعادة التشغيل."""
    from ..deps import assert_same_company

    pr = db.get(models.PayrollRun, run_id)
    if not pr:
        raise HTTPException(status_code=404, detail="المسيّر غير موجود")
    assert_same_company(user, pr.company_id, db=db)
    if pr.status != "finalized":
        raise HTTPException(status_code=409, detail="يجب أن يكون المسيّر بحالة finalized قبل القفل")
    pr.status = LOCKED_STATUS
    pr.locked_by_user_id = user.id
    pr.locked_at = datetime.utcnow()
    audit(db, user, "lock_payroll_run", "payroll_run", pr.id, detail=pr.period, request=request)
    db.commit()
    return {"ok": True, "status": pr.status}


@router.post("/runs/{run_id}/adjustment")
def adjustment_run(run_id: int, reason: str, request: Request,
                   user: models.User = Depends(require_perm("run_payroll")),
                   db: Session = Depends(get_db)):
    """PILOT-P0-7 — تسوية بعد الـlock: ينشئ سجل adjustment_run منفصل يرتبط بالأصلي.
    السبب إلزامي ويتسجل في audit."""
    from ..deps import assert_same_company
    if not reason or not reason.strip():
        raise HTTPException(status_code=400, detail="سبب التسوية مطلوب")
    original = db.get(models.PayrollRun, run_id)
    if not original:
        raise HTTPException(status_code=404, detail="المسيّر الأصلي غير موجود")
    assert_same_company(user, original.company_id, db=db)
    if original.status != LOCKED_STATUS:
        raise HTTPException(status_code=409,
                            detail="التسويات تُنشأ فقط بعد قفل المسيّر الأصلي")
    y, m = _parse_period(original.period)
    result = payroll_engine.compute_payroll(db, original.company_id, y, m)
    pr = models.PayrollRun(
        company_id=original.company_id,
        period=f"{original.period}-ADJ-{original.id}",  # تمييز التسوية
        status="adjustment_run", totals_json=result,
        prepared_by_user_id=user.id, prepared_at=datetime.utcnow(),
        adjustment_of_run_id=original.id, adjustment_reason=reason.strip(),
    )
    db.add(pr)
    db.flush()
    audit(db, user, "payroll_adjustment_run", "payroll_run", pr.id,
          detail=f"of={original.id} reason={reason}", request=request)
    db.commit()
    return {"ok": True, "run_id": pr.id, "status": pr.status,
            "adjustment_of": original.id}


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
