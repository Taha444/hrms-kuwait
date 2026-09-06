# -*- coding: utf-8 -*-
"""P0 — إرسالان متطابقان لا يصيران طلبين.

**العطل**: قِيس على البناء الحالي — ثلاث ضغطات على الزرّ نفسه أنتجت
**ثلاثة طلبات حيّة**، كلٌّ منها يدخل دورة اعتماد مستقلة. والسبب المعتاد
ليس سوء نية: ضغطة مزدوجة، أو إعادة محاولة بعد انقطاع شبكة، أو تحديث
الصفحة بعد الإرسال.

**والحماية على الإرسال الواحد لا على الطلب القائم مطلًقا**: الضغطة
المزدوجة تُنتج طلًبا **لم يمسّه أحد** — في مرحلته الأولى، بلا قرار
مسجَّل، وقبل دقائق. وما تجاوز ذلك طلٌب حيٌّ قائم بذاته.

وأول كتابة لهذا الحارس أهملت القيد الأخير فأعادت طلًبا في مرحلته
الثالثة كأنه جديد — فوصل المستخدم طلٌب لا يستطيع أحد اتخاذ قرار فيه.
والقياس هو الذي كشفه: أربعة عشر اختباًرا سقطت.

وبعد الرفض أو الإلغاء تُقبل إعادة التقديم — حالة مشروعة لا تكرار.

**ويُعاد الطلب القائم لا خطأ**: إعادة المحاولة بعد انقطاع يجب أن تنجح،
ورسالة فشل تدفع المستخدم إلى محاولة ثالثة.

**والفحص قبل الإدراج لا يكفي** — طلبان في اللحظة نفسها يجتازانه معًا.
فالقيد الفريد الجزئي في القاعدة هو ما يحسم السباق.
"""
from __future__ import annotations

from sqlalchemy import func, select

from app import models, workflow
from app.database import SessionLocal
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
MGR = ("100000000001", "manager123")


def _emp_id() -> int:
    db = SessionLocal()
    try:
        return db.scalar(select(models.Employee.id).where(
            models.Employee.civil_id == EMP[0]))
    finally:
        db.close()


def _body(**over):
    return {"employee_id": _emp_id(), "request_type_code": "REQLV",
            "payload_json": {"start_date": "2029-03-01", "end_date": "2029-03-03",
                             "days": 3, "leave_type": "unpaid",
                             "reason": "قياس التكرار", **over}}


def test_three_identical_submissions_make_one_request(client):
    """**جوهر العطل**: ثلاث ضغطات كانت ثلاثة طلبات."""
    hdr = auth_headers(login(client, *EMP))
    body = _body()
    out = [client.post("/api/requests", headers=hdr, json=body) for _ in range(3)]
    assert all(r.status_code == 201 for r in out), [r.status_code for r in out]
    ids = {r.json()["id"] for r in out}
    assert len(ids) == 1, f"تولّدت طلبات متعدّدة: {ids}"


def test_a_different_request_still_passes(client):
    """ولا يُحجَب المختلف: الحارس على التطابق لا على النوع."""
    hdr = auth_headers(login(client, *EMP))
    first = client.post("/api/requests", headers=hdr,
                        json=_body(reason="سبب أول")).json()["id"]
    second = client.post("/api/requests", headers=hdr,
                         json=_body(reason="سبب ثانٍ")).json()["id"]
    assert first != second, "حُجب طلب مختلف"


def test_resubmission_is_allowed_once_the_first_is_closed(client):
    """**وبعد الإغلاق يُقبل مثله**: إعادة التقديم بعد رفض حالة مشروعة.

    ولولا أن القيد **جزئي** لبقي الرفض مانًعا للأبد.
    """
    hdr = auth_headers(login(client, *EMP))
    body = _body(start_date="2029-04-01", end_date="2029-04-02", days=2)
    first = client.post("/api/requests", headers=hdr, json=body).json()["id"]

    # إلغاء المدير يُغلق الطلب
    r = client.post(f"/api/requests/{first}/cancel?note=قياس",
                    headers=auth_headers(login(client, *MGR)))
    assert r.status_code == 200, r.text[:200]

    again = client.post("/api/requests", headers=hdr, json=body)
    assert again.status_code == 201, again.text[:200]
    assert again.json()["id"] != first, "أُعيد الطلب الملغى بدل إنشاء جديد"


def test_the_fingerprint_ignores_key_order():
    """وحمولتان متطابقتان بترتيب مختلف بصمٌة واحدة.

    ولولا ذلك لأفلت التكرار من فرق في الترتيب لا معنى له.
    """
    a = workflow.request_fingerprint(1, "REQLV", {"x": 1, "y": 2})
    b = workflow.request_fingerprint(1, "REQLV", {"y": 2, "x": 1})
    assert a == b
    assert a != workflow.request_fingerprint(1, "REQLV", {"x": 1, "y": 3})
    assert a != workflow.request_fingerprint(2, "REQLV", {"x": 1, "y": 2})


def test_the_database_itself_refuses_a_duplicate(client):
    """**والفحص وحده لا يكفي**: القيد في القاعدة هو ما يحسم السباق.

    فحصٌ ثم إدراج يمرّ منه طلبان متزامنان معًا. وهذا يقيس القيد مباشرًة
    بمحاولة إدراج صفٍّ ثانٍ بالبصمة نفسها.
    """
    from sqlalchemy.exc import IntegrityError

    hdr = auth_headers(login(client, *EMP))
    body = _body(start_date="2029-05-01", end_date="2029-05-02", days=2)
    rid = client.post("/api/requests", headers=hdr, json=body).json()["id"]

    db = SessionLocal()
    try:
        row = db.get(models.Request, rid)
        assert row.dedup_fingerprint, "الطلب بلا بصمة — القيد لا يحرسه"
        db.add(models.Request(
            company_id=row.company_id, employee_id=row.employee_id,
            requester_user_id=row.requester_user_id,
            request_type_code=row.request_type_code,
            payload_json=row.payload_json, status="pending", current_stage=0,
            dedup_fingerprint=row.dedup_fingerprint))
        try:
            db.commit()
            raised = False
        except IntegrityError:
            db.rollback()
            raised = True
    finally:
        db.close()
    assert raised, "القاعدة قبلت صًفا ثانًيا بالبصمة نفسها"


def test_a_new_request_carries_a_fingerprint(client):
    """والطلب المُنشأ للتوّ يحمل بصمًة — وإلا فهو خارج الحماية.

    **ولا تُطلَب من كل مفتوح**: أول كتابة لهذا الحارس ادّعت ذلك فسقطت،
    والتصميم هو الذي تغيّر لا العكس. فطلٌب تجاوز النافذة أو تحرّك في
    مساره تُرفَع بصمته عمًدا ليخرج من القيد، وإلا مَنع إعادة تقديم
    مشروعة إلى الأبد.
    """
    hdr = auth_headers(login(client, *EMP))
    rid = client.post("/api/requests", headers=hdr,
                      json=_body(start_date="2029-06-01", end_date="2029-06-02",
                                 days=2)).json()["id"]
    db = SessionLocal()
    try:
        row = db.get(models.Request, rid)
        assert row.dedup_fingerprint, "طلب جديد بلا بصمة — خارج الحماية"
        expected = workflow.request_fingerprint(
            row.employee_id, row.request_type_code, row.payload_json)
        assert row.dedup_fingerprint == expected, "بصمة لا تطابق حسابها"
    finally:
        db.close()


def test_a_superseded_fingerprint_is_released(client):
    """**ورفع البصمة مقصود**: بلا ذلك يصير طلٌب قديم مانًعا دائًما.

    تُقاس الآلية لا أثرها العرَضي: طلب متقادم تُرفَع بصمته حين يصل
    إرسال مطابق، فيُنشأ الجديد ولا يُعاد القديم.
    """
    hdr = auth_headers(login(client, *EMP))
    body = _body(start_date="2029-07-01", end_date="2029-07-02", days=2)
    first = client.post("/api/requests", headers=hdr, json=body).json()["id"]

    # نُقدّم عمره خارج النافذة كما لو مضى يوم
    from datetime import datetime, timedelta, timezone

    db = SessionLocal()
    try:
        row = db.get(models.Request, first)
        row.created_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()
    finally:
        db.close()

    second = client.post("/api/requests", headers=hdr, json=body)
    assert second.status_code == 201, second.text[:200]
    assert second.json()["id"] != first, "أُعيد طلب متقادم بدل إنشاء جديد"

    db = SessionLocal()
    try:
        assert db.get(models.Request, first).dedup_fingerprint is None
    finally:
        db.close()
