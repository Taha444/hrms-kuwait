# -*- coding: utf-8 -*-
"""التسليم الفوري: أجهزة، ونقل، وتنظيف — بمزوّد مُستبدَل.

**الفصل مقصود**: قرار «هل يُدفَع» مقيس في ``test_zzz_push_policy`` بلا
شبكة، والنقل هنا بمزوّد يُستبدَل. فلا اختبار يحتاج Firebase حًيا —
وإلا صار أول ما يُعطَّل عند الضيق.

**والفشل لا يُفقد إشعاًرا**: الإشعار الداخلي مكتوب في القاعدة قبل أن
يُستدعى الدفع. وهذا ما يُقاس هنا صراحًة — لا يُفترَض.
"""
from __future__ import annotations

import pytest
from sqlalchemy import delete as sa_delete, select

from app import channels, models, push
from app.database import SessionLocal
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
HR = ("100000000002", "hr12345")


@pytest.fixture
def sent(monkeypatch):
    """مزوّد مُستبدَل يسجّل ما أُرسل — ولا يلمس الشبكة."""
    log: list[tuple[str, dict]] = []

    def fake(token, payload):
        log.append((token, payload))
        return True, None

    monkeypatch.setattr(push, "fcm_send", fake)
    monkeypatch.setattr(push, "is_configured", lambda: True)
    return log


@pytest.fixture
def user_id():
    db = SessionLocal()
    try:
        uid = db.scalar(select(models.User.id).where(
            models.User.civil_id == EMP[0]))
        db.execute(sa_delete(models.DeviceToken).where(
            models.DeviceToken.user_id == uid))
        db.commit()
        yield uid
    finally:
        db.execute(sa_delete(models.DeviceToken).where(
            models.DeviceToken.user_id == uid))
        db.commit()
        db.close()


def test_registering_a_device_then_pushing_reaches_it(user_id, sent):
    """خطّ الأساس: جهاز مسجَّل يصله الإشعار."""
    db = SessionLocal()
    try:
        push.register(db, user_id, "TOKEN-A", platform="web", label="حاسب")
        db.commit()
        out = push.push_to_user(db, user_id, kind="request",
                                title="طلب", body="طلب #120 يحتاج قرارك",
                                entity_type="request", entity_id=120)
        db.commit()
    finally:
        db.close()
    assert out["sent"] == 1, out
    assert len(sent) == 1
    token, payload = sent[0]
    assert token == "TOKEN-A"
    assert payload["link"] == "/requests/120"


def test_every_device_of_the_same_user_gets_it(user_id, sent):
    """**جهاز لا مستخدم**: الهاتف والحاسب كلاهما يصله."""
    db = SessionLocal()
    try:
        push.register(db, user_id, "TOKEN-PHONE", platform="android")
        push.register(db, user_id, "TOKEN-LAPTOP", platform="web")
        db.commit()
        out = push.push_to_user(db, user_id, kind="task", title="مهمة",
                                body="مهمة مسندة إليك")
        db.commit()
    finally:
        db.close()
    assert out["sent"] == 2, out
    assert {t for t, _ in sent} == {"TOKEN-PHONE", "TOKEN-LAPTOP"}


def test_a_token_that_moved_to_another_user_is_not_duplicated(user_id, sent):
    """**والرمز ينتقل ولا يُنسَخ**: وإلا وصل إشعار زيد إلى جهاز عمرو.

    Firebase قد تُعيد الرمز نفسه لجهاز انتقل بين حسابين على المتصفّح
    ذاته.
    """
    db = SessionLocal()
    other = None
    try:
        other = db.scalar(select(models.User.id).where(
            models.User.civil_id == HR[0]))
        push.register(db, other, "TOKEN-SHARED")
        db.commit()
        push.register(db, user_id, "TOKEN-SHARED")
        db.commit()
        rows = db.scalars(select(models.DeviceToken).where(
            models.DeviceToken.token == "TOKEN-SHARED")).all()
        owners = {r.user_id for r in rows}
    finally:
        db.execute(sa_delete(models.DeviceToken).where(
            models.DeviceToken.token == "TOKEN-SHARED"))
        db.commit()
        db.close()
    assert len(rows) == 1, f"تكرّر الرمز في {len(rows)} صًفا"
    assert owners == {user_id}, owners


def test_a_dead_token_is_marked_and_never_retried(user_id, monkeypatch):
    """**والجهاز الميت يُوسَم**: وإلا بقي يفشل مع كل إشعار إلى الأبد."""
    calls = []

    def refuse(token, payload):
        calls.append(token)
        return False, "UNREGISTERED"

    monkeypatch.setattr(push, "fcm_send", refuse)
    monkeypatch.setattr(push, "is_configured", lambda: True)

    db = SessionLocal()
    try:
        push.register(db, user_id, "TOKEN-DEAD")
        db.commit()
        first = push.push_to_user(db, user_id, kind="request", title="ط",
                                  body="نصّ")
        db.commit()
        second = push.push_to_user(db, user_id, kind="request", title="ط",
                                   body="نصّ")
        db.commit()
        row = db.scalar(select(models.DeviceToken).where(
            models.DeviceToken.token == "TOKEN-DEAD"))
        revoked_at, reason = row.revoked_at, row.revoked_reason
    finally:
        db.close()

    assert first["revoked"] == 1, first
    assert revoked_at is not None and reason == "UNREGISTERED"
    assert second["skipped"] == "no_devices", second
    assert len(calls) == 1, f"أُعيدت المحاولة على رمز ميت: {len(calls)}"


def test_a_transient_failure_does_not_kill_the_device(user_id, monkeypatch):
    """وعطل شبكة عابر لا يُلغي الجهاز: الفرق بين «لم يصل» و«لم يعد موجوًدا»."""
    monkeypatch.setattr(push, "fcm_send", lambda t, p: (False, "NETWORK"))
    monkeypatch.setattr(push, "is_configured", lambda: True)
    db = SessionLocal()
    try:
        push.register(db, user_id, "TOKEN-FLAKY")
        db.commit()
        out = push.push_to_user(db, user_id, kind="request", title="ط", body="ن")
        db.commit()
        row = db.scalar(select(models.DeviceToken).where(
            models.DeviceToken.token == "TOKEN-FLAKY"))
        still_live = row.revoked_at is None
    finally:
        db.close()
    assert out["failed"] == 1 and out["revoked"] == 0, out
    assert still_live, "أُلغي جهاز بسبب عطل عابر"


def test_what_the_policy_refuses_never_reaches_the_provider(user_id, sent):
    """**والقرار يسبق النقل**: الملخّص اليومي لا يصل المزوّد أصًلا."""
    db = SessionLocal()
    try:
        push.register(db, user_id, "TOKEN-X")
        db.commit()
        out = push.push_to_user(db, user_id, kind="digest", title="ملخّص",
                                body="٣ مهام")
        db.commit()
    finally:
        db.close()
    assert out["skipped"] == "policy", out
    assert not sent, "أُرسل ما لا يُدفَع"


def test_nothing_is_sent_when_firebase_is_not_configured(user_id, monkeypatch):
    """وبلا اعتماد لا محاولة: القناة معلَنة غير متاحة، والمحاولة ضجيج."""
    monkeypatch.setattr(push, "is_configured", lambda: False)
    db = SessionLocal()
    try:
        push.register(db, user_id, "TOKEN-Y")
        db.commit()
        out = push.push_to_user(db, user_id, kind="request", title="ط", body="ن")
        db.commit()
    finally:
        db.close()
    assert out["skipped"] == "not_configured", out


def test_the_internal_notification_survives_a_push_failure(client, monkeypatch):
    """**جوهر الأمان**: سقوط Firebase لا يُفقد إشعاًرا.

    الإشعار الداخلي يُكتب في القاعدة قبل الدفع — فالموظف يراه حين يفتح
    النظام. وهذا يُقاس صراحًة لا يُفترَض.
    """
    from app import notifications

    def explode(*a, **k):
        raise RuntimeError("Firebase ساقط")

    monkeypatch.setattr(push, "push_to_user", explode)

    db = SessionLocal()
    made = None
    try:
        uid = db.scalar(select(models.User.id).where(
            models.User.civil_id == EMP[0]))
        cid = db.scalar(select(models.User.company_id).where(
            models.User.id == uid))
        task = notifications.create_task(
            db, company_id=cid, type="request", title="طلب ينتظر قرارك",
            assignee_user_id=uid, detail="طلب #999")
        db.commit()
        made = task.id if task else None
        stored = db.get(models.Task, made) if made else None
        title = stored.title if stored else None
    finally:
        if made:
            db.execute(sa_delete(models.Task).where(models.Task.id == made))
            db.commit()
        db.close()
    assert made, "لم يُكتب الإشعار الداخلي حين سقط الدفع"
    assert title == "طلب ينتظر قرارك"


def test_the_channel_is_declared_and_unavailable_without_credentials():
    """والقناة تظهر «غير مُفعَّلة» بلا اعتماد — لا مفتاح يَعِد بلا تسليم."""
    avail = channels.channel_availability()
    assert "push" in avail, sorted(avail)
    assert avail["push"]["available"] is False
    assert avail["push"]["reason"], "معطَّلة بلا سبب"


def test_registering_goes_through_the_endpoint_as_the_caller(client):
    """والمستخدم من الرمز لا من الحمولة: لا يوجّه أحد إشعارات غيره."""
    hdr = auth_headers(login(client, *EMP))
    r = client.post("/api/notifications/devices", headers=hdr,
                    json={"token": "TOKEN-ENDPOINT-1", "platform": "web",
                          "label": "متصفّح الاختبار"})
    assert r.status_code == 201, r.text[:200]

    listed = client.get("/api/notifications/devices", headers=hdr).json()
    assert any(d["label"] == "متصفّح الاختبار" for d in listed), listed
    # والرمز نفسه لا يُعاد: هو ما يُرسَل به، وعرضه يجعله قابًلا للنسخ.
    assert all("token" not in d for d in listed), listed

    did = next(d["id"] for d in listed if d["label"] == "متصفّح الاختبار")
    assert client.delete(f"/api/notifications/devices/{did}",
                         headers=hdr).status_code == 200
    assert not any(d["id"] == did for d in client.get(
        "/api/notifications/devices", headers=hdr).json())


def test_a_bad_token_is_refused(client):
    """ورمز فارغ أو طويل لا يُكتب: صفّ لا يصل إليه شيء."""
    hdr = auth_headers(login(client, *EMP))
    for bad in ("", "قصير", "x" * 300):
        r = client.post("/api/notifications/devices", headers=hdr,
                        json={"token": bad})
        assert r.status_code == 400, (bad[:20], r.status_code)
