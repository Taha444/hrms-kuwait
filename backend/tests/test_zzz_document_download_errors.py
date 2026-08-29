# -*- coding: utf-8 -*-
"""تنزيل المستند: الرفض يقول أي عطل وقع.

**البلاغ**: ضغط «طباعة المستند» يعطي «خطأ» — كلمة واحدة لا تدلّ على شيء.

**عطلان اجتمعا**:

1. الواجهة تطلب الملف بـ``responseType: "blob"``، فجسم الخطأ يصل Blob
   أيًضا. و``errMsg`` تقرأ ``data.detail`` فتجده ``undefined`` وتسقط إلى
   النصّ الاحتياطي. فالسبب مكتوب في الردّ ولا يقرؤه أحد.

2. والخادم كان يردّ «المستند غير موجود» على ثلاث حالات مختلفة: لم
   يُولَّد، أو وُلّد ولم يكتمل، أو **فُقد ملفّه من التخزين**. والثالثة هي
   الشائعة على قرص حاوية يُمحى مع كل نشرة — والسجلّ يبقى في القاعدة
   فيبدو المستند موجوًدا وهو ليس كذلك.

ومن يقرأ «غير موجود» يعيد المحاولة؛ ومن يقرأ «فُقد ملفّه» يعرف أن عليه
إعادة التوليد.
"""
from __future__ import annotations

import pytest
from sqlalchemy import delete as sa_delete, select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")


@pytest.fixture
def a_request():
    """طلب يُبنى هنا — لا يُنتظَر أن تصادفه البذرة.

    والمقيس هو ردّ التنزيل لا الطلب نفسه، لكن الطلب يجب أن يكون في شركة
    من يسأل عنه وإلا رُدّ بـ404 لسبب آخر تماًما فمرّ الاختبار كذًبا.
    """
    db = SessionLocal()
    made = {}
    try:
        hr = db.scalar(select(models.User).where(
            models.User.civil_id == HR[0]))
        rt = db.scalars(select(models.RequestType)).first()
        emp = models.Employee(
            company_id=hr.company_id, name="موظف فحص التنزيل",
            name_en="Download Test Employee", civil_id="277700110022",
            job_title="فني", basic_salary=300, status="active",
            nationality="مصري")
        db.add(emp); db.flush()
        req = models.Request(
            company_id=hr.company_id, employee_id=emp.id,
            request_type_code=(rt.code if rt else ""),
            status="completed", current_stage=0)
        db.add(req); db.commit()
        made = {"req": req.id, "emp": emp.id}
        yield req.id
    finally:
        if made:
            db.execute(sa_delete(models.RequestDocument).where(
                models.RequestDocument.request_id == made["req"]))
            db.execute(sa_delete(models.Request).where(
                models.Request.id == made["req"]))
            db.execute(sa_delete(models.Employee).where(
                models.Employee.id == made["emp"]))
            db.commit()
        db.close()


def _cleanup(req_id: int, kind: str) -> None:
    db = SessionLocal()
    try:
        db.execute(sa_delete(models.RequestDocument).where(
            models.RequestDocument.request_id == req_id,
            models.RequestDocument.kind == kind))
        db.commit()
    finally:
        db.close()


def test_a_never_generated_document_says_so(client, a_request):
    """لا صفّ: لم يُطلب توليده."""
    _cleanup(a_request, "test_kind_absent")
    hdr = auth_headers(login(client, *HR))
    r = client.get(f"/api/requests/{a_request}/document/test_kind_absent",
                   headers=hdr)
    assert r.status_code == 404, r.text
    assert "لم يُولَّد" in r.json()["detail"], r.json()


def test_a_row_without_a_path_is_named_incomplete(client, a_request):
    """صفّ بلا مسار: التوليد بدأ ولم يكتمل — لا «غير موجود»."""
    kind = "test_kind_nopath"
    _cleanup(a_request, kind)
    db = SessionLocal()
    try:
        db.add(models.RequestDocument(request_id=a_request, kind=kind,
                                      version=1, file_path=None))
        db.commit()
    finally:
        db.close()
    try:
        hdr = auth_headers(login(client, *HR))
        r = client.get(f"/api/requests/{a_request}/document/{kind}", headers=hdr)
        assert r.status_code == 404
        assert "لم يكتمل" in r.json()["detail"], r.json()
    finally:
        _cleanup(a_request, kind)


def test_a_lost_file_is_distinguished_from_a_missing_record(client, a_request):
    """**الحالة التي أنتجت البلاغ**: السجلّ موجود والملف مفقود.

    وهي الشائعة على قرص حاوية يُمحى مع كل نشرة. وتمييزها عن «لم يُولَّد»
    هو الفرق بين «أعد التوليد» و«اطلبه أوًلا».
    """
    kind = "test_kind_lost"
    _cleanup(a_request, kind)
    db = SessionLocal()
    try:
        db.add(models.RequestDocument(
            request_id=a_request, kind=kind, version=1,
            file_path="uploads/requests/ملف-اختفى-مع-النشرة.pdf"))
        db.commit()
    finally:
        db.close()
    try:
        hdr = auth_headers(login(client, *HR))
        r = client.get(f"/api/requests/{a_request}/document/{kind}", headers=hdr)
        assert r.status_code == 410, (
            f"الملف المفقود لا يُميَّز عن السجلّ الغائب: {r.status_code}"
        )
        detail = r.json()["detail"]
        assert "مفقود" in detail, detail
        assert "أعد توليد" in detail, "الرسالة لا تقول ماذا يفعل القارئ"
    finally:
        _cleanup(a_request, kind)


def test_the_three_cases_do_not_share_one_message(client, a_request):
    """الادّعاء الجامع: ثلاث رسائل لا واحدة.

    لو تشابهت لعاد العطل الأصلي — رسالة واحدة تُخفي ثلاثة أعطال.
    """
    hdr = auth_headers(login(client, *HR))
    details = []

    _cleanup(a_request, "k_absent")
    details.append(client.get(f"/api/requests/{a_request}/document/k_absent",
                              headers=hdr).json()["detail"])

    db = SessionLocal()
    try:
        db.add(models.RequestDocument(request_id=a_request, kind="k_nopath",
                                      version=1, file_path=None))
        db.add(models.RequestDocument(request_id=a_request, kind="k_lost",
                                      version=1, file_path="uploads/gone.pdf"))
        db.commit()
    finally:
        db.close()
    try:
        for kind in ("k_nopath", "k_lost"):
            details.append(client.get(
                f"/api/requests/{a_request}/document/{kind}",
                headers=hdr).json()["detail"])
    finally:
        for kind in ("k_nopath", "k_lost"):
            _cleanup(a_request, kind)

    assert len(set(details)) == 3, f"رسائل متطابقة لأعطال مختلفة: {details}"
