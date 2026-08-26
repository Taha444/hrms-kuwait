# -*- coding: utf-8 -*-
"""DLV-28/29/31 (ACCESS-10) — لا حساب بذرة يعمل على بيئة تسليم.

ROOT CAUSE: المنع القائم يغطّي **تشغيل** البذر (``ALLOW_DEMO_SEED``) لا **وجود**
حسابها. فقاعدة بُذرت مرة على staging ثم رُقّيت إلى الإنتاج، أو بيئة شُغّل عليها
البذر بتصريح مؤقّت ونُسي — تبقى فيها حسابات بكلمات مرور منشورة في المستودع،
وأخطرها ``super_admin`` مشترك.

الفحص هنا يسأل السؤال الصحيح: **هل تعمل كلمة مرور بذرة على هذه القاعدة الآن؟**
لا "هل شُغّل البذر؟" — الأول واقع يُقاس، والثاني تاريخ لا أحد يتذكّره.

السلوك عند الاكتشاف في الإنتاج: **رفض الإقلاع**. تعطيل الحساب صامًتا يترك
مشرًفا يظنّ أن له وصوًلا وهو لا يملكه؛ والاكتفاء بتحذير في سجل لا يقرأه أحد
يعني تسليم نظام ببابٍ مفتوح. الرفض يجعل الخطأ مستحيل التجاهل.

يُعطَّل عمًدا بـ``ALLOW_SEED_ACCOUNTS=true`` لبيئة عرض واعية بما تفعل.
"""
import logging
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .security import verify_password

log = logging.getLogger("hrms.seed_guard")

#: سقف المستخدمين المفحوصين عند الإقلاع — انظر find_seed_accounts
BOOT_SCAN_LIMIT = 25

# كلمات مرور البذرة كما هي في seed.py — تُقرأ منه لا تُكرَّر هنا، فلا تنحرف
# القائمتان حين تتغيّر واحدة.
def _seed_passwords() -> set[str]:
    from .seed import PW

    # "Kuwait@2024" كانت الافتراضية الموحّدة قبل إلغائها — قاعدة أُنشئت
    # قبل ذلك قد تحمل حسابات ما زالت تقبلها.
    return {*PW.values(), "admin123", "owner123", "Kuwait@2024"}


def find_seed_accounts(db: Session, privileged_only: bool = False,
                       max_users: int | None = None) -> list[dict]:
    """الحسابات التي ما زالت تقبل كلمة مرور بذرة.

    **تكلفة الفحص مقصودة ولا مفرّ منها.** التجزئة PBKDF2 بـ240 ألف دورة والملح
    فريد لكل كلمة، فلا سبيل لمعرفة أن كلمة بذرة تفتح حساًبا إلا بتجريبها فعًلا:
    ~64 ميلي ثانية للمحاولة، و~0.6 ثانية للمستخدم الواحد عبر كل الكلمات. على
    قاعدة بخمسمئة موظف يعني ذلك خمس دقائق **في كل إقلاع**، وعلى قاعدة نظيفة
    أيًضا — فالنظافة لا تُعرف إلا بعد فحص الجميع. أي أن الفحص نفسه يصير سبب
    انهيار الإقلاع بمهلة المنصّة، لا الحسابات التي يبحث عنها.

    ولذلك يُضيَّق عند الإقلاع بحدّين:

    - ``privileged_only``: الأدوار التي يهمّ اختراقها. حساب مالك أو مدير بكلمة
      منشورة في المستودع يفتح النظام كلّه؛ وحساب موظف يفتح ملفه هو. الأول
      يستحقّ فحًصا في كل إقلاع، والثاني يكفيه المسح الشامل عند التسليم.
    - ``max_users``: سقف مطلق يحمي من قاعدة بمئات الإداريين.

    والمعالجة (``remediate_seed_accounts``) تفحص **بلا حدود** وتعالج الجميع.
    """
    candidates = _seed_passwords()
    #: الأدوار التي يفتح اختراقها أكثر من ملف صاحبها، مرتّبة بالخطورة
    PRIVILEGED = ("super_admin", "company_owner", "company_manager", "hr",
                  "accountant", "delegate", "branch_supervisor")
    order = {r: i for i, r in enumerate(PRIVILEGED)}

    q = select(models.User).where(models.User.is_active == True)  # noqa: E712
    if privileged_only:
        q = q.where(models.User.role.in_(PRIVILEGED))
    users = sorted(db.scalars(q).all(), key=lambda u: order.get(u.role, 99))
    if max_users:
        users = users[:max_users]

    hits = []
    for user in users:
        if not user.password_hash:
            continue
        for pw in candidates:
            if verify_password(pw, user.password_hash):
                hits.append({"id": user.id, "civil_id": user.civil_id,
                             "role": user.role, "name": user.full_name})
                break
    return hits


def _neutralize(db: Session, hits: list[dict]) -> None:
    """يُبطل كلمات البذرة فوًرا: كلمة عشوائية لا يعرفها أحد + إبطال الجلسات.

    الحساب يبقى **فعّاًلا** — لا نعطّله. التعطيل يمنع صاحبه من استعادته بنفسه
    ويحتاج تدخّل من يملك القاعدة؛ أما كلمة عشوائية مع ``must_change_password``
    فتغلق الباب وتترك المسار الطبيعي للاستعادة مفتوًحا.
    """
    from datetime import datetime, timezone

    from .security import generate_temp_password, hash_password

    now = datetime.now(timezone.utc)
    for h in hits:
        user = db.get(models.User, h["id"])
        if not user:
            continue
        user.password_hash = hash_password(generate_temp_password())
        user.must_change_password = True
        user.failed_attempts = 0
        user.locked_until = None
        user.tokens_valid_after = now  # من دخل بالكلمة المنشورة يخرج الآن
    db.commit()


def _raise_alarm(db: Session, hits: list[dict]) -> None:
    """مهمة حرجة لكل super_admin — الإبطال الصامت أسوأ من عدمه.

    من لا يقرأ سجلّ الإقلاع يجب أن يرى في صندوق مهامه لماذا لم تعد كلمة
    مروره تعمل. بلا هذا يبدو الإبطال عطًلا غامًضا.
    """
    try:
        from sqlalchemy import select as _select

        from .notifications import create_task

        summary = "، ".join(f"{h['civil_id']} ({h['role']})" for h in hits)
        admins = db.scalars(_select(models.User).where(
            models.User.role == "super_admin",
            models.User.is_active == True)).all()  # noqa: E712
        for admin in admins:
            create_task(
                db, company_id=admin.company_id, type="security",
                assignee_user_id=admin.id, severity="critical",
                title=f"أُبطلت {len(hits)} كلمة مرور بذرة على بيئة منشورة",
                detail=("حسابات كانت تقبل كلمات مرور منشورة في المستودع: "
                        f"{summary}. أُبطلت تلقائًيا وتحتاج كلمات جديدة — "
                        "شغّل: python -m app.remediate_seed_accounts --user <رقم> --apply. "
                        "وفحص الإقلاع يغطّي الأدوار الإدارية وحدها لأن تجريب "
                        "كل كلمة على كل مستخدم مكلف؛ شغّل المسح الشامل قبل "
                        "التسليم: python -m app.remediate_seed_accounts --apply"),
                dedup_key=f"seed_neutralized:{now_key(hits)}",
            )
        db.commit()
    except Exception:  # noqa: BLE001 — فشل التنبيه لا يُعيد فتح الباب
        log.exception("تعذّر إنشاء مهمة التنبيه بعد إبطال كلمات البذرة")


def now_key(hits: list[dict]) -> str:
    from datetime import date
    return f"{date.today().isoformat()}:{len(hits)}"


def enforce(db: Session) -> list[dict]:
    """يفحص، ويُبطل كلمات البذرة على بيئة منشورة. يعيد ما وُجد.

    **لماذا لا يمنع الإقلاع بعد الآن.** كان يرفع RuntimeError فيموت الإقلاع.
    بدا ذلك صواًبا: خطأ مستحيل التجاهل. لكن التشغيل الفعلي على منصّة استضافة
    كشف عكسه — النشر يدخل حلقة انهيار، والمخرج الوحيد أمام المشغّل أن يضبط
    ``ALLOW_SEED_ACCOUNTS=true`` **ويتركها**. فينتهي الحارس إلى إنتاج الباب
    المفتوح الذي بُني ليمنعه، وهذه هزيمة ذاتية لا صرامة.

    السلوك الآن: **يُبطل الخطر بنفسه** — كلمة عشوائية لا يعرفها أحد وإبطال
    الجلسات — ثم يُنبّه بصوت عالٍ ويترك النظام يقلع. الباب يُغلق فوًرا وبلا
    اعتماد على أن يقرأ أحد سجًلا أو يلاحظ انهياًرا.

    ``SEED_GUARD_MODE=block`` يعيد المنع لمن يريده صراحًة.
    """
    from .config import settings

    # حدّ عند الإقلاع: الغاية معرفة أن البيئة ملوّثة، وقد عُرفت بأول مصاب.
    # المعالجة (remediate_seed_accounts) تفحص بلا حدّ وتعالج الكلّ.
    hits = find_seed_accounts(db, privileged_only=True, max_users=BOOT_SCAN_LIMIT)
    if not hits:
        return []

    summary = "، ".join(f"{h['civil_id']} ({h['role']})" for h in hits)
    allowed = os.environ.get("ALLOW_SEED_ACCOUNTS", "").lower() in ("1", "true", "yes")

    if allowed or not settings.is_production:
        log.warning("حسابات بكلمات مرور بذرة: %s", summary)
        return hits

    if os.environ.get("SEED_GUARD_MODE", "").lower() == "block":
        raise RuntimeError(
            "رفض الإقلاع: حسابات ما زالت تقبل كلمات مرور البذرة على بيئة إنتاجية — "
            f"{summary}. غيّر كلمات مرورها أو عطّلها، أو اضبط ALLOW_SEED_ACCOUNTS=true "
            "إن كانت بيئة عرض واعية بذلك."
        )

    log.error("أُبطلت كلمات مرور بذرة على بيئة منشورة: %s — تحتاج كلمات جديدة "
              "(python -m app.remediate_seed_accounts --user <رقم> --apply)", summary)
    _neutralize(db, hits)
    _raise_alarm(db, hits)
    return hits
