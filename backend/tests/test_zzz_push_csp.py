# -*- coding: utf-8 -*-
"""سياسة أمن المحتوى تسمح للإشعارات الفورية بالعمل.

**العطل المقيس على الإنتاج**: يضغط المستخدم «فعّل على هذا الجهاز»
فيظهر:

    Failed to register a ServiceWorker … ServiceWorker script evaluation failed

والسبب أن ``script-src 'self'`` تحجب ``importScripts`` من ``gstatic``
داخل عامل الخدمة، فيُرمى استثناء ويفشل تقييم العامل. والرسالة تقول
«فشل التقييم» ولا تقول لماذا — فيبدو الدفع معطًَّلا بلا سبب.

**وعطٌل ثانٍ خلف الأول**: لو سُمح بالاستيراد وحده لنجح تحميل المكتبة ثم
فشل ``getToken`` — لأنه يُسجّل الجهاز لدى Firebase عبر مصدرين آخرين
تحجبهما ``connect-src``. ولا يظهر هذا إلا بعد إصلاح الأول.

**والمصادر بالاسم لا بـ**``*``: إذن لخادمات معروفة، لا فتح للسياسة.
"""
from __future__ import annotations

import re

from app.main import _CSP, _STATIC_HEADERS


def _directive(name: str) -> str:
    for part in _CSP.split(";"):
        part = part.strip()
        if part.startswith(name + " "):
            return part
    raise AssertionError(f"التوجيه «{name}» غائب عن السياسة")


def test_the_worker_may_import_the_firebase_library():
    """**جوهر العطل**: بلا هذا يفشل تقييم عامل الخدمة كلّه."""
    assert "https://www.gstatic.com" in _directive("script-src"), _directive("script-src")


def test_the_device_may_register_itself_with_firebase():
    """والعطل الثاني: تُحمَّل المكتبة ثم يفشل تسجيل الجهاز."""
    connect = _directive("connect-src")
    for host in ("https://fcmregistrations.googleapis.com",
                 "https://firebaseinstallations.googleapis.com"):
        assert host in connect, f"{host} محجوب — {connect}"


def test_the_policy_is_not_opened_wildly():
    """**ولا يُفتَح الباب على مصراعيه**: السماح بالاسم لا بـ``*``.

    وإصلاح عطل بتعطيل الحماية يستبدل عطًلا ظاهًرا بعطل صامت.
    """
    for name in ("default-src", "script-src", "connect-src", "object-src"):
        d = _directive(name) if name != "object-src" else "object-src 'none'"
        assert "*" not in d.replace("'self'", ""), f"{name} مفتوح: {d}"
    assert "'unsafe-inline'" not in _directive("script-src")
    assert "'unsafe-eval'" not in _directive("script-src")


def test_the_worker_scope_is_still_allowed():
    """وعامل الخدمة نفسه يُسجَّل من نفس الأصل — لا يُمسّ ``worker-src``."""
    assert "'self'" in _directive("worker-src")


def test_the_policy_is_actually_served():
    """وسياسة لا تُرسَل لا تحمي ولا تحجب — فيُقاس أنها في الترويسة."""
    assert _STATIC_HEADERS.get("Content-Security-Policy") == _CSP


def test_the_hosts_match_what_the_worker_actually_loads():
    """**والسماح يطابق ما يُحمَّل فعًلا** — لا اسًما يُظنّ.

    فلو غيّر العامل مصدر مكتبته ولم تتبعه السياسة، عاد العطل نفسه.
    """
    from pathlib import Path

    sw = (Path(__file__).resolve().parents[2] / "frontend" / "public"
          / "firebase-messaging-sw.js").read_text(encoding="utf-8")
    hosts = {re.match(r"https://[^/]+", u).group(0)
             for u in re.findall(r'importScripts\(\s*"([^"]+)"', sw)}
    assert hosts, "العامل لا يستورد شيًئا — تغيّرت بنيته"
    script_src = _directive("script-src")
    for h in hosts:
        assert h in script_src, f"العامل يحمّل من {h} والسياسة تحجبه"
