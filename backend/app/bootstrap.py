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
        # R9 §15 — كفالة catalog الافتراضي (request types + templates) في كل startup
        _ensure_catalog()
        # R9 §14 — auto-link pass دائم: يفحص كل حساب unlinked ويربطه بموظف مطابق
        _run_auto_link()
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
    # حتى بعد الـseed، شغّل auto-link (في التطوير الـseed بيربط بالفعل، بس آمن لو أي فرق)
    _run_auto_link()


def _ensure_catalog() -> None:
    """R9 §15 — يكفل وجود 53 request type + 42 قالب في DB (safety net فوق الـmigration).
    idempotent — لو الـmigration اشتغل، لن يُضاف شيء."""
    try:
        from .catalog_seed import ensure_default_catalog
        db = SessionLocal()
        try:
            report = ensure_default_catalog(db)
        finally:
            db.close()
    except Exception as e:  # pragma: no cover
        print(f"[bootstrap] ensure_catalog فشل: {e} — نستمر.")
        return

    if report["request_types_added"] or report["templates_added"]:
        print(f"[bootstrap] ✓ catalog seeded: +{report['request_types_added']} request types, "
              f"+{report['templates_added']} templates")
    print(f"[bootstrap]   catalog totals: {report['request_types_total']} request types, "
          f"{report['templates_total']} templates")


def _run_auto_link() -> None:
    """R9 §14 — atomic pass يربط كل user unlinked بموظف مطابق (idempotent).
    يطبع تقرير مختصر. أي فشل لا يوقف الـstartup."""
    try:
        from .user_employee_link import auto_link_users_to_employees
        db = SessionLocal()
        try:
            report = auto_link_users_to_employees(db)
        finally:
            db.close()
    except Exception as e:  # pragma: no cover
        print(f"[bootstrap] auto-link فشل: {e} — نستمر.")
        return

    if report["linked"]:
        print(f"[bootstrap] ✓ auto-linked {len(report['linked'])} user↔employee pairs")
        for row in report["linked"][:8]:
            print(f"  · {row['role']} {row['name']} (civil_id={row['civil_id']}) → emp #{row['employee_id']}")
        if len(report["linked"]) > 8:
            print(f"  ... و{len(report['linked']) - 8} آخرين")
    if report["no_employee"]:
        print(f"[bootstrap] ⚠ {len(report['no_employee'])} حساب بدون employee مطابق (يحتاج إنشاء يدوي):")
        for row in report["no_employee"][:5]:
            print(f"  · {row['role']} {row['name']} (civil_id={row['civil_id']})")
    if report["conflicts"]:
        print(f"[bootstrap] ⚠ {len(report['conflicts'])} تعارض (الموظف مربوط بحساب آخر):")
        for row in report["conflicts"][:5]:
            print(f"  · user #{row['user_id']} تعارض مع user #{row['other_user_id']}")

    # DLV-28/29/31 (ACCESS-10) — آخر ما يُفحص قبل اعتبار الإقلاع ناجًحا.
    # المنع القائم يغطّي تشغيل البذر لا وجود حسابها: قاعدة بُذرت على staging
    # ثم رُقّيت للإنتاج تبقى فيها كلمات مرور منشورة في المستودع.
    from . import seed_guard
    db = SessionLocal()
    try:
        hits = seed_guard.enforce(db)
        if hits:
            print(f"[bootstrap] ⚠ {len(hits)} حساب بكلمة مرور بذرة — غيّرها قبل التسليم")
    finally:
        db.close()


if __name__ == "__main__":
    main()
