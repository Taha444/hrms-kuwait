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
    # **حساسيُة الحالة تختلف بين المحرّكين — فبحٌث يعمل محلًّيا ويفشل
    # في اإلنتاج.**
    #
    # ``LIKE`` في SQLite **ال يميّز حالَة الحروف** لأحرف ASCII، وفي
    # PostgreSQL **يميّزها**. والسويُت تجري على SQLite — فال اختباَر يمسك
    # هذا أبًدا. وهو الصنُف نفسه الذي تكرَّر اليوم ثالث مرات: ترويسٌة ال
    # تُكشَف إال عبر األصول، وساعُة مضيٍف تُقارَن بـUTC، وكتالوٌج نسخُته في
    # القاعدة هي التي تعمل.
    #
    # واألثُر يمسّ ما فيه حروٌف التينية: رقُم الجواز (``A9988776``) ورقُم
    # الترخيص ورقُم الملف والسجلُّ التجاري. فمن يكتب ``a9988776`` ال يجد
    # شيًئا في اإلنتاج ويجده محلًّيا.
    #
    # و``ilike`` صحيحٌة على المحرّكين: SQLAlchemy تترجمها إلى
    # ``lower(x) LIKE lower(y)`` على SQLite وإلى ``ILIKE`` على Postgres.
    # والعربيُة ال حالَة لها فال يمسّها التحويل. وال فهٌرس يُفقَد: النمُط
    # ``%q%`` بعالمَتي بدٍل ال يستعمل فهرًسا أصًلا.
    like = f"%{q}%"
    cid = scope_company_id(user)
    assigned = get_user_perms(user, db)
    can = lambda p: check_legacy(user.role, assigned, p)  # noqa: E731

    def scoped(stmt, model):
        return stmt.where(model.company_id == cid) if cid is not None else stmt

    # ونطاقُ الفرع كما في قائمة الموظفين وملفّاتهم: كان البحُث يُرشّح بالشركة
    # وحدها، فيجد مسؤوُل الفرع موظّفي الفروع الأخرى ورقَمهم المدنيَّ — وملفُّهم
    # يردّه 404. فالبحُث كان يكشف ما يحجبه الملف.
    from ..deps import resolve_scope
    _sc = resolve_scope(user, db)

    from ..deps import hidden_staff_ids
    _hidden = hidden_staff_ids(user, db, _sc)

    def in_scope(stmt, emp_col, branch_col=None):
        if _sc.self_employee_id is not None:
            return stmt.where(emp_col == _sc.self_employee_id)
        if _hidden:
            # ومن هو أعلى منه لا يُوجَد بالبحث — قرار 33.
            stmt = stmt.where(emp_col.notin_(_hidden))
        if _sc.branch_ids is not None and branch_col is not None:
            return stmt.where(branch_col.in_(_sc.branch_ids))
        return stmt

    results: dict = {}

    # الموظفون (بالاسم/المدني/الجواز/رقم الموظف)
    if can("view_employee"):
        # قرار المسح الشامل (2026-09-24، M05): البحث بالاسم والمدني والجواز — بلا الرقم الوظيفي
        # (GUF-HQ-00001) رغم أنه المعرّف المطبوع على كل مستند رسمي. مطابقٌ ما وُجد في قائمة الموظفين.
        # employee_no داخليٌّ حاسمُ حالة — نمطٌ منفصلُ الاسم لا ``like`` نفسها.
        no_pattern = like
        conds = [models.Employee.name.ilike(like), models.Employee.civil_id.ilike(like),
                 models.Employee.passport_number.ilike(like),
                 models.Employee.employee_no.like(no_pattern)]
        if q.isdigit():
            conds.append(models.Employee.id == int(q))
        emp_q = select(models.Employee).where(or_(*conds))
        emp_q = in_scope(emp_q, models.Employee.id, models.Employee.branch_id)
        emps = db.scalars(scoped(emp_q, models.Employee).limit(8)).all()
        results["employees"] = [{"id": e.id, "label": e.name,
                                 "sub": f"{e.civil_id or ''} · {e.job_title or ''}",
                                 "link": f"/employees/{e.id}"} for e in emps]

    # الشركات (للإدارة العليا/المالك)
    if user.role in CROSS_COMPANY_ROLES:
        comps = db.scalars(select(models.Company).where(or_(
            models.Company.name.ilike(like), models.Company.commercial_reg.ilike(like),
            models.Company.file_number.ilike(like))).limit(6)).all()
        results["companies"] = [{"id": c.id, "label": c.name,
                                 "sub": f"س.ت {c.commercial_reg or '—'}", "link": "/companies"} for c in comps]

    # الفروع
    br_q = scoped(select(models.Branch).where(models.Branch.name.ilike(like)), models.Branch)
    if _sc.branch_ids is not None:
        br_q = br_q.where(models.Branch.id.in_(_sc.branch_ids))
    branches = db.scalars(br_q.limit(6)).all()
    if branches:
        results["branches"] = [{"id": b.id, "label": b.name, "sub": b.address or "",
                                "link": f"/employees?branch={b.id}"} for b in branches]

    # التراخيص (شأن حكومي → المندوب/الإدارة العليا فقط)
    if can("manage_licenses"):
        lic_q = scoped(select(models.License).where(or_(
            models.License.name.ilike(like), models.License.license_no.ilike(like))), models.License)
        lics = db.scalars(lic_q.limit(6)).all()
        if lics:
            results["licenses"] = [{"id": l.id, "label": l.name,
                                    "sub": f"رقم {l.license_no or '—'}", "link": "/pro"} for l in lics]

    # الإقامات (برقم الإقامة)
    if can("manage_permits"):
        pm_q = scoped(select(models.Permit).where(models.Permit.number.ilike(like)), models.Permit)
        if _sc.branch_ids is not None or _sc.self_employee_id is not None:
            visible = select(models.Employee.id)
            visible = in_scope(visible, models.Employee.id, models.Employee.branch_id)
            pm_q = pm_q.where(models.Permit.employee_id.in_(visible))
        permits = db.scalars(pm_q.limit(6)).all()
        if permits:
            emp_map = {e.id: e.name for e in db.scalars(select(models.Employee)).all()}
            results["permits"] = [{"id": p.id, "label": f"{p.number}",
                                   "sub": emp_map.get(p.employee_id, ""), "link": "/pro"} for p in permits]

    total = sum(len(v) for v in results.values())
    return {"query": q, "total": total, "results": results}
