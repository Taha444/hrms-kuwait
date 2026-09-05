# -*- coding: utf-8 -*-
"""عقد الواجهة مع الخادم في الإشعارات الفورية.

**الإعدادات من الخادم لا من متغيّرات البناء**: قيم Firebase للويب
علنية بطبعها (تُشحن في حزمة أي تطبيق ويب، وأمنُها من قواعد المشروع لا
من إخفائها). فتقديمها من الخادم يجعل تفعيل الدفع **متغيّر بيئة** لا
نشرة واجهة جديدة.

**والمفتاح الخاص لحساب الخدمة لا يخرج أبًدا** — وهذا ما يُقاس هنا
صراحًة، لا يُفترَض.

**وعاملا الخدمة يتعايشان**: التطبيق يستعمل Workbox على نطاق الجذر،
وFirebase على نطاقها الخاص. ودمجُهما يتطلّب تحويل البناء إلى
``injectManifest`` — تغيير في بنية النشر لا حاجة إليه.
"""
from __future__ import annotations

from pathlib import Path

from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")

FRONT = Path(__file__).resolve().parents[2] / "frontend"
SW = FRONT / "public" / "firebase-messaging-sw.js"
CLIENT = FRONT / "src" / "push.ts"


def test_the_config_endpoint_never_leaks_the_service_account(client):
    """**الحدّ الأمني**: المفتاح الخاص لا يخرج من الخادم."""
    hdr = auth_headers(login(client, *EMP))
    r = client.get("/api/notifications/push-config", headers=hdr)
    assert r.status_code == 200, r.text
    body = r.json()

    flat = str(body)
    for secret in ("PRIVATE KEY", "private_key", "client_email",
                   "fcm_private_key"):
        assert secret not in flat, f"تسرّب «{secret}»: {flat[:200]}"
    assert set(body) == {"enabled", "vapid_key", "firebase", "reason"}, sorted(body)


def test_it_says_why_when_push_is_not_ready(client):
    """ومن يفتح الشاشة ولا يجد زًرا يحتاج أن يعرف لماذا."""
    hdr = auth_headers(login(client, *EMP))
    body = client.get("/api/notifications/push-config", headers=hdr).json()
    if not body["enabled"]:
        assert body["reason"], "غير مفعَّل بلا سبب"
        # ولا يُسلَّم مفتاح ويب بلا اعتماد خادم: رمز يُسجَّل ولا يصله شيء.
        assert body["firebase"] == {} and body["vapid_key"] == ""


def test_the_endpoint_is_not_public(client):
    """ولا تُقرأ الإعدادات بلا مصادقة: بصمة مشروع لمن يعرف الرابط."""
    assert client.get("/api/notifications/push-config").status_code in (401, 403)


def test_the_worker_reads_its_config_from_the_registration():
    """**والعامل لا يحمل إعدادات مثبَّتة**: تفعيل الدفع بلا إعادة بناء."""
    assert SW.exists(), "لا عامل خدمة للإشعارات"
    text = SW.read_text(encoding="utf-8")
    assert "searchParams" in text, "العامل لا يقرأ إعداداته من رابط التسجيل"
    # ولا مفتاح مكتوب فيه — ولو كان علنًيا، تثبيتُه يعني نشرة لكل تغيير.
    assert "AIza" not in text, "مفتاح ويب مثبَّت في العامل"


def test_the_two_workers_do_not_share_a_scope():
    """وعامل الـPWA لا يُمسّ: نطاقان مختلفان فيتعايشان."""
    client_src = CLIENT.read_text(encoding="utf-8")
    assert "/firebase-cloud-messaging-push-scope" in client_src, (
        "عامل Firebase يُسجَّل على نطاق الجذر — يتصادم مع عامل PWA"
    )
    vite = (FRONT / "vite.config.ts").read_text(encoding="utf-8")
    assert "VitePWA" in vite and "injectManifest" not in vite, (
        "تغيّرت بنية بناء عامل الـPWA — أعد النظر في التعايش"
    )


def test_the_permission_is_asked_by_a_click_not_on_load():
    """**والإذن بضغطة صريحة**: الرفض في Chrome دائم ولا يُعاد سؤاله.

    متصفّح يسأل عند فتح الصفحة يُرفض غالًبا — فيُحرَم المستخدم من
    الميزة إلى الأبد بقرار اتُّخذ قبل أن يفهمها.
    """
    prefs = (FRONT / "src" / "pages" / "NotificationPrefs.tsx").read_text(
        encoding="utf-8")
    assert "onClick={askPush}" in prefs, "لا زرّ صريح لطلب الإذن"

    app = (FRONT / "src" / "App.tsx").read_text(encoding="utf-8")
    assert "requestPermission" not in app, (
        "طلب إذن عند الإقلاع — يُرفض غالًبا والرفض دائم"
    )
    assert "listenInApp" in app, (
        "لا استقبال داخل الصفحة — يبدو الدفع معطًَّلا لمن يجلس أمام الشاشة"
    )


def test_the_client_reports_why_it_failed():
    """ومن يضغط الزرّ ولا يحدث شيء يحتاج سبًبا لا صمًتا."""
    text = CLIENT.read_text(encoding="utf-8")
    for phrase in ("لا يدعم", "محظورة", "لم يُمنَح"):
        assert phrase in text, f"لا رسالة لحالة «{phrase}»"


def test_the_worker_shows_only_what_the_server_sent():
    """والنصّ يصل **معتًَّما من الخادم** — لا يُبنى في العامل.

    نصّ يُركَّب في المتصفّح يتجاوز ``push_policy.redact``، فتظهر على
    شاشة القفل بيانات قُرِّر ألّا تظهر.
    """
    text = SW.read_text(encoding="utf-8")
    assert "n.title" in text and "n.body" in text
    # ولا تركيب: لا قوالب نصّية تضيف إلى ما وصل.
    assert "payload.data.employee" not in text
    assert "d.link" in text, "الرابط لا يُقرأ من البيانات"
