# -*- coding: utf-8 -*-
"""المستخدمون والصلاحيات: إنشاء، إسناد/نسخ صلاحيات، قوالب، صلاحيات مؤقتة."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import settings
from ..database import get_db
from ..deps import (
    audit, get_current_user, get_user_perms, require_perm, require_super_admin, scope_company_id,
)
from ..permissions import (
    ACTIONS_AR,
    CROSS_COMPANY_ROLES,
    PERMISSION_TEMPLATES,
    PERMISSIONS,
    ROLE_LEVEL,
    ROLES,
    can_manage_role,
    effective_permissions,
    has_page_action,
    permission_matrix_catalog,
)
from ..security import hash_password

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/catalog")
def perm_catalog(user: models.User = Depends(require_perm("manage_users"))):
    """كتالوج الصلاحيات والقوالب والأدوار لواجهة الإدارة."""
    # المستخدم يدير فقط الأدوار الأدنى منه مستوى
    if user.role == "super_admin":
        assignable = ROLES
    else:
        assignable = [r for r in ROLES if can_manage_role(user.role, r)]
    return {"permissions": PERMISSIONS, "templates": PERMISSION_TEMPLATES,
            "roles": ROLES, "assignable_roles": assignable, "levels": ROLE_LEVEL}


@router.get("", response_model=list[schemas.UserOut])
def list_users(company_id: int | None = None,
               user: models.User = Depends(require_perm("manage_users")),
               db: Session = Depends(get_db)):
    """قائمة المستخدمين مع فلترة اختيارية بالشركة.

    R9 §16 — مستخدمو is_cross_company (يخدمون شركات متعددة، company_id=NULL) يظهرون
    عند فلترة أي شركة يخدمونها — نتحقق عبر user_company_links.
    """
    cid = scope_company_id(user, company_id)
    q = select(models.User)
    if cid is not None:
        # R9 §16 — يشمل: users بـcompany_id مطابق OR cross-company users مربوطون بها
        cross_company_uids = {
            uid for uid in db.scalars(select(models.UserCompanyLink.user_id).where(
                models.UserCompanyLink.company_id == cid
            )).all()
        }
        if cross_company_uids:
            q = q.where(
                (models.User.company_id == cid) |
                (models.User.id.in_(cross_company_uids))
            )
        else:
            q = q.where(models.User.company_id == cid)
    return list(db.scalars(q).all())


@router.post("", response_model=schemas.UserOut, status_code=201)
def create_user(data: schemas.UserIn, request: Request,
                user: models.User = Depends(require_perm("manage_users")),
                db: Session = Depends(get_db)):
    if data.role not in ROLES:
        raise HTTPException(status_code=400, detail="دور غير صالح")
    # التسلسل الهرمي: لا تُنشئ دورًا أعلى من مستواك أو مساويًا له
    if not can_manage_role(user.role, data.role):
        raise HTTPException(status_code=403, detail="لا يمكنك إنشاء مستخدم بهذا الدور")
    # الشركة: الإدارة العليا/المالك يختاران الشركة، والباقي مقيّد بشركته
    if user.role in CROSS_COMPANY_ROLES:
        company_id = data.company_id
    else:
        company_id = user.company_id
    if db.scalar(select(models.User).where(models.User.civil_id == data.civil_id)):
        raise HTTPException(status_code=409, detail="الرقم المدني مستخدم بالفعل")

    # PILOT-P0-1: حساب بدور "employee" لازم يكون مربوطًا بموظف (حماية صارمة).
    # V2.2 §3: باقي الأدوار الداخلية (hr/accountant/manager/supervisor/delegate) هم فعليًا
    # موظفون بالشركة، وحسابهم يجب ربطه بموظف حتى يقدروا يقدموا طلبات لأنفسهم (إجازة/
    # شهادة راتب/تصحيح حضور). لكن لا نُلزم فورًا للحفاظ على التوافق مع تدفقات HR الحالية —
    # نعرض تحذير مسموع في /orphaned و POST /link-employee للربط الرجعي.
    if data.role == "employee" and not data.employee_id:
        raise HTTPException(
            status_code=400,
            detail="حساب موظف يجب ربطه بسجل موظف فعلي (employee_id مطلوب)",
        )
    if data.employee_id:
        emp = db.get(models.Employee, data.employee_id)
        if not emp:
            raise HTTPException(status_code=404, detail="سجل الموظف غير موجود")
        if company_id is None:
            company_id = emp.company_id
        elif emp.company_id != company_id:
            raise HTTPException(
                status_code=400,
                detail="سجل الموظف من شركة مختلفة عن شركة الحساب",
            )
        existing_link = db.scalar(
            select(models.User).where(models.User.employee_id == data.employee_id)
        )
        if existing_link:
            raise HTTPException(
                status_code=409,
                detail=f"هذا الموظف مربوط بحساب موجود بالفعل (المستخدم #{existing_link.id})",
            )

    pw = data.password or settings.default_user_password
    new_user = models.User(
        civil_id=data.civil_id, full_name=data.full_name, role=data.role,
        company_id=company_id, email=data.email, phone=data.phone,
        employee_id=data.employee_id, password_hash=hash_password(pw),
        must_change_password=True,
    )
    db.add(new_user)
    db.flush()
    audit(db, user, "create_user", "user", new_user.id, request=request)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.get("/orphaned")
def list_orphaned_users(user: models.User = Depends(require_perm("manage_users")),
                       db: Session = Depends(get_db)):
    """V2.2 §3 — كل الأدوار داخل الشركة (employee/hr/accountant/delegate/
    branch_supervisor/company_manager) لازم تكون مربوطة بموظف. المالك و
    super_admin مستثنون. هنا نعرض كل الحسابات المكسورة داخل شركة المستخدم."""
    from ..permissions import CROSS_COMPANY_ROLES as _CC
    INTERNAL_ROLES = ["employee", "hr", "accountant", "delegate",
                      "branch_supervisor", "company_manager", "admin_employee"]
    q = select(models.User).where(
        models.User.role.in_(INTERNAL_ROLES),
        models.User.employee_id.is_(None),
        models.User.is_active == True,  # noqa: E712
    )
    if user.role not in _CC:
        q = q.where(models.User.company_id == user.company_id)
    rows = db.scalars(q).all()
    return [
        {"id": u.id, "civil_id": u.civil_id, "full_name": u.full_name,
         "role": u.role, "company_id": u.company_id, "created_at": u.created_at}
        for u in rows
    ]


@router.post("/{user_id}/link-employee")
def link_user_to_employee(user_id: int, employee_id: int, request: Request,
                          user: models.User = Depends(require_perm("manage_users")),
                          db: Session = Depends(get_db)):
    """V2.2 §3 — يربط user موجود بسجل موظف. يفشل لو الاثنين من شركات مختلفة
    أو الموظف مربوط بحساب آخر بالفعل."""
    target = _get_scoped_user(db, user, user_id)
    emp = db.get(models.Employee, employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="سجل الموظف غير موجود")
    if target.company_id and emp.company_id != target.company_id:
        raise HTTPException(status_code=400, detail="سجل الموظف من شركة مختلفة")
    other = db.scalar(select(models.User).where(
        models.User.employee_id == employee_id,
        models.User.id != user_id,
    ))
    if other:
        raise HTTPException(
            status_code=409,
            detail=f"هذا الموظف مربوط بحساب آخر (#{other.id})",
        )
    old = target.employee_id
    target.employee_id = employee_id
    if not target.company_id:
        target.company_id = emp.company_id
    audit(db, user, "link_user_to_employee", "user", target.id,
          detail=f"{old} → {employee_id}", request=request)
    db.commit()
    return {"ok": True, "user_id": target.id, "employee_id": employee_id}


@router.post("/{user_id}/link-employee")
def link_orphan_to_employee(user_id: int, employee_id: int, request: Request,
                            user: models.User = Depends(require_perm("manage_users")),
                            db: Session = Depends(get_db)):
    """V2.2 §1 (نهاية القائمة): معالجة الحسابات القديمة بدون employee_id.
    HR/Admin يربط User يتيم بسجل Employee متطابق (نفس الشركة، لا رابط سابق)."""
    target = _get_scoped_user(db, user, user_id)
    if target.employee_id:
        raise HTTPException(status_code=409,
                            detail=f"المستخدم مربوط بالفعل بموظف #{target.employee_id}")
    emp = db.get(models.Employee, employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    if emp.company_id != target.company_id:
        raise HTTPException(status_code=400,
                            detail="الموظف من شركة مختلفة عن حساب المستخدم")
    # ما فيش يوزر تاني مربوط بنفس الموظف
    existing = db.scalar(select(models.User).where(
        models.User.employee_id == employee_id, models.User.id != target.id))
    if existing:
        raise HTTPException(status_code=409,
                            detail=f"الموظف مربوط بحساب مستخدم آخر (#{existing.id})")
    target.employee_id = employee_id
    audit(db, user, "link_user_to_employee", "user", target.id,
          detail=f"employee_id={employee_id}", request=request)
    db.commit()
    return {"ok": True, "user_id": target.id, "employee_id": employee_id}


@router.post("/auto-link-employees")
def auto_link_all_orphans(request: Request,
                          user: models.User = Depends(require_perm("manage_users")),
                          db: Session = Depends(get_db)):
    """R9 §14 — يمر atomic على كل حساب unlinked ويربطه بموظف مطابق (نفس الرقم
    المدني والشركة). idempotent — تشغيل ثاني لا يعمل شيء.

    القواعد:
    - لا يمس super_admin/company_owner (بلا employee بشكل مقصود)
    - لا يستبدل رابط موجود
    - لا يُنشئ Employee وهمي — يتخطى ويبلّغ لو مافيش موظف مطابق
    - لا يسمح بربطين لنفس الموظف — يبلّغ عن التعارض
    """
    from ..user_employee_link import auto_link_users_to_employees
    report = auto_link_users_to_employees(db)
    # سجل كل ربط في Audit
    for entry in report["linked"]:
        audit(db, user, "auto_link_user_to_employee", "user", entry["user_id"],
              detail=f"→ employee #{entry['employee_id']} (civil_id={entry['civil_id']})",
              request=request)
    db.commit()
    return report


# =============================================================================
# R9 §16 — Multi-Company User Management
# =============================================================================

@router.post("/{user_id}/enable-cross-company")
def enable_cross_company(user_id: int, request: Request,
                        user: models.User = Depends(require_super_admin),
                        db: Session = Depends(get_db)):
    """R9 §16 — يفعّل flag is_cross_company على user موجود.
    - يمسح company_id (كان يشير لشركة واحدة → الآن NULL)
    - يمسح employee_id (كان يشير لسجل موظف واحد → الآن يُحسم من link حسب الشركة النشطة)
    - super_admin فقط لأن هذا تغيير معماري في نطاق الحساب
    - المستخدم لازم يعمل تسجيل خروج ثم دخول عشان الـflag يفعل"""
    target = db.get(models.User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    if target.role in ("super_admin", "company_owner"):
        raise HTTPException(status_code=400,
                          detail="super_admin/company_owner cross-company بالفعل — لا يحتاج flag")
    target.is_cross_company = True
    old_company = target.company_id
    old_emp = target.employee_id
    target.company_id = None
    target.employee_id = None
    audit(db, user, "enable_cross_company", "user", target.id,
          detail=f"was company_id={old_company}, employee_id={old_emp}",
          request=request)
    db.commit()
    return {"ok": True, "user_id": target.id, "is_cross_company": True,
            "note": "أضف company links عبر POST /users/{id}/company-links ثم اطلب من المستخدم إعادة الدخول"}


@router.post("/{user_id}/company-links")
def add_company_link(user_id: int, request: Request,
                    company_id: int, employee_id: int,
                    role: str = "delegate",
                    non_payroll: bool | None = None,
                    user: models.User = Depends(require_super_admin),
                    db: Session = Depends(get_db)):
    """R9 §16 — يضيف عضوية شركة لمستخدم متعدد الشركات.
    - يتحقق: employee.company_id == company_id (لا خلط شركات)
    - يتحقق: user.is_cross_company=True
    - يتحقق: ما فيش user آخر مربوط بهذا employee
    - Idempotent: لو الرابط موجود لنفس الاثنين، يرجع 200 بدون تكرار
    """
    target = db.get(models.User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    if not target.is_cross_company:
        raise HTTPException(status_code=400,
                          detail="فعّل is_cross_company أولاً عبر /enable-cross-company")

    company = db.get(models.Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="الشركة غير موجودة")

    emp = db.get(models.Employee, employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    if emp.company_id != company_id:
        raise HTTPException(status_code=400,
                          detail=f"الموظف #{employee_id} ينتمي للشركة #{emp.company_id} مش #{company_id}")

    # ما فيش user آخر مربوط بنفس الموظف عبر user.employee_id (single link)
    other = db.scalar(select(models.User).where(
        models.User.employee_id == employee_id,
        models.User.id != user_id,
    ))
    if other:
        raise HTTPException(status_code=409,
                          detail=f"الموظف #{employee_id} مربوط بحساب آخر #{other.id}")

    # ولا user آخر متعدد الشركات مربوط بنفس الموظف عبر link
    other_link = db.scalar(select(models.UserCompanyLink).where(
        models.UserCompanyLink.employee_id == employee_id,
        models.UserCompanyLink.user_id != user_id,
    ))
    if other_link:
        raise HTTPException(status_code=409,
                          detail=f"الموظف #{employee_id} مربوط عبر link لحساب آخر #{other_link.user_id}")

    # هل الرابط موجود بالفعل؟
    existing = db.scalar(select(models.UserCompanyLink).where(
        models.UserCompanyLink.user_id == user_id,
        models.UserCompanyLink.company_id == company_id,
    ))
    if existing:
        if existing.employee_id != employee_id:
            existing.employee_id = employee_id
            existing.role = role
            audit(db, user, "update_company_link", "user", user_id,
                  detail=f"company#{company_id} → emp#{employee_id}", request=request)
            db.commit()
        return {"ok": True, "link_id": existing.id, "updated": True}

    # QA-18 — الإسناد الثانوي ليس وظيفة ثانية: من له وظيفة أصلية في شركة
    # يحتاج سجل موظف في الشركة الأخرى ليعمل فيها، لا راتًبا ثانًيا. بلا هذا
    # التمييز دخل المندوب كشف الشركة الثانية براتب صفر واحتُسب له مستحق
    # نهاية خدمة لا وجود له. الافتراض مشتقّ لا مفروض: يُعتبر ثانوًيا إن كانت
    # للمستخدم وظيفة أصلية أو عضوية سابقة — ويبقى للمشرف تجاوزه صراحًة.
    is_secondary = bool(target.employee_id) or bool(db.scalar(
        select(models.UserCompanyLink).where(models.UserCompanyLink.user_id == user_id)))
    mark_non_payroll = is_secondary if non_payroll is None else non_payroll
    if mark_non_payroll and not emp.non_payroll:
        emp.non_payroll = True
        emp.non_payroll_reason = f"إسناد ثانوي لحساب #{user_id} — وصول/صلاحية فقط"

    link = models.UserCompanyLink(
        user_id=user_id, company_id=company_id, employee_id=employee_id,
        role=role, created_by=user.id,
    )
    db.add(link)
    db.flush()
    audit(db, user, "add_company_link", "user", user_id,
          detail=f"company#{company_id} + emp#{employee_id} ({role})",
          request=request, company_id=company_id)
    db.commit()
    return {"ok": True, "link_id": link.id, "created": True}


@router.get("/{user_id}/company-links")
def list_company_links(user_id: int,
                      user: models.User = Depends(require_perm("manage_users")),
                      db: Session = Depends(get_db)):
    """R9 §16 — يعرض عضويات user متعدد الشركات."""
    target = db.get(models.User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    links = db.scalars(select(models.UserCompanyLink).where(
        models.UserCompanyLink.user_id == user_id
    )).all()
    out = []
    for lk in links:
        co = db.get(models.Company, lk.company_id)
        emp = db.get(models.Employee, lk.employee_id)
        out.append({
            "id": lk.id, "company_id": lk.company_id,
            "company_name": co.name if co else None,
            "employee_id": lk.employee_id,
            "employee_name": emp.name if emp else None,
            "role": lk.role, "created_at": lk.created_at,
        })
    return {"user_id": user_id, "is_cross_company": target.is_cross_company,
            "links": out}


@router.delete("/{user_id}/company-links/{link_id}")
def remove_company_link(user_id: int, link_id: int, request: Request,
                       user: models.User = Depends(require_super_admin),
                       db: Session = Depends(get_db)):
    """R9 §16 — يمسح عضوية شركة (لو المستخدم ما عاد يخدمها)."""
    link = db.get(models.UserCompanyLink, link_id)
    if not link or link.user_id != user_id:
        raise HTTPException(status_code=404, detail="الرابط غير موجود")
    audit(db, user, "remove_company_link", "user", user_id,
          detail=f"removed link #{link_id} (company#{link.company_id})",
          request=request, company_id=link.company_id)
    db.delete(link)
    db.commit()
    return {"ok": True}


@router.post("/{user_id}/toggle")
def toggle_active(user_id: int, request: Request,
                  user: models.User = Depends(require_perm("manage_users")),
                  db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    target = _get_scoped_user(db, user, user_id)
    target.is_active = not target.is_active
    target.status = "active" if target.is_active else "inactive"
    # V2.2 §9 — عند التعطيل، إبطال كل الجلسات النشطة فورًا (JWT الحالية تفشل)
    if not target.is_active:
        target.tokens_valid_after = datetime.now(timezone.utc)
    audit(db, user, "toggle_user", "user", target.id, request=request)
    db.commit()
    return {"ok": True, "is_active": target.is_active, "status": target.status}


USER_STATUSES = {"active", "inactive", "suspended", "locked"}


@router.post("/{user_id}/status")
def set_user_status(user_id: int, status: str, request: Request,
                    user: models.User = Depends(require_perm("manage_users")),
                    db: Session = Depends(get_db)):
    """تغيير حالة المستخدم (نشط/غير نشط/موقوف/مقفل) — لا يُحذف نهائيًا.
    V2.2 §9: أي انتقال إلى حالة غير نشطة (inactive/suspended/locked) يبطل
    الجلسات الحالية تلقائيًا حتى لا يبقى token صالح لحساب معطّل."""
    if status not in USER_STATUSES:
        raise HTTPException(status_code=400, detail="حالة غير صالحة")
    from datetime import datetime, timedelta, timezone
    target = _get_scoped_user(db, user, user_id)
    prev_status = target.status
    target.status = status
    target.is_active = status == "active"
    if status == "locked":
        target.locked_until = datetime.now(timezone.utc) + timedelta(days=3650)
    elif status == "active":
        target.locked_until = None
    # إبطال الجلسات عند أي تعطيل — يمنع بقاء JWT صالح لحساب suspended/inactive
    if status != "active" and prev_status == "active":
        target.tokens_valid_after = datetime.now(timezone.utc)
    audit(db, user, "set_user_status", "user", target.id, detail=status, request=request)
    db.commit()
    return {"ok": True, "status": status}


@router.post("/{user_id}/scope")
def set_data_scope(user_id: int, level: str | None = None, branch_id: int | None = None,
                   branch_ids: list[int] | None = Query(None), request: Request = None,
                   user: models.User = Depends(require_perm("manage_users")),
                   db: Session = Depends(get_db)):
    """يضبط مستوى نطاق بيانات المستخدم: company | branch | multi | self.

    - branch: فرع واحد عبر branch_id.
    - multi : عدة فروع عبر branch_ids (تُخزّن في branch_supervisors).
    - company/self: لا فروع.
    لتوافق خلفي: تمرير branch_id وحده (بلا level) يُفسَّر كـ branch، وتركه فارغًا = company.
    """
    from ..deps import SCOPE_LEVELS

    target = _get_scoped_user(db, user, user_id)
    old_level, old_branch = target.scope_level, target.scope_branch_id

    # توافق خلفي: استنتاج المستوى من المُدخل القديم
    if level is None:
        level = "branch" if branch_id else "company"
    if level not in SCOPE_LEVELS:
        raise HTTPException(status_code=400, detail="مستوى نطاق غير صالح")

    def _assert_branch(bid: int) -> models.Branch:
        b = db.get(models.Branch, bid)
        if not b or (user.role not in CROSS_COMPANY_ROLES and b.company_id != user.company_id):
            raise HTTPException(status_code=404, detail="الفرع غير موجود")
        return b

    # تنظيف أي إسناد فروع سابق ثم إعادة الضبط حسب المستوى
    db.query(models.BranchSupervisor).filter(
        models.BranchSupervisor.user_id == target.id).delete()
    target.scope_branch_id = None

    if level == "branch":
        if not branch_id:
            raise HTTPException(status_code=400, detail="يلزم تحديد فرع للمستوى branch")
        _assert_branch(branch_id)
        target.scope_branch_id = branch_id
    elif level == "multi":
        ids = branch_ids or ([branch_id] if branch_id else [])
        if not ids:
            raise HTTPException(status_code=400, detail="يلزم تحديد فرع واحد على الأقل للمستوى multi")
        for bid in dict.fromkeys(ids):  # إزالة التكرار مع الحفاظ على الترتيب
            b = _assert_branch(bid)
            db.add(models.BranchSupervisor(company_id=b.company_id, branch_id=bid, user_id=target.id))

    target.scope_level = level
    audit(db, user, "set_data_scope", "user", target.id,
          detail=f"قبل: level={old_level} branch={old_branch} ← بعد: level={level} "
                 f"branch={branch_id} multi={branch_ids}", request=request)
    db.commit()
    return {"ok": True, "scope_level": level, "scope_branch_id": target.scope_branch_id}


@router.post("/{user_id}/impersonate")
def impersonate(user_id: int, request: Request, reason: str | None = None,
                actor: models.User = Depends(require_super_admin),
                db: Session = Depends(get_db)):
    """انتحال هوية مستخدم مؤقتًا (للإدارة العليا فقط) — يُسجَّل في التدقيق."""
    from ..security import create_access_token, create_refresh_token

    target = db.get(models.User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    if target.role == "super_admin":
        raise HTTPException(status_code=400, detail="لا يمكن انتحال إدارة عليا")
    audit(db, actor, "impersonate_start", "user", target.id,
          detail=f"reason={reason or '-'}", request=request, company_id=target.company_id)
    db.commit()
    return {
        "access_token": create_access_token(target.id, target.role, target.company_id,
                                            impersonator_id=actor.id),
        "refresh_token": create_refresh_token(target.id),
        "impersonated": {"id": target.id, "full_name": target.full_name, "role": target.role},
    }


@router.post("/impersonate-end")
def impersonate_end(request: Request,
                    user: models.User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """يسجّل انتهاء الانتحال (P1-04) — يُستدعى من الواجهة قبل استعادة رمز الإدارة العليا
    الأصلي مباشرًة، ويحتاج claim خاص (impersonator_id) موجود فقط في رمز مُنتحَل فعًلا."""
    from ..security import decode_token

    token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="بيانات اعتماد غير صالحة")
    impersonator_id = payload.get("impersonator_id")
    if not impersonator_id:
        raise HTTPException(status_code=400, detail="هذا الرمز ليس رمز انتحال")
    actor = db.get(models.User, impersonator_id)
    audit(db, actor, "impersonate_end", "user", user.id, request=request, company_id=user.company_id)
    db.commit()
    return {"ok": True}


@router.get("/{user_id}/permissions")
def get_permissions(user_id: int, user: models.User = Depends(require_perm("manage_users")),
                    db: Session = Depends(get_db)):
    target = _get_scoped_user(db, user, user_id)
    assigned = [{"perm_code": p.perm_code, "expires_at": p.expires_at}
                for p in target.permissions]
    return {
        "role": target.role,
        "assigned": assigned,
        "effective": sorted(effective_permissions(target.role, get_user_perms(target, db))),
    }


@router.post("/{user_id}/permissions")
def assign_permissions(user_id: int, data: schemas.PermissionAssignIn, request: Request,
                       user: models.User = Depends(require_perm("manage_users")),
                       db: Session = Depends(get_db)):
    target = _get_scoped_user(db, user, user_id)
    for code in data.perm_codes:
        if code not in PERMISSIONS:
            raise HTTPException(status_code=400, detail=f"صلاحية غير معروفة: {code}")
        existing = next((p for p in target.permissions if p.perm_code == code), None)
        if existing:
            existing.expires_at = data.expires_at
        else:
            db.add(models.UserPermission(user_id=target.id, perm_code=code,
                                         expires_at=data.expires_at))
    audit(db, user, "assign_permissions", "user", target.id,
          detail=",".join(data.perm_codes), request=request)
    db.commit()
    return {"ok": True}


@router.delete("/{user_id}/permissions/{perm_code}")
def revoke_permission(user_id: int, perm_code: str, request: Request,
                      user: models.User = Depends(require_perm("manage_users")),
                      db: Session = Depends(get_db)):
    target = _get_scoped_user(db, user, user_id)
    perm = next((p for p in target.permissions if p.perm_code == perm_code), None)
    if perm:
        db.delete(perm)
        audit(db, user, "revoke_permission", "user", target.id, detail=perm_code, request=request)
        db.commit()
    return {"ok": True}


@router.post("/apply-template/{user_id}/{template_code}")
def apply_template(user_id: int, template_code: str, request: Request,
                   user: models.User = Depends(require_perm("manage_users")),
                   db: Session = Depends(get_db)):
    if template_code not in PERMISSION_TEMPLATES:
        raise HTTPException(status_code=404, detail="القالب غير موجود")
    target = _get_scoped_user(db, user, user_id)
    existing = {p.perm_code for p in target.permissions}
    for code in PERMISSION_TEMPLATES[template_code]["perms"]:
        if code not in existing:
            db.add(models.UserPermission(user_id=target.id, perm_code=code))
    audit(db, user, "apply_template", "user", target.id, detail=template_code, request=request)
    db.commit()
    return {"ok": True}


@router.get("/permission-matrix")
def matrix_catalog(user: models.User = Depends(require_perm("manage_users"))):
    """قائمة الصفحات والأفعال لبناء مصفوفة الأذونات."""
    return {"pages": permission_matrix_catalog(), "actions_ar": ACTIONS_AR}


@router.get("/{user_id}/matrix")
def get_matrix(user_id: int, user: models.User = Depends(require_perm("manage_users")),
               db: Session = Depends(get_db)):
    """المصفوفة الفعّالة للمستخدم (صفحة×فعل) + الصفحات المُدارة صراحةً."""
    target = _get_scoped_user(db, user, user_id)
    assigned = get_user_perms(target, db)
    catalog = permission_matrix_catalog()
    grid: dict[str, dict[str, bool]] = {}
    custom: list[str] = []
    for page in catalog:
        pc = page["code"]
        if any(c.startswith(pc + ".") for c in assigned):
            custom.append(pc)
        grid[pc] = {a: has_page_action(target.role, assigned, pc, a) for a in page["actions"]}
    return {"role": target.role, "matrix": grid, "custom_pages": custom}


@router.post("/{user_id}/matrix")
def set_matrix(user_id: int, data: schemas.MatrixIn, request: Request,
               user: models.User = Depends(require_perm("manage_users")),
               db: Session = Depends(get_db)):
    """يضبط مصفوفة دقيقة للمستخدم. كل صفحة مذكورة تصبح مُدارة صراحةً (تتجاوز الدور)."""
    target = _get_scoped_user(db, user, user_id)
    valid_pages = {p["code"]: set(p["actions"]) for p in permission_matrix_catalog()}
    # احذف كل المنح الدقيقة الحالية ثم اكتب الجديدة (لقطة كاملة)
    for p in [x for x in target.permissions if "." in x.perm_code]:
        db.delete(p)
    for page, actions in data.grants.items():
        if page not in valid_pages:
            continue
        db.add(models.UserPermission(user_id=target.id, perm_code=f"{page}._"))  # علامة "مُدارة"
        for a in actions:
            if a in valid_pages[page]:
                db.add(models.UserPermission(user_id=target.id, perm_code=f"{page}.{a}"))
    audit(db, user, "set_permission_matrix", "user", target.id, request=request)
    db.commit()
    return {"ok": True}


@router.post("/{user_id}/matrix/reset")
def reset_matrix(user_id: int, user: models.User = Depends(require_perm("manage_users")),
                 db: Session = Depends(get_db)):
    """يعيد المستخدم إلى صلاحيات دوره الافتراضية (حذف كل المنح الدقيقة)."""
    target = _get_scoped_user(db, user, user_id)
    for p in [x for x in target.permissions if "." in x.perm_code]:
        db.delete(p)
    db.commit()
    return {"ok": True}


@router.post("/copy-permissions")
def copy_permissions(data: schemas.CopyPermsIn, request: Request,
                     user: models.User = Depends(require_perm("manage_users")),
                     db: Session = Depends(get_db)):
    src = _get_scoped_user(db, user, data.from_user_id)
    dst = _get_scoped_user(db, user, data.to_user_id)
    existing = {p.perm_code for p in dst.permissions}
    for p in src.permissions:
        if p.perm_code not in existing:
            db.add(models.UserPermission(user_id=dst.id, perm_code=p.perm_code,
                                         expires_at=p.expires_at))
    audit(db, user, "copy_permissions", "user", dst.id,
          detail=f"from {src.id}", request=request)
    db.commit()
    return {"ok": True}


def _get_scoped_user(db: Session, actor: models.User, user_id: int) -> models.User:
    target = db.get(models.User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    # العزل: غير الإدارة العليا/المالك مقيّد بشركته
    if actor.role not in CROSS_COMPANY_ROLES and target.company_id != actor.company_id:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    # التسلسل الهرمي: لا تُدِر من هم في مستواك أو أعلى (إلا الإدارة العليا)
    if actor.id != target.id and not can_manage_role(actor.role, target.role):
        raise HTTPException(status_code=403, detail="لا يمكنك إدارة مستخدم بهذا المستوى")
    return target


@router.post("/{user_id}/2fa/reset")
def reset_user_2fa(user_id: int, request: Request, reason: str,
                   user: models.User = Depends(require_super_admin),
                   db: Session = Depends(get_db)):
    """QA-30 — إعادة تعيين 2FA لمستخدم فقد جهازه ورموز الاسترداد مًعا.

    رموز الاسترداد تغطي الحالة الشائعة، لكن من يفقدها هي أيًضا يبقى محبوًسا:
    الدخول يستلزم رمًزا، وكل نقاط 2FA تستلزم جلسة تستلزم الدخول. المخرج
    الأخير قرار إداري موثَّق لا تعديل يدوي في قاعدة البيانات.

    السبب إلزامي: هذا إجراء يُضعف حماية حساب حسّاس، فيجب أن يُقرأ في التدقيق
    بعد شهور ويُفهم لماذا اتُّخذ ومن اتخذه.
    """
    if not (reason or "").strip():
        raise HTTPException(status_code=400, detail="سبب إعادة التعيين إلزامي")
    target = db.get(models.User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    if not target.totp_confirmed and not target.totp_secret:
        return {"ok": True, "already_disabled": True}

    target.totp_secret = None
    target.totp_confirmed = False
    target.totp_recovery_hashes = None
    audit(db, user, "totp_admin_reset", "user", target.id,
          detail=f"{target.full_name or target.civil_id}: {reason.strip()}",
          request=request, company_id=target.company_id)
    db.commit()
    # يُطلب منه التفعيل من جديد عند أول دخول لأن دوره يستوجبه
    return {"ok": True, "reset": True, "must_enroll_again": True}
