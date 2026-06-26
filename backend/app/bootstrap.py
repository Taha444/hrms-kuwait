# -*- coding: utf-8 -*-
"""إقلاع آمن للنشر: ينشئ الجداول، ويُعبّئ البيانات التجريبية *مرة واحدة فقط*
إن كانت القاعدة فارغة — فلا تُمسح البيانات الحقيقية عند كل إعادة نشر.

التشغيل:  python -m app.bootstrap
"""
import sys

from .database import SessionLocal, init_db


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    init_db()  # ينشئ الجداول الناقصة (آمن وقابل للتكرار)
    from . import models

    db = SessionLocal()
    try:
        has_data = db.query(models.User).first() is not None
    finally:
        db.close()

    if has_data:
        print("[bootstrap] القاعدة تحتوي بيانات بالفعل — تخطّي التعبئة (حفاظًا على البيانات).")
        return

    print("[bootstrap] قاعدة فارغة — تعبئة بيانات البداية...")
    from . import seed
    seed.run()


if __name__ == "__main__":
    main()
