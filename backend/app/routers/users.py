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
    cid = scope_company_id(user, company_id)
    q = select(models.User)
    if cid is not None:
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

    # PILOT-P0-1: حساب بدور "employee" لازم يكون مربوطًا بموظف فعلي في نفس الشركة —
    # كل الشاشات (My Profile, Attendance, Leaves) تعتمد على user.employee_id، ولو
    # كان None يظهر 404 صامت. نمنع الإنشاء أصلًا لغلق هذا المصدر للخطأ.
    if data.role == "employee":
        if not data.employee_id:
            raise HTTPException(
                status_code=400,
                detail="حساب موظف يجب ربطه بسجل موظف فعلي (employee_id مطلوب)",
            )
        emp = db.get(models.Employee, data.employee_id)
        if not emp:
            raise HTTPException(status_code=404, detail="سجل الموظف غير موجود")
        if company_id is None:
            company_id = emp.company_id  # نستخدم شركة الموظف كافتراضي
        elif emp.company_id != company_id:
            raise HTTPException(
                status_code=400,
                detail="سجل الموظف من شركة مختلفة عن شركة الحساب",
            )
        # فحص إن الموظف لسه ما اترتبطش بحساب آخر
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
    """PILOT-P0-1: يعرض المستخدمين بدور 'employee' اللي ما اتربطوش بسجل موظف —
    وسيلة تشخيصية لأي حسابات قديمة اتعملت قبل الفحص الحالي وتحتاج إصلاح."""
    q = select(models.User).where(
        models.User.role == "employee",
        models.User.employee_id.is_(None),
        models.User.is_active == True,  # noqa: E712
    )
    if user.role not in CROSS_COMPANY_ROLES:
        q = q.where(models.User.company_id == user.company_id)
    rows = db.scalars(q).all()
    return [
        {"id": u.id, "civil_id": u.civil_id, "full_name": u.full_name,
         "company_id": u.company_id, "created_at": u.created_at}
        for u in rows
    ]


@router.post("/{user_id}/toggle")
def toggle_active(user_id: int, request: Request,
                  user: models.User = Depends(require_perm("manage_users")),
                  db: Session = Depends(get_db)):
    target = _get_scoped_user(db, user, user_id)
    target.is_active = not target.is_active
    target.status = "active" if target.is_active else "inactive"
    audit(db, user, "toggle_user", "user", target.id, request=request)
    db.commit()
    return {"ok": True, "is_active": target.is_active, "status": target.status}


USER_STATUSES = {"active", "inactive", "suspended", "locked"}


@router.post("/{user_id}/status")
def set_user_status(user_id: int, status: str, request: Request,
                    user: models.User = Depends(require_perm("manage_users")),
                    db: Session = Depends(get_db)):
    """تغيير حالة المستخدم (نشط/غير نشط/موقوف/مقفل) — لا يُحذف نهائيًا."""
    if status not in USER_STATUSES:
        raise HTTPException(status_code=400, detail="حالة غير صالحة")
    target = _get_scoped_user(db, user, user_id)
    target.status = status
    target.is_active = status == "active"
    if status == "locked":
        from datetime import datetime, timedelta, timezone
        target.locked_until = datetime.now(timezone.utc) + timedelta(days=3650)
    elif status == "active":
        target.locked_until = None
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
