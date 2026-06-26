# -*- coding: utf-8 -*-
"""
نسخ احتياطي / استعادة لقاعدة بيانات SQLite باستخدام واجهة backup الآمنة
(تعمل أثناء تشغيل النظام). الاستخدام:
    python backup.py            # إنشاء نسخة احتياطية مؤرّخة
    python backup.py restore <ملف>   # استعادة من نسخة
"""
import os
import sqlite3
import sys
from datetime import datetime

import db
from config import config


def backup():
    os.makedirs(config.BACKUP_DIR, exist_ok=True)
    if not os.path.exists(db.DB_PATH):
        print("لا توجد قاعدة بيانات للنسخ.")
        return None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(config.BACKUP_DIR, f"hrms_{stamp}.db")
    src = sqlite3.connect(db.DB_PATH)
    dst = sqlite3.connect(dest)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    print(f"تم إنشاء نسخة احتياطية: {dest}")
    return dest


def restore(path):
    if not os.path.exists(path):
        print("ملف النسخة غير موجود:", path)
        return
    src = sqlite3.connect(path)
    dst = sqlite3.connect(db.DB_PATH)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    print("تمت الاستعادة بنجاح إلى:", db.DB_PATH)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "restore":
        restore(sys.argv[2])
    else:
        backup()
