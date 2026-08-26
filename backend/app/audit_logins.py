# -*- coding: utf-8 -*-
"""تقرير عمليات الدخول — للتحقّق ممّا حدث قبل إغلاق ثغرة.

حين يتبيّن أن حساًبا كان يقبل كلمة مرور معروفة لمدة، لا يكفي إغلاق الباب:
يبقى السؤال **هل دخل أحد قبل إغلاقه؟** والجواب في سجل التدقيق وحده — لا في
الذاكرة ولا في التخمين.

الأداة تعرض عمليات الدخول مجمَّعة بعنوان الشبكة، لأن **النمط هو الدليل**:
دخول واحد من عنوان لم يظهر قبله ولا بعده أوضح دلالة من مئة دخول من عنوان
معتاد. ولا تحكم الأداة بنفسها: تعرض وتترك الحكم لمن يعرف أين كان.

    python -m app.audit_logins                      # آخر 30 يوًما، كل الحسابات
    python -m app.audit_logins --user 260092101255  # حساب بعينه
    python -m app.audit_logins --days 60
    python -m app.audit_logins --failed             # المحاولات الفاشلة أيًضا
"""
from __future__ import annotations

import sys
from collections import defaultdict
from datetime import timedelta

from sqlalchemy import select

from . import models
from .clock import now as kuwait_now
from .database import SessionLocal


def _arg(name: str, default=None):
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def main() -> int:
    days = int(_arg("--days", "30"))
    target = _arg("--user")
    show_failed = "--failed" in sys.argv

    since = kuwait_now() - timedelta(days=days)
    db = SessionLocal()
    try:
        actions = ["login"]
        if show_failed:
            actions += ["login_failed", "login_locked"]

        q = select(models.AuditLog).where(
            models.AuditLog.action.in_(actions),
            models.AuditLog.created_at >= since.replace(tzinfo=None),
        ).order_by(models.AuditLog.created_at)

        rows = db.scalars(q).all()
        users = {}

        def _who(uid):
            if uid not in users:
                u = db.get(models.User, uid) if uid else None
                users[uid] = u
            return users[uid]

        if target:
            rows = [r for r in rows
                    if (_who(r.user_id) and _who(r.user_id).civil_id == target)]

        if not rows:
            print(f"لا عمليات دخول مسجَّلة خلال {days} يوًما"
                  + (f" للحساب {target}" if target else "") + ".")
            return 0

        # التجميع بالعنوان: النمط هو الدليل لا العدد
        by_ip: dict[str, list] = defaultdict(list)
        for r in rows:
            by_ip[r.ip or "—"].append(r)

        print(f"عمليات الدخول خلال {days} يوًما — {len(rows)} عملية من "
              f"{len(by_ip)} عنوان\n")
        print(f"{'العنوان':<20}{'مرات':>6}  {'أول مرة':<17}{'آخر مرة':<17}الحسابات")
        print("─" * 96)

        for ip, items in sorted(by_ip.items(), key=lambda kv: len(kv[1]), reverse=True):
            names = sorted({
                f"{u.civil_id}({u.role})"
                for u in (_who(x.user_id) for x in items) if u
            })
            first = items[0].created_at.strftime("%Y-%m-%d %H:%M")
            last = items[-1].created_at.strftime("%Y-%m-%d %H:%M")
            flag = "  ← عنوان بعملية واحدة" if len(items) == 1 else ""
            print(f"{ip:<20}{len(items):>6}  {first:<17}{last:<17}"
                  f"{'، '.join(names)[:40]}{flag}")

        print("\nما تبحث عنه: عنوان لا تعرفه، أو دخول في وقت لم تكن تعمل فيه،")
        print("أو حساب دخل من عنوانين متباعدين في وقت متقارب.")

        if target:
            print(f"\nتفصيل الحساب {target}:")
            for r in rows[-25:]:
                ua = (r.user_agent or "—")[:52]
                print(f"  {r.created_at:%Y-%m-%d %H:%M}  {r.ip or '—':<16}{ua}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
