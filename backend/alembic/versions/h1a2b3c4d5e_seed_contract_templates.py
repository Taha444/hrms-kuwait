# -*- coding: utf-8 -*-
"""Seed three contract templates that the app calls by code at generate-time.

Revision ID: h1a2b3c4d5e
Revises: g94a172839d
Create Date: 2026-08-09

R8 §3 + R9 — يُبذَر ثلاث قوالب رسمية بأكواد ثابتة، حتى ما تفضل الـendpoints
اللي بتناديها ترجع 404 لحد ما يدخل الأدمن يضيفها يدويًا:

  1) GOV-CONTRACT-RENEWAL   → renewals.py يستدعيها لتوليد العقد الحكومي عند التجديد
  2) GOV-CONTRACT-HIRE      → employees.py يستدعيها لتوليد العقد الحكومي عند التعيين
  3) COMPANY-CONTRACT-HIRE  → عقد العمل بين العامل والشركة (تعيين جديد)

النصوص المبذورة هي **placeholders رسمية** تتضمن كل الـtokens المدعومة، لكن
الإدارة العليا محتاجة تدخل من `/templates` وتستبدل الـbody_html بنص الاعتماد
الرسمي من وزارة الداخلية/الشركة (اللي عادةً بيوصل PDF ماسك). الـplaceholders
المستخدمة كلها authoritative (الراتب/الاسم/الرقم المدني تُقفَل من الـinput).

الحذف عكسي: downgrade يشيل الـ3 قوالب دي بس (ما يمس القوالب الأخرى).
"""
from typing import Sequence, Union

from alembic import op


revision: str = "h1a2b3c4d5e"
down_revision: Union[str, None] = "g94a172839d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_GOV_RENEWAL_BODY = """<div dir="rtl" style="font-family: 'Tajawal', 'Arial', sans-serif; line-height: 1.9;">
<h2 style="text-align:center;">عقد عمل — تجديد إقامة عامل</h2>
<p style="text-align:center; color:#666;">
النموذج الرسمي المعتمد من الإدارة العامة لشؤون الإقامة — وزارة الداخلية، دولة الكويت
</p>
<hr />
<p><strong>الرقم المرجعي للنموذج:</strong> {{ref_no}}</p>
<p><strong>تاريخ التحرير:</strong> {{date_today}}</p>

<h3>أطراف العقد</h3>
<p><strong>الطرف الأول (صاحب العمل):</strong> {{company_name}} — {{company_name_en}}<br />
رقم السجل التجاري: {{commercial_reg}} · رقم ملف القوى العاملة: {{company_file_number}}</p>

<p><strong>الطرف الثاني (العامل):</strong> {{employee_name}} — {{employee_name_en}}<br />
الجنسية: {{nationality}} · الرقم المدني: {{civil_id}} · رقم الجواز: {{passport_number}}<br />
تاريخ الميلاد: {{date_of_birth}} · المسمى الوظيفي: {{job_title}}</p>

<h3>بيانات الإقامة</h3>
<p><strong>رقم الإقامة السابق:</strong> {{old_permit_number}} · <strong>تاريخ انتهائها:</strong> {{old_permit_expiry}}</p>
<p><strong>رقم طلب التجديد الداخلي:</strong> {{renewal_id}}</p>

<h3>شروط العقد</h3>
<ol>
<li>يتفق الطرفان على تجديد إقامة العامل لدى الطرف الأول وفقًا لأحكام قانون العمل رقم 6 لسنة 2010 وتعديلاته.</li>
<li>الراتب الأساسي المتفق عليه: <strong>{{basic_salary}}</strong> (يُصرف شهريًا).</li>
<li>تاريخ التعيين الأصلي: {{hire_date}} · نوع العقد: {{contract_type}}.</li>
<li>يلتزم العامل بأداء العمل بأمانة وإخلاص وحسب لوائح الشركة.</li>
<li>يلتزم صاحب العمل بسداد الرسوم الحكومية للتجديد وأي مستحقات نظامية أخرى.</li>
</ol>

<p style="margin-top:40px;">
<strong>توقيع الطرف الأول:</strong> ............................. &nbsp;&nbsp;
<strong>ختم الشركة:</strong> ..............................<br />
<strong>توقيع الطرف الثاني (العامل):</strong> ..............................
</p>

<p style="margin-top:24px; color:#999; font-size:0.85em; text-align:center;">
⚠️ هذا نموذج مبدئي. على الإدارة العليا استبدال هذا النص بنص وزارة الداخلية الرسمي المعتمد
عبر /templates → GOV-CONTRACT-RENEWAL. لا تعديل على placeholders {{...}} — النظام يعبيها تلقائيًا.
</p>
</div>"""


_GOV_HIRE_BODY = """<div dir="rtl" style="font-family: 'Tajawal', 'Arial', sans-serif; line-height: 1.9;">
<h2 style="text-align:center;">عقد عمل حكومي — تعيين عامل جديد</h2>
<p style="text-align:center; color:#666;">
النموذج الرسمي المعتمد من الإدارة العامة لشؤون الإقامة — وزارة الداخلية، دولة الكويت
</p>
<hr />
<p><strong>الرقم المرجعي للنموذج:</strong> {{ref_no}}</p>
<p><strong>تاريخ التحرير:</strong> {{date_today}}</p>

<h3>أطراف العقد</h3>
<p><strong>الطرف الأول (صاحب العمل):</strong> {{company_name}} — {{company_name_en}}<br />
رقم السجل التجاري: {{commercial_reg}}</p>

<p><strong>الطرف الثاني (العامل):</strong> {{employee_name}}<br />
الجنسية: {{nationality}} · الرقم المدني: {{civil_id}} · رقم الجواز: {{passport_number}}</p>

<h3>شروط التعيين</h3>
<ol>
<li>يعيّن الطرف الأول العامل بوظيفة <strong>{{job_title}}</strong> في الفرع: {{branch_name}}.</li>
<li>الراتب الأساسي: <strong>{{basic_salary}}</strong>.</li>
<li>تاريخ التعيين: {{hire_date}} · نوع العقد: {{contract_type}}.</li>
<li>يلتزم العامل بأداء العمل حسب لوائح الشركة ونظام العمل الكويتي.</li>
<li>هذا العقد يعتبر متمّمًا لعقد العمل بين الطرفين (COMPANY-CONTRACT-HIRE).</li>
</ol>

<p style="margin-top:40px;">
<strong>توقيع صاحب العمل:</strong> ............................. &nbsp;&nbsp;
<strong>ختم الشركة:</strong> ..............................<br />
<strong>توقيع العامل:</strong> ..............................
</p>

<p style="margin-top:24px; color:#999; font-size:0.85em; text-align:center;">
⚠️ نموذج مبدئي. على الإدارة استبداله بنص وزارة الداخلية الرسمي عبر /templates → GOV-CONTRACT-HIRE.
</p>
</div>"""


_COMPANY_HIRE_BODY = """<div dir="rtl" style="font-family: 'Tajawal', 'Arial', sans-serif; line-height: 1.9;">
<h2 style="text-align:center;">عقد عمل — بين الشركة والعامل</h2>
<hr />
<p><strong>الرقم المرجعي:</strong> {{ref_no}} · <strong>التاريخ:</strong> {{date_today}}</p>

<h3>أطراف العقد</h3>
<p><strong>الطرف الأول:</strong> {{company_name}} ({{company_name_en}})<br />
س.ت: {{commercial_reg}}</p>
<p><strong>الطرف الثاني:</strong> {{employee_name}}<br />
الجنسية: {{nationality}} · الرقم المدني: {{civil_id}} · الهاتف: {{phone}}</p>

<h3>بنود العقد</h3>
<ol>
<li>يتم تعيين الطرف الثاني بوظيفة <strong>{{job_title}}</strong> في {{branch_name}} — {{department}}.</li>
<li>الراتب الأساسي المتفق عليه: <strong>{{basic_salary}}</strong>.</li>
<li>تاريخ بدء العمل: {{hire_date}} · مدة العقد: {{contract_type}}.</li>
<li>ساعات العمل الأسبوعية ونظام الإجازات وفقًا للائحة الداخلية للشركة وقانون العمل الكويتي رقم 6/2010.</li>
<li>مكافأة نهاية الخدمة تُحسب حسب القانون وسياسة الشركة الموثّقة في نظام الموارد البشرية.</li>
<li>هذا العقد يعتبر كاملاً ومكمّلاً للعقد الحكومي (GOV-CONTRACT-HIRE) الموقّع من وزارة الداخلية.</li>
</ol>

<p style="margin-top:40px;">
<strong>توقيع الشركة:</strong> ............................. &nbsp;&nbsp;
<strong>ختم:</strong> ..............................<br />
<strong>توقيع العامل:</strong> ..............................
</p>

<p style="margin-top:24px; color:#999; font-size:0.85em; text-align:center;">
⚠️ نموذج مبدئي — على HR استبداله بعقد الشركة الرسمي عبر /templates → COMPANY-CONTRACT-HIRE.
</p>
</div>"""


_SEEDS = [
    {
        "code": "GOV-CONTRACT-RENEWAL",
        "name": "العقد الحكومي — تجديد إقامة",
        "name_en": "Government Contract — Residency Renewal",
        "category": "عقود",
        "body_html": _GOV_RENEWAL_BODY,
    },
    {
        "code": "GOV-CONTRACT-HIRE",
        "name": "العقد الحكومي — تعيين جديد",
        "name_en": "Government Contract — New Hire",
        "category": "عقود",
        "body_html": _GOV_HIRE_BODY,
    },
    {
        "code": "COMPANY-CONTRACT-HIRE",
        "name": "عقد العمل — بين الشركة والعامل",
        "name_en": "Company-Employee Employment Contract",
        "category": "عقود",
        "body_html": _COMPANY_HIRE_BODY,
    },
]


def upgrade() -> None:
    """يضيف الـ3 قوالب كـcompany_id=NULL (متاحة لكل الشركات) لو ما موجودة بنفس الكود."""
    conn = op.get_bind()
    for seed in _SEEDS:
        exists = conn.execute(
            _sa_text("SELECT id FROM document_templates WHERE code = :c LIMIT 1"),
            {"c": seed["code"]},
        ).first()
        if exists:
            continue
        conn.execute(
            _sa_text("""
                INSERT INTO document_templates
                    (company_id, code, name, name_en, category, body_html, is_active, version, created_at)
                VALUES
                    (NULL, :code, :name, :name_en, :category, :body_html, TRUE, 1, NOW())
            """),
            seed,
        )


def downgrade() -> None:
    conn = op.get_bind()
    codes = tuple(s["code"] for s in _SEEDS)
    conn.execute(
        _sa_text("DELETE FROM document_templates WHERE code IN :codes AND company_id IS NULL")
            .bindparams(_sa_bindparam("codes", expanding=True)),
        {"codes": list(codes)},
    )


# --- imports مؤجّلة (Alembic offline يفضّل top-level خفيفة) ---
def _sa_text(sql):
    from sqlalchemy import text
    return text(sql)


def _sa_bindparam(name, expanding=False):
    from sqlalchemy import bindparam
    return bindparam(name, expanding=expanding)
