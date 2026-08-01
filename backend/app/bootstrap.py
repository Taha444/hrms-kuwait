# -*- coding: utf-8 -*-
"""إقلاع آمن للنشر: ينشئ الجداول ويُعبّئ البيانات الأولية مرة واحدة فقط.

منطق التعبئة:
- إن كانت القاعدة تحوي بيانات → لا شيء (حفاظًا على البيانات الحقيقية)
- إن كانت فارغة وفي بيئة تطوير (SQLite) → seed تجريبي كامل بشركات
- إن كانت فارغة وفي بيئة إنتاجية → super_admin فقط + owner + رسالة إرشادية
  (seed التجريبي محظور بلا ALLOW_DEMO_SEED=true — راجع seed.py)

التشغيل:  python -m app.bootstrap
"""
import os
import sys

from .database import SessionLocal, init_db


def _minimal_production_seed(db) -> None:
    """V2.2 §9 — في الإنتاج: ينشئ super_admin و owner فقط مع كلمات سر عشوائية
    قوية تُطبع مرة واحدة. لا يُنشئ شركات/فروع/موظفين تجريبيين.
    """
    import secrets
    import string
    from . import models
    from .security import hash_password

    def _strong_pw() -> str:
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        return "".join(secrets.choice(chars) for _ in range(16))

    admin_pw = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD") or _strong_pw()
    owner_pw = os.environ.get("BOOTSTRAP_OWNER_PASSWORD") or _strong_pw()
    admin_civil = os.environ.get("BOOTSTRAP_ADMIN_CIVIL_ID", "000000000000")
    owner_civil = os.environ.get("BOOTSTRAP_OWNER_CIVIL_ID", "111111111111")

    db.add(models.User(
        civil_id=admin_civil, password_hash=hash_password(admin_pw),
        full_name="Super Admin", role="super_admin",
        must_change_password=True,
    ))
    db.add(models.User(
        civil_id=owner_civil, password_hash=hash_password(owner_pw),
        full_name="Company Owner", role="company_owner",
        must_change_password=True,
    ))
    db.commit()

    print("=" * 68)
    print("[bootstrap] تم إنشاء الحسابات الأولية (بيئة إنتاجية):")
    print(f"  Super Admin : {admin_civil} / {admin_pw}")
    print(f"  Owner       : {owner_civil} / {owner_pw}")
    print("=" * 68)
    print("⚠ سجّل كلمات السر الآن — لن تُطبع مرة أخرى. غيّرها فور أول دخول.")
    print("  بدلًا من ذلك: اضبط BOOTSTRAP_ADMIN_PASSWORD/OWNER_PASSWORD كـenv vars")
    print("=" * 68)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    init_db()  # ينشئ الجداول الناقصة (آمن وقابل للتكرار)
    from . import models
    from .config import settings

    db = SessionLocal()
    try:
        has_data = db.query(models.User).first() is not None
    finally:
        db.close()

    if has_data:
        print("[bootstrap] القاعدة تحتوي بيانات بالفعل — تخطّي التعبئة (حفاظًا على البيانات).")
        return

    is_prod = settings.is_production
    allow_demo = os.environ.get("ALLOW_DEMO_SEED", "").lower() in ("1", "true", "yes")

    if is_prod and not allow_demo:
        print("[bootstrap] بيئة إنتاجية — تعبئة الحد الأدنى (Super Admin + Owner فقط).")
        print("[bootstrap] للـseed التجريبي الكامل: اضبط ALLOW_DEMO_SEED=true.")
        db = SessionLocal()
        try:
            _minimal_production_seed(db)
        finally:
            db.close()
        return

    print("[bootstrap] قاعدة فارغة — تعبئة بيانات البداية (seed كامل)...")
    from . import seed
    seed.run()


if __name__ == "__main__":
    main()
