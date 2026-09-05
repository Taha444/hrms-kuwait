# -*- coding: utf-8 -*-
"""V1.5 §3 — تفويض الاعتماد: صار له طريق، وأثره مقيس.

**العطل**: المحرّك يقرأ التفويضات في ثلاثة مواضع
(``expand_approvers_with_delegates``) فيوسّع دائرة من يعتمد المرحلة —
ولا سبيل إلى إنشائها إلا بالواجهة البرمجية. فمن يسافر تقف طلباته عنده
حتى يعود.

**وقياسان غيّرا شكل الشاشة قبل بنائها**:

1. ``scope`` يُخزَّن ولا يقرؤه أحد. فقائمة «الإجازات فقط» كانت ستَعِد
   بتقييد لا يفرضه شيء — والمفوَّض إليه يأخذ كل شيء. فلا ضابط، والصفحة
   تقول ما يشمله التفويض صراحًة.
2. ``/users`` محجوزة لـ``manage_users``، فمسؤول الفرع الذي يسافر لا يجد
   زميًلا يفوّضه رغم أن الخادم يسمح له بالتفويض عن نفسه.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from app import delegation, models, workflow
from app.database import SessionLocal
from tests.conftest import auth_headers, login

SUP = ("100000000005", "sup12345")      # مسؤول الفرع — يعتمد المرحلة الأولى
SUP2 = ("100000000006", "sup12345")     # زميله
HR = ("100000000002", "hr12345")
EMP = ("100000000101", "emp12345")

FRONT = Path(__file__).resolve().parents[2] / "frontend"
PAGE = FRONT / "src" / "pages" / "Delegations.tsx"
APP = FRONT / "src" / "App.tsx"
I18N = FRONT / "src" / "i18n.tsx"


def _uid(civil: str) -> int:
    db = SessionLocal()
    try:
        return db.scalar(select(models.User.id).where(
            models.User.civil_id == civil))
    finally:
        db.close()


def test_a_plain_approver_can_find_someone_to_delegate_to(client):
    """**بلا هذا لا تعمل الشاشة أصًلا لمن يحتاجها**.

    ``/users`` محجوزة لـ``manage_users``، ومسؤول الفرع لا يملكها —
    فيسمح له الخادم بالتفويض ولا يجد اسًما يختاره.
    """
    hdr = auth_headers(login(client, *SUP))
    assert client.get("/api/users", headers=hdr).status_code in (401, 403), (
        "تغيّرت صلاحية قائمة المستخدمين — أعد النظر في نقطة المرشَّحين"
    )
    r = client.get("/api/delegations/candidates", headers=hdr)
    assert r.status_code == 200, r.text[:200]
    people = r.json()
    assert people, "لا مرشَّحين — الشاشة بلا خيارات"
    assert all(p["id"] != _uid(SUP[0]) for p in people), "المستخدم يفوّض نفسه"


def test_the_candidates_list_says_only_what_it_must(client):
    """ولا تكشف أكثر ممّا يلزم: اسم ودور ومعرّف — لا بريد ولا رقم مدني."""
    hdr = auth_headers(login(client, *SUP))
    people = client.get("/api/delegations/candidates", headers=hdr).json()
    assert set(people[0]) == {"id", "full_name", "role"}, sorted(people[0])


def test_the_list_shows_names_not_numbers(client):
    """وصفٌّ يقول «12 ← 7» لا يُقرأ. وكانت القائمة تُعيد المعرّفات وحدها."""
    hdr = auth_headers(login(client, *SUP))
    r = client.post("/api/delegations", headers=hdr, json={
        "delegate_user_id": _uid(SUP2[0]),
        "starts_at": datetime.utcnow().isoformat(),
        "ends_at": (datetime.utcnow() + timedelta(days=3)).isoformat(),
        "reason": "سفر"})
    assert r.status_code == 201, r.text[:200]

    rows = client.get("/api/delegations", headers=hdr).json()
    assert rows and rows[0]["delegator_name"] and rows[0]["delegate_name"], rows[:1]


def test_in_effect_is_not_the_same_as_not_revoked(client):
    """**سارٍ ≠ غير ملغى**: تفويض لم تبدأ مدّته يبدو فعّاًلا ولا يعمل.

    والمستخدم يقرؤه «مفعَّل» ثم يجد طلباته واقفة بلا سبب ظاهر.
    """
    hdr = auth_headers(login(client, *SUP))
    later = datetime.utcnow() + timedelta(days=10)
    r = client.post("/api/delegations", headers=hdr, json={
        "delegate_user_id": _uid(SUP2[0]),
        "starts_at": later.isoformat(),
        "ends_at": (later + timedelta(days=2)).isoformat()})
    assert r.status_code == 201, r.text[:200]
    made = r.json()["id"]

    rows = client.get("/api/delegations", headers=hdr,
                      params={"only_active": False}).json()
    row = next(x for x in rows if x["id"] == made)
    assert row["is_active"] is True and row["in_effect"] is False, row


def test_a_delegation_actually_opens_the_approval(client):
    """**والتفويض يعمل فعًلا**: المفوَّض إليه يدخل قائمة معتمِدي المرحلة.

    شاشة تكتب في جدول لا يقرؤه أحد أسوأ من لا شاشة. وهذا يقيس السلسلة:
    الإنشاء ← توسيع المعتمِدين ← قرار يُقبل.
    """
    hdr = auth_headers(login(client, *SUP))
    now = datetime.utcnow()
    client.post("/api/delegations", headers=hdr, json={
        "delegate_user_id": _uid(SUP2[0]),
        "starts_at": (now - timedelta(hours=1)).isoformat(),
        "ends_at": (now + timedelta(days=2)).isoformat(),
        "reason": "قياس"})

    db = SessionLocal()
    try:
        delegates = delegation.active_delegates_for(db, _uid(SUP[0]))
    finally:
        db.close()
    assert any(u.id == _uid(SUP2[0]) for u in delegates), (
        "التفويض لا يوسّع دائرة المعتمِدين — الكتابة بلا أثر"
    )
    # والمحرّك يمرّ بهذا الباب نفسه لا ببابٍ ثانٍ.
    assert "expand_approvers_with_delegates" in inspect.getsource(workflow)


def test_the_screen_offers_no_scope_control():
    """**ولا ضابط نطاق بقصد**: العمود يُخزَّن ولا يقرؤه أحد.

    قائمة «الإجازات فقط» كانت ستَعِد بتقييد لا يفرضه شيء — وهو أسوأ من
    غياب الخيار، لأنه يبدو مضبوًطا. فالصفحة تقول ما يشمله التفويض بدل
    أن تدّعي حصره.
    """
    page = PAGE.read_text(encoding="utf-8")
    assert "dlg_scope_note" in page, "لا شرح لما يشمله التفويض"
    assert 'value="leave"' not in page and "scope_type" not in page, (
        "ظهر ضابط نطاق — تحقّق أوًلا أن المحرّك صار يقرأ scope"
    )
    # والدعوى تُقاس لا تُفترَض: لا قارئ لـ``scope`` خارج التخزين.
    src = inspect.getsource(delegation) + inspect.getsource(workflow)
    assert ".scope" not in src, (
        "صار للنطاق قارئ — أعد النظر في إخفاء الضابط"
    )


def test_the_screen_has_a_way_in():
    """وشاشة بلا رابط غير موجودة عملًيا."""
    app = APP.read_text(encoding="utf-8")
    assert 'to="/delegations"' in app and 'path="/delegations"' in app
    assert "import Delegations" in app


def test_every_label_exists_in_both_languages():
    """ونصٌّ ناقص في لغة يظهر مفتاًحا خاًما على الشاشة."""
    import re

    page = PAGE.read_text(encoding="utf-8")
    i18n = I18N.read_text(encoding="utf-8")
    keys = set(re.findall(r't\("(dlg_[a-z_0-9]+)"\)', page))
    assert keys, "لا مفاتيح — تحقّق من الشاشة"
    for k in sorted(keys):
        at = i18n.find(f"{k}: {{")
        assert at >= 0, f"المفتاح «{k}» غير معرَّف"
        nxt = re.search(r"\n  [a-z_0-9]+: ", i18n[at + len(k):])
        entry = i18n[at:at + len(k) + (nxt.start() if nxt else 400)]
        assert "ar:" in entry and "en:" in entry, f"«{k}» ناقص في إحدى اللغتين"


def test_no_label_key_is_defined_twice():
    """ومفتاح معرَّف مرّتين يفوز فيه الأخير بصمت."""
    import collections
    import re

    keys = re.findall(r"^  ([a-z_0-9]+):\s*\{",
                      I18N.read_text(encoding="utf-8"), re.M)
    dupes = [k for k, n in collections.Counter(keys).items() if n > 1]
    assert not dupes, f"مفاتيح مكرَّرة: {dupes}"


def test_no_label_leaks_markdown():
    """ونصّ الواجهة يُعرَض كما هو — لا يُفسَّر.

    كتبتُ ``**كل**`` في شرح النطاق ظًنا أنها تُشدَّد، فظهرت النجمات
    خاًما على الشاشة. والقياس البصري أمسكها لا المترجم: كل ما في الملف
    نصٌّ سليم عند الفحص، وأثره على العين خطأ.
    """
    import re

    text = I18N.read_text(encoding="utf-8")
    leaks = re.findall(r'(?:ar|en): "([^"]*\*\*[^"]*)"', text)
    assert not leaks, f"ماركداون في نصّ يُعرَض حرفًيا: {leaks[:3]}"


def test_the_screen_sends_utc_and_shows_local():
    """**فارق التوقيت ليس تفصيًلا**: أفسد الميزة كاملة قبل إصلاحه.

    الخادم يخزّن بالـUTC ويقارن بـ``utcnow()``، وحقل ``datetime-local``
    يعطي توقيت الجهاز. فتفويض يبدأ «الآن» في الكويت كان يُخزَّن متقدًما
    ثلاث ساعات: **لا يسري، ويختفي من القائمة الافتراضية** — فيظنّ
    المستخدم أن الحفظ فشل ويعيده.

    ولم يكن أي اختبار ليمسكها: الخادم سليم، والشاشة سليمة، والعطل في
    الحدّ بينهما. أمسكه القياس الحيّ: الخادم عند 21:22Z والصفّ يبدأ
    00:21 — إزاحة الكويت بالضبط.
    """
    page = PAGE.read_text(encoding="utf-8")
    assert "toISOString" in page, "الشاشة ترسل توقيًتا محلًيا إلى خادم يقارن بالـUTC"
    assert "`${iso}Z`" in page, "ما يعود ساذًجا يُقرأ محلًيا فيُعرض متأخًرا"


def test_the_server_still_compares_in_utc():
    """وتحويل الشاشة مبنيٌّ على اصطلاح الخادم — فإن تغيّر وجب معه.

    قاعدة واحدة موزَّعة على طرفين: هذا الحارس هو الرابط بينهما.
    """
    from app.routers import delegations as dl

    # وللـUTC صيغتان في الشيفرة: ``utcnow()`` الساذجة في المسار،
    # و``now(timezone.utc)`` الواعية في الوحدة. كلتاهما UTC — والحارس
    # على **الاصطلاح** لا على تهجئته. (أول كتابة سقطت لأنها حرفية.)
    for mod in (inspect.getsource(dl), inspect.getsource(delegation)):
        assert "utcnow()" in mod or "timezone.utc" in mod, (
            "تغيّر اصطلاح وقت الخادم — أعد النظر في تحويل الشاشة"
        )


def test_revoking_stops_the_delegation_and_keeps_the_record(client):
    """والإلغاء يُوقف الأثر فوًرا ولا يمحو السجل (R6).

    فمن سافر وعاد مبكًرا يستعيد قراره في الحال، ويبقى مكتوًبا من اعتمد
    نيابًة عنه ومتى.
    """
    hdr = auth_headers(login(client, *SUP))
    now = datetime.utcnow()
    made = client.post("/api/delegations", headers=hdr, json={
        "delegate_user_id": _uid(SUP2[0]),
        "starts_at": (now - timedelta(hours=1)).isoformat(),
        "ends_at": (now + timedelta(days=1)).isoformat(),
        "reason": "قياس الإلغاء"}).json()["id"]

    # القياس على **الفارق** لا على الغياب المطلق: اختبارات أخرى في هذه
    # الوحدة تترك تفويضات قائمة للمفوِّض نفسه، فأول كتابة سقطت على
    # ``[8, 8]`` — والعيب كان في دعوى الاختبار لا في الإلغاء.
    db = SessionLocal()
    try:
        before = len(delegation.active_delegates_for(db, _uid(SUP[0])))
    finally:
        db.close()
    assert before >= 1

    r = client.post(f"/api/delegations/{made}/revoke", headers=hdr)
    assert r.status_code == 200, r.text[:200]

    db = SessionLocal()
    try:
        after = len(delegation.active_delegates_for(db, _uid(SUP[0])))
        row = db.get(models.ApprovalDelegation, made)
    finally:
        db.close()
    assert after == before - 1, f"الإلغاء لم يوقف الأثر: {before} ← {after}"
    assert row is not None and row.revoked_at, "الإلغاء محا السجل بدل أن يوثّقه"


def test_nobody_revokes_a_delegation_that_is_not_theirs(client):
    """ولا يُلغي أحٌد تفويض غيره: الخادم يفحص، والزرّ يتبعه."""
    hdr = auth_headers(login(client, *SUP))
    now = datetime.utcnow()
    made = client.post("/api/delegations", headers=hdr, json={
        "delegate_user_id": _uid(SUP2[0]),
        "starts_at": now.isoformat(),
        "ends_at": (now + timedelta(days=1)).isoformat()}).json()["id"]

    other = auth_headers(login(client, *EMP))
    assert client.post(f"/api/delegations/{made}/revoke",
                       headers=other).status_code == 403

    page = PAGE.read_text(encoding="utf-8")
    assert "mine(r) || onBehalf" in page, (
        "الزرّ يظهر لمن سيُرفض طلبه"
    )
