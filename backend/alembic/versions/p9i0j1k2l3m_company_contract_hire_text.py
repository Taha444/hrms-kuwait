# -*- coding: utf-8 -*-
"""Give COMPANY-CONTRACT-HIRE a real bilingual body (was still placeholder).

Revision ID: p9i0j1k2l3m
Revises: o8h9i0j1k2l
Create Date: 2026-08-10

QA §8 — GOV-CONTRACT-HIRE و GOV-CONTRACT-RENEWAL أخذا النص الرسمي في
n7g8h9i0j1k، لكن COMPANY-CONTRACT-HIRE فضل على النص المؤقت.

عقد الشركة يكمّل العقد الحكومي: الحكومي يغطي المتطلبات النظامية للهيئة
العامة للقوى العاملة، وعقد الشركة يوثّق شروط العمل الداخلية (الوردية،
البدلات، سياسة الإجازات، السرية، الملكية الفكرية) — لا يعارض قانون العمل
رقم 6/2010 وأي شرط أقل من الحد القانوني باطل.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = "p9i0j1k2l3m"
down_revision: Union[str, None] = "o8h9i0j1k2l"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_BODY = """<div dir="rtl" style="font-family: 'Tajawal', 'Arial', sans-serif; line-height: 1.85; padding: 12px;">
<h2 style="text-align:center; margin:0 0 4px;">عقد عمل — بين الشركة والعامل</h2>
<p style="text-align:center; color:#555; margin:0 0 16px;">
Employment Contract — Company &amp; Employee<br/>
<span style="font-size:12px;">مكمّل للعقد الحكومي المعتمد من الهيئة العامة للقوى العاملة</span>
</p>
<hr />

<p><strong>الرقم المرجعي / Reference:</strong> {{ref_no}} — <strong>التاريخ / Date:</strong> {{date_today}}</p>

<h3>أطراف العقد — Parties</h3>
<p><strong>الطرف الأول / First Party:</strong> {{company_name}} ({{company_name_en}})<br/>
رقم السجل التجاري / Commercial Reg.: {{commercial_reg}}</p>
<p><strong>الطرف الثاني / Second Party:</strong> {{employee_name}} — {{employee_name_en}}<br/>
الرقم المدني / Civil ID: {{civil_id}} · الجنسية / Nationality: {{nationality}}<br/>
رقم الجواز / Passport: {{passport_number}} · الهاتف / Phone: {{phone}}<br/>
الرقم الوظيفي / Employee No.: {{employee_no}}</p>

<h3>البند الأول — الوظيفة ومكان العمل / Position &amp; Workplace</h3>
<p>يعمل الطرف الثاني لدى الطرف الأول بوظيفة <strong>{{job_title}}</strong>، بالفرع: {{branch_name}}، القسم: {{department}}.<br/>
<em>The second party is employed as {{job_title}} at branch {{branch_name}}, department {{department}}.</em></p>

<h3>البند الثاني — بدء العمل ومدة العقد / Start Date &amp; Term</h3>
<p>يبدأ العمل اعتبارًا من <strong>{{hire_date}}</strong>، والعقد <strong>{{contract_type_ar}}</strong>.<br/>
<em>Employment starts {{hire_date}}. The contract is {{contract_type_en}}.</em></p>

<h3>البند الثالث — الأجر / Wage</h3>
<p>الراتب الأساسي الشهري: <strong>{{basic_salary}}</strong>، يُصرف في نهاية كل شهر ميلادي عن طريق التحويل البنكي.<br/>
<em>Monthly basic salary: {{basic_salary}}, paid at the end of each calendar month by bank transfer.</em></p>
<p style="font-size:12px; color:#666;">أي بدلات إضافية (سكن، مواصلات، طبيعة عمل) تُحدَّد بقرار إداري موثّق ولا تُعتبر جزءًا من الأجر الأساسي لأغراض مكافأة نهاية الخدمة ما لم ينص القانون على خلاف ذلك.</p>

<h3>البند الرابع — ساعات العمل / Working Hours</h3>
<p>ثماني ساعات يوميًا كحد أقصى، تتخللها فترة راحة لا تقل عن ساعة، وفق اللائحة الداخلية للشركة وأحكام قانون العمل رقم 6 لسنة 2010.<br/>
<em>Maximum eight hours daily with at least one hour rest, per company policy and Labour Law 6/2010.</em></p>

<h3>البند الخامس — الإجازة السنوية / Annual Leave</h3>
<p>يستحق الطرف الثاني إجازة سنوية مدفوعة الأجر مدتها <strong>{{annual_leave_days}}</strong> يومًا، ولا يستحقها عن السنة الأولى إلا بعد مضي تسعة أشهر من تاريخ بدء العمل. تُنظَّم مواعيد الإجازة باتفاق الطرفين وبما لا يعطّل سير العمل.<br/>
<em>{{annual_leave_days}} days paid annual leave, not due in the first year until nine months have elapsed. Timing agreed between the parties without disrupting operations.</em></p>

<h3>البند السادس — فترة التجربة / Probation</h3>
<p>يخضع الطرف الثاني لفترة تجربة لا تتجاوز <strong>{{probation_days}}</strong> يوم عمل، يحق خلالها لأي من الطرفين إنهاء العقد دون إخطار أو تعويض.<br/>
<em>Probation not exceeding {{probation_days}} work days; either party may terminate without notice or compensation during this period.</em></p>

<h3>البند السابع — واجبات العامل / Employee Obligations</h3>
<ol>
<li>أداء العمل المتفق عليه بنفسه وبالدقة والأمانة المطلوبة.</li>
<li>الالتزام بمواعيد العمل واللوائح الداخلية وتعليمات الرؤساء المباشرين.</li>
<li>المحافظة على أدوات وممتلكات الشركة المسلّمة إليه وإعادتها عند انتهاء العلاقة.</li>
<li>عدم إفشاء أسرار العمل أو بيانات العملاء أثناء العقد وبعد انتهائه.</li>
</ol>

<h3>البند الثامن — السرية والملكية / Confidentiality &amp; IP</h3>
<p>تُعد كل المعلومات والبيانات والمستندات التي يطّلع عليها الطرف الثاني بحكم عمله سرية ومملوكة للطرف الأول، ويلتزم بعدم استخدامها أو إفشائها لأي طرف ثالث. كل عمل أو ابتكار يُنجَز أثناء العمل وباستخدام موارد الشركة يعود لها.<br/>
<em>All information accessed by virtue of the role is confidential and owned by the first party. Work product created during employment using company resources belongs to the company.</em></p>

<h3>البند التاسع — مكافأة نهاية الخدمة / End of Service</h3>
<p>يستحق الطرف الثاني مكافأة نهاية الخدمة وفق أحكام قانون العمل رقم 6 لسنة 2010 وسياسة الشركة الموثّقة في نظام الموارد البشرية.<br/>
<em>End-of-service benefit per Labour Law 6/2010 and the company's documented HR policy.</em></p>

<h3>البند العاشر — إنهاء العقد / Termination</h3>
<p>ينتهي العقد بانتهاء مدته، أو باتفاق الطرفين، أو بإخطار كتابي وفق المدد القانونية، أو في الحالات المنصوص عليها في المادتين 41 و42 من قانون العمل.<br/>
<em>The contract ends by expiry, mutual agreement, written notice per statutory periods, or in the cases set out in Articles 41 and 42 of the Labour Law.</em></p>

<h3>البند الحادي عشر — العلاقة بالعقد الحكومي / Relation to the Government Contract</h3>
<p>هذا العقد مكمّل للعقد الحكومي المودع لدى الهيئة العامة للقوى العاملة، ولا يجوز أن يتضمن شرطًا أقل من الحد الأدنى المقرر قانونًا. وفي حال التعارض تسود النصوص الأصلح للعامل.<br/>
<em>This contract complements the government contract filed with PAM and may not include terms below the statutory minimum. Where they conflict, whichever is more favorable to the worker prevails.</em></p>

<h3>البند الثاني عشر — لغة العقد / Language</h3>
<p>حُرِّر هذا العقد بالعربية والإنجليزية، وتسود النصوص العربية عند الاختلاف.<br/>
<em>Executed in Arabic and English; the Arabic text prevails in case of conflict.</em></p>

<div style="display:flex; justify-content:space-between; margin-top:50px; text-align:center;">
<div style="flex:1;">
<p><strong>الطرف الأول — First Party</strong></p>
<p>....................................<br/>{{company_name}}</p>
</div>
<div style="flex:1;">
<p><strong>الطرف الثاني — Second Party</strong></p>
<p>....................................<br/>{{employee_name}}</p>
</div>
</div>
</div>"""


def upgrade() -> None:
    conn = op.get_bind()
    code = "COMPANY-CONTRACT-HIRE"
    exists = conn.execute(
        text("SELECT id FROM document_templates WHERE code = :c LIMIT 1"), {"c": code}
    ).first()
    if exists:
        conn.execute(text("""
            UPDATE document_templates
            SET name = :name, name_en = :name_en, body_html = :body,
                category = 'عقود', is_active = TRUE,
                version = COALESCE(version, 1) + 1
            WHERE code = :c
        """), {"c": code, "name": "عقد العمل — بين الشركة والعامل",
               "name_en": "Company-Employee Employment Contract", "body": _BODY})
    else:
        conn.execute(text("""
            INSERT INTO document_templates
                (company_id, code, name, name_en, category, body_html,
                 is_active, version, created_at)
            VALUES (NULL, :c, :name, :name_en, 'عقود', :body, TRUE, 1, CURRENT_TIMESTAMP)
        """), {"c": code, "name": "عقد العمل — بين الشركة والعامل",
               "name_en": "Company-Employee Employment Contract", "body": _BODY})


def downgrade() -> None:
    # لا رجوع: النص القديم كان مسودّة داخلية استُبدلت بالصيغة الرسمية. إعادته
    # تُنتج عقوًدا بنصٍّ لم يعد معتمًَدا، والتراجع الصحيح تعديل من /templates.
    pass
