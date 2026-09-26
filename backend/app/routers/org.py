# -*- coding: utf-8 -*-
"""الهيكل التنظيمي: الفروع/المواقع، الورديات، التراخيص، مسؤولو الفروع، ورمز QR الحيّ."""
import secrets
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import (license_headcount, assert_same_company, audit, get_current_user, require_perm,
                    resolve_scope, scope_company_id)
from ..qr import current_code, seconds_remaining
from ..clock import today as kuwait_today
from ..expiry_windows import WINDOW

router = APIRouter(tags=["org"])


# ----------------------------- الفروع -----------------------------

@router.get("/branches", response_model=list[schemas.BranchOut])
def list_branches(company_id: int | None = None, include_archived: bool = False,
                  user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    cid = scope_company_id(user, company_id)
    q = select(models.Branch)
    # الفرع المؤرشَف لا يُختار ولا يُعرض — ويبقى تاريخه (طلب المالك 2026-09-19).
    if not include_archived:
        q = q.where(models.Branch.status != "archived")
    if cid is not None:
        q = q.where(models.Branch.company_id == cid)
    # تقييد بنطاق فروع المستخدم (مسؤول الفرع لا يرى فروعًا أخرى)
    bids = resolve_scope(user, db).branch_ids
    if bids is not None:
        q = q.where(models.Branch.id.in_(bids))
    return list(db.scalars(q).all())


@router.post("/branches", response_model=schemas.BranchOut, status_code=201)
def create_branch(data: schemas.BranchIn, request: Request,
                  company_id: int | None = None,
                  user: models.User = Depends(require_perm("manage_branches")),
                  db: Session = Depends(get_db)):
    """BR-EDIT — إنشاء فرع.

    **وصاحب الشركات والإدارة العليا لا شركة لهما**، فكان الإنشاء يردّهما
    بـ400 «يجب أن يكون المستخدم تابًعا لشركة» — أي أن من يملك كل الشركات
    وحده **لا يستطيع إنشاء فرع في أيٍّ منها**. و``company_id`` صريح
    مخرجهما، ولا يُقبل ممّن له شركته: نطاقه يحكمه لا اختياره.
    """
    from ..permissions import CROSS_COMPANY_ROLES

    if company_id is not None and user.role in CROSS_COMPANY_ROLES:
        if db.get(models.Company, company_id) is None:
            raise HTTPException(status_code=404, detail="الشركة غير موجودة")
        cid = company_id
    else:
        cid = user.company_id
    if cid is None:
        raise HTTPException(
            status_code=400,
            detail="حدّد الشركة (company_id) — حسابك لا يتبع شركة بعينها")
    branch = models.Branch(company_id=cid, qr_secret=secrets.token_hex(16), **data.model_dump())
    db.add(branch)
    db.flush()
    audit(db, user, "create_branch", "branch", branch.id, request=request)
    db.commit()
    db.refresh(branch)
    return branch


HQ_NAME = "مقر الشركة"


@router.post("/companies/{company_id}/headquarters", response_model=schemas.BranchOut,
             status_code=201)
def create_headquarters(company_id: int, data: schemas.BranchIn, request: Request,
                        user: models.User = Depends(require_perm("manage_branches")),
                        db: Session = Depends(get_db)):
    """**مقرُّ الشركة** — طلب المالك (2026-09-19).

    ليس «فرًعا»: يُسمّى «مقر الشركة»، ومديُره مديُر الشركة (مرحلُة «مسؤول
    الفرع» لموظفيه تذهب إليه)، وعليه الموظفون الإداريون. **واحٌد لكل شركة.**
    """
    from ..permissions import CROSS_COMPANY_ROLES

    if user.role not in CROSS_COMPANY_ROLES and user.company_id != company_id:
        raise HTTPException(status_code=403, detail="ليست شركتك")
    if db.get(models.Company, company_id) is None:
        raise HTTPException(status_code=404, detail="الشركة غير موجودة")
    existing = db.scalar(select(models.Branch).where(
        models.Branch.company_id == company_id, models.Branch.is_headquarters.is_(True)))
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"للشركة مقرٌّ قائم (#{existing.id})")
    body = data.model_dump()
    body.update(name=HQ_NAME, code=body.get("code") or "HQ")
    hq = models.Branch(company_id=company_id, qr_secret=secrets.token_hex(16),
                       kiosk_key=secrets.token_hex(16), is_headquarters=True, **body)
    db.add(hq)
    db.flush()
    audit(db, user, "create_headquarters", "branch", hq.id, request=request)
    db.commit()
    db.refresh(hq)
    return hq


def _live_employees_on(db: Session, branch_id: int) -> int:
    from ..deps import INACTIVE_EMPLOYMENT

    return db.scalar(select(func.count()).select_from(models.Employee).where(
        models.Employee.branch_id == branch_id,
        models.Employee.status.notin_(INACTIVE_EMPLOYMENT))) or 0


@router.post("/branches/{branch_id}/archive", response_model=schemas.BranchOut)
def archive_branch(branch_id: int, reason: str, request: Request,
                   user: models.User = Depends(require_perm("manage_branches")),
                   db: Session = Depends(get_db)):
    """أرشفُة فرٍع مكرٍَّر أو خارج ملف الشركة — **لا حذف**: يبقى حضوره وتاريخه.

    ولا يُؤرشَف فرٌع عليه موظفون قائمون — يُنقلون أولًا بطلب النقل، فلا يبقى
    موظٌف على فرٍع لا يُعرض ولا يُبصَم فيه. ولا يُؤرشَف مقرُّ الشركة.
    """
    branch = db.get(models.Branch, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="الفرع غير موجود")
    assert_same_company(user, branch.company_id, db=db)
    if not (reason or "").strip():
        raise HTTPException(status_code=400, detail="سبب الأرشفة إلزامي")
    if branch.is_headquarters:
        raise HTTPException(status_code=409, detail="لا يُؤرشَف مقر الشركة")
    n = _live_employees_on(db, branch.id)
    if n:
        raise HTTPException(status_code=409, detail=(
            f"على الفرع {n} موظف — انقلهم إلى فرعهم الصحيح أولًا بطلب النقل، ثم أرشفه"))
    branch.status = "archived"
    audit(db, user, "archive_branch", "branch", branch.id, detail=reason.strip()[:300],
          request=request)
    db.commit()
    db.refresh(branch)
    return branch


def _branch_references(db: Session, branch_id: int) -> dict[str, int]:
    """كلُّ صفٍّ في أي جدولٍ يشير إلى هذا الفرع — من مخطط النماذج نفسه لا من قائمٍة تُنسى."""
    from ..database import Base
    found: dict[str, int] = {}
    for table in Base.metadata.tables.values():
        for fk in table.foreign_keys:
            if fk.column.table.name == "branches" and fk.column.name == "id":
                n = db.scalar(select(func.count()).select_from(table).where(
                    table.c[fk.parent.name] == branch_id)) or 0
                if n:
                    found[f"{table.name}.{fk.parent.name}"] = n
    return found


@router.delete("/branches/{branch_id}")
def delete_branch(branch_id: int, reason: str, request: Request,
                  user: models.User = Depends(require_perm("manage_branches")),
                  db: Session = Depends(get_db)):
    """حذٌف **نهائيٌّ** لفرٍع مكرَّر — للإدارة العليا وحدها، ولفرٍع **لا يشير إليه شيء**.

    طلب المالك (2026-09-23): المكرَّر يُمسح لا يُؤرشَف. لكنّ الحذف لا يرجع، فلا
    يُحذف فرٌع عليه موظف أو حضور أو ترخيص أو أي سجلٍّ آخر (يُفحص كلُّ جدولٍ
    يشير إليه) — يُرفض بقائمة ما عليه، ويبقى الأرشفُة طريَق التاريخ. ولا يُحذف
    مقرُّ الشركة. والحذف مقيَّد في التدقيق باسم الفرع وكوده قبل أن يزول.
    """
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="حذف الفرع للإدارة العليا وحدها")
    branch = db.get(models.Branch, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="الفرع غير موجود")
    if not (reason or "").strip():
        raise HTTPException(status_code=400, detail="سبب الحذف إلزامي")
    if branch.is_headquarters:
        raise HTTPException(status_code=409, detail="لا يُحذف مقر الشركة")
    refs = _branch_references(db, branch.id)
    if refs:
        raise HTTPException(status_code=409, detail=(
            "على الفرع سجلّات لا تُحذف: " + "، ".join(f"{k}={v}" for k, v in refs.items())
            + " — أرشِفه بدل حذفه"))
    audit(db, user, "delete_branch", "branch", branch.id, request=request,
          company_id=branch.company_id,
          detail=f"{branch.code} «{branch.name}» — {reason.strip()[:200]}")
    db.delete(branch)
    db.commit()
    return {"ok": True, "deleted": branch_id}


@router.post("/branches/{branch_id}/restore", response_model=schemas.BranchOut)
def restore_branch(branch_id: int, request: Request,
                   user: models.User = Depends(require_perm("manage_branches")),
                   db: Session = Depends(get_db)):
    """استرجاُع فرٍع أُرشف بالخطأ."""
    branch = db.get(models.Branch, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="الفرع غير موجود")
    assert_same_company(user, branch.company_id, db=db)
    branch.status = "active"
    audit(db, user, "restore_branch", "branch", branch.id, request=request)
    db.commit()
    db.refresh(branch)
    return branch


@router.put("/branches/{branch_id}", response_model=schemas.BranchOut)
def update_branch(branch_id: int, data: schemas.BranchUpdate, request: Request,
                  user: models.User = Depends(require_perm("manage_branches")),
                  db: Session = Depends(get_db)):
    """BR-EDIT — تعديل فرع. **ولم يكن للفروع تعديٌل أصًلا.**

    فرٌع أُنشئ باسم فيه خطأ يبقى به إلى الأبد، وفرٌع بلا إحداثيات لا
    يُضبَط فلا يعمل البصم بالموقع فيه، وفرٌع بلا محافظة يوقف توليد العقد
    الحكومي لكل موظفيه — وثلاثتها بلا باب.

    وما لا يُرسَل لا يُمسّ (``exclude_unset``): طلٌب بحقلين لا يمحو ما
    عداهما، وهو العطل الذي قِيس في تعديل الموظفين من قبل.
    """
    branch = db.get(models.Branch, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="الفرع غير موجود")
    assert_same_company(user, branch.company_id, db=db)

    payload = data.model_dump(exclude_unset=True)
    before = {k: getattr(branch, k, None) for k in payload}
    for field, value in payload.items():
        setattr(branch, field, value)
    changed = {k: (before[k], payload[k]) for k in payload if before[k] != payload[k]}
    audit(db, user, "update_branch", "branch", branch.id,
          detail="، ".join(f"{k}: {a} ← {b}" for k, (a, b) in changed.items())[:400],
          request=request)
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

    bq = select(models.Branch).where(models.Branch.company_id == cid)
    scope_bids = resolve_scope(user, db).branch_ids
    if scope_bids is not None:  # مسؤول الفرع: فروعه فقط
        bq = bq.where(models.Branch.id.in_(scope_bids))
    branches = db.scalars(bq.order_by(models.Branch.name)).all()
    # BR-27 — ما تعرضه الشاشة مسنًدا هو ما يُوجَّه إليه الطلب: مصدر واحد.
    # كانت تقرأ ``branch_supervisors`` مباشرة، والتوجيه يقرأها كذلك — ثم
    # يفترقان عن نيّة الإسناد حين يُضبَط النطاق على فرع واحد.
    from ..deps import branch_supervisor_users

    sup_by_branch = {
        b.id: [u.full_name for u in branch_supervisor_users(db, cid, b.id)]
        for b in branches
    }

    out = [{
        "id": b.id, "name": b.name, "address": b.address,
        "geofence_radius_m": b.geofence_radius_m,
        "auto_checkout_minutes": b.auto_checkout_minutes,
        "employee_count": emp_count(models.Employee.branch_id == b.id),
        "supervisors": sup_by_branch.get(b.id, []),
    } for b in branches]

    # الإجماليات تتبع النطاق: مسؤول الفرع يرى إجمالي فروعه فقط
    if scope_bids is not None:
        total = emp_count(models.Employee.branch_id.in_(scope_bids))
        unassigned = 0
    else:
        total = emp_count()
        unassigned = emp_count(models.Employee.branch_id.is_(None))
    return {
        "company": {"id": company.id, "name": company.name},
        "branches": out,
        "unassigned_employees": unassigned,
        "total_employees": total,
    }


@router.get("/branches/{branch_id}/stats")
def branch_stats(branch_id: int, user: models.User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """إحصائيات فرع واحد: الموظفون، حضور اليوم، في إجازة، إقامات قرب الانتهاء."""
    branch = db.get(models.Branch, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="الفرع غير موجود")
    assert_same_company(user, branch.company_id, db=db)
    # مسؤول الفرع لا يطّلع على إحصائيات فرع خارج نطاقه
    bids = resolve_scope(user, db).branch_ids
    if bids is not None and branch_id not in bids:
        raise HTTPException(status_code=404, detail="الفرع غير موجود")
    today = kuwait_today()
    from ..deps import hidden_staff_ids
    emp_ids = select(models.Employee.id).where(models.Employee.branch_id == branch_id,
                                               models.Employee.status == "active",
                                               models.Employee.id.notin_(hidden_staff_ids(user, db) or {-1}))

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
        models.Permit.expiry_date <= today + WINDOW)) or 0

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
    assert_same_company(user, branch.company_id, db=db)
    return {
        "branch_id": branch.id, "branch_name": branch.name,
        "code": current_code(branch.qr_secret),
        "expires_in": seconds_remaining(), "period": 60,
    }


def _mask_kiosk_key(key: str | None) -> str | None:
    """R3-A §5 — إخفاء المفتاح ما عدا آخر 4 خانات: 'abc...xyz9' → '****xyz9'."""
    if not key:
        return None
    if len(key) <= 4:
        return "****"
    return "****" + key[-4:]


@router.post("/branches/{branch_id}/kiosk-key/rotate")
def rotate_kiosk_key(branch_id: int, request: Request,
                     user: models.User = Depends(require_perm("manage_branches")),
                     db: Session = Depends(get_db)):
    """R3-A §5 — يولّد/يدوّر مفتاح شاشة العرض. يعيد المفتاح الكامل *مرة واحدة فقط*
    (هذه هي المرة الوحيدة اللي هيظهر فيها كامل — بعدها يُعرض masked في القوائم).
    القديم يُبطل فورًا؛ أي شاشة تستخدمه ستنقطع."""
    branch = db.get(models.Branch, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="الفرع غير موجود")
    assert_same_company(user, branch.company_id, db=db)
    branch.kiosk_key = secrets.token_urlsafe(24)
    audit(db, user, "rotate_kiosk_key", "branch", branch.id, request=request)
    db.commit()
    return {
        "branch_id": branch.id,
        "kiosk_key": branch.kiosk_key,  # ← الكامل، مرة واحدة فقط
        "kiosk_key_masked": _mask_kiosk_key(branch.kiosk_key),
        "kiosk_path": f"/kiosk/qr/{branch.id}?key={branch.kiosk_key}",
        "warning": "احفظ المفتاح الآن — لن يُعرض كاملاً مرة أخرى. أي شاشة تستخدم "
                   "المفتاح القديم قد تحتاج لإعادة الفتح بالرابط الجديد.",
    }


@router.get("/branches/{branch_id}/kiosk-url")
def get_kiosk_url(branch_id: int,
                  user: models.User = Depends(require_perm("manage_branches")),
                  db: Session = Depends(get_db)):
    """R3-A §5 — يعرض المفتاح masked فقط (آخر 4 خانات). للحصول على المفتاح الكامل،
    يجب استخدام /rotate الذي يعيد إنشاء واحد جديد."""
    branch = db.get(models.Branch, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="الفرع غير موجود")
    assert_same_company(user, branch.company_id, db=db)
    if not branch.kiosk_key:
        return {"branch_id": branch.id, "kiosk_key_masked": None, "kiosk_path": None}
    return {
        "branch_id": branch.id,
        "kiosk_key_masked": _mask_kiosk_key(branch.kiosk_key),
        # نُبقي رابط الشاشة الكامل لأن الفرع يحتاج فتحه فعلًا لعرض QR
        # (هو المستخدم النهائي الوحيد للمفتاح — الموظفون يمسحون QR لا يرون المفتاح)
        "kiosk_path": f"/kiosk/qr/{branch.id}?key={branch.kiosk_key}",
    }


@router.post("/branches/{branch_id}/supervisors/{user_id}")
def add_supervisor(branch_id: int, user_id: int, request: Request,
                   user: models.User = Depends(require_perm("manage_branches")),
                   db: Session = Depends(get_db)):
    branch = db.get(models.Branch, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="الفرع غير موجود")
    assert_same_company(user, branch.company_id, db=db)
    target = db.get(models.User, user_id)
    if not target or target.company_id != branch.company_id:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    # BR-27 — الدور يحدّد ما يُعتمَد. وربط من ليس مسؤول فرع كان يُكتَب
    # ويبدو ناجًحا ثم لا يصله طلب — إسناٌد صامت بلا أثر. يُردّ صراحًة.
    if target.role != "branch_supervisor":
        raise HTTPException(
            status_code=400,
            detail=(f"«{target.full_name}» دوره ليس مسؤول فرع، فلا تصله "
                    "طلبات هذه المرحلة. غيّر دوره أوًلا ثم أسنِده للفرع."))
    exists = db.scalar(select(models.BranchSupervisor).where(
        models.BranchSupervisor.branch_id == branch_id,
        models.BranchSupervisor.user_id == user_id))
    if not exists:
        db.add(models.BranchSupervisor(company_id=branch.company_id, branch_id=branch_id,
                                       user_id=user_id))
        audit(db, user, "add_supervisor", "branch", branch_id, detail=str(user_id), request=request)
        db.commit()
    return {"ok": True}


# ----------------------------- الإدارات/الأقسام -----------------------------

@router.get("/departments")
def list_departments(company_id: int | None = None, branch_id: int | None = None,
                     user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    cid = scope_company_id(user, company_id)
    q = select(models.Department).where(models.Department.status == "active")
    if cid is not None:
        q = q.where(models.Department.company_id == cid)
    if branch_id:
        q = q.where(models.Department.branch_id == branch_id)
    rows = db.scalars(q.order_by(models.Department.name)).all()
    counts = {}
    for d in rows:
        counts[d.id] = len(db.scalars(select(models.Employee.id).where(
            models.Employee.department_id == d.id, models.Employee.status == "active")).all())
    return [{"id": d.id, "name": d.name, "branch_id": d.branch_id,
             "employee_count": counts.get(d.id, 0)} for d in rows]


@router.post("/departments", status_code=201)
def create_department(name: str, branch_id: int | None = None, request: Request = None,
                      user: models.User = Depends(require_perm("manage_departments")),
                      db: Session = Depends(get_db)):
    if user.company_id is None:
        raise HTTPException(status_code=400, detail="يجب أن يكون المستخدم تابعًا لشركة")
    if branch_id:
        branch = db.get(models.Branch, branch_id)
        if not branch or branch.company_id != user.company_id:
            raise HTTPException(status_code=404, detail="الفرع غير موجود")
    dept = models.Department(company_id=user.company_id, branch_id=branch_id, name=name)
    db.add(dept)
    db.flush()
    audit(db, user, "create_department", "department", dept.id, request=request)
    db.commit()
    return {"ok": True, "id": dept.id}


# ----------------------------- الورديات -----------------------------

@router.get("/shifts")
def list_shifts(company_id: int | None = None,
                user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    cid = scope_company_id(user, company_id)
    q = select(models.Shift)
    if cid is not None:
        q = q.where(models.Shift.company_id == cid)
    rows = db.scalars(q).all()
    # **وردية لا أحد عليها لا تفعل شيًئا**: التأخير والانصراف المبكّر
    # يُحسبان من ``emp.shift_id``، ومن لا وردية له «حاضر» دائًما. فالعدد
    # معروض ليرى المعرِّف أن ما عرّفه بلا أثر.
    counts = dict(db.execute(
        select(models.Employee.shift_id, func.count(models.Employee.id))
        .where(models.Employee.shift_id.is_not(None))
        .group_by(models.Employee.shift_id)).all())
    return [{"id": s.id, "name": s.name, "start_time": str(s.start_time),
             "end_time": str(s.end_time), "work_days": s.work_days,
             "grace_minutes": s.grace_minutes,
             "employee_count": counts.get(s.id, 0)} for s in rows]


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


@router.put("/shifts/{shift_id}")
def update_shift(shift_id: int, data: schemas.ShiftIn, request: Request,
                 user: models.User = Depends(require_perm("manage_attendance")),
                 db: Session = Depends(get_db)):
    """تعديل وردية قائمة.

    **ولماذا لزم**: السجل كان إنشاًء بلا تعديل، فخطأ في وقت البدء يبقى
    إلى الأبد ويُخطئ في وسم كل حضور بعده — والعلاج الوحيد إنشاء وردية
    ثانية وإعادة إسناد كل من عليها.
    """
    shift = db.get(models.Shift, shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="الوردية غير موجودة")
    assert_same_company(user, shift.company_id, db=db)
    before = {"name": shift.name, "start_time": str(shift.start_time),
              "end_time": str(shift.end_time), "work_days": shift.work_days,
              "grace_minutes": shift.grace_minutes}
    for k, v in data.model_dump().items():
        setattr(shift, k, v)
    # التعديل يمسّ وسم حضور من عليها — فيُقيَّد بما كان وما صار.
    audit(db, user, "update_shift", "shift", shift.id, request=request,
          before=before, after=data.model_dump(mode="json"))
    db.commit()
    return {"ok": True, "id": shift.id}


# ----------------------------- التراخيص -----------------------------

@router.get("/licenses")
def list_licenses(company_id: int | None = None,
                  user: models.User = Depends(require_perm("manage_licenses")),
                  db: Session = Depends(get_db)):
    cid = scope_company_id(user, company_id)
    q = select(models.License)
    if cid is not None:
        q = q.where(models.License.company_id == cid)
    rows = db.scalars(q).all()
    out = []
    today = kuwait_today()
    for lic in rows:
        actual = license_headcount(db, lic.id)
        # «منتهٍ» **مشتقٌّ من التاريخ** لا يُكتب في الحالة المخزَّنة: مسحُ الانتهاء يمرّ على النشطة ويحسب الأيامَ منه، فقلبُ
        # الحالة يُسكت تنبيهَ من انتهى ترخيصه فعلًا (SW-016). فالعرضُ يقول الصدق والتنبيهُ يبقى.
        expired = bool(lic.expiry_date and lic.expiry_date < today)
        out.append({
            "id": lic.id, "name": lic.name, "license_no": lic.license_no,
            "issuing_authority": lic.issuing_authority, "status": lic.status,
            "is_expired": expired,
            "effective_status": "expired" if expired and lic.status == "active" else lic.status,
            "expiry_date": lic.expiry_date, "allowed_workers": lic.allowed_workers,
            "actual_workers": actual, "over_capacity": actual > (lic.allowed_workers or 0),
        })
    return out


@router.post("/licenses", status_code=201)
def create_license(name: str, license_no: str | None = None, issuing_authority: str | None = None,
                   allowed_workers: int = 0, expiry_date: date | None = None,
                   issue_date: date | None = None, address: str | None = None,
                   license_type: str | None = None, company_id: int | None = None,
                   request: Request = None,
                   user: models.User = Depends(require_perm("manage_licenses")),
                   db: Session = Depends(get_db)):
    """ترخيٌص للشركة.

    **وكان بلا تاريخ انتهاء**: الترخيُص يُسجَّل ولا يأتي تنبيُه تجديده أبًدا —
    فالمسُح اليومي يقرأ ``expiry_date``. ومن لا شركة له (الإدارة العليا وصاحب
    الشركات) يحدّد الشركة صراحًة، كإنشاء الفرع.
    """
    from ..permissions import CROSS_COMPANY_ROLES

    cid = user.company_id
    if company_id is not None and user.role in CROSS_COMPANY_ROLES:
        if db.get(models.Company, company_id) is None:
            raise HTTPException(status_code=404, detail="الشركة غير موجودة")
        cid = company_id
    if cid is None:
        raise HTTPException(status_code=400, detail="حدّد الشركة (company_id)")
    lic = models.License(company_id=cid, name=name, license_no=license_no,
                         issuing_authority=issuing_authority, allowed_workers=allowed_workers,
                         expiry_date=expiry_date, issue_date=issue_date, address=address,
                         license_type=license_type)
    db.add(lic)
    db.flush()
    audit(db, user, "create_license", "license", lic.id, request=request)
    db.commit()
    return {"ok": True, "id": lic.id}
