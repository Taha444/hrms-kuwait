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

# كلمات مرور البذرة كما هي في seed.py — تُقرأ منه لا تُكرَّر هنا، فلا تنحرف
# القائمتان حين تتغيّر واحدة.
def _seed_passwords() -> set[str]:
    from .seed import PW

    # "Kuwait@2024" كانت الافتراضية الموحّدة قبل إلغائها — قاعدة أُنشئت
    # قبل ذلك قد تحمل حسابات ما زالت تقبلها.
    return {*PW.values(), "admin123", "owner123", "Kuwait@2024"}


def find_seed_accounts(db: Session) -> list[dict]:
    """الحسابات التي ما زالت تقبل كلمة مرور بذرة."""
    candidates = _seed_passwords()
    hits = []
    for user in db.scalars(select(models.User).where(models.User.is_active == True)):  # noqa: E712
        if not user.password_hash:
            continue
        for pw in candidates:
            if verify_password(pw, user.password_hash):
                hits.append({"id": user.id, "civil_id": user.civil_id,
                             "role": user.role, "name": user.full_name})
                break
    return hits


def enforce(db: Session) -> list[dict]:
    """يفحص، ويرفض الإقلاع في الإنتاج إن وُجد حساب بذرة فعّال.

    يعيد القائمة (فارغة = نظيف) ليستخدمها فحص الصحة أيًضا.
    """
    from .config import settings

    hits = find_seed_accounts(db)
    if not hits:
        return []

    # لا تُطبع كلمات المرور ولا تُسجَّل — الرقم المدني والدور يكفيان للتصحيح
    summary = "، ".join(f"{h['civil_id']} ({h['role']})" for h in hits)
    allowed = os.environ.get("ALLOW_SEED_ACCOUNTS", "").lower() in ("1", "true", "yes")

    if settings.is_production and not allowed:
        raise RuntimeError(
            "رفض الإقلاع: حسابات ما زالت تقبل كلمات مرور البذرة على بيئة إنتاجية — "
            f"{summary}. غيّر كلمات مرورها أو عطّلها، أو اضبط ALLOW_SEED_ACCOUNTS=true "
            "إن كانت بيئة عرض واعية بذلك."
        )
    log.warning("حسابات بكلمات مرور بذرة: %s", summary)
    return hits
