# -*- coding: utf-8 -*-
"""معالجة حسابات كلمات مرور البذرة على بيئة منشورة.

يوقف ``seed_guard`` الإقلاع حين يجد حساًبا ما زال يقبل كلمة مرور بذرة على
بيئة إنتاجية. وهذا صواب: البيئة على رابط عامّ، وكلمات البذرة مكتوبة في
``seed.py`` داخل المستودع — فمن يقرأ الكود يدخل بالحساب.

**الحلّ ليس تعطيل الحارس.** تعطيله يترك الباب مفتوًحا ويُسكت الإنذار وحده.
الحلّ تدوير كلمات المرور، وهو ما تفعله هذه الأداة.

التشغيل:

    python -m app.remediate_seed_accounts              # فحص فقط — لا يغيّر شيًئا
    python -m app.remediate_seed_accounts --apply      # يدوّر كلمات المرور
    python -m app.remediate_seed_accounts --apply --deactivate-qa

كلمة المرور الجديدة تُطبع **مرة واحدة** في مخرجات هذا الأمر. لا تُحفظ في أي
سجل ولا تُرسَل في أي قناة، وتُطلب من صاحبها بتغييرها عند أول دخول
(``must_change_password``). سلّمها لصاحب الحساب مباشرة.
"""
from __future__ import annotations

import sys

from sqlalchemy import select

from . import models, seed_guard
from .database import SessionLocal
from .security import generate_temp_password, hash_password

#: حسابات الاختبار المتروكة. بادئة QA ليست اصطلاًحا عابًرا: هذه حسابات أُنشئت
#: أثناء ضبط الجودة ولا مكان لها على بيئة يراها العميل — وأحدها كان من بين
#: من يقبلون كلمة بذرة.
QA_PREFIX = "QA"


def _rotate(db, user) -> str:
    pw = generate_temp_password()
    user.password_hash = hash_password(pw)
    user.must_change_password = True
    user.failed_attempts = 0
    user.locked_until = None
    # إبطال الجلسات القائمة: من دخل بالكلمة القديمة يخرج فوًرا
    from datetime import datetime, timezone
    user.tokens_valid_after = datetime.now(timezone.utc)
    return pw


def main() -> int:
    apply_changes = "--apply" in sys.argv
    deactivate_qa = "--deactivate-qa" in sys.argv

    db = SessionLocal()
    try:
        hits = seed_guard.find_seed_accounts(db)
        if not hits:
            print("✔ لا حساب يقبل كلمة مرور بذرة — لا شيء للمعالجة.")
            return 0

        print(f"وُجد {len(hits)} حساب يقبل كلمة مرور بذرة:")
        for h in hits:
            print(f"  · {h['civil_id']}  ({h['role']})  {h['name'] or ''}")
        print()

        if not apply_changes:
            print("فحص فقط — لم يتغيّر شيء.")
            print("أعد التشغيل مع --apply لتدوير كلمات المرور.")
            return 0

        print("=" * 62)
        print(" كلمات المرور الجديدة — تُعرض مرة واحدة، سلّمها لأصحابها مباشرة")
        print("=" * 62)
        rotated = 0
        for h in hits:
            user = db.get(models.User, h["id"])
            if not user:
                continue
            pw = _rotate(db, user)
            print(f"  {user.civil_id:<16}{user.role:<18}{pw}")
            rotated += 1
        print("=" * 62)

        deactivated = 0
        if deactivate_qa:
            qa_users = db.scalars(select(models.User).where(
                models.User.civil_id.like(f"{QA_PREFIX}%"),
                models.User.is_active == True,  # noqa: E712
            )).all()
            for u in qa_users:
                u.is_active = False
                deactivated += 1
            if deactivated:
                print(f"\nعُطِّل {deactivated} حساب اختبار (بادئة {QA_PREFIX}).")

        db.commit()
        print(f"\n✔ دُوِّرت {rotated} كلمة مرور. كلٌّ منها مختلفة، ويُطلب تغييرها عند أول دخول.")
        print("  الجلسات القائمة بالكلمات القديمة أُبطلت.")
        print("\nأعد النشر الآن — سيمرّ الحارس.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
