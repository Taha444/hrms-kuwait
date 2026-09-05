# -*- coding: utf-8 -*-
"""حرّاس نتائج مراجعة الباكند (F-001..F-004).

المراجعة تكشف، والحرّاس يمنعون العودة. ونتيجة أمنية تُصلَح بلا اختبار
تعود مع أول إعادة كتابة — لأن لا شيء يقول إنها كانت عيًبا.

التقرير الكامل في ``docs/qa/BACKEND_AUDIT.md``.
"""
from __future__ import annotations

import io

import pytest
from sqlalchemy import text

from app.config import settings
from app.database import engine
from tests.conftest import auth_headers, login

SUPER = ("000000000000", "admin123")
HR = ("100000000002", "hr12345")


# ---------------------------------------------------------------------------
# F-001 — تفصيل حالة النظام ليس للعابرين
# ---------------------------------------------------------------------------
#: ما كان يُقرأ بلا مصادقة: أرقام عمل وبصمة بنية تحتية.
LEAKED_KEYS = ("companies", "employees", "users", "documents")


def test_anonymous_sees_component_status_without_numbers(client):
    """**العطل**: عدد الموظفين والمستخدمين ومسار التخزين ورقم الترحيل
    كانت تُقرأ بلا أي ترويسة — لمن يعرف الرابط فقط."""
    r = client.get("/api/health/deep")
    assert r.status_code in (200, 503), r.text
    body = r.json()

    assert "checks" in body, "المجهول لا يرى حالة المكوّنات — أُغلق أكثر ممّا يلزم"
    data = body["checks"].get("data") or {}
    for key in LEAKED_KEYS:
        assert key not in data, f"«{key}» ما زال مكشوًفا بلا مصادقة: {data}"

    storage = body["checks"].get("storage") or {}
    assert "path" not in storage, f"مسار التخزين مكشوف: {storage}"
    alembic = body["checks"].get("alembic") or {}
    assert "head" not in alembic, f"نسخة القاعدة مكشوفة: {alembic}"


def test_the_summary_still_serves_deployment_verification(client):
    """ولا يُغلق ما يحتاجه من ينشر.

    إغلاق كلّي يدفع من يحتاج النقطة إلى تخطّيها لا إلى تأمينها. فتبقى
    حالة كل مكوّن، ويبقى ما يُحسم به نجاح النشرة.
    """
    body = client.get("/api/health/deep").json()
    checks = body["checks"]
    assert body.get("status") in ("ok", "degraded")
    for comp in ("database", "storage", "alembic", "gov_contract"):
        assert comp in checks, f"«{comp}» غائب — لا يمكن التحقّق من نشرة"
        assert "status" in checks[comp]
    assert "up_to_date" in checks["alembic"], "لا يُعرف هل طُبّقت الترحيلات"
    assert "can_render_pdf" in checks["gov_contract"], "لا يُعرف هل العقد قابل للإخراج"


def test_super_admin_sees_the_full_detail(client):
    """والتفصيل موجود لمن يملكه — وإلا كنّا حذفنا الميزة لا أمّناها."""
    hdr = auth_headers(login(client, *SUPER))
    body = client.get("/api/health/deep", headers=hdr).json()
    data = body["checks"].get("data") or {}
    assert "employees" in data, f"الإدارة العليا لا ترى التفصيل: {data}"


def test_a_plain_user_does_not_unlock_the_detail(client):
    """ولا يفتحه أي حساب: المصادقة وحدها ليست إذًنا."""
    hdr = auth_headers(login(client, *HR))
    data = client.get("/api/health/deep", headers=hdr).json()["checks"].get("data") or {}
    assert "employees" not in data, f"حساب عادي فتح التفصيل: {data}"


def test_a_wrong_health_token_does_not_unlock_it(client, monkeypatch):
    """ورمز خاطئ لا يفتحه — والمقارنة ثابتة الزمن."""
    monkeypatch.setattr(settings, "health_token", "correct-token", raising=False)
    data = client.get("/api/health/deep",
                      headers={"X-Health-Token": "wrong"}).json()["checks"].get("data") or {}
    assert "employees" not in data

    ok = client.get("/api/health/deep",
                    headers={"X-Health-Token": "correct-token"}).json()["checks"].get("data") or {}
    assert "employees" in ok, "الرمز الصحيح لا يفتح التفصيل"


# ---------------------------------------------------------------------------
# F-004 — معرّف خارج المدى ليس عطًلا في الخادم
# ---------------------------------------------------------------------------
HUGE = 99999999999999999999


@pytest.mark.parametrize("path", [
    f"/api/employees/{HUGE}",
    f"/api/requests/{HUGE}",
    f"/api/renewals/{HUGE}",
])
def test_an_out_of_range_id_is_not_a_server_error(client, path):
    """**العطل**: كل مسار فيه ``/{id}`` يقبل عدًدا بلا حدّ، فيصل إلى
    مشغّل القاعدة ويتجاوز مدى العمود ويردّ 500 غير معالَج."""
    hdr = auth_headers(login(client, *HR))
    r = client.get(path, headers=hdr)
    assert r.status_code != 500, f"{path} ما زال يسقط بـ500: {r.text[:200]}"
    assert r.status_code in (403, 404, 422), r.status_code


def test_the_refusal_does_not_teach_the_column_limits(client):
    """و404 لا تشرح للمُجرِّب أين حدود الأعمدة."""
    hdr = auth_headers(login(client, *HR))
    body = client.get(f"/api/employees/{HUGE}", headers=hdr).text
    for leak in ("OverflowError", "out of range", "sqlite", "psycopg", "Traceback"):
        assert leak.lower() not in body.lower(), f"تسرّب «{leak}»: {body[:200]}"


def test_a_normal_missing_id_still_answers_normally(client):
    """ولم يُبتلع الطريق الطبيعي: معرّف صغير غير موجود يبقى 404."""
    hdr = auth_headers(login(client, *HR))
    assert client.get("/api/employees/999999", headers=hdr).status_code in (403, 404)


# ---------------------------------------------------------------------------
# F-002 — الرسالة تذكر الحدّ المطبَّق
# ---------------------------------------------------------------------------
def test_the_size_message_states_the_limit_actually_applied(client):
    """**العطل**: الرسالة كانت تقول 15MB دائًما، ومسار التوقيع يمرّر
    500KB. فيُرفض ملف 600KB ويُقال لصاحبه إن الحدّ خمسة عشر ميجابايت."""
    hdr = auth_headers(login(client, "100000000101", "emp12345"))
    big = b"\x89PNG\r\n\x1a\n" + b"0" * 900_000
    r = client.post("/api/me/signature", headers=hdr,
                    files={"file": ("AUDIT_big.png", io.BytesIO(big), "image/png")})
    assert r.status_code == 413, r.text
    detail = r.json()["detail"]
    assert "15MB" not in detail, f"الرسالة تذكر حًدا غير المطبَّق: {detail}"
    assert "500KB" in detail, f"الرسالة لا تذكر الحدّ الفعلي: {detail}"


def test_the_default_limit_is_still_reported_in_megabytes():
    """ولم تُكسر الرسالة للمسارات ذات الحدّ الكبير."""
    import asyncio

    from fastapi import HTTPException, UploadFile

    from app.safe_files import MAX_UPLOAD_BYTES, read_limited

    payload = b"0" * (MAX_UPLOAD_BYTES + 10)
    up = UploadFile(filename="x.bin", file=io.BytesIO(payload))
    with pytest.raises(HTTPException) as err:
        asyncio.get_event_loop().run_until_complete(read_limited(up))
    assert "MB" in err.value.detail, err.value.detail


# ---------------------------------------------------------------------------
# F-003 — **أُغلقت**، والتشخيص الذي أبقاها مفتوحة كان خاطًئا
# ---------------------------------------------------------------------------
def test_the_absence_of_a_delete_policy_is_the_right_policy():
    """المراجع الاثنان والستون بلا ``ondelete`` — وهذا **صواب** لا نقص.

    كان مكتوًبا أن غيابها يمنع التفعيل، وأن التفعيل بلا سياسات «ينقل
    العطل من لا يُفرَض إلى يُفرَض فيمنع كل حذف».

    **والقياس نقض المقدّمة**: لا مسار في التطبيق يحذف مستخدًما — لا
    نقطة نهاية ``DELETE /users`` ولا ``db.delete(user)``. المستخدم
    يُعطَّل (``is_active=False``) ولا يُحذَف، لأن سجلّه دليل على ما
    فعله.

    فـ«يمنع كل حذف» هو **المطلوب بعينه**، وغياب ``ondelete`` يعني
    ``RESTRICT`` وهو الافتراض. لم يكن الناقص سياسًة بل ترتيب حذف في
    تنظيف الاختبارات.
    """
    from app.database import Base

    users_refs = [
        (t.name, fk.parent.name)
        for t in Base.metadata.tables.values()
        for fk in t.foreign_keys
        if fk.column.table.name == "users" and fk.ondelete is None
    ]
    assert users_refs, "لا مراجع إلى users — راجع الفحص نفسه"


def test_no_code_path_deletes_a_user():
    """**والمقدّمة التي بُني عليها الإغلاق**، محروسة.

    لو أُضيف غًدا مسار يحذف مستخدًما، لصار غياب ``ondelete`` عيًبا
    حقيقًيا: حذف يُرفض في وجه من يحتاجه. فيسقط هذا الاختبار عندئذٍ،
    وهو الوقت الصحيح لمراجعة السياسات — لا اليوم.
    """
    import re
    from pathlib import Path

    # الشيفرة وحدها لا التعليقات: أول كتابة أمسكت التعليق الذي يشرح
    # هذه القاعدة نفسها في ``database.py`` — حارس يتّهم توثيقه.
    pattern = re.compile(r"db\.delete\(\s*user|delete\(models\.User\)"
                         r"|models\.User\.__table__\.delete")
    root = Path(__file__).resolve().parents[1] / "app"
    hits = []
    for path in root.rglob("*.py"):
        for lineno, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if pattern.search(line):
                hits.append(f"{path.name}:{lineno}")
    assert not hits, (
        "صار التطبيق يحذف مستخدمين — راجع سياسات ondelete للمراجع الـ62: "
        + ", ".join(hits)
    )


def test_foreign_keys_are_enforced_on_sqlite():
    """F-003 أُغلقت — والتشخيص الذي أبقاها مفتوحة كان خاطًئا.

    كان مكتوًبا: «اثنان وستون مفتاًحا أجنبًيا يشير إلى ``users`` بلا
    سياسة ``ondelete``، فتُراجَع أوًلا ثم يُفعَّل الفرض». وحين قِستُ
    وجدت أن **لا مسار في التطبيق يحذف مستخدًما** — لا نقطة نهاية ولا
    ``db.delete``. المستخدم يُعطَّل ولا يُحذَف.

    فالسياسة الصحيحة للمراجع الاثنين والستين هي **الرفض** — وهي
    افتراض SQL، أي أنها كانت صحيحة أصًلا. ولم يكن الناقص سياسًة، بل
    **ترتيب حذف في تنظيف الاختبارات**: تحذف الأب قبل أبنائه.

    وسبعة عشر اختباًرا صارت تسعة بعد إصلاحات هذه الجولة، وكلها من
    ذلك السبب وحده — أُصلحت بمُساعد ``purge`` يشتقّ الترتيب من
    ``metadata`` لا من قائمة تُكتب باليد وتتقادم.
    """
    from sqlalchemy import text

    from app.database import engine

    if not str(engine.url).startswith("sqlite"):
        return
    with engine.connect() as conn:
        enforced = conn.execute(text("PRAGMA foreign_keys")).scalar()
    assert enforced == 1, (
        "عاد فرض المفاتيح الأجنبية معطًَّلا — بيانات يقبلها الاختبار "
        "ويرفضها الإنتاج"
    )


def test_the_enforcement_actually_bites():
    """ولا يكفي أن يقول ``PRAGMA`` نعم: يُجرَّب انتهاك فعلي.

    راية مضبوطة على اتصال لا تعني أنها مضبوطة على كل اتصال — وجلسة
    واحدة بلا فرض تكفي لتمرير ما يرفضه الإنتاج.
    """
    import pytest as _pytest
    from sqlalchemy.exc import IntegrityError

    from app import models
    from app.database import SessionLocal, engine

    if not str(engine.url).startswith("sqlite"):
        return
    db = SessionLocal()
    try:
        db.add(models.Task(company_id=999999, type="probe_fk",
                           assignee_user_id=999999, title="انتهاك مقصود"))
        with _pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


# ---------------------------------------------------------------------------
# التخزين المؤقّت على الإنتاج يُعلَن، لا يُكتشف عند الطباعة
# ---------------------------------------------------------------------------
def test_local_storage_in_production_is_reported_as_degraded(client, monkeypatch,
                                                             tmp_path):
    """**العطل الذي وقع فعًلا**: قرص الحاوية يُمحى مع كل نشرة، فالسجلّ
    يبقى في القاعدة والملف يختفي. ويبدو المستند موجوًدا حتى يُضغط زرّ
    الطباعة — واكتشفه المستخدم لا النظام.

    **وP1-01 صحّح معيار هذا الادّعاء، لا نيّته.** كان يقيس على اسم
    الخلفية: ``local`` على الإنتاج = degraded. وبعد قرار المالك (قرص
    Railway دائم) تبقى الخلفية ``local`` وهي سليمة — فمعيار الاسم صار
    يشتكي من الإصلاح نفسه، وفحص يشتكي دائًما يُدرَّب الناس على تجاهله.

    فالادّعاء انتقل من «أي خلفية؟» إلى **«هل يبقى ما نكتبه؟»**: تخزين
    محلّي بلا دليل دوام يُعلَن ويُقرأ سببه، لا يُكتشف عند الطباعة.
    """
    from app.config import settings

    # is_production مشتقّة من رابط القاعدة لا من حقل بيئة صريح
    # (config.py:70)، فيُضبط ما يُقرأ فعًلا لا اسم يبدو صحيًحا.
    monkeypatch.setattr(settings, "database_url",
                        "postgresql+psycopg2://x/y", raising=False)
    monkeypatch.setattr(settings, "storage_backend", "local", raising=False)
    # مجلّد بكر: لا علامة نجاة ولا قرص دائم مُعلَن — أي لا دليل دوام.
    from app import storage_persistence as _sp

    fresh = tmp_path / "ephemeral"
    fresh.mkdir()
    monkeypatch.setattr(settings, "upload_dir", str(fresh), raising=False)
    monkeypatch.delenv(_sp.MOUNT_ENV, raising=False)
    assert settings.is_production, "لم تُضبط حالة الإنتاج — الاختبار لا يقيس شيًئا"

    hdr = auth_headers(login(client, *SUPER))
    storage = client.get("/api/health/deep", headers=hdr).json()["checks"]["storage"]
    assert storage["status"] == "degraded", (
        f"تخزين بلا دليل دوام على الإنتاج يُبلَّغ «{storage['status']}»"
    )
    assert storage["persistence"]["persistent"] is None, storage["persistence"]
    assert storage.get("note"), "أُعلنت الحالة بلا سبب يُقرأ"


def test_s3_in_production_is_not_flagged(client, monkeypatch):
    """ولا يُبلَّغ عن تخزين دائم — إنذار دائم لا يُقرأ."""
    from app.config import settings

    monkeypatch.setattr(settings, "database_url",
                        "postgresql+psycopg2://x/y", raising=False)
    monkeypatch.setattr(settings, "storage_backend", "s3", raising=False)
    assert settings.is_production

    hdr = auth_headers(login(client, *SUPER))
    storage = client.get("/api/health/deep", headers=hdr).json()["checks"]["storage"]
    assert storage["status"] != "degraded", storage
