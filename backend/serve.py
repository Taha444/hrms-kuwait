# -*- coding: utf-8 -*-
"""مشغّل ذكي: يختار منفذًا متاحًا تلقائيًا ويشغّل الخادم (الواجهة + الـ API معًا).

يحلّ مشكلة WinError 10013 (منافذ محجوزة من Hyper-V/WSL/Docker على ويندوز):
يجرّب عدة منافذ شائعة، وإن فشلت كلها يطلب من نظام التشغيل منفذًا حرًّا.

التشغيل:  python serve.py
ثم افتح الرابط المطبوع في المتصفح. لا حاجة لبروكسي أو خادم ثانٍ.
"""
import socket
import sys

import uvicorn

CANDIDATE_PORTS = [8001, 5180, 3500, 6500, 8888, 9090, 8123, 7123, 4321]


def _bindable(port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def pick_port() -> int:
    # منفذ يطلبه المستخدم صراحةً: python serve.py 9000
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        return int(sys.argv[1])
    for p in CANDIDATE_PORTS:
        if _bindable(p):
            return p
    # احتياطي: دع نظام التشغيل يختار منفذًا حرًّا مضمونًا
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _upgrade_schema() -> None:
    """يشغّل alembic upgrade head قبل تشغيل الخادم — يضمن أن الـDB المحلي متزامن
    مع الـmodels بعد أي pull جديد. لو Alembic غير متاح أو DB جديد، يتخطى بأمان.
    """
    try:
        from alembic import command
        from alembic.config import Config
        import os
        cfg = Config(os.path.join(os.path.dirname(__file__), "alembic.ini"))
        command.upgrade(cfg, "head")
        print("✓ alembic upgrade head — DB متزامن")
    except Exception as e:
        print(f"⚠ فشل تحديث DB (سيتم المتابعة): {e}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    _upgrade_schema()
    port = pick_port()
    url = f"http://127.0.0.1:{port}"
    print("=" * 60)
    print(f"  النظام يعمل الآن — افتح هذا الرابط في المتصفح:")
    print(f"     {url}")
    print(f"  توثيق الـ API: {url}/docs")
    print("=" * 60)
    uvicorn.run("app.main:app", host="127.0.0.1", port=port)
