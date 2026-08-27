# -*- coding: utf-8 -*-
"""FRM-01 — الصيغ الخمس نظيفة من النوائب والمعرّفات الداخلية.

القاعدة: **حقل لم يُملأ لا يُطبع نائبه.** النموذج الورقي فيه خانات تُملأ
باليد؛ أما مستند يولّده النظام فخانته الفارغة إقرار مطبوع بأن البيانات
ناقصة — في ورقة تُقدَّم لبنك أو سفارة.

والفحص على **المخرَج** لا على القالب: السكيل صريح في أن القالب قد يبدو
سليًما ويخرج معطوًبا، وهذا ما حدث فعًلا — نمط تنقية الصفوف كان يحمل حرًفا
غير مرئي فلا يطابق شيًئا، والشيفرة تُقرأ صحيحة.
"""
from __future__ import annotations

import re

import pytest
from sqlalchemy import select

from app import models
from app.database import SessionLocal
from app.routers.templates import _fill_html, _resolve_authoritative_data

FIVE = ["HRMS-PR-001", "HRMS-PR-006", "HRMS-PR-008",
        "HRMS-PR-009", "HRMS-PR-032"]

#: ما لا يجوز أن يظهر في مستند صادر
FORBIDDEN = {
    "نائب فراغ [____]": r"\[_+\]",
    "خيار غير محسوم [Bank/Embassy/Other]": r"\[Bank/Embassy/Other\]",
    "خيار غير محسوم [Bank/Cash]": r"\[Bank/Cash\]",
    "قالب تاريخ [DD/MM/YYYY]": r"\[DD/MM/YYYY\]",
    "قالب شهر [MM/YYYY]": r"\[MM/YYYY\]",
    "خانة فارغة [ ]": r"\[\s*\]",
    "حالة مكتوبة [Active]": r"\[Active\]",
    "نوع عقد [Fixed/Unlimited]": r"\[Fixed/Unlimited\]",
    "دورة [Monthly]": r"\[Monthly\]",
    "اسم حقل تقني": r"allowances_total|gross_salary|target_entity|"
                    r"basic_salary_kwd|employee_id\b",
    "رمز قالب غير مستبدَل": r"\{\{\w+\}\}",
}


def _text(html_out: str) -> str:
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html_out, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))


@pytest.fixture(scope="module")
def rendered():
    """يولّد الخمسة فعليًّا — لا حكم من قراءة الكود."""
    db = SessionLocal()
    try:
        emp = db.query(models.Employee).first()
        assert emp is not None, "لا موظف في بيانات الاختبار"
        ctx = _resolve_authoritative_data(db, emp, extras={})
        ctx["ref_no"] = "HRMS-PR-TEST/1/202608/0001"
        out = {}
        for code in FIVE:
            tpl = db.scalar(select(models.DocumentTemplate).where(
                models.DocumentTemplate.code == code))
            assert tpl is not None, f"القالب {code} غير موجود"
            out[code] = (_text(_fill_html(tpl, ctx)), emp)
        yield out
    finally:
        db.close()


def test_no_visible_placeholders_in_any_of_the_five(rendered):
    """لا نائب يظهر في مستند صادر — لا في أيٍّ من الخمسة."""
    problems = []
    for code, (text, _emp) in rendered.items():
        for label, pattern in FORBIDDEN.items():
            hits = re.findall(pattern, text)
            if hits:
                problems.append(f"{code}: {label} ×{len(hits)} → {hits[:3]}")
    assert not problems, "نوائب ظاهرة في المخرَج:\n" + "\n".join(problems)


def test_employee_number_not_the_database_id(rendered):
    """معرّف الصفّ تفصيلة داخلية لا تخرج في ورقة رسمية.

    كان يُطبع تحت عنوان «الرقم الوظيفي / Employee ID» حرفيًّا.
    """
    for code, (text, emp) in rendered.items():
        m = re.search(r"الرقم الوظيفي[^أ-ي]*?([^\s]+)", text)
        assert m, f"{code}: خانة الرقم الوظيفي غائبة"
        printed = m.group(1)
        assert printed != str(emp.id), (
            f"{code}: يطبع معرّف الصفّ ({emp.id}) مكان الرقم الوظيفي"
        )
        assert "Employee ID" not in text, (
            f"{code}: العنوان ما زال Employee ID — وهو معرّف داخلي"
        )


def test_seeded_employees_have_a_real_employee_number():
    """«ولّده أو أوقف التوليد» — لا تُطبع شرطة مكان رقم إلزامي.

    النطاق موظفو البذرة وحدهم: اختبارات أخرى تُنشئ موظفين بالإدراج المباشر
    في القاعدة متجاوزًة مسار الإنشاء الذي يولّد الرقم. وإدخال بيانات
    اختبار ناقصة عمًدا ليس عيًبا في المنتج، وادّعاء يشملها يسقط لسبب لا
    يخصّه ويشير إلى المكان الخطأ.
    """
    db = SessionLocal()
    try:
        seeded = db.scalars(select(models.Employee).where(
            models.Employee.civil_id.like("1000000001%")
            | models.Employee.civil_id.like("2000000001%"))).all()
        assert seeded, "لا موظفي بذرة — تغيّرت بيانات الاختبار"
        missing = [e for e in seeded if not e.employee_no]
        assert not missing, (
            f"{len(missing)} من موظفي البذرة بلا رقم وظيفي — "
            "مستنداتهم ستطبع خانة فارغة مكان رقم إلزامي"
        )
    finally:
        db.close()


def test_api_created_employee_gets_a_number(client):
    """الضمان الفعليّ: من يُنشأ من الواجهة يحصل على رقمه.

    هذا ما يحمي بيانات العميل؛ والبذرة تُعبّئ القديم وحده.
    """
    from .conftest import auth_headers, login

    hdr = auth_headers(login(client, "100000000002", "hr12345"))
    r = client.post("/api/employees", headers=hdr, json={
        "name": "موظف اختبار الترقيم", "civil_id": "299119911991",
        "job_title": "محاسب", "basic_salary": 400,
        "hire_date": "2026-01-01", "nationality": "مصري",
    })
    if r.status_code not in (200, 201):
        pytest.skip(f"تعذّر إنشاء موظف: {r.text[:160]}")
    body = r.json()
    try:
        assert body.get("employee_no"), (
            "موظف أُنشئ من الواجهة بلا رقم وظيفي"
        )
        assert body["employee_no"] != str(body["id"]), (
            "الرقم الوظيفي هو معرّف الصفّ نفسه"
        )
    finally:
        db = SessionLocal()
        try:
            e = db.get(models.Employee, body["id"])
            if e:
                db.delete(e)
                db.commit()
        finally:
            db.close()


def test_unfilled_segment_is_removed_but_filled_one_survives():
    """جوهر القاعدة: يُحذف الناقص ويبقى الموجود.

    حذف الصفّ كله عند نقص جزء منه يُضيّع بياًنا صحيًحا لأن بياًنا آخر
    مفقود — وهو ضرر لا إصلاح.
    """
    from app.routers.templates import _UNFILLED, _prune_unfilled

    row = ("<tr><td dir='rtl'>الراتب: 2500 د.ك · الفعلي: "
           + _UNFILLED + " د.ك</td><td>X</td></tr>")
    out = _prune_unfilled(row)
    assert "2500" in out, "حُذفت قيمة صحيحة مع الناقص"
    assert _UNFILLED not in out and "الفعلي" not in out, "بقي الجزء الناقص"


def test_row_with_nothing_filled_disappears_entirely():
    """عنوان بلا قيمة يسأل قارئه عن سبب الفراغ؛ وغيابه لا يسأل."""
    from app.routers.templates import _UNFILLED, _prune_unfilled

    row = ("<tr><td dir='rtl'>إقامة: " + _UNFILLED + " · انتهاء: "
           + _UNFILLED + "</td><td>Residency</td></tr>")
    assert _prune_unfilled(row).strip() == "", "بقي صفّ خالٍ من كل قيمة"


def test_pruning_patterns_actually_match_real_markup():
    """حارس ضدّ عطل وقعتُ فيه: نمط يبدو صحيًحا ولا يطابق شيًئا.

    كان ``_CELL_RE`` يحمل حرف backspace غير مرئي تسرّب أثناء التحرير، فلا
    يطابق ``<td>`` أبًدا — والتنقية تمرّ بلا أثر، والشيفرة تُقرأ سليمة.
    فحص الأنماط على نصّ حقيقي هو ما يكشف هذا الصنف.
    """
    from app.routers.templates import _CELL_RE, _ROW_RE, _SEG_SPLIT

    for rx in (_CELL_RE, _ROW_RE, _SEG_SPLIT):
        assert not any(ord(c) < 32 for c in rx.pattern), (
            f"النمط يحمل حرًفا تحكميًّا غير مرئي: {rx.pattern!r}"
        )
    sample = "<tr><td dir='rtl'>أ · ب</td><td>x</td></tr>"
    assert len(_CELL_RE.findall(sample)) == 2, "نمط الخانة لا يطابق <td>"
    assert len(_ROW_RE.findall(sample)) == 1, "نمط الصفّ لا يطابق <tr>"
    assert len(_SEG_SPLIT.split("أ · ب")) == 2, "نمط الفاصل لا يقسم"


def test_no_repeated_prefix_in_output(rendered):
    """«شركة شركة» · «د.ك د.ك» — سببها أن القالب يضيف بادئة تحملها القيمة."""
    for code, (text, _emp) in rendered.items():
        for pattern, label in ((r"شركة\s+شركة", "شركة شركة"),
                               (r"د\.ك\s*د\.ك", "د.ك د.ك"),
                               (r"\bKWD\s+KWD\b", "KWD KWD")):
            assert not re.search(pattern, text), f"{code}: تكرار «{label}»"
