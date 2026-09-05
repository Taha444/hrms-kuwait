# -*- coding: utf-8 -*-
"""SEC2-15 — سجل المخوّلين بالتوقيع: صار له طريق، وأثره مقيس.

**العطل**: السجل يُقرأ عند توليد **كل مستند رسمي**
(``generate_document`` → ``resolve_authorized_signatory``) ولا سبيل إلى
الكتابة فيه إلا بالواجهة البرمجية. فكل شركة تبقى على المسار الاحتياطي:
توقيع **آخر معتمِد** على الورقة، وبلا عنوان وظيفي أصًلا.

**والفخّ الأخطر ليس غياب الشاشة بل صمتها**: مخوّل بلا صورة توقيع محفوظة
يسقط إلى الاحتياط بلا خطأ ولا تنبيه. فيقرأ المالك سجًلا مكتمًلا
والمستندات تخرج بتوقيع غيره. ولذلك ``has_signature`` **بشرط التوليد
نفسه** — لا بشرط يشبهه.
"""
from __future__ import annotations

import inspect
from pathlib import Path

from sqlalchemy import select

from app import models, workflow
from app.database import SessionLocal
from app.routers import signatories as sigmod
from tests.conftest import auth_headers, login

#: **من يُهيّئ السجل**: ``manage_users`` — والشؤون القانونية لا تملكها.
#: أول كتابة لهذا الاختبار افترضتها فسقطت، وكان الافتراض سيصير رابًطا في
#: الشريط لدور لا يستطيع استعماله.
MGR = ("100000000001", "manager123")
EMP = ("100000000101", "emp12345")

FRONT = Path(__file__).resolve().parents[2] / "frontend"
PAGE = FRONT / "src" / "pages" / "Signatories.tsx"
APP = FRONT / "src" / "App.tsx"
I18N = FRONT / "src" / "i18n.tsx"


def _mgr_user_id() -> int:
    db = SessionLocal()
    try:
        return db.scalar(select(models.User.id).where(
            models.User.civil_id == MGR[0]))
    finally:
        db.close()


def test_the_registry_is_readable_and_writable_from_the_screen(client):
    """**جوهر البناء**: ما كان يُقرأ عند كل توليد صار يُكتَب من شاشة."""
    hdr = auth_headers(login(client, *MGR))
    r = client.post("/api/signatories", headers=hdr, json={
        "user_id": _mgr_user_id(), "title_ar": "مدير الشؤون الإدارية",
        "scope_type": "any"})
    assert r.status_code == 201, r.text[:250]
    sid = r.json()["id"]

    listed = client.get("/api/signatories", headers=hdr)
    assert listed.status_code == 200
    assert any(s["id"] == sid for s in listed.json())

    gone = client.delete(f"/api/signatories/{sid}", headers=hdr)
    assert gone.status_code == 200 and gone.json()["is_active"] is False
    # والإلغاء لا يمحو: يبقى للمراجعة (R6).
    kept = client.get("/api/signatories", headers=hdr,
                      params={"include_inactive": True}).json()
    assert any(s["id"] == sid for s in kept), "الإلغاء محا الصفّ"


def test_a_signatory_without_an_image_is_flagged_not_silent(client):
    """**الفخّ الصامت معروض**: مخوّل بلا صورة توقيع يسقط إلى الاحتياط.

    وبلا هذه الراية يقرأ المالك سجًلا مكتمًلا والمستندات تخرج بتوقيع
    غيره — وهو أسوأ من غياب السجل، لأنه يبدو مضبوًطا.
    """
    hdr = auth_headers(login(client, *MGR))
    uid = _mgr_user_id()
    db = SessionLocal()
    try:
        u = db.get(models.User, uid)
        had = u.signature_path
        u.signature_path = None
        db.commit()
    finally:
        db.close()

    r = client.post("/api/signatories", headers=hdr, json={
        "user_id": uid, "title_ar": "بلا صورة", "scope_type": "code",
        "scope_value": "HRMS-PR-999"})
    assert r.status_code == 201, r.text[:200]
    assert r.json()["has_signature"] is False, "لا راية على مخوّل بلا صورة"

    db = SessionLocal()
    try:
        db.get(models.User, uid).signature_path = had
        db.commit()
    finally:
        db.close()


def test_the_flag_uses_the_same_condition_generation_uses():
    """وشرطان متشابهان ينحرفان: الراية تفحص **وجود الملف** لا العمود.

    مسار يشير إلى ملف محذوف كان سيقول «جاهز» ويسقط عند التوليد.
    """
    src = inspect.getsource(sigmod._has_signature)
    assert "key_exists" in src, (
        "الراية تفحص العمود وحده — تقول «جاهز» عن ملف محذوف"
    )
    gen = inspect.getsource(workflow.generate_document)
    assert "key_exists(signer_user.signature_path)" in gen, (
        "تغيّر شرط التوليد — أعد مطابقة الراية عليه"
    )


def test_the_registry_actually_changes_the_document(client):
    """**والسجل يؤثّر فعًلا**: مخوّل مسجَّل يُقدَّم على الاحتياط.

    شاشة تكتب في جدول لا يقرؤه أحد أسوأ من لا شاشة. وهذا يقيس السلسلة
    كاملة: الكتابة ← الحلّ ← اختيار التوقيع عند التوليد.
    """
    hdr = auth_headers(login(client, *MGR))
    uid = _mgr_user_id()
    created = client.post("/api/signatories", headers=hdr, json={
        "user_id": uid, "title_ar": "المدير المفوَّض", "scope_type": "any"})
    assert created.status_code in (201, 409), created.text[:200]

    db = SessionLocal()
    try:
        resolved = sigmod.resolve_authorized_signatory(
            db, db.get(models.User, uid).company_id, "HRMS-PR-001")
    finally:
        db.close()
    assert resolved is not None, "السجل لا يُحَل — الكتابة بلا أثر"
    assert resolved.user_id == uid

    # والتوليد يقرأ من هذا الباب نفسه لا من باب ثانٍ.
    gen = inspect.getsource(workflow.generate_document)
    assert "resolve_authorized_signatory" in gen


def test_the_screen_has_a_way_in():
    """وشاشة بلا رابط غير موجودة عملًيا — والدرس تكرّر في هذه الجولة."""
    app = APP.read_text(encoding="utf-8")
    assert 'to="/signatories"' in app, "لا رابط في الشريط"
    assert 'path="/signatories"' in app, "لا مسار"
    assert "import Signatories" in app


def test_the_screen_warns_when_the_registry_is_empty():
    """ومن يفتح سجًلا فارًغا يحتاج أن يعرف ما يجري بدونه."""
    page = PAGE.read_text(encoding="utf-8")
    assert "sig_none_title" in page and "sig_none_hint" in page, (
        "سجل فارغ بلا تفسير — لا يعرف المالك أن مستنداته تُوقَّع بالاحتياط"
    )
    assert "has_signature" in page, "الراية غير معروضة"


def test_the_screen_asks_for_what_the_server_requires():
    """ولا تُرسل الشاشة ما تعرف أنه سيُرفض: ``scope_value`` مع نطاق مخصَّص."""
    page = PAGE.read_text(encoding="utf-8")
    assert "sig_scope_value_required" in page
    validator = inspect.getsource(sigmod.SignatoryIn)
    assert "scope_value مطلوب" in validator, "تغيّر شرط الخادم — راجع الشاشة"


def test_every_label_exists_in_both_languages():
    """ونصٌّ ناقص في لغة يظهر مفتاًحا خاًما على الشاشة."""
    import re

    page = PAGE.read_text(encoding="utf-8")
    i18n = I18N.read_text(encoding="utf-8")
    keys = set(re.findall(r't\("(sig_[a-z_0-9]+)"\)', page))
    assert keys, "لا مفاتيح — تحقّق من الشاشة"
    for k in sorted(keys):
        at = i18n.find(f"{k}: {{")
        assert at >= 0, f"المفتاح «{k}» غير معرَّف"
        nxt = re.search(r"\n  [a-z_0-9]+: ", i18n[at + len(k):])
        entry = i18n[at:at + len(k) + (nxt.start() if nxt else 400)]
        assert "ar:" in entry and "en:" in entry, f"«{k}» ناقص في إحدى اللغتين"


def test_no_label_key_is_defined_twice():
    """ومفتاح معرَّف مرّتين يفوز فيه الأخير بصمت.

    أول كتابة لهذه الشاشة سمّت مفتاحها ``sig_title`` وكان اسًما مأخوًذا
    لشاشة التوقيع الشخصي — فكان عنوان تلك الشاشة سيتغيّر بلا أن يمسّها
    أحد.
    """
    import collections
    import re

    keys = re.findall(r"^  ([a-z_0-9]+):\s*\{",
                      I18N.read_text(encoding="utf-8"), re.M)
    dupes = [k for k, n in collections.Counter(keys).items() if n > 1]
    assert not dupes, f"مفاتيح مكرَّرة: {dupes}"


def test_whoever_may_configure_can_reach_the_screen():
    """**وزرّ خلف باب مغلق لا وجود له**.

    الرابط محكوم بـ``manage_users`` والمسار بـ``view_documents``. فلو
    ملك دوٌر التهيئة دون القراءة لَمَا فتح الشاشة التي يملك تعديلها.
    """
    from app.permissions import ROLE_DEFAULT_PERMS

    blind = [r for r, p in ROLE_DEFAULT_PERMS.items()
             if "manage_users" in p and "view_documents" not in p]
    assert not blind, f"يملك التهيئة ولا يصل إلى شاشتها: {blind}"
