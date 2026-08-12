# -*- coding: utf-8 -*-
"""المصادقة: دخول بالرقم المدني، تجديد الرمز، تغيير كلمة المرور، إعادة التعيين."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import audit, get_current_user, get_user_perms, require_perm
from .. import permissions
from ..permissions import effective_permissions
from ..security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from ..config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

MAX_FAILED = 5
LOCK_MINUTES = 15

# تحديد معدّل بسيط في الذاكرة لمنع القوة الغاشمة على الدخول (لكل IP)
_RATE_WINDOW = 60          # ثانية
_RATE_MAX = 10             # محاولات كحدّ أقصى في النافذة
_login_hits: dict[str, list[float]] = {}


def _rate_limit(ip: str):
    import time

    from ..config import settings
    if not settings.rate_limit_enabled:
        return
    now = time.time()
    hits = [t for t in _login_hits.get(ip, []) if now - t < _RATE_WINDOW]
    if len(hits) >= _RATE_MAX:
        raise HTTPException(status_code=429, detail="محاولات كثيرة، انتظر دقيقة ثم أعد المحاولة")
    hits.append(now)
    _login_hits[ip] = hits


def _perm_list(user: models.User, db: Session) -> list[str]:
    return sorted(effective_permissions(user.role, get_user_perms(user, db)))


@router.post("/login", response_model=schemas.TokenOut)
def login(data: schemas.LoginIn, request: Request, db: Session = Depends(get_db)):
    _rate_limit(request.client.host if request.client else "?")
    user = db.scalar(select(models.User).where(models.User.civil_id == data.civil_id))
    now = datetime.now(timezone.utc)
    if not user:
        raise HTTPException(status_code=401, detail="الرقم المدني أو كلمة المرور غير صحيحة")

    if user.locked_until and user.locked_until.replace(tzinfo=timezone.utc) > now:
        raise HTTPException(status_code=423, detail="الحساب مقفل مؤقتًا، حاول لاحقًا")

    if not user.is_active or user.status in ("inactive", "suspended"):
        msg = "الحساب موقوف" if user.status == "suspended" else "الحساب غير مفعّل"
        raise HTTPException(status_code=403, detail=msg)

    if not verify_password(data.password, user.password_hash):
        user.failed_attempts += 1
        if user.failed_attempts >= MAX_FAILED:
            user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
            user.failed_attempts = 0
        db.commit()
        raise HTTPException(status_code=401, detail="الرقم المدني أو كلمة المرور غير صحيحة")

    # V2.2 §9 — لو 2FA مفعّل، يجب تمرير رمز TOTP صحيح لتكتمل الجلسة.
    if user.totp_confirmed and user.totp_secret:
        if not data.totp_code:
            raise HTTPException(
                status_code=401,
                detail={"requires_2fa": True, "message": "أدخل رمز التحقق الثنائي"},
            )
        from .twofa import _verify_code
        if not _verify_code(user.totp_secret, data.totp_code):
            audit(db, user, "totp_login_fail", "user", user.id, request=request)
            db.commit()
            raise HTTPException(status_code=401, detail="رمز التحقق الثنائي غير صحيح")
        user.totp_last_used_at = now
    # SEC-02 — أدوار يُلزَم أصحابها بالتفعيل. لا نمنعهم من الدخول (وإلا تعذّر
    # التفعيل نفسه)، بل نُعلم الواجهة لتوجّههم لصفحة التفعيل قبل أي عمل آخر.
    # ولا يوجد "تذكّر الجهاز": بعد التفعيل يُطلب الرمز في كل دخول (SEC-03) لأن
    # الشرط أعلاه يفحص totp_confirmed في كل مرة بلا استثناء.
    must_enroll_2fa = permissions.requires_2fa(user.role) and not user.totp_confirmed

    user.failed_attempts = 0
    user.locked_until = None
    user.last_login = now
    audit(db, user, "login", "user", user.id, request=request)
    db.commit()

    # R9 §16 — مستخدم متعدد الشركات: نرد قائمة شركاته للـpicker.
    # التوكن يُنشأ بلا active_company_id — بعد الاختيار يُصدَر توكن جديد.
    companies_list: list[dict] | None = None
    if user.is_cross_company:
        links = db.scalars(select(models.UserCompanyLink).where(
            models.UserCompanyLink.user_id == user.id
        )).all()
        companies_list = []
        for lk in links:
            co = db.get(models.Company, lk.company_id)
            if co:
                companies_list.append({"id": co.id, "name": co.name,
                                       "name_en": co.name_en, "role": lk.role})

    return schemas.TokenOut(
        access_token=create_access_token(user.id, user.role, user.company_id),
        refresh_token=create_refresh_token(user.id),
        must_change_password=user.must_change_password,
        role=user.role, full_name=user.full_name, company_id=user.company_id,
        permissions=_perm_list(user, db),
        is_cross_company=user.is_cross_company,
        companies=companies_list,
        must_enroll_2fa=must_enroll_2fa,
    )


@router.get("/my-companies")
def my_companies(user: models.User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    """R9 §16 + P0-#1 — قائمة الشركات المتاحة للمستخدم للاختيار من الـpicker.

    التمييز:
    - is_cross_company (flag, مثل محمد فاروق): فقط الشركات في UserCompanyLink
    - super_admin / company_owner: كل الشركات (portfolio view)
    - غيرهم: شركتهم الواحدة فقط
    """
    if user.is_cross_company:
        links = db.scalars(select(models.UserCompanyLink).where(
            models.UserCompanyLink.user_id == user.id
        )).all()
        out = []
        for lk in links:
            co = db.get(models.Company, lk.company_id)
            if co:
                out.append({"id": co.id, "name": co.name, "name_en": co.name_en,
                          "role": lk.role})
        return {"is_cross_company": True, "kind": "member", "companies": out}
    # super_admin/owner: portfolio كامل — يشوفوا الكل ويختاروا أي
    if user.role in ("super_admin", "company_owner"):
        all_co = db.scalars(select(models.Company)).all()
        return {
            "is_cross_company": True,  # widened concept — يشوف multiple
            "kind": "portfolio",
            "companies": [{"id": c.id, "name": c.name, "name_en": c.name_en,
                          "role": user.role} for c in all_co],
        }
    # مستخدم عادي: شركة واحدة
    if user.company_id:
        co = db.get(models.Company, user.company_id)
        return {"is_cross_company": False, "kind": "single",
                "companies": [{"id": co.id, "name": co.name, "name_en": co.name_en,
                              "role": user.role}] if co else []}
    return {"is_cross_company": False, "kind": "none", "companies": []}


@router.post("/select-company", response_model=schemas.TokenOut)
def select_company(company_id: int, request: Request,
                  user: models.User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """R9 §16 + P0-#1 (unified) — يختار المستخدم شركة يشتغل فيها.

    مدعوم لكل مستخدم يشوف أكثر من شركة:
    - super_admin / company_owner: يقدر يختار أي شركة موجودة (informational).
      لا يقيد نطاق البيانات — لا يزال يقدر يمرّر company_id في queries.
    - is_cross_company flag (مثل محمد فاروق): يقتصر على شركاته المرتبطة
      عبر UserCompanyLink فقط. الاختيار يُطبَّق كـhard filter عبر JWT claim
      في get_current_user (يفرض user.company_id + employee_id لهذا الطلب).

    الرد: token جديد بـactive_company_id claim.
    لغير المصرح لهم بأي شركات متعددة: 400.
    """
    from ..permissions import CROSS_COMPANY_ROLES

    is_admin_cross = user.role in CROSS_COMPANY_ROLES  # super_admin/owner
    is_flag_cross = bool(user.is_cross_company)         # delegate متعدد

    if not (is_admin_cross or is_flag_cross):
        raise HTTPException(status_code=400,
                          detail="هذا الحساب مش متعدد الشركات — لا يحتاج اختيار.")

    # التحقق من الشركة
    company = db.get(models.Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail=f"الشركة #{company_id} غير موجودة")

    # For flag-based cross-company (delegate): must be a member
    if is_flag_cross and not is_admin_cross:
        link = db.scalar(select(models.UserCompanyLink).where(
            models.UserCompanyLink.user_id == user.id,
            models.UserCompanyLink.company_id == company_id,
        ))
        if not link:
            raise HTTPException(status_code=403,
                              detail=f"لست عضوًا في الشركة #{company_id}")

    audit(db, user, "select_company", "user", user.id,
          detail=f"active_company_id={company_id} ({'admin' if is_admin_cross else 'member'})",
          request=request, company_id=company_id)
    db.commit()

    # For admin cross-company (super_admin/owner), company_id in response reflects
    # their selection but user.company_id in DB stays NULL (they can still see all).
    return schemas.TokenOut(
        access_token=create_access_token(user.id, user.role, user.company_id,
                                        active_company_id=company_id),
        refresh_token=create_refresh_token(user.id),
        must_change_password=user.must_change_password,
        role=user.role, full_name=user.full_name,
        company_id=company_id,  # informational — for UI display
        permissions=_perm_list(user, db),
        is_cross_company=True, active_company_id=company_id,
    )


@router.post("/refresh", response_model=schemas.TokenOut)
def refresh(data: schemas.RefreshIn, db: Session = Depends(get_db)):
    try:
        payload = decode_token(data.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError
        user = db.get(models.User, int(payload["sub"]))
    except Exception:
        raise HTTPException(status_code=401, detail="رمز التجديد غير صالح")
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="رمز التجديد غير صالح")
    # R9 §16 — refresh لا يعيد active_company_id — على cross-company user يعيد الاختيار
    # (نتوقع أن التوكن يُستهلك عبر واجهة تسجل تلقائيًا اختيار الشركة الأخير من localStorage).
    return schemas.TokenOut(
        access_token=create_access_token(user.id, user.role, user.company_id),
        refresh_token=create_refresh_token(user.id),
        must_change_password=user.must_change_password,
        role=user.role, full_name=user.full_name, company_id=user.company_id,
        permissions=_perm_list(user, db),
        is_cross_company=user.is_cross_company,
    )


@router.get("/me")
def me(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    from ..permissions import can_submit_on_behalf, is_cross_company_user, requires_2fa
    return {
        "id": user.id, "civil_id": user.civil_id, "full_name": user.full_name,
        "role": user.role, "company_id": user.company_id, "email": user.email,
        "must_change_password": user.must_change_password,
        "employee_id": user.employee_id,
        # is_cross_company: مفهوم موسّع "يشوف شركات متعددة" — يشمل super_admin/owner
        # (متوافق مع كود سابق يعتمد عليه لعرض CompanyPicker للـsuper_admin).
        "is_cross_company": is_cross_company_user(user),
        # R9 §16 — needs_company_selection: التمييز الحقيقي — يدل هل المستخدم
        # يحتاج شاشة /select-company المخصّصة (JWT-based picker) أم لا.
        # True فقط للـflag الفعلي، False لـsuper_admin/owner (اللي عندهم CompanyPicker).
        "needs_company_selection": bool(user.is_cross_company),
        # هل يظهر له اختيار "تقديم نيابةً عن"؟ يأتي من الخادم لا باستنتاج الواجهة:
        # كانت تستنتجه من view_employee، فظهر للمحاسب بقائمة تضم المدير العام وHR
        # بينما الخادم يقصره على HR — قائمتان لقاعدة واحدة.
        "can_submit_on_behalf": can_submit_on_behalf(user.role),
        # SEC-02/04 — حالة التحقق الثنائي ومهلة الخمول: تأتيان من الخادم فلا
        # تُكرَّر القاعدة ولا الرقم في الواجهة
        "twofa_required": requires_2fa(user.role),
        "twofa_enabled": bool(user.totp_confirmed),
        "idle_logout_minutes": settings.idle_logout_minutes,
        # R9 §17 — bool للـavatar (يُستخدم في UI لعرض الصورة بدل الأيقونة)
        "has_avatar": bool(user.avatar_path),
        "avatar_updated_at": (user.avatar_updated_at.isoformat()
                             if user.avatar_updated_at else None),
        "permissions": _perm_list(user, db),
    }


@router.post("/change-password")
def change_password(data: schemas.ChangePasswordIn, request: Request,
                    user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(data.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="كلمة المرور الحالية غير صحيحة")
    user.password_hash = hash_password(data.new_password)
    user.must_change_password = False
    # V2.2 §9 — إبطال كل الجلسات السابقة (بما فيها الحالية) بعد تغيير كلمة المرور
    user.tokens_valid_after = datetime.now(timezone.utc)
    audit(db, user, "change_password", "user", user.id, request=request)
    db.commit()
    return {"ok": True, "message": "تم تغيير كلمة المرور بنجاح — سيلزمك تسجيل الدخول مجددًا"}


@router.post("/reset-password")
def reset_password(data: schemas.ResetPasswordIn, request: Request,
                   actor: models.User = Depends(require_perm("manage_users")),
                   db: Session = Depends(get_db)):
    from ..permissions import CROSS_COMPANY_ROLES, can_manage_role

    target = db.get(models.User, data.user_id)
    if not target:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    # العزل + التسلسل الهرمي
    if actor.role not in CROSS_COMPANY_ROLES and target.company_id != actor.company_id:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    if actor.id != target.id and not can_manage_role(actor.role, target.role):
        raise HTTPException(status_code=403, detail="لا يمكنك إدارة مستخدم بهذا المستوى")
    new_pw = data.new_password or settings.default_user_password
    target.password_hash = hash_password(new_pw)
    target.must_change_password = True
    target.failed_attempts = 0
    target.locked_until = None
    # V2.2 §9 — إبطال جلسات المستخدم الحالية عند إعادة تعيين كلمة المرور
    target.tokens_valid_after = datetime.now(timezone.utc)
    audit(db, actor, "reset_password", "user", target.id, request=request, company_id=target.company_id)
    db.commit()
    return {"ok": True, "message": "تمت إعادة تعيين كلمة المرور", "temporary_password": new_pw}
