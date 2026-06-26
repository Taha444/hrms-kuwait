# -*- coding: utf-8 -*-
"""التقارير والتصدير: الموظفون والرواتب والحضور إلى CSV / Excel (بدعم العربية)."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import exports, models
from ..database import get_db
from ..deps import assert_same_company, require_perm, scope_company_id

router = APIRouter(prefix="/reports", tags=["reports"])

CSV_MIME = "text/csv; charset=utf-8"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _file(content: bytes, name: str, mime: str) -> Response:
    return Response(content=content, media_type=mime,
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


def _employee_rows(db: Session, cid: int | None):
    q = select(models.Employee).where(models.Employee.status != "archived")
    if cid is not None:
        q = q.where(models.Employee.company_id == cid)
    emps = db.scalars(q.order_by(models.Employee.name)).all()
    headers = ["الاسم", "الرقم المدني", "الجنسية", "المسمى", "الراتب الأساسي",
               "تاريخ التعيين", "نوع العقد", "الحالة"]
    rows = [[e.name, e.civil_id or "", e.nationality or "", e.job_title or "",
             e.basic_salary, e.hire_date.isoformat() if e.hire_date else "",
             e.contract_type, e.status] for e in emps]
    return headers, rows


@router.get("/employees")
def export_employees(fmt: str = "xlsx", company_id: int | None = None,
                     user: models.User = Depends(require_perm("export_reports")),
                     db: Session = Depends(get_db)):
    cid = scope_company_id(user, company_id)
    headers, rows = _employee_rows(db, cid)
    if fmt == "csv":
        return _file(exports.to_csv(headers, rows), "employees.csv", CSV_MIME)
    return _file(exports.to_xlsx("الموظفون", headers, rows), "employees.xlsx", XLSX_MIME)


@router.get("/payroll/{run_id}")
def export_payroll(run_id: int, fmt: str = "xlsx",
                   user: models.User = Depends(require_perm("export_reports")),
                   db: Session = Depends(get_db)):
    pr = db.get(models.PayrollRun, run_id)
    if not pr or not pr.totals_json:
        raise HTTPException(status_code=404, detail="المسيّر غير موجود")
    assert_same_company(user, pr.company_id)
    headers = ["الاسم", "المسمى", "الأساسي", "أيام الحضور", "أيام الغياب",
               "الإضافي", "خصم الغياب", "خصومات أخرى", "الإجمالي", "الصافي"]
    rows = [[p["name"], p["job_title"] or "", p["basic_salary"], p["present_days"],
             p["absent_days"], p["overtime_pay"], p["absence_deduction"],
             p["other_deductions"], p["gross"], p["net"]]
            for p in pr.totals_json.get("payslips", [])]
    name = f"payroll_{pr.period}"
    if fmt == "csv":
        return _file(exports.to_csv(headers, rows), f"{name}.csv", CSV_MIME)
    return _file(exports.to_xlsx(f"رواتب {pr.period}", headers, rows), f"{name}.xlsx", XLSX_MIME)


@router.get("/attendance")
def export_attendance(month: str | None = None, fmt: str = "csv", company_id: int | None = None,
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
    recs = db.scalars(q.order_by(models.AttendanceRecord.check_in_at)).all()
    emp_names = {e.id: e.name for e in db.scalars(select(models.Employee)).all()}
    headers = ["الموظف", "الدخول", "الخروج", "الحالة", "دقائق العمل", "الإضافي"]
    rows = [[emp_names.get(r.employee_id, r.employee_id),
             r.check_in_at.strftime("%Y-%m-%d %H:%M") if r.check_in_at else "",
             r.check_out_at.strftime("%Y-%m-%d %H:%M") if r.check_out_at else "",
             r.status, r.worked_minutes, r.overtime_minutes] for r in recs]
    if fmt == "xlsx":
        return _file(exports.to_xlsx(f"حضور {y}-{m:02d}", headers, rows),
                     f"attendance_{y}-{m:02d}.xlsx", XLSX_MIME)
    return _file(exports.to_csv(headers, rows), f"attendance_{y}-{m:02d}.csv", CSV_MIME)
