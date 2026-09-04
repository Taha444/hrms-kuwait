# -*- coding: utf-8 -*-
"""P3-15 — للتوقيع طريق واحد، والطريق الثاني كان لا يصل.

**ما ظهر بالقياس، لا ما وصفه البند:**

REQSIG لم يكن مساًرا موازًيا يُركّب توقيًعا بطريقة ثانية — كان مساًرا
**لا يصل**. أنشأه الموظف بمرفق توقيعه وسببه، واعتمده HR، فرُدّ الطلب
``completed``… والتوقيع بعده ``signature_path=None`` و``version=0``
وسجلّ النسخ **صفر**. لا شيء وقع، والشاشة تقول «مكتمل».

وأخطر ما فيه أن الواجهة كانت تقوده إليه: زرّ «استبدال التوقيع» في
الملف الشخصي ينقل الموظف إلى نموذج REQSIG. فالباب المعروض معطَّل،
والباب العامل (``POST /me/signature`` بسبب) لا يصل إليه أحد.

**ولم يُوصَل اعتماد REQSIG بتركيب التوقيع**، لأن ذلك يصنع المسار
الموازي الذي يحذّر منه البند حًقا: كاتب ثانٍ لسجلّ نسخ التوقيع —
والتوقيع دليل يُحتجّ به على كل مستند وُقِّع سابًقا.
"""
from __future__ import annotations

import inspect

from sqlalchemy import func, select

from app import models, module_owned
from app.database import SessionLocal
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
HR = ("100000000002", "hr12345")

REQSIG_PAYLOAD = {"change_reason": "improve", "reason": "توقيع غير واضح",
                  "_attachments": ["signature"]}


def _emp_id(db, civil_id: str) -> int:
    return db.scalar(select(models.Employee.id).where(
        models.Employee.civil_id == civil_id))


def test_the_declaration_names_where_to_go_not_only_that_it_is_blocked():
    """من يُمنع بلا وجهة يعيد المحاولة أو يستسلم — وحاجته تبقى قائمة."""
    info = module_owned.owning_module("REQSIG")
    assert info, "REQSIG غير معلَن كموضوع تملكه وحدة التوقيع"
    msg = module_owned.rejection_message("REQSIG")
    assert info["where"] in msg, f"الرسالة بلا وجهة: {msg}"
    assert "التوقيع" in msg


def test_creating_reqsig_is_refused_with_a_destination(client):
    """**جوهر البند**: الباب المسدود يُقفَل ويُشار إلى الباب العامل."""
    db = SessionLocal()
    try:
        eid = _emp_id(db, EMP[0])
    finally:
        db.close()
    hdr = auth_headers(login(client, *EMP))
    r = client.post("/api/requests", headers=hdr, json={
        "employee_id": eid, "request_type_code": "REQSIG",
        "payload_json": REQSIG_PAYLOAD})
    assert r.status_code == 409, (
        f"REQSIG ما زال يُقبل: {r.status_code} {r.text[:200]}"
    )
    detail = r.json().get("detail") or {}
    assert detail.get("code") == "MODULE_OWNED_SUBJECT", detail
    assert detail.get("where"), "رفض بلا وجهة"


def test_hr_cannot_open_it_either(client):
    """ولا يفتحه HR: الطريق معطَّل لكل الأدوار لا للموظف وحده."""
    db = SessionLocal()
    try:
        eid = _emp_id(db, EMP[0])
    finally:
        db.close()
    hdr = auth_headers(login(client, *HR))
    r = client.post("/api/requests", headers=hdr, json={
        "employee_id": eid, "request_type_code": "REQSIG",
        "payload_json": REQSIG_PAYLOAD})
    assert r.status_code == 409, f"{r.status_code} {r.text[:200]}"


def test_it_is_gone_from_the_creatable_catalogue(client):
    """والكتالوج لا يَعرض ما يرفضه الخادم — وهو ما وقع قبل توحيد القاعدة."""
    hdr = auth_headers(login(client, *EMP))
    # نفس ما تطلبه شاشة «طلب جديد» بالضبط (Requests.tsx): قياسها بمعاملات
    # أخرى يفحص كتالوًجا لا يراه أحد.
    rows = client.get("/api/requests/types", headers=hdr,
                      params={"creatable_only": True}).json()
    rows = rows if isinstance(rows, list) else rows.get("items", [])
    codes = {c.get("code") for c in rows}
    assert codes, "كتالوج فارغ — القياس بلا معنى"
    assert "REQSIG" not in codes, "REQSIG ما زال معروًضا في «طلب جديد»"


def test_the_catalogue_and_the_server_agree(client):
    """الادّعاء الجامع: كل ما يُعرض يُقبل — لا باب معروض مسدود.

    القياس على الإعلان لا على كود بعينه: أي موضوع يُسنَد غًدا لوحدة
    مستقلة يختفي من الكتالوج يوم يُعلَن، لا يوم يتذكّره أحد.
    """
    hdr = auth_headers(login(client, *EMP))
    rows = client.get("/api/requests/types", headers=hdr,
                      params={"creatable_only": True}).json()
    rows = rows if isinstance(rows, list) else rows.get("items", [])
    shown = {c.get("code") for c in rows}
    owned = set(module_owned.MODULE_OWNED)
    assert not (shown & owned), f"معروض ومرفوض مًعا: {shown & owned}"


def test_the_historical_requests_are_still_readable(client):
    """والطلبات القديمة تبقى مقروءة: المنع على الإنشاء لا على القراءة."""
    hdr = auth_headers(login(client, *HR))
    r = client.get("/api/requests/types", headers=hdr,
                   params={"creatable_only": False})
    assert r.status_code == 200, r.text
    rows = r.json()
    rows = rows if isinstance(rows, list) else rows.get("items", [])
    codes = {c.get("code") for c in rows}
    assert "REQSIG" in codes, (
        "اختفى النوع من الكتالوج الكامل — فتصير الطلبات التاريخية بلا اسم"
    )


def test_only_the_signature_module_installs_a_signature():
    """**الحارس ضد الغد**: كاتب ثانٍ للتوقيع لا يظهر بصمت.

    لو وُصِل اعتماد REQSIG بتركيب التوقيع، لصار السجلّ غير القابل
    للتعديل يُكتب من موضعين: أحدهما يرفع النسخة ويدقّق، والآخر يقلّده.
    وسجلّ دليل يُحتجّ به لا يحتمل كاتًبا ثانًيا.
    """
    from app import workflow
    from app.routers import requests as req_router

    for mod in (workflow, req_router):
        src = inspect.getsource(mod)
        assert "signature_path =" not in src, (
            f"{mod.__name__} يكتب signature_path — التركيب لوحدة التوقيع وحدها"
        )
        assert "pending_signature_path =" not in src, (
            f"{mod.__name__} يكتب توقيًعا معلًَّقا خارج وحدة التوقيع"
        )


def test_the_working_path_still_works(client):
    """ولم يُقفل الباب العامل — أًيا كانت حالة الموظف قبله.

    ادّعاء المنع بلا هذا نصف قياس: قد يكون الطريقان مقفولَين مًعا.

    ولا يفترض ملًفا بلا توقيع: اختبار آخر يرفع توقيع الموظف نفسه قبله،
    فيصير الرفع **استبداًلا** يستوجب سبًبا — ومحاولتي الأولى سقطت بذلك
    لا بالمنع الذي تقيسه. فيُرسَل السبب دائًما، ويُقاس الفرعان مًعا:
    أول رفع يُركَّب ويُسجَّل، والاستبدال يصير معلًَّقا بسببه.
    """
    import io as _io

    from PIL import Image, ImageDraw

    # حبر حقيقي: الخادم يرفض الصورة البيضاء بـ«لم يُكتشف توقيع» — وهو
    # فحص سليم سقطت به محاولة أخرى قبل هذه.
    img = Image.new("RGB", (240, 90), "white")
    d = ImageDraw.Draw(img)
    d.line([(20, 70), (70, 20), (120, 70), (170, 25), (215, 60)],
           fill=(10, 10, 40), width=5)
    buf = _io.BytesIO()
    img.save(buf, format="PNG")

    db = SessionLocal()
    try:
        u = db.scalar(select(models.User).where(models.User.civil_id == EMP[0]))
        had_one = bool(u.signature_path)
        uid = u.id
    finally:
        db.close()

    hdr = auth_headers(login(client, *EMP))
    r = client.post("/api/me/signature?reason=فحص+الطريق+العامل", headers=hdr,
                    files={"file": ("sig.png", buf.getvalue(), "image/png")})
    assert r.status_code == 201, f"الباب العامل مقفول أيًضا: {r.text[:200]}"

    db = SessionLocal()
    try:
        u = db.get(models.User, uid)
        rows = db.scalar(select(func.count()).select_from(
            models.UserSignatureVersion).where(
                models.UserSignatureVersion.user_id == uid))
        path, ver, pending = u.signature_path, u.signature_version, u.pending_signature_path
        reason = u.pending_signature_reason
    finally:
        db.close()

    if had_one:
        # استبدال: القديم يبقى ساًريا والجديد ينتظر اعتماد HR بسببه.
        assert pending, "استبدال بلا نسخة معلَّقة"
        assert reason, "استبدال معلَّق بلا سبب مسجَّل"
        assert path, "أُلغي التوقيع الساري أثناء الاستبدال"
    else:
        # أول رفع: يُركَّب مباشرة ويُكتب في سجلّ النسخ.
        assert path and ver >= 1, f"لم يُركَّب التوقيع: path={path} ver={ver}"
        assert rows >= 1, "رُكِّب التوقيع بلا سطر في سجلّ النسخ"
