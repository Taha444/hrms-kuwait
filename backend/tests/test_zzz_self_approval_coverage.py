# -*- coding: utf-8 -*-
"""فصُل السلطات — قاعدٌة واحدٌة تُقاس في كل موضٍع يعتمد شيًئا.

**القاعدة**: «ممنوع Self Approval لكل الأدوار» — قراُر مالٍك صريح. وهي
مطبَّقٌة في المسيّر (``_self_approval_blocked``) وفي نهاية الخدمة
(``calculated_by == user.id``) وفي تعديل الراتب وفي الطلبات
(``request_actions``).

**وتصحيُح قياٍس**: قصدتُ أن ``approve_replacement`` يسمح لموظف موارٍد بأن
يعتمد استبداَل توقيعه. وقراءُة الفرع أعلاه تُبطل ذلك في المسار المعتاد::

    is_privileged = user.role in ("hr", "super_admin")
    if is_first_upload or is_privileged:
        # تطبيق مباشر: أول رفع، أو المستخدم HR/Super Admin

فتوقيُع موارد البشرية **ال يصير له طلٌب معلَّق أصًلا** — يُستبدَل مباشرًة،
ويُقيَّد في السجل غير القابل للتعديل بـ``stage="direct"`` و``approver`` هو
نفسه. فالنداُء ال يُصيب النفَس إال في مسٍار ضيّق: **من رفع استبداًال ثم
رُقِّي إلى موارد بشرية**، فيجد طلبَه معّلًقا ويعتمده. وهو باٌب صغير، وسدُّه
ال يكلّف شيًئا — فسُدّ، ويُحرَس هنا بالحالة التي يتركها تغييُر الدور.

**وما هو أكبُر من ذلك قراٌر مكتوٌب ال سهو**: ``hr`` و``super_admin``
يتخّطيان مسار اعتماد التوقيع كلَّه. وهذا يخالف حرَف القاعدة بالنسبة
لـ``hr`` — فيُحرَس **كما هو** ليُرى: من يُغيّره يُغيّره بقصد، ال يجده
منحرًفا بعد حين.

**ولماذا التوقيُع خاصًّة**: هو ما يُختَم على المستندات الرسمية، و
``signature_version`` يُثبَّت على كل مستنٍد صادر (DOC-20) لتبقى حُّجيته على
نسخته ال على نسخة اليوم.
"""
from __future__ import annotations

import io

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

HR1 = ("100000000002", "hr12345")
MGR1 = ("100000000001", "manager123")
ADMIN = ("000000000000", "admin123")

_PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00"
        b"\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\n"
        b"IDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n\x2d\xb4\x00\x00"
        b"\x00\x00IEND\xaeB`\x82")


def _snapshot(civil_id: str):
    db = SessionLocal()
    try:
        u = db.scalar(select(models.User).where(models.User.civil_id == civil_id))
        return (u.id, u.signature_path, u.signature_version,
                u.pending_signature_path)
    finally:
        db.close()


def _restore(uid: int, path, version, pending) -> None:
    """**وحاٌرس ال يُغيّر حالًة يقرؤها غيره** — الصفُّ مشترٌك بين الملفات.

    **ويُعاد عدّاُد النسخة وسجلُّها معًا.** و``user_signature_versions``
    فريٌد بـ``(user_id, version)``: فإعادُة العدّاد وحده تُبقي صًفّا بالرقم
    نفسه، فيسقط أوُل رفٍع تاٍل بـ``IntegrityError`` — وهو ما وقع لي في
    ثالثة اختبارات، والسبُب تنظيفي ال الشيفرة. فما سجَّلتُه أنا يُحذف.
    """
    from sqlalchemy import delete as sa_delete

    db = SessionLocal()
    try:
        u = db.get(models.User, uid)
        if u:
            u.signature_path = path
            u.signature_version = version
            u.pending_signature_path = pending
            u.pending_signature_uploaded_at = None
            u.pending_signature_reason = None
            db.execute(sa_delete(models.UserSignatureVersion).where(
                models.UserSignatureVersion.user_id == uid,
                models.UserSignatureVersion.version > (version or 0)))
            db.commit()
    finally:
        db.close()


def _upload(client, who, reason: str | None = None):
    """**والسبُب معامُل استعلاٍم ال حقُل نموذج.**

    ``reason: str | None = None`` بال ``Form(...)`` — فـFastAPI يقرؤه من
    الاستعلام. والواجهُة تُرسله كذلك (``/me/signature?reason=...`` في
    ``MyProfile.tsx``)، فالعقُد متّسٌق والخطُأ كان في قياسي: أرسلتُه في
    ``data`` فلم يصل، فردَّ «السبب إلزامي» — وكاد يُقرأ عطًلا في الشيفرة.
    """
    params = {"reason": reason} if reason else None
    return client.post("/api/me/signature", params=params,
                       files={"file": ("sig.png", io.BytesIO(_PNG), "image/png")},
                       headers=auth_headers(login(client, *who)))


# ---------------------------------------------------------------------------
# ما هو واقٌع فعًلا — يُحرَس ليُرى
# ---------------------------------------------------------------------------

def test_an_hr_signature_change_needs_no_second_pair_of_eyes(client):
    """**قراٌر مكتوٌب يُحرَس ليُرى**: موارُد البشرية تُبدِّل توقيعها مباشرًة.

    وهو المسلُك القائم (``is_privileged``): ال طلَب معّلًقا وال معتمًِدا
    غيرها، والسجلُّ يُقيّد ``stage="direct"``. ويخالف حرَف «ممنوع Self
    Approval لكل الأدوار» — فإن أُريد تغييرُه فليكن بقصد.
    """
    uid, path0, ver0, pend0 = _snapshot(HR1[0])
    try:
        r = _upload(client, HR1, reason="قياُس فصل السلطات")
        assert r.status_code in (200, 201), (r.status_code, r.text[:250])
        assert r.json().get("status") == "active", r.json()

        db = SessionLocal()
        try:
            u = db.get(models.User, uid)
            assert not u.pending_signature_path, "صار له طلٌب معلَّق — المسلُك تغيّر"
            assert u.signature_version == (ver0 or 0) + 1, (ver0, u.signature_version)
            last = db.scalar(select(models.UserSignatureVersion).where(
                models.UserSignatureVersion.user_id == uid
            ).order_by(models.UserSignatureVersion.version.desc()))
            assert last is not None and last.stage in ("direct", "first_upload"), \
                getattr(last, "stage", None)
        finally:
            db.close()
    finally:
        _restore(uid, path0, ver0, pend0)


def test_a_plain_user_replacement_waits_for_someone_else(client):
    """**ومن ليس موارَد بشرية ينتظر عيًنا ثانية** — وهذا نصُف القاعدة القائم.

    فالمسار المعلَّق موجوٌد ويعمل: يُحفَظ ``pending`` ويبقى القديُم نشًطا.
    """
    uid, path0, ver0, pend0 = _snapshot(MGR1[0])
    try:
        first = _upload(client, MGR1)             # يُثبِّت توقيًعا إن لم يكن
        assert first.status_code in (200, 201), first.text[:250]
        second = _upload(client, MGR1, reason="تغيير خط اليد")
        assert second.status_code in (200, 201), second.text[:250]

        db = SessionLocal()
        try:
            u = db.get(models.User, uid)
            assert u.pending_signature_path, "ال طلَب معلًَّقا لمن ليس HR"
            assert u.signature_path and u.signature_path != u.pending_signature_path, \
                "القديُم لم يبقَ نشًطا حتى الاعتماد"
        finally:
            db.close()
    finally:
        _restore(uid, path0, ver0, pend0)


def test_a_replacement_reason_is_not_optional(client):
    """والاستبداُل يستوجب سبًبا — دليٌل يُقرأ بعد سنين ال حقٌل يُملأ."""
    uid, path0, ver0, pend0 = _snapshot(MGR1[0])
    try:
        _upload(client, MGR1)
        r = _upload(client, MGR1)   # بال سبب، وله توقيٌع قائم
        assert r.status_code == 400, (r.status_code, r.text[:200])
    finally:
        _restore(uid, path0, ver0, pend0)


# ---------------------------------------------------------------------------
# والباُب الضيُّق مسدود
# ---------------------------------------------------------------------------

def test_nobody_approves_the_replacement_of_their_own_signature(client):
    """**ومن رُقِّي وجد طلبَه معّلًقا — فال يعتمده بنفسه.**

    الحالُة تُصنَع كما يتركها تغييُر الدور: طلٌب معلٌَّق على صفِّ موظف موارٍد.
    ولو أُزيل الفحُص مرّ الاعتماُد وبقي الأثُر شاهًدا على الفعل بالفاعل نفسه.
    """
    uid, path0, ver0, pend0 = _snapshot(HR1[0])
    db = SessionLocal()
    try:
        u = db.get(models.User, uid)
        u.signature_path = u.signature_path or "signatures/seed_hr.png"
        u.pending_signature_path = "signatures/zzz_pending_probe.png"
        u.pending_signature_reason = "قياُس فصل السلطات"
        db.commit()
    finally:
        db.close()
    try:
        r = client.post(f"/api/signatures/pending/{uid}/approve",
                        headers=auth_headers(login(client, *HR1)))
        assert r.status_code == 403, (r.status_code, r.text[:250])
        db = SessionLocal()
        try:
            assert db.get(models.User, uid).pending_signature_path, \
                "اعتُمد استبداُل توقيعه بنفسه"
        finally:
            db.close()
    finally:
        _restore(uid, path0, ver0, pend0)


def test_the_escape_hatch_is_real(client):
    """**ومنٌع بال مخرٍج يُقفل شركة** — فالإدارُة العليا تعتمد.

    وهذا نصُف القاعدة: لو لم يوجد من يعتمد لصار الفصُل عائًقا ال ضماًنا،
    فيُلجأ إلى تعطيله كلَّه.
    """
    uid, path0, ver0, pend0 = _snapshot(HR1[0])
    db = SessionLocal()
    try:
        u = db.get(models.User, uid)
        u.signature_path = u.signature_path or "signatures/seed_hr.png"
        u.pending_signature_path = "signatures/zzz_pending_probe2.png"
        u.pending_signature_reason = "قياُس المخرَج"
        db.commit()
    finally:
        db.close()
    try:
        r = client.post(f"/api/signatures/pending/{uid}/approve",
                        headers=auth_headers(login(client, *ADMIN)))
        assert r.status_code == 200, (r.status_code, r.text[:250])
        db = SessionLocal()
        try:
            u = db.get(models.User, uid)
            assert not u.pending_signature_path, "لم يُعتمَد"
        finally:
            db.close()
    finally:
        _restore(uid, path0, ver0, pend0)


# ---------------------------------------------------------------------------
# والقاعدُة الواحدُة تُقاس في مواضعها كلّها
# ---------------------------------------------------------------------------

def test_the_rule_is_applied_at_every_approval_it_names():
    """ولو أُضيفت نقطُة اعتماٍد بال منٍع سقط هذا الحارس، فيُنظَر فيها.

    وهذا أحُد المواضع القليلة التي تقرأ الشيفرَة بحقّ: **غياُب** شرٍط ال
    سلوَك له يُقاس — فالنقطُة التي ال تُمنَع تُحرَس بأنها ما زالت تُمنَع.
    """
    import inspect

    from app.routers import eos, payroll, signatures

    assert "_self_approval_blocked" in inspect.getsource(payroll.approve_run)
    assert "calculated_by == user.id" in inspect.getsource(eos.approve_case)
    assert "target.id == user.id" in inspect.getsource(signatures.approve_replacement)
    # ولا يعتمد الموظُف تسويَة نفسه.
    assert "user.employee_id == case.employee_id" in inspect.getsource(eos.approve_case)


def test_the_exemption_is_only_the_technical_root():
    """**واالستثناُء واحٌد معلوم**: ``super_admin`` — ال دوٌر آخر.

    وهو متَّسٌق مع «ال تمنح أي مستخدم Super Admin»: مخرٌج للجذر التقني ال
    لشخص. ولو تسّرب االستثناُء إلى دوٍر ثاٍن سقط هذا الحارس.
    """
    import inspect

    from app.routers import eos, payroll, signatures

    for fn in (payroll._self_approval_blocked, eos.approve_case,
               signatures.approve_replacement):
        for ln in inspect.getsource(fn).splitlines():
            if "user.role !=" in ln:
                assert '"super_admin"' in ln, (fn.__name__, ln.strip())
