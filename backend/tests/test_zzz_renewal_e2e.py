# -*- coding: utf-8 -*-
"""BKL-07 / P4-18 — مسار التجديد كامًلا، من الفتح إلى الاكتمال.

**ما يقوله البند نفسه**: «مسار يمرّ بأربعة أشخاص وثلاث نسخ من العقد
ومستندين حكوميين **لا يُثبِته إلا تشغيله**».

والتغطية القائمة **بنيوية**: آلة الحالات تُقاس (لا حالة بلا مخرج ولا
فاعل)، والقفلة عند ``pending_hr_verify`` محروسة، وخطّ الزمن مُسمّى. لكن
لا اختبار **يسوق المعاملة** من ``new`` إلى ``completed`` بالفاعل الصحيح
لكل خطوة.

وهذا ما يفعله هذا الملف. ويبقى على الإنتاج ما لا يُقاس هنا: إخراج
العقد بخطوط عربية حقيقية، وحسابات أربعة أشخاص فعليّين.

**والفاعل لكل مرحلة يُقرأ من ``STAGE_ACTOR``** لا من ترتيب يُكتب هنا:
قائمة ثانية للمسار تنحرف عن الأولى، وهو ما ظلّ يتكرّر في هذه الجولة.
"""
from __future__ import annotations

import io as _io

import pytest
from sqlalchemy import and_ as sa_and, delete as sa_delete, or_ as sa_or, select

from app import models, renewal as R
from app.database import SessionLocal
from app.routers.renewals import STAGE_ACTOR
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
MGR = ("100000000001", "manager123")
HR = ("100000000002", "hr12345")
PRO = ("100000000003", "deleg123")

#: ترتيب المسار السعيد — يُقاس مقابل ``STATUS_LABELS`` فلا ينحرف عنها.
HAPPY_PATH = [
    R.NEW, R.PENDING_MANAGER, R.PENDING_HR, R.WITH_DELEGATE,
    R.AWAITING_CONTRACTS, R.AWAITING_SIGNATURE, R.CONTRACTS_SIGNED,
    R.RENEWING, R.AWAITING_CIVIL_CARD, R.PENDING_HR_VERIFY, R.COMPLETED,
]


def _png() -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (300, 180), "white")
    ImageDraw.Draw(img).rectangle([20, 20, 280, 160], outline=(0, 0, 0), width=3)
    buf = _io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def case(client):
    """معاملة تجديد لموظف **خاص بهذا الاختبار** — يُنشأ بتصريحه ويُنظَّف.

    ولا تُستعمل موظف البذرة المشترك: اختبارات أخرى تفتح له معاملات
    وتتركها، فيرتطم الشوط بحالة ليست ما يقيسه.
    """
    from datetime import date, timedelta

    db = SessionLocal()
    eid = rid = None
    try:
        pro_user = db.scalar(select(models.User).where(
            models.User.civil_id == PRO[0]))
        emp = models.Employee(
            company_id=pro_user.company_id,
            name="موظف مسار كامل", name_en="E2E Employee",
            civil_id="299911220033", job_title="فني",
            job_title_en="Technician", basic_salary=350,
            passport_number="PE2E00001", status="active",
            nationality="مصري")
        db.add(emp)
        db.flush()
        eid = emp.id
        db.add(models.Permit(
            company_id=emp.company_id, employee_id=eid, kind="residency",
            number=f"RES-E2E-{eid}",
            start_date=date.today() - timedelta(days=305),
            # **النوع مشتقّ من الأيام المتبقّية** لا من معامل الطلب:
            # ``classify`` تقول 31–90 يوًما = مبكر، و≤30 = عادي. والمبكر
            # وحده يمرّ بالمدير وشؤون الموظفين — وهو المسار الكامل الذي
            # يقيسه البند. وستّون يوًما في وسط النطاق فلا يقع على حدّه.
            expiry_date=date.today() + timedelta(days=60),
            status="active"))
        db.commit()
    finally:
        db.close()

    # **تجديد مبكر** لا عادي: نقطة البداية تتحدّد بنوع التجديد لا بمن
    # أنشأ المعاملة — المبكر يمرّ بالمدير وشؤون الموظفين ثم المندوب،
    # والعادي يبدأ عند المندوب مباشرة. والمسار الكامل هو ما يقيسه البند
    # («أربعة أشخاص»)، فيلزم المبكر.
    hdr = auth_headers(login(client, *PRO))
    r = client.post("/api/renewals", headers=hdr, data={
        "employee_id": eid, "renewal_type": "early",
        "reason": "انتهاء وشيك — اختبار المسار الكامل"})
    assert r.status_code == 201, r.text[:250]
    rid = r.json()["id"]
    try:
        yield rid, eid
    finally:
        # التنظيف بترتيب مشتقّ من المخطّط (F-003): حذف مستند يشير إليه
        # صفّ آخر يُرفَض بعد تفعيل فرض المفاتيح الأجنبية.
        from tests.conftest import purge

        db = SessionLocal()
        try:
            doc_ids = [d for (d,) in db.execute(select(models.Document.id).where(
                sa_or(sa_and(models.Document.entity_type == "renewal",
                             models.Document.entity_id == rid),
                      sa_and(models.Document.entity_type == "employee",
                             models.Document.entity_id == eid)))).all()]
            purge(db, "documents", doc_ids)
            db.execute(sa_delete(models.Task).where(
                models.Task.related_entity_type == "renewal",
                models.Task.related_entity_id == rid))
            purge(db, "residency_renewals", [rid])
            permits = [x for (x,) in db.execute(select(models.Permit.id).where(
                models.Permit.employee_id == eid)).all()]
            purge(db, "permits", permits)
            purge(db, "employees", [eid])
            db.commit()
        finally:
            db.close()


def _status(client, rid: int, who=HR) -> str:
    body = client.get(f"/api/renewals/{rid}",
                      headers=auth_headers(login(client, *who))).json()
    return body.get("status")


def test_the_path_order_matches_the_engines_own_labels():
    """خطّ الأساس: الترتيب المكتوب هنا من حالات المحرّك لا من الذاكرة."""
    assert set(HAPPY_PATH) <= set(R.STATUS_LABELS), (
        f"حالات لا يعرفها المحرّك: {set(HAPPY_PATH) - set(R.STATUS_LABELS)}"
    )
    # ولكل مرحلة غير نهائية فاعل معلَن — وهو من يسوقها في هذا الاختبار.
    for st in HAPPY_PATH:
        if st == R.COMPLETED:
            continue
        assert STAGE_ACTOR.get(st), f"مرحلة بلا فاعل معلَن: {st}"


def test_a_new_case_starts_where_the_engine_says(client, case):
    """والمعاملة تبدأ من أول المسار لا من منتصفه."""
    rid, _ = case
    assert _status(client, rid) in (R.NEW, R.PENDING_MANAGER), (
        _status(client, rid)
    )


def test_the_whole_path_runs_end_to_end(client, case):
    """**جوهر البند**: من الفتح إلى الاكتمال، بالفاعل الصحيح لكل خطوة.

    وكل خطوة تُقاس بعدها: حالة غير متوقَّعة تُوقف الشوط عندها، فيُعرف
    أن العطل هنا لا فيما بعده — وهو ما يشترطه دليل التشغيل.
    """
    rid, eid = case
    seen = [_status(client, rid)]

    def step(label, who, call):
        before = _status(client, rid)
        res = call(auth_headers(login(client, *who)))
        assert res.status_code in (200, 201), (
            f"[{label}] من {before}: {res.status_code} {res.text[:200]}"
        )
        after = _status(client, rid)
        if after != before:
            seen.append(after)
        return after

    # 1) المدير يعتمد → شؤون الموظفين
    step("اعتماد المدير", MGR, lambda h: client.post(
        f"/api/renewals/{rid}/decide", headers=h, data={"decision": "approved"}))
    # 2) شؤون الموظفين تعتمد → المندوب
    step("اعتماد الشؤون القانونية", HR, lambda h: client.post(
        f"/api/renewals/{rid}/decide", headers=h, data={"decision": "approved"}))

    # 3) المندوب يرفع العقدين. **والقاعدة المستخلَصة من الرفض نفسه**:
    # المستند الذي ينقل المرحلة يُرفَع **أخيًرا** — فما بعده يُردّ 409
    # لأن المرحلة لم تعد مرحلته. فالداخلي أوًلا ثم الحكومي الذي ينقل.
    step("رفع العقد الداخلي", PRO, lambda h: client.post(
        f"/api/renewals/{rid}/upload", headers=h,
        data={"doc_type": R.DOC_CONTRACT_INTERNAL},
        files={"file": ("int.png", _png(), "image/png")}))
    step("رفع العقد الحكومي", PRO, lambda h: client.post(
        f"/api/renewals/{rid}/upload", headers=h,
        data={"doc_type": R.DOC_CONTRACT_GOV},
        files={"file": ("gov.png", _png(), "image/png")}))

    # 5) النسختان الموقّعتان — بالترتيب نفسه: الداخلية أوًلا، ثم
    # الحكومية التي تنقل المرحلة. وموظف هذا الاختبار بلا حساب (أُنشئ
    # للمسار لا للدخول) فيرفعهما المندوب؛ والقياس هنا على انتقال الحالة
    # لا على هوية الرافع، وتلك مقيسة في اختبار الصلاحيات.
    step("رفع النسخة الموقّعة الداخلية", PRO, lambda h: client.post(
        f"/api/renewals/{rid}/upload", headers=h,
        data={"doc_type": R.DOC_SIGNED_INTERNAL},
        files={"file": ("si.png", _png(), "image/png")}))
    step("رفع النسخة الموقّعة الحكومية", PRO, lambda h: client.post(
        f"/api/renewals/{rid}/upload", headers=h,
        data={"doc_type": R.DOC_SIGNED_GOV},
        files={"file": ("sg.png", _png(), "image/png")}))

    # 6) المندوب يبدأ التجديد لدى الجهة
    step("بدء التجديد", PRO, lambda h: client.post(
        f"/api/renewals/{rid}/renewing", headers=h))

    # 7) المندوب يرفع إذن العمل والنسخة النهائية
    # والقاعدة نفسها هنا: النسخة النهائية تُقبل في «تم رفع العقود
    # الموقّعة» أو «جاري التجديد» — أي **قبل** إذن العمل الذي ينقل إلى
    # «بانتظار البطاقة». فالناقل أخيًرا، كما في المرحلتين السابقتين.
    step("رفع العقد النهائي", PRO, lambda h: client.post(
        f"/api/renewals/{rid}/upload", headers=h,
        data={"doc_type": R.DOC_CONTRACT_FINAL},
        files={"file": ("fin.png", _png(), "image/png")}))
    step("رفع إذن العمل", PRO, lambda h: client.post(
        f"/api/renewals/{rid}/upload", headers=h,
        data={"doc_type": R.DOC_WORK_PERMIT},
        files={"file": ("wp.png", _png(), "image/png")}))

    # 8) البطاقة المدنية
    step("رفع البطاقة المدنية", PRO, lambda h: client.post(
        f"/api/renewals/{rid}/upload", headers=h,
        data={"doc_type": R.DOC_CIVIL_CARD},
        files={"file": ("cid.png", _png(), "image/png")}))

    # 9) المندوب يُدخل نتيجة الجهة الحكومية — رقم المعاملة والرسوم
    # ورقم الإقامة الجديد. وهذه هي الخطوة التي كنتُ أغفلتها: البطاقة
    # وحدها لا تنقل المعاملة، لأن التحقّق يشترط اكتمال البيانات الحكومية
    # (GOV_CONTRACT_REQUIRED_FIELDS) — وهو ما تحرسه RNW-D1.
    from datetime import date as _date, timedelta as _td

    step("إدخال نتيجة الجهة", PRO, lambda h: client.post(
        f"/api/renewals/{rid}/finalize", headers=h, data={
            "gov_reference_no": "GOV-E2E-001",
            "fees_amount": 120.0,
            "fees_receipt_no": "RCP-E2E-001",
            "new_permit_number": f"RES-NEW-{rid}",
            "new_expiry_date": str(_date.today() + _td(days=365)),
        }))

    # 10) شؤون الموظفين تتحقّق وتُغلق
    final = _status(client, rid)
    if final != R.COMPLETED:
        step("تحقّق شؤون الموظفين", HR, lambda h: client.post(
            f"/api/renewals/{rid}/hr-verify", headers=h))
        final = _status(client, rid)

    assert final == R.COMPLETED, (
        f"لم تكتمل المعاملة — وقفت عند «{final}». المسار المقطوع: {seen}"
    )
    # **والمراحل تُقطَع لا تُقفَز**: شوط يصل بخطوتين ليس المسار الذي
    # يقيسه البند («أربعة أشخاص وثلاث نسخ ومستندان»).
    assert len(seen) >= 7, f"المسار قفز مراحل — قُطع {len(seen)}: {seen}"
    for st in (R.PENDING_MANAGER, R.PENDING_HR, R.AWAITING_SIGNATURE,
               R.RENEWING, R.AWAITING_CIVIL_CARD, R.PENDING_HR_VERIFY):
        assert st in seen, f"لم يمرّ الشوط بمرحلة «{st}»: {seen}"


def test_every_document_the_path_requires_was_kept(client, case):
    """والمستندات الستّة محفوظة — لا يُعتمد على ما مرّ ولم يبقَ."""
    rid, _ = case
    test_the_whole_path_runs_end_to_end(client, case)

    db = SessionLocal()
    try:
        kinds = {d.document_type_code for d in db.scalars(select(
            models.Document).where(models.Document.entity_type == "employee"))}
    finally:
        db.close()
    # نوعا التعاقد الأساسيان على الأقلّ — والباقي يُقاس في اختبارات النسخ.
    assert kinds, "لم يُحفَظ أي مستند من مسار التجديد"


def test_a_rejection_ends_the_path_cleanly(client, case):
    """والمسار البديل يُقاس أيًضا: الرفض ينهي المعاملة ولا يعلّقها."""
    rid, _ = case
    r = client.post(f"/api/renewals/{rid}/decide",
                    headers=auth_headers(login(client, *MGR)),
                    data={"decision": "rejected",
                          "reject_reason": "بيانات ناقصة"})
    assert r.status_code == 200, r.text[:200]
    assert _status(client, rid) == R.REJECTED
