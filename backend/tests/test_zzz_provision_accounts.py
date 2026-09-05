# -*- coding: utf-8 -*-
"""BKL-07 (الخطوة الأولى) — تجهيز حسابات الأدوار بلا كسر قاعدة أمنية.

مسار التجديد لا يُختبر بحساب واحد، وبيئة الإنتاج تُنشئ الإدارة العليا
والمالك فقط — فيتوقّف الاختبار قبل أن يبدأ.

وأخطر ما في أداة تُنشئ حسابات أنها تُغري بالتساهل: كلمة موحّدة «لأنها
للاختبار»، أو موظف وهمي «يُحذف لاحًقا». وكلاهما يبقى. فنصف هذه الاختبارات
على ما لا يجوز أن تفعله الأداة.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models
from app.database import SessionLocal
from app.provision_accounts import FORBIDDEN_ROLES, TEST_ROLES, provision
from app.security import verify_password


@pytest.fixture
def clean_company():
    """**شركة خاصّة بهذا الاختبار** بموظفين نشطين بلا حسابات.

    البذرة تحمل حسابات لكل الأدوار، فاختبار الأداة عليها يقيس البذرة لا
    الأداة: تُبلّغ «موجود» ولا تُنشئ شيًئا فتمرّ الادّعاءات فراًغا. وبناء
    الحالة هنا يجعل الاختبار مستقًلا عن كل ما سبقه.
    """
    db = SessionLocal()
    company_id = None
    created = []
    try:
        company = models.Company(
            name="شركة تجهيز الحسابات", name_en="Provisioning Test Co.",
            commercial_reg="PRV-0001", entity_type="ذات مسؤولية محدودة",
            eos_day_divisor=26, eos_max_months=18, alert_lead_days=60)
        db.add(company)
        db.flush()
        company_id = company.id
        for i in range(4):
            e = models.Employee(
                company_id=company_id, name=f"موظف تجهيز {i}",
                name_en=f"Provision Employee {i}",
                civil_id=f"2880011100{i:02d}", job_title="فني",
                job_title_en="Technician", basic_salary=400,
                passport_number=f"P77700{i:02d}",
                status="active", nationality="مصري")
            db.add(e)
            db.flush()
            created.append(e.id)
        db.commit()
        yield company_id, created
    finally:
        # F-003 — الحذف بترتيب مشتقّ من المخطّط لا بترتيب مكتوب باليد.
        #
        # كان التنظيف يحذف المستخدم ثم الموظف ثم الشركة — والمستخدم له
        # أبناء (تدقيق، جلسات، مهام، تفضيلات) فيرفضه فرضُ المفاتيح
        # الأجنبية. وهو أحد الأسباب التسعة التي أبقت F-003 مفتوحة.
        from tests.conftest import purge

        uids = [u.id for u in db.scalars(select(models.User).where(
            models.User.company_id == company_id)).all()]
        purge(db, "users", uids)
        purge(db, "employees", created)
        purge(db, "companies", [company_id] if company_id else [])
        db.commit()
        db.close()


def test_never_creates_a_fake_employee(clean_company):
    """موظف مخترع يدخل التقارير والمسيّر ويبقى بعد الاختبار."""
    company_id, _ = clean_company
    db = SessionLocal()
    try:
        before = db.scalar(select(models.Employee.id).order_by(
            models.Employee.id.desc()))
        provision(db, company_id, ["employee"], apply_changes=True)
        after = db.scalar(select(models.Employee.id).order_by(
            models.Employee.id.desc()))
        assert after == before, "الأداة أنشأت موظًفا — والقاعدة تمنع ذلك"
    finally:
        db.close()


def test_each_account_gets_its_own_random_password(clean_company):
    """لا كلمة موحّدة ولا مشتركة — ولو «للاختبار»."""
    company_id, _ = clean_company
    db = SessionLocal()
    try:
        rows = provision(db, company_id, ["employee", "delegate",
                                          "branch_supervisor"],
                         apply_changes=True)
        made = [r for r in rows if r.get("password")]
        assert len(made) >= 2, f"لم تُنشأ حسابات كافية للقياس: {rows}"
        passwords = [r["password"] for r in made]
        assert len(set(passwords)) == len(passwords), (
            "كلمة مرور مكرَّرة بين حسابين"
        )
        assert all(len(p) >= 10 for p in passwords), "كلمة قصيرة"
    finally:
        db.close()


def test_password_works_once_and_must_be_changed(clean_company):
    """الكلمة المطبوعة للتسليم لا للاستعمال الدائم."""
    company_id, _ = clean_company
    db = SessionLocal()
    try:
        rows = provision(db, company_id, ["employee"], apply_changes=True)
        made = next(r for r in rows if r.get("password"))
        user = db.scalar(select(models.User).where(
            models.User.civil_id == made["civil_id"]))
        assert user is not None
        assert verify_password(made["password"], user.password_hash), (
            "الكلمة المطبوعة لا تفتح الحساب — سلّمنا ما لا يعمل"
        )
        assert user.must_change_password is True, (
            "لا يُطلب تغيير الكلمة عند أول دخول"
        )
    finally:
        db.close()


#: الأدوار الممنوعة **مكتوبة هنا مستقلّة** عن ثابت الوحدة عمًدا.
#: قراءتها من الوحدة تجعل تفريغها يُفرغ الاختبار: الحلقة لا تدور فيمرّ
#: أخضر وهو لم يفحص شيًئا — وهذا ما حدث فعًلا في أول كتابة.
PRIVILEGED_ROLES = ["super_admin", "company_owner"]


def test_refuses_to_create_privileged_roles(clean_company):
    """أداة تُنشئ صلاحية مطلقة ليست أداة تجهيز اختبار."""
    company_id, _ = clean_company
    db = SessionLocal()
    try:
        for role in PRIVILEGED_ROLES:
            with pytest.raises(SystemExit):
                provision(db, company_id, [role], apply_changes=True)
        assert set(PRIVILEGED_ROLES) <= FORBIDDEN_ROLES, (
            "قائمة المنع في الوحدة لم تعد تشمل الأدوار الخطرة"
        )
    finally:
        db.close()


def test_one_account_per_person_no_sharing(clean_company):
    """حساب لكل شخص: دوران لا يتقاسمان موظًفا واحًدا."""
    company_id, _ = clean_company
    db = SessionLocal()
    try:
        rows = provision(db, company_id, ["employee", "delegate"],
                         apply_changes=True)
        made = [r for r in rows if r.get("password")]
        ids = [r["civil_id"] for r in made]
        assert len(set(ids)) == len(ids), "حسابان لنفس الشخص"

        linked = [db.scalar(select(models.User).where(
            models.User.civil_id == cid)).employee_id for cid in ids]
        assert len(set(linked)) == len(linked), "دوران مرتبطان بموظف واحد"
    finally:
        db.close()


def test_dry_run_changes_nothing(clean_company):
    """الفحص لا يكتب: من يجرّب الأداة على بيئة عميل لا يفاجأ بحسابات."""
    company_id, _ = clean_company
    db = SessionLocal()
    try:
        before = db.scalar(select(models.User.id).order_by(
            models.User.id.desc()))
        rows = provision(db, company_id, TEST_ROLES, apply_changes=False)
        after = db.scalar(select(models.User.id).order_by(
            models.User.id.desc()))
        assert after == before, "الفحص أنشأ حساًبا"
        assert all(r.get("password") is None for r in rows), (
            "الفحص أعاد كلمات مرور لحسابات لم تُنشأ"
        )
    finally:
        db.close()


def test_existing_role_account_is_reported_not_duplicated(clean_company):
    """دور له حساب قائم لا يُنشأ له ثانٍ — والحساب المشترك ممنوع."""
    company_id, _ = clean_company
    db = SessionLocal()
    try:
        provision(db, company_id, ["employee"], apply_changes=True)
        again = provision(db, company_id, ["employee"], apply_changes=True)
        assert again[0]["action"] == "موجود", (
            f"أُنشئ حساب ثانٍ للدور نفسه: {again}"
        )
        assert again[0].get("password") is None
    finally:
        db.close()


def test_picks_the_most_complete_employee(clean_company):
    """العقد الحكومي يتوقّف عند أول حقل ناقص.

    فاختيار موظف ناقص البيانات يوقف الاختبار في منتصفه لسبب لا علاقة له
    بالمسار المُختبَر — ويُقرأ كعطل في التجديد وهو عطل في التجهيز.
    """
    company_id, emp_ids = clean_company
    db = SessionLocal()
    try:
        # نُفقر أحدهم عمًدا
        poor = db.get(models.Employee, emp_ids[0])
        poor.name_en = None
        poor.job_title_en = None
        poor.passport_number = None
        db.commit()

        rows = provision(db, company_id, ["employee"], apply_changes=True)
        made = next(r for r in rows if r.get("password"))
        assert made["civil_id"] != poor.civil_id, (
            "اختيرت أفقر البيانات — سيتوقّف توليد العقد"
        )
    finally:
        db.close()
