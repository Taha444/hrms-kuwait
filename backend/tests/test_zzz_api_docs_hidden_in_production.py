# -*- coding: utf-8 -*-
"""توثيُق الـAPI لا يُخدَم علنًا في الإنتاج.

قيس على الإنتاج: ``/docs`` (Swagger) و``/openapi.json`` يردّان 200 بلا دخول
— المخطُط الكامل لكل نقطٍة وحقولها لأيّ زائر. ليس ثغرًة بذاته (النقاط
محروسة) لكنه خريطٌة جاهزة لمن يبحث عن واحدٍة غير محروسة. فيُطفأ في الإنتاج،
ويُعاد عند الحاجة بـ``ENABLE_API_DOCS=1``.
"""
from __future__ import annotations


def test_production_serves_no_api_docs_unless_enabled():
    from app.main import api_docs_kwargs

    off = {"docs_url": None, "redoc_url": None, "openapi_url": None}
    assert api_docs_kwargs(production=True, flag="") == off
    assert api_docs_kwargs(production=True, flag="0") == off
    assert api_docs_kwargs(production=True, flag="1") == {}
    assert api_docs_kwargs(production=False, flag="") == {}


def test_the_running_app_follows_it():
    from app.config import settings
    from app.main import app

    if settings.is_production:
        assert app.openapi_url is None
    else:
        assert app.openapi_url == "/openapi.json"
