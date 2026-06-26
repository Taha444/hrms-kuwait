# -*- coding: utf-8 -*-
"""
نقطة دخول الإنتاج عبر waitress (بديل خادم تطوير Flask).
التشغيل:  python wsgi.py    أو    waitress-serve --call wsgi:get_app
"""
from app import create_app
from config import config

application = create_app()


def get_app():
    return application


if __name__ == "__main__":
    from waitress import serve
    print(f">> waitress يعمل على {config.HOST}:{config.PORT}")
    serve(application, host=config.HOST, port=config.PORT)
