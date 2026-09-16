# -*- coding: utf-8 -*-
"""عقُد التعيين لا يصدر بحقٍل ناقص — القاعدُة المُقرَّة في التجديد، على الطريق الشقيق.

**التناظُر المنكسر**: ``renewals`` يبني سياَق العقد الحكومي ثم يرفض
التوليَد إن نقص حقٌل من ``GOV_CONTRACT_REQUIRED_FIELDS`` ويسمّيه بالعربية
(RNW-06). و``_generate_hire_contract`` يبني السياَق بلا ``extras`` ويُصدر —
و``_fill_html`` يحذف الناقَص صامًتا (FRM-01، وهو صحيٌح لمستنٍد عادي)، فيصدر
**عقٌد يوقّعه الموظف** وقد سقط منه اسُمه أو رقُمه المدني، ويُحفَظ مستنًدا
صادًرا على ملفه.

**وهو كامٌن اليوم**: القالبان ``GOV-CONTRACT-HIRE`` و``COMPANY-CONTRACT-HIRE``
غيُر موجودَين في القاعدة، والشاشُة تُعطّل الزرَّ لذلك. فأوُّل قالٍب يُنشئه
المالك يفتحه — فيُسَدّ قبل ذلك.

**والفحُص على ما يستعمله القالُب فقط**: القالُب يكتبه المالك، وحقٌل لا
يذكره لا يُطلَب منه — فلا يُمنع عقٌد صحيحٌ لأن القائمة أطوُل منه.
"""
from __future__ import annotations

from sqlalchemy import delete as sa_delete, select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

HR1 = ("100000000002", "hr12345")
_CODE = "GOV-CONTRACT-HIRE"

#: قوالُب قائمٌة بالكود نفسه عُطِّلت مؤقًتا — تُعاد بعد كل اختبار.
_PARKED: list[int] = []


def _doc_code(emp_id: int) -> str:
    """المفتاُح الذي يُحفَظ به العقُد الصادر — كما يكتبه ``_generate_hire_contract``."""
    return f"{_CODE.lower().replace('-', '_')}_{emp_id}"


def _setup(body: str):
    db = SessionLocal()
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1,
            models.Employee.nationality.isnot(None)))
        assert emp is not None, "لا موظَف بجنسيٍة في الشركة الأولى"
        # **والحارُس يولّد بقالبه هو.** ``test_z_r8_r9`` يزرع قالًبا بالكود
        # نفسه ويُبقيه، والمولُِّد يأخذ أوَّل قالٍب نشط — فكان في السويت
        # الكاملة يولّد بقالٍب لا يذكر الجنسيَّة، فيمرّ ما يجب أن يُرفَض.
        # فتُعطَّل القائمُة مؤقًتا، وتُعاد في ``_teardown``.
        _PARKED[:] = [r.id for r in db.scalars(select(models.DocumentTemplate).where(
            models.DocumentTemplate.code == _CODE,
            models.DocumentTemplate.is_active == True)).all()]  # noqa: E712
        for rid in _PARKED:
            db.get(models.DocumentTemplate, rid).is_active = False
        tpl = models.DocumentTemplate(company_id=None, code=_CODE,
                                      name="قالُب قياس", category="عقود",
                                      body_html=body, is_active=True)
        db.add(tpl)
        db.commit()
        return emp.id, emp.nationality, tpl.id
    finally:
        db.close()


def _teardown(emp_id: int, nationality, tpl_id: int) -> None:
    db = SessionLocal()
    try:
        emp = db.get(models.Employee, emp_id)
        emp.nationality = nationality
        db.execute(sa_delete(models.Document).where(
            models.Document.entity_type == "employee",
            models.Document.entity_id == emp_id,
            models.Document.document_type_code == _doc_code(emp_id)))
        db.execute(sa_delete(models.DocumentTemplate).where(
            models.DocumentTemplate.id == tpl_id))
        for rid in _PARKED:
            row = db.get(models.DocumentTemplate, rid)
            if row is not None:
                row.is_active = True
        _PARKED.clear()
        db.commit()
    finally:
        db.close()


def _blank_nationality(emp_id: int) -> None:
    db = SessionLocal()
    try:
        db.get(models.Employee, emp_id).nationality = None
        db.commit()
    finally:
        db.close()


def _issued(emp_id: int) -> int:
    db = SessionLocal()
    try:
        return len(db.scalars(select(models.Document).where(
            models.Document.entity_type == "employee",
            models.Document.entity_id == emp_id,
            models.Document.document_type_code == _doc_code(emp_id))).all())
    finally:
        db.close()


def test_a_hire_contract_missing_a_used_field_is_refused(client):
    """**ولا مستنَد يُحفَظ** — والرسالُة تسمّي الناقَص بالعربية كما في التجديد."""
    emp_id, nat, tpl_id = _setup(
        "<p>{{employee_name}} — {{civil_id}} — {{nationality}}</p>")
    try:
        _blank_nationality(emp_id)
        r = client.post(f"/api/employees/{emp_id}/gov-contract/generate",
                        headers=auth_headers(login(client, *HR1)))
        assert r.status_code == 400, (r.status_code, r.text[:250])
        assert "الجنسية" in r.text, r.text[:250]
        assert _issued(emp_id) == 0, "صدر عقٌد ناقٌص وحُفظ على ملف الموظف"
    finally:
        _teardown(emp_id, nat, tpl_id)


def test_a_field_the_template_does_not_use_is_not_demanded(client):
    """**والقائمُة لا تمنع قالًبا لا يطلبها** — فالجنسيُة الفارغة لا تعني شيًئا هنا."""
    emp_id, nat, tpl_id = _setup("<p>{{employee_name}} — {{civil_id}}</p>")
    try:
        _blank_nationality(emp_id)
        r = client.post(f"/api/employees/{emp_id}/gov-contract/generate",
                        headers=auth_headers(login(client, *HR1)))
        assert r.status_code == 200, (r.status_code, r.text[:250])
        assert _issued(emp_id) == 1, _issued(emp_id)
    finally:
        _teardown(emp_id, nat, tpl_id)


def test_the_two_paths_read_one_list():
    """**قاعدٌة واحدٌة لا نصّان** — الطريقان يقرآن القائمَة نفسها."""
    import inspect

    from app.routers import employees, renewals

    assert "GOV_CONTRACT_REQUIRED_FIELDS" in inspect.getsource(
        employees._generate_hire_contract)
    assert "GOV_CONTRACT_REQUIRED_FIELDS" in inspect.getsource(renewals)
