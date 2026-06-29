# -*- coding: utf-8 -*-
"""البحث الشامل (Global Search): يبحث في كل الكيانات ويُصنّف النتائج حسب النوع."""
from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import get_current_user, get_user_perms, scope_company_id
from ..permissions import CROSS_COMPANY_ROLES, check_legacy

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def global_search(q: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """بحث موحّد: الموظفون، الشركات، الفروع، التراخيص، الإقامات — مصنّفًا ومحترِمًا للصلاحيات."""
    q = (q or "").strip()
    if len(q) < 2:
        return {"query": q, "results": {}}
    like = f"%{q}%"
    cid = scope_company_id(user)
    assigned = get_user_perms(user, db)
    can = lambda p: check_legacy(user.role, assigned, p)  # noqa: E731

    def scoped(stmt, model):
        return stmt.where(model.company_id == cid) if cid is not None else stmt

    results: dict = {}

    # الموظفون (بالاسم/المدني/رقم الموظف)
    if can("view_employee"):
        emp_q = select(models.Employee).where(or_(
            models.Employee.name.like(like), models.Employee.civil_id.like(like)))
        if q.isdigit():
            emp_q = select(models.Employee).where(or_(
                models.Employee.name.like(like), models.Employee.civil_id.like(like),
                models.Employee.id == int(q)))
        emps = db.scalars(scoped(emp_q, models.Employee).limit(8)).all()
        results["employees"] = [{"id": e.id, "label": e.name,
                                 "sub": f"{e.civil_id or ''} · {e.job_title or ''}",
                                 "link": f"/employees/{e.id}"} for e in emps]

    # الشركات (للإدارة العليا/المالك)
    if user.role in CROSS_COMPANY_ROLES:
        comps = db.scalars(select(models.Company).where(or_(
            models.Company.name.like(like), models.Company.commercial_reg.like(like),
            models.Company.file_number.like(like))).limit(6)).all()
        results["companies"] = [{"id": c.id, "label": c.name,
                                 "sub": f"س.ت {c.commercial_reg or '—'}", "link": "/companies"} for c in comps]

    # الفروع
    br_q = scoped(select(models.Branch).where(models.Branch.name.like(like)), models.Branch)
    branches = db.scalars(br_q.limit(6)).all()
    if branches:
        results["branches"] = [{"id": b.id, "label": b.name, "sub": b.address or "",
                                "link": f"/employees?branch={b.id}"} for b in branches]

    # التراخيص (شأن حكومي → المندوب/الإدارة العليا فقط)
    if can("manage_licenses"):
        lic_q = scoped(select(models.License).where(or_(
            models.License.name.like(like), models.License.license_no.like(like))), models.License)
        lics = db.scalars(lic_q.limit(6)).all()
        if lics:
            results["licenses"] = [{"id": l.id, "label": l.name,
                                    "sub": f"رقم {l.license_no or '—'}", "link": "/pro"} for l in lics]

    # الإقامات (برقم الإقامة)
    if can("manage_permits"):
        pm_q = scoped(select(models.Permit).where(models.Permit.number.like(like)), models.Permit)
        permits = db.scalars(pm_q.limit(6)).all()
        if permits:
            emp_map = {e.id: e.name for e in db.scalars(select(models.Employee)).all()}
            results["permits"] = [{"id": p.id, "label": f"{p.number}",
                                   "sub": emp_map.get(p.employee_id, ""), "link": "/pro"} for p in permits]

    total = sum(len(v) for v in results.values())
    return {"query": q, "total": total, "results": results}
