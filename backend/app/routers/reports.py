# -*- coding: utf-8 -*-
"""التقارير والتصدير: الموظفون والرواتب والحضور إلى CSV / Excel (بدعم العربية)."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import exports, models
from ..database import get_db
from ..deps import assert_same_company, audit, require_perm, resolve_scope, scope_company_id

# التقارير الحساسة (رواتب/نهاية خدمة) تتطلب سببًا صريحًا قبل التصدير (FIX-016)
_SENSITIVE_REASON_ERR = "سبب التصدير إلزامي لهذا التقرير الحساس"

router = APIRouter(prefix="/reports", tags=["reports"])

CSV_MIME = "text/csv; charset=utf-8"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _file(content: bytes, name: str, mime: str) -> Response:
    return Response(content=content, media_type=mime,
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


def _scoped_branches(user, db, branch_id: int | None) -> set[int] | None:
    """يدمج الفرع المطلوب مع نطاق فروع المستخدم (مسؤول الفرع لا يتعدّى فروعه)."""
    allowed = resolve_scope(user, db).branch_ids  # None = كل الفروع المسموحة
    if branch_id:
        if allowed is not None and branch_id not in allowed:
            return {-1}  # فرع خارج نطاقه → لا نتائج
        return {branch_id}
    return allowed


def _employee_rows(db: Session, cid: int | None, branch_ids: set[int] | None = None):
    q = select(models.Employee).where(models.Employee.status != "archived")
    if cid is not None:
        q = q.where(models.Employee.company_id == cid)
    if branch_ids is not None:
        q = q.where(models.Employee.branch_id.in_(branch_ids))
    emps = db.scalars(q.order_by(models.Employee.name)).all()
    headers = ["الاسم", "الرقم المدني", "الجنسية", "المسمى", "الراتب الأساسي",
               "تاريخ التعيين", "نوع العقد", "الحالة"]
    rows = [[e.name, e.civil_id or "", e.nationality or "", e.job_title or "",
             e.basic_salary, e.hire_date.isoformat() if e.hire_date else "",
             e.contract_type, e.status] for e in emps]
    return headers, rows


@router.get("/employees")
def export_employees(request: Request, fmt: str = "xlsx", company_id: int | None = None,
                     branch_id: int | None = None, reason: str | None = None,
                     user: models.User = Depends(require_perm("export_reports")),
                     db: Session = Depends(get_db)):
    cid = scope_company_id(user, company_id)
    headers, rows = _employee_rows(db, cid, _scoped_branches(user, db, branch_id))
    audit(db, user, "EXPORT_REPORT", "report", None, detail=f"employees:{reason or ''}", request=request)
    db.commit()
    if fmt == "csv":
        return _file(exports.to_csv(headers, rows), "employees.csv", CSV_MIME)
    return _file(exports.to_xlsx("الموظفون", headers, rows), "employees.xlsx", XLSX_MIME)


@router.get("/payroll/{run_id}")
def export_payroll(run_id: int, request: Request, fmt: str = "xlsx", reason: str | None = None,
                   # view_payroll (لا export_reports العام) — بيانات مالية حسّاسة (FIX-013)
                   user: models.User = Depends(require_perm("view_payroll")),
                   db: Session = Depends(get_db)):
    if not (reason and reason.strip()):
        raise HTTPException(status_code=400, detail=_SENSITIVE_REASON_ERR)
    pr = db.get(models.PayrollRun, run_id)
    if not pr or not pr.totals_json:
        raise HTTPException(status_code=404, detail="المسيّر غير موجود")
    assert_same_company(user, pr.company_id, db=db, request=request)
    headers = ["الاسم", "المسمى", "الأساسي", "أيام الحضور", "أيام الغياب",
               "الإضافي", "خصم الغياب", "خصومات أخرى", "الإجمالي", "الصافي"]
    rows = [[p["name"], p["job_title"] or "", p["basic_salary"], p["present_days"],
             p["absent_days"], p["overtime_pay"], p["absence_deduction"],
             p["other_deductions"], p["gross"], p["net"]]
            for p in pr.totals_json.get("payslips", [])]
    name = f"payroll_{pr.period}"
    audit(db, user, "EXPORT_REPORT", "payroll_run", run_id, detail=f"payroll:{reason}", request=request)
    db.commit()
    if fmt == "csv":
        return _file(exports.to_csv(headers, rows), f"{name}.csv", CSV_MIME)
    return _file(exports.to_xlsx(f"رواتب {pr.period}", headers, rows), f"{name}.xlsx", XLSX_MIME)


@router.get("/eos/{emp_id}")
def export_eos(emp_id: int, request: Request, fmt: str = "xlsx", reason: str | None = None,
               user: models.User = Depends(require_perm("calculate_eos")),
               db: Session = Depends(get_db)):
    """تصدير/طباعة تقرير مكافأة نهاية الخدمة المحفوظ للموظف (DEMO-014)."""
    import json
    if not (reason and reason.strip()):
        raise HTTPException(status_code=400, detail=_SENSITIVE_REASON_ERR)
    emp = db.get(models.Employee, emp_id)
    if not emp or not emp.eos_settlement_json:
        raise HTTPException(status_code=404, detail="لا توجد حسبة نهاية خدمة محفوظة")
    assert_same_company(user, emp.company_id, db=db, request=request)
    audit(db, user, "EXPORT_REPORT", "employee", emp_id, detail=f"eos:{reason}", request=request)
    db.commit()
    s = json.loads(emp.eos_settlement_json)
    lv = s.get("leave", {})
    headers = ["البند", "القيمة"]
    rows = [
        ["الموظف", emp.name],
        ["تاريخ الانتهاء", str(emp.termination_date or "")],
        ["السبب", s.get("inputs", {}).get("reason_label", emp.termination_reason or "")],
        ["مدة الخدمة", s.get("service", {}).get("text", "")],
        ["أجر اليوم", s.get("daily_wage", "")],
        ["نسبة الاستحقاق %", round(s.get("entitlement_factor", 0) * 100, 2)],
        ["المكافأة", s.get("indemnity", "")],
        ["رصيد الإجازات المستحق", lv.get("accrued_days", "")],
        ["المستهلَك", lv.get("used_days", "")],
        ["المتبقّي", lv.get("remaining_days", "")],
        ["بدل الإجازات", s.get("leave_payout", "")],
        ["إجمالي التسوية (د.ك)", s.get("total_settlement", "")],
    ]
    name = f"eos_{emp.id}"
    if fmt == "csv":
        return _file(exports.to_csv(headers, rows), f"{name}.csv", CSV_MIME)
    return _file(exports.to_xlsx(f"نهاية خدمة {emp.name}", headers, rows), f"{name}.xlsx", XLSX_MIME)


@router.get("/attendance")
def export_attendance(request: Request, month: str | None = None, fmt: str = "csv",
                      company_id: int | None = None, branch_id: int | None = None,
                      reason: str | None = None,
                      user: models.User = Depends(require_perm("export_reports")),
                      db: Session = Depends(get_db)):
    cid = scope_company_id(user, company_id)
    today = datetime.today()
    try:
        y, m = (int(p) for p in month.split("-")) if month else (today.year, today.month)
    except Exception:
        y, m = today.year, today.month
    q = select(models.AttendanceRecord).where(
        models.AttendanceRecord.check_in_at >= datetime(y, m, 1))
    if cid is not None:
        q = q.where(models.AttendanceRecord.company_id == cid)
    bscope = _scoped_branches(user, db, branch_id)
    if bscope is not None:
        q = q.where(models.AttendanceRecord.branch_id.in_(bscope))
    recs = db.scalars(q.order_by(models.AttendanceRecord.check_in_at)).all()
    emp_names = {e.id: e.name for e in db.scalars(select(models.Employee)).all()}
    headers = ["الموظف", "الدخول", "الخروج", "الحالة", "دقائق العمل", "الإضافي"]
    rows = [[emp_names.get(r.employee_id, r.employee_id),
             r.check_in_at.strftime("%Y-%m-%d %H:%M") if r.check_in_at else "",
             r.check_out_at.strftime("%Y-%m-%d %H:%M") if r.check_out_at else "",
             r.status, r.worked_minutes, r.overtime_minutes] for r in recs]
    audit(db, user, "EXPORT_REPORT", "report", None, detail=f"attendance:{reason or ''}", request=request)
    db.commit()
    if fmt == "xlsx":
        return _file(exports.to_xlsx(f"حضور {y}-{m:02d}", headers, rows),
                     f"attendance_{y}-{m:02d}.xlsx", XLSX_MIME)
    return _file(exports.to_csv(headers, rows), f"attendance_{y}-{m:02d}.csv", CSV_MIME)
