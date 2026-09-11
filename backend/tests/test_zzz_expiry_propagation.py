# -*- coding: utf-8 -*-
"""تاريٌخ يُجدَّد وتنبيٌه ينادي على القديم — ومسٌح يُسكِت العالم كلَّه.

**العطل الأخطر**: رفُع جواٍز لموظٍف واحد كان ينفّذ::

    update(Task).where(related_entity_type == "document",
                       type == "doc_expiring",
                       status.in_(["open", "in_progress"]))
         .values(status="done", ...)

**بلا قيٍد على مستنٍد ولا على شركة.** فيُغلق كلَّ مهمة انتهاء مستند
مفتوحة **في قاعدة البيانات بأسرها**: كلُّ موظف، في كل شركة. والمحرّك
الذي يمنع سقوط الإقامات يخرس. وهو خرٌق لعزل الشركات فوق ذلك.

ولم يكن يضيف شيًئا: إغلاُق مهامّ النسخة المستبدَلة يقع قبله لكل نسخٍة على
حدة بـ``_close_expiry_tasks_for(db, d.id)`` — المقيَّدة بمستندها، اثنَي
عشر سطًرا فوقه. **قاعدٌة في موضعين: أحدهما صحيٌح والآخر يعمل.**

**والعطل الثاني**: تاريُخ الانتهاء في مصدرين. ``Employee.passport_expiry``
تقرؤه شاشُة الملف، و``Document.expiry_date`` يقرؤه محرُّك التنبيهات
**وحده**. فـ``REQPASS`` كان يكتب عموَد الموظف فقط: الشاشة تُظهر الجديد
والتنبيه ينادي على القديم. و``REQCID`` أسوأ — لا عموَد للبطاقة المدنية
في الموظف أصًلا، فكان النموذج يسأل «تاريخ الانتهاء الجديد» **ولا أحَد
يكتبه في أيّ موضع**.

والقاعدُة من ``hrms-renewal-propagation`` بنصّها: «حدّث المصدر الواحد
الذي تقرأ منه الشاشات… ولا يبقى جزٌء من النظام شايف التاريخ القديم وجزٌء
آخر شايف الجديد».
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import delete as sa_delete, select

from app import models
from app.clock import today as kuwait_today
from app.database import SessionLocal

EMP = ("100000000101", "emp12345")


def _emp_id() -> int:
    db = SessionLocal()
    try:
        return db.scalar(select(models.Employee.id).where(
            models.Employee.civil_id == EMP[0]))
    finally:
        db.close()


def _current_doc(doc_type: str, emp_id: int) -> models.Document | None:
    db = SessionLocal()
    try:
        return db.scalar(select(models.Document).where(
            models.Document.entity_type == "employee",
            models.Document.entity_id == emp_id,
            models.Document.document_type_code == doc_type,
            models.Document.is_current == True))  # noqa: E712
    finally:
        db.close()


# ---------------------------------------------------------------------------
# المسح لا يُسكِت غير مستنده
# ---------------------------------------------------------------------------

def test_uploading_one_passport_does_not_silence_every_other_document():
    """**جوهر العطل الأخطر**: لا تحديَث مهامّ بلا قيٍد على مستنده.

    والحارس يقرأ الشيفرة لأن السلوك نفسه كان يمسّ قاعدًة بأسرها: تركيُب
    حالٍة تُثبته يعني إفساد بيانات كل السويت.
    """
    import inspect

    from app.routers import documents as D

    src = inspect.getsource(D.upload_document)
    assert "update(models.Task)" not in src, \
        "ما زال هناك تحديُث مهامّ جماعي في مسار الرفع"
    # والإغلاق الصحيح باٍق — لا يُحذف الحارس بحذف ما يحرسه.
    assert "_close_expiry_tasks_for" in inspect.getsource(D), \
        "ذهب الإغلاق المقيَّد بمستنده"


def test_the_scoped_closure_names_its_document():
    """والدالُة المقيَّدة تقيّد بمعرّف المستند — لا بنوعه ولا بشيء أعمّ."""
    import inspect

    from app.routers import documents as D

    src = inspect.getsource(D._close_expiry_tasks_for)
    assert "related_entity_id == doc_id" in src, src[:400]


def test_replacing_a_version_closes_only_that_versions_tasks():
    """وإغلاُق مهامّ النسخة المستبدَلة يقع لكل نسخٍة على حدة."""
    import inspect

    from app.routers import documents as D

    src = inspect.getsource(D.upload_document)
    assert "_close_expiry_tasks_for(db, d.id)" in src, \
        "لم يعد يُغلق مهامّ النسخة التي استُبدلت"


# ---------------------------------------------------------------------------
# والتاريخ في مصدٍر واحد
# ---------------------------------------------------------------------------

def test_every_declared_expiry_effect_names_a_real_request_type():
    """مفتاٌح لا يطابق نوًعا لا يعمل أبًدا — وكانت ثلاثٌة كذلك قبًلا."""
    from app import request_effects as RE, workflow

    types = {rt["code"] for rt in workflow.DEFAULT_REQUEST_TYPES}
    ghosts = [c for c in RE.DOCUMENT_EXPIRY_EFFECTS if c not in types]
    assert not ghosts, f"نشٌر مسجٌَّل لنوٍع لا وجود له: {ghosts}"


def test_every_asked_expiry_field_has_a_writer():
    """**وحقٌل يسأله النموذج ولا أحَد يكتبه حقٌل يُلقى.**

    فـ``REQCID`` كان يسأل ``new_expiry`` ولا موضَع يكتبه: لا عموَد في
    الموظف، ولا نشَر إلى المستند.
    """
    from app import form_schemas, request_effects as RE

    for code in ("REQPASS", "REQCID"):
        sch = form_schemas.get_schema(code)
        if not sch:
            continue
        asks = {f["code"] for f in sch["fields"]}
        if "new_expiry" not in asks:
            continue
        col_writer = any(src == "new_expiry" for src, _c
                         in (RE.FIELD_EFFECTS.get(code, ("", {}))[1]).values())
        doc_writer = (RE.DOCUMENT_EXPIRY_EFFECTS.get(code) or ("",))[0] == "new_expiry"
        assert col_writer or doc_writer, \
            f"{code}: النموذج يسأل «new_expiry» ولا أحَد يكتبه"


def test_the_engine_and_the_effect_read_the_same_store():
    """**ولا يُنشَر إلى موضٍع لا يقرؤه المحرّك.**

    محرُّك التنبيهات يستعلم ``Document.expiry_date``. فالنشُر إليه لا إلى
    عموٍد آخر، وإلا كان تحديًثا لا يراه من بُني له.
    """
    import inspect

    from app import notifications as N, request_effects as RE

    engine = inspect.getsource(N.daily_scan)
    assert "models.Document.expiry_date" in engine, \
        "افتراض القياس: المحرّك يقرأ المستند"
    prop = inspect.getsource(RE._propagate_document_expiry)
    assert "models.Document" in prop and "expiry_date" in prop


def test_propagation_moves_the_document_the_engine_reads():
    """والنشُر يُحرِّك تاريَخ المستند فعًلا — لا سطَر تدقيٍق وحده."""
    from app import request_effects as RE

    emp_id = _emp_id()
    doc = _current_doc("civil_id", emp_id)
    if doc is None:
        import pytest
        pytest.skip("لا بطاقَة مدنية جارية في هذه القاعدة")

    was = doc.expiry_date
    new = (kuwait_today() + timedelta(days=900))
    db = SessionLocal()
    try:
        emp = db.get(models.Employee, emp_id)
        req = models.Request(company_id=emp.company_id, employee_id=emp_id,
                             request_type_code="REQCID", status="draft",
                             payload_json={"new_civil": emp.civil_id,
                                           "new_expiry": new.isoformat()})
        db.add(req)
        db.flush()
        rid = req.id
        changed = RE._propagate_document_expiry(db, req, emp, req.payload_json)
        db.commit()
    finally:
        db.close()

    try:
        assert changed, "لم يُنشَر شيء"
        after = _current_doc("civil_id", emp_id)
        assert after.expiry_date == new, (was, after.expiry_date)
    finally:
        db = SessionLocal()
        try:
            d = db.scalar(select(models.Document).where(
                models.Document.id == doc.id))
            if d is not None:
                d.expiry_date = was
            db.execute(sa_delete(models.Task).where(
                models.Task.related_entity_type == "document",
                models.Task.related_entity_id == doc.id))
            db.execute(sa_delete(models.Request).where(models.Request.id == rid))
            db.commit()
        finally:
            db.close()


def test_a_stale_alert_is_closed_so_a_corrected_one_can_exist():
    """**وتنبيٌه قديٌم مفتوٌح يمنع أيَّ تنبيٍه مصّحح.**

    المسُح اليومي يتخطّى أيَّ مستنٍد له مهمٌة ``doc_expiring`` مفتوحة. فلو
    بقي تنبيُه التاريخ القديم مفتوًحا بعد التجديد، بقي على الشاشة تاريٌخ
    مضى **ولا سبيل لتصحيحه**.
    """
    from app import request_effects as RE

    emp_id = _emp_id()
    doc = _current_doc("passport", emp_id)
    if doc is None:
        import pytest
        pytest.skip("لا جواَز جاٍر في هذه القاعدة")

    was = doc.expiry_date
    db = SessionLocal()
    try:
        stale = models.Task(
            company_id=doc.company_id, type="doc_expiring",
            title="جواٌز قارب على الانتهاء", detail="بتاريٍخ قديم",
            related_entity_type="document", related_entity_id=doc.id,
            status="open", severity="warning",
            dedup_key=f"doc_expiring:{doc.id}:test")
        db.add(stale)
        db.flush()
        task_id = stale.id
        emp = db.get(models.Employee, emp_id)
        req = models.Request(company_id=emp.company_id, employee_id=emp_id,
                             request_type_code="REQPASS", status="draft",
                             payload_json={
                                 "new_passport": emp.passport_number or "A1",
                                 "new_expiry": (kuwait_today()
                                                + timedelta(days=1200)).isoformat()})
        db.add(req)
        db.flush()
        rid = req.id
        RE._propagate_document_expiry(db, req, emp, req.payload_json)
        db.commit()
    finally:
        db.close()

    try:
        db = SessionLocal()
        try:
            t = db.get(models.Task, task_id)
            assert t.status == "done", \
                f"بقي تنبيُه التاريخ القديم مفتوًحا ({t.status})"
        finally:
            db.close()
    finally:
        db = SessionLocal()
        try:
            d = db.scalar(select(models.Document).where(
                models.Document.id == doc.id))
            if d is not None:
                d.expiry_date = was
            db.execute(sa_delete(models.Task).where(models.Task.id == task_id))
            db.execute(sa_delete(models.Request).where(models.Request.id == rid))
            db.commit()
        finally:
            db.close()


def test_propagation_never_creates_a_document_out_of_a_request():
    """**ولا يُخلَق مستنٌد من طلب** — النظام لا يُصدر وثائق الجهات."""
    from app import request_effects as RE

    emp_id = _emp_id()
    db = SessionLocal()
    try:
        emp = db.get(models.Employee, emp_id)
        before = db.scalar(select(models.Document).where(
            models.Document.entity_type == "employee",
            models.Document.entity_id == emp_id,
            models.Document.document_type_code == "no_such_type"))
        req = models.Request(company_id=emp.company_id, employee_id=emp_id,
                             request_type_code="REQPASS", status="draft",
                             payload_json={"new_expiry": "2040-01-01"})
        # نوٌع لا مستنَد جاٍر له: تُغيَّر الخريطة مؤقًتا لقياس الاتجاه.
        saved = RE.DOCUMENT_EXPIRY_EFFECTS["REQPASS"]
        RE.DOCUMENT_EXPIRY_EFFECTS["REQPASS"] = ("new_expiry", "no_such_type")
        try:
            out = RE._propagate_document_expiry(db, req, emp, req.payload_json)
        finally:
            RE.DOCUMENT_EXPIRY_EFFECTS["REQPASS"] = saved
        db.rollback()
    finally:
        db.close()
    assert out == {}, out
    assert before is None, "افتراض القياس"
