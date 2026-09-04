# -*- coding: utf-8 -*-
"""P1-03 — المستند المولَّد يدخل ملف الموظف عند صدوره، والطباعة اختيارية.

**ما ظهر بالقياس:**

سُقتُ طلب شهادة راتب إلى الاكتمال. المستند وُلّد فعًلا
(``GENERATED``، مرجع ``REQ-000001-GENERA-v1``) — وأرشيف الموظف بقي على
مستنداته الثلاثة القديمة، ليست الشهادة بينها. الدخول كان يقع **داخل
``mark-filed`` وحدها**، وهي ترفض قبل ``mark-printed``.

**والعطل الثاني يفسّر لماذا لم يُلاحَظ الأول**: مهمة «جاهز للطباعة»
تُنشأ عند الاكتمال ثم يكنسها ``_close_open_tasks`` في اللحظة نفسها —
قرأتُها ``dismissed``. فالطريق الوحيد إلى الأرشيف كان يُغلق قبل أن
يُفتح، وأثره أن ملف الموظف يبقى ناقًصا بلا أن يشتكي أحد.
"""
from __future__ import annotations

from sqlalchemy import select

from app import doc_archive, models, task_kinds
from app.database import SessionLocal
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
HR = ("100000000002", "hr12345")

CERT_PAYLOAD = {"purpose": "بنك", "reason": "فتح حساب",
                "language": "ar", "addressed_to": "بنك الخليج"}


def _emp_id(db) -> int:
    return db.scalar(select(models.Employee.id).where(
        models.Employee.civil_id == EMP[0]))


def _archived(db, eid: int, type_code: str):
    return db.scalars(select(models.Document).where(
        models.Document.entity_type == "employee",
        models.Document.entity_id == eid,
        models.Document.document_type_code == type_code)).all()


def _complete_a_certificate(client) -> tuple[int, int]:
    """يسوق طلب شهادة راتب إلى الاكتمال، ويعيد (رقم الطلب، رقم الموظف)."""
    db = SessionLocal()
    try:
        eid = _emp_id(db)
    finally:
        db.close()
    hdr = auth_headers(login(client, *EMP))
    r = client.post("/api/requests", headers=hdr, json={
        "employee_id": eid, "request_type_code": "REQCERTSAL",
        "payload_json": CERT_PAYLOAD})
    assert r.status_code == 201, r.text[:200]
    rid = r.json()["id"]

    hh = auth_headers(login(client, *HR))
    for _ in range(6):
        a = client.post(f"/api/requests/{rid}/decide", headers=hh,
                        json={"decision": "approved"})
        assert a.status_code == 200, a.text[:200]
        st = client.get(f"/api/requests/{rid}", headers=hh).json().get("status")
        if st in ("completed", "cancelled", "rejected"):
            assert st == "completed", st
            break
    return rid, eid


def test_the_document_is_really_generated(client):
    """خطّ الأساس: بلا مستند مولَّد يكون ما بعده قياًسا على فراغ."""
    rid, _ = _complete_a_certificate(client)
    db = SessionLocal()
    try:
        docs = db.scalars(select(models.RequestDocument).where(
            models.RequestDocument.request_id == rid)).all()
    finally:
        db.close()
    assert docs, "لم يُولَّد مستند للطلب"
    assert any(d.lifecycle_status == "GENERATED" and d.file_path for d in docs), \
        [(d.kind, d.lifecycle_status) for d in docs]


def test_it_enters_the_employee_file_without_anyone_printing(client):
    """**جوهر البند**: الصدور هو الدخول — لا انتظار لضغطة «طُبع»."""
    rid, eid = _complete_a_certificate(client)
    type_code = doc_archive.archive_type_code("REQCERTSAL")

    db = SessionLocal()
    try:
        rows = _archived(db, eid, type_code)
        rdoc = db.scalar(select(models.RequestDocument).where(
            models.RequestDocument.request_id == rid))
        print_status = rdoc.print_status if rdoc else None
    finally:
        db.close()

    assert print_status != "filed", (
        "أُرشف يدوًيا داخل الاختبار — القياس لا يقيس التلقائية"
    )
    assert rows, (
        "اكتمل الطلب ووُلّد المستند ولم يدخل ملف الموظف — "
        f"print_status={print_status}"
    )
    assert rows[-1].is_issued, "دخل الأرشيف بلا ختم الإصدار"
    assert rows[-1].reference_no, "دخل بلا رقم مرجعي — لا يُحتجّ به"
    assert rows[-1].checksum_sha256, "دخل بلا بصمة"


def test_filing_it_afterwards_does_not_duplicate_it(client):
    """ومن يضغط «طُبع» ثم «أُرشف» بعده لا يُنشئ نسخة ثانية.

    القاعدة في موضع واحد، فلو كُتبت مرّتين لحمل الملف صفَّين
    ``is_current`` لورقة واحدة — وأيّهما الحاليّ يصير سؤاًلا بلا جواب.
    """
    rid, eid = _complete_a_certificate(client)
    type_code = doc_archive.archive_type_code("REQCERTSAL")

    db = SessionLocal()
    try:
        n_before = len(_archived(db, eid, type_code))
    finally:
        db.close()
    assert n_before >= 1

    hh = auth_headers(login(client, *HR))
    p = client.post(f"/api/requests/{rid}/document/generated_pdf/mark-printed",
                    headers=hh)
    assert p.status_code == 200, p.text[:200]
    f = client.post(f"/api/requests/{rid}/document/generated_pdf/mark-filed",
                    headers=hh)
    assert f.status_code == 200, f.text[:200]

    db = SessionLocal()
    try:
        rows = _archived(db, eid, type_code)
        current = [d for d in rows if d.is_current]
    finally:
        db.close()
    assert len(rows) == n_before, (
        f"الأرشفة اليدوية كرّرت الصفّ: {n_before} → {len(rows)}"
    )
    assert len(current) == 1, f"أكثر من نسخة «حاليّة»: {len(current)}"


def test_printing_is_a_notification_not_a_blocking_task():
    """والطباعة أثر ورقي: لا يتعطّل عمل إن لم يطبع أحد."""
    assert task_kinds.is_notification("ready_to_print"), (
        "«جاهز للطباعة» ما زال يُعدّ عمًلا واجًبا بعد أن صارت الأرشفة تلقائية"
    )


def test_the_ready_notice_survives_completion(client):
    """**والعطل الثاني**: كان يُنشأ ثم يُكنَس في اللحظة نفسها.

    مهمة تُغلق قبل أن يراها أحد ليست تذكيًرا — هي صمت يبدو نظاًما.
    """
    rid, _ = _complete_a_certificate(client)
    db = SessionLocal()
    try:
        rows = db.scalars(select(models.Task).where(
            models.Task.related_entity_type == "request",
            models.Task.related_entity_id == rid,
            models.Task.type == "ready_to_print")).all()
    finally:
        db.close()
    assert rows, "لم يُنشأ إخطار الجاهزية أصًلا"
    assert any(t.status in ("open", "in_progress") for t in rows), (
        f"أُنشئ ثم كُنس فوًرا: {[t.status for t in rows]}"
    )


def test_archiving_never_deletes_the_previous_version(client):
    """والنسخة السابقة تُنزَّل ولا تُحذف (القاعدة 15): ما بُني عليها يبقى له أصل."""
    import inspect
    src = inspect.getsource(doc_archive.archive_request_document)
    assert "is_current = False" in src, "لا تنزيل للنسخة السابقة"
    assert "delete" not in src.lower(), "حذف داخل قاعدة الأرشفة"
