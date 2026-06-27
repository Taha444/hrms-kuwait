# -*- coding: utf-8 -*-
"""تبعيات FastAPI: استخراج المستخدم الحالي، فرض الصلاحيات، وتطبيق العزل.

مبدأ أساسي: العزل والصلاحيات تُفرَض على السيرفر — لا تعتمد الواجهة أبدًا.
"""
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .database import get_db
from .permissions import check_legacy, effective_permissions, has_permission
from .security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


# مسارات مسموح بها حتى قبل تغيير كلمة المرور الإلزامي
_PRE_CHANGE_ALLOWED = ("/auth/me", "/auth/change-password", "/auth/logout")


def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="بيانات اعتماد غير صالحة",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise cred_exc
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise cred_exc
        user_id = int(payload["sub"])
    except Exception:
        raise cred_exc

    user = db.get(models.User, user_id)
    if not user or not user.is_active:
        raise cred_exc

    # فرض تغيير كلمة المرور الإلزامي على مستوى الخادم (لا الواجهة فقط)
    if user.must_change_password and not request.url.path.endswith(_PRE_CHANGE_ALLOWED):
        raise HTTPException(status_code=403, detail="يجب تغيير كلمة المرور أولًا")

    return user


def get_user_perms(user: models.User, db: Session) -> set[str]:
    """مجموعة الصلاحيات المُسندة صراحةً (غير المنتهية)."""
    from datetime import date

    rows = db.scalars(
        select(models.UserPermission).where(models.UserPermission.user_id == user.id)
    ).all()
    today = date.today()
    assigned = {r.perm_code for r in rows if not (r.expires_at and r.expires_at < today)}
    return assigned


def require_perm(perm: str):
    """مولّد تبعية تتحقق من امتلاك المستخدم صلاحية معيّنة."""

    def checker(
        user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> models.User:
        assigned = get_user_perms(user, db)
        # يمرّ عبر المصفوفة الدقيقة إن كانت الصلاحية مرتبطة بصفحة/فعل
        if not check_legacy(user.role, assigned, perm):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"ليس لديك صلاحية: {perm}",
            )
        return user

    return checker


def require_super_admin(user: models.User = Depends(get_current_user)) -> models.User:
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="هذا الإجراء للإدارة العليا فقط")
    return user


def scope_company_id(user: models.User, requested: int | None = None) -> int | None:
    """يطبّق العزل: غير الإدارة العليا/المالك يُجبَر على company_id الخاص به.

    super_admin / company_owner: يختاران الشركة (requested) أو None = كل الشركات.
    باقي الأدوار: مقيّدون بشركتهم بغضّ النظر عمّا طُلب.
    """
    from .permissions import CROSS_COMPANY_ROLES

    if user.role in CROSS_COMPANY_ROLES:
        return int(requested) if requested else None
    return user.company_id


def get_branch_scope(user: models.User, db: Session) -> set[int] | None:
    """نطاق الفروع المسموح للمستخدم: مجموعة معرّفات أو None (كل الفروع).

    - مسؤول الفرع: الفروع التي يشرف عليها فقط.
    - أي مستخدم له scope_branch_id: ذلك الفرع فقط.
    - غير ذلك: None (لا تقييد على مستوى الفرع).
    """
    if user.role in ("super_admin", "company_owner"):
        return None
    if user.scope_branch_id:
        return {user.scope_branch_id}
    if user.role == "branch_supervisor":
        ids = {bs.branch_id for bs in db.scalars(
            select(models.BranchSupervisor).where(models.BranchSupervisor.user_id == user.id)).all()}
        return ids or {-1}  # لا فروع مُسندة → لا يرى شيئًا
    return None


def assert_same_company(user: models.User, entity_company_id: int | None):
    """يمنع الوصول لكيان خارج نطاق شركة المستخدم (إلا الإدارة العليا والمالك)."""
    from .permissions import CROSS_COMPANY_ROLES

    if user.role in CROSS_COMPANY_ROLES:
        return
    if entity_company_id != user.company_id:
        raise HTTPException(status_code=404, detail="غير موجود")  # 404 لإخفاء الوجود


def audit(db: Session, user: models.User | None, action: str, entity_type: str | None = None,
          entity_id: int | None = None, detail: str | None = None, request: Request | None = None):
    """تسجيل عملية في سجل التدقيق."""
    log = models.AuditLog(
        company_id=user.company_id if user else None,
        user_id=user.id if user else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=detail,
        ip=(request.client.host if request and request.client else None),
    )
    db.add(log)
