# -*- coding: utf-8 -*-
"""P10-33 — لا مفتاح قبل التحقّق من التكامل.

**ما ظهر بالقياس:**

``GET /notifications/preferences`` كان يعرض القنوات الأربع بلا شرط،
وافتراضه ``enabled=True``. فيفتح المستخدم الشاشة فيرى «واتساب» و«SMS»
و«بريد» مُفعَّلة — ولا يصله عبرها شيء أبًدا.

**والبريد أوضحها**: معلَن في القائمة منذ البداية و**لا صنف قناة له
إطلاًقا** (``channels.py`` فيه Log وSms وWhatsApp فقط). فمفتاحه لا
يعمل في أي ضبط، لا اليوم ولا بعد ضبط المزوّدين.

**والقائمة كانت مكتوبة ثلاث مرّات**: تعليق النموذج، و``CHANNELS`` في
الراوتر، ومصفوفة داخل شاشة التفضيلات. وثلاث نسخ لقائمة واحدة تنحرف
إحداها — والانحراف هنا يَعِد بتسليم لا يقع.
"""
from __future__ import annotations

from pathlib import Path

from app import channels
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")


def test_email_is_declared_but_has_no_channel_class():
    """خطّ الأساس: القناة معلَنة ولا وجود لها — والادّعاء يقيس ذلك."""
    assert "email" in channels.CHANNEL_CATALOG, "البريد اختفى من الكتالوج"
    assert not channels.CHANNEL_CATALOG["email"]["implemented"], (
        "البريد صار مُنفًَّذا — احذف هذا الادّعاء وفعّل مفتاحه"
    )
    src = Path(channels.__file__).read_text(encoding="utf-8")
    assert "class EmailChannel" not in src, (
        "وُجد صنف بريد بينما الكتالوج يقول إنه غير مُنفَّذ — تناقض"
    )


def test_availability_says_why_not_only_that_not():
    """ومن يُمنع بلا سبب يظنّ العطل عنده."""
    avail = channels.channel_availability()
    for name, info in avail.items():
        if not info["available"]:
            assert info["reason"], f"قناة «{name}» معطَّلة بلا سبب"


def test_the_in_app_channel_is_always_available():
    """وداخل النظام يعمل بلا مزوّد — وإلا كان الفحص أعلاه يمنع كل شيء."""
    assert channels.channel_availability()["in_app"]["available"] is True


def test_preferences_carry_the_integration_state(client):
    """**جوهر البند**: الشاشة تعرف أي قناة تُسلِّم قبل أن تعرض مفتاحها."""
    hdr = auth_headers(login(client, *HR))
    r = client.get("/api/notifications/preferences", headers=hdr)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert rows, "لا تفضيلات — القياس فارغ"
    for row in rows:
        assert "available" in row, f"صفّ بلا حالة تكامل: {row}"
        if not row["available"]:
            assert row["unavailable_reason"], row


def test_an_undeliverable_channel_is_not_on_by_default(client):
    """ولا يُعرَض مُفعًَّلا افتراًضا: الوعد الذي لا يقع أسوأ من خانة معطَّلة."""
    hdr = auth_headers(login(client, *HR))
    rows = client.get("/api/notifications/preferences", headers=hdr).json()
    promised = [r for r in rows if r["enabled"] and not r["available"]]
    assert not promised, (
        f"قنوات مُفعَّلة ولا تُسلِّم: "
        f"{sorted({r['channel'] for r in promised})}"
    )


def test_the_server_refuses_to_save_a_promise_it_cannot_keep(client):
    """والخادم يفرضها: تعطيل خانة في الواجهة لا يمنع طلًبا مباشًرا."""
    hdr = auth_headers(login(client, *HR))
    rows = client.get("/api/notifications/preferences", headers=hdr).json()
    dead = next((r for r in rows if not r["available"]), None)
    assert dead, "كل القنوات تُسلِّم — لا شيء يُقاس هنا"

    r = client.put("/api/notifications/preferences", headers=hdr, json=[{
        "category": dead["category"], "channel": dead["channel"], "enabled": True}])
    assert r.status_code == 409, (
        f"حُفظ تفعيل قناة لا تُسلِّم: {r.status_code} {r.text[:150]}"
    )


def test_muting_an_undeliverable_channel_is_still_allowed(client):
    """والكتم مقبول دائًما: من أراد إسكات قناة يُسكت له، سلّمت أو لا."""
    hdr = auth_headers(login(client, *HR))
    rows = client.get("/api/notifications/preferences", headers=hdr).json()
    dead = next((r for r in rows if not r["available"]), None)
    assert dead
    r = client.put("/api/notifications/preferences", headers=hdr, json=[{
        "category": dead["category"], "channel": dead["channel"], "enabled": False}])
    assert r.status_code == 200, r.text[:150]


def test_a_working_channel_can_still_be_toggled(client):
    """ولم تُقفل القنوات العاملة: ادّعاء المنع بلا هذا نصف قياس."""
    hdr = auth_headers(login(client, *HR))
    rows = client.get("/api/notifications/preferences", headers=hdr).json()
    live = next(r for r in rows if r["available"])
    r = client.put("/api/notifications/preferences", headers=hdr, json=[{
        "category": live["category"], "channel": live["channel"], "enabled": True}])
    assert r.status_code == 200, r.text[:150]


def test_an_unknown_channel_is_refused(client):
    """وقناة لا يعرفها الكتالوج لا تُكتب: صفّ لا يقرؤه أحد."""
    hdr = auth_headers(login(client, *HR))
    rows = client.get("/api/notifications/preferences", headers=hdr).json()
    r = client.put("/api/notifications/preferences", headers=hdr, json=[{
        "category": rows[0]["category"], "channel": "pigeon", "enabled": True}])
    assert r.status_code == 400, r.status_code


def test_the_channel_list_lives_in_one_place():
    """**الحارس**: نسخة ثانية من القائمة تنحرف عن الأولى.

    كانت ثلاثًا. والانحراف هنا لا يُنتج خطأ ظاهًرا — يُنتج وعًدا صامًتا
    بتسليم لا يقع، وهو أسوأ ما قد يفعله جدول إعدادات.
    """
    from app.routers import notification_settings as ns

    assert set(ns.CHANNELS) == set(channels.CHANNEL_CATALOG), (
        "قائمة الراوتر انحرفت عن الكتالوج"
    )

    ui = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages"
          / "NotificationPrefs.tsx")
    if ui.exists():
        text = ui.read_text(encoding="utf-8")
        assert 'const CHANNELS = ["in_app"' not in text, (
            "الواجهة عادت تحمل نسختها الخاصة من قائمة القنوات"
        )
        assert "/notifications/channels" in text, (
            "الواجهة لا تقرأ القنوات من الخادم"
        )
