# -*- coding: utf-8 -*-
"""Replace placeholder gov-contract templates with official Kuwait PAM text.

Revision ID: n7g8h9i0j1k
Revises: m6f7g8h9i0j
Create Date: 2026-08-10

P0-#11 — النص الرسمي لعقد العمل من الهيئة العامة للقوى العاملة (Kuwait PAM)،
مأخوذ من نموذج PDF الرسمي (16 مادة، ثنائي اللغة، سيادة العربية عند التعارض).

الاستبدال يشمل:
- GOV-CONTRACT-HIRE (تعيين جديد): النص الكامل
- GOV-CONTRACT-RENEWAL (تجديد): مماثل مع تعديل التاريخ ورقم إقامة قديم

Placeholders المطلوبة (يوفرها _resolve_authoritative_data):
- {{company_name}}, {{company_name_en}}
- {{commercial_reg}} — للسجل التجاري (Article Preamble)
- {{employee_name}}, {{employee_name_en}}
- {{nationality}}, {{passport_number}}, {{civil_id}}
- {{job_title}} — المهنة
- {{basic_salary}} — بالدينار الكويتي
- {{hire_date}} — تاريخ التعيين (Article 5)
- {{contract_type}} — 'indefinite' أو 'definite'
- {{date_today}}, {{ref_no}}
- extras (يقبلها _resolve مع تجاوز LOCKED):
  {{probation_days}} (افتراضي 100), {{annual_leave_days}} (30),
  {{contract_years}} (لو definite)
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = "n7g8h9i0j1k"
down_revision: Union[str, None] = "m6f7g8h9i0j"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_HIRE_BODY = """<div dir="rtl" style="font-family: 'Tajawal', 'Arial', sans-serif; line-height: 1.85; padding: 12px;">
<h2 style="text-align:center; margin: 0 0 4px;">نموذج عقد عمل استرشادى فى القطاع الأهلى</h2>
<p style="text-align:center; margin: 0 0 4px;">دولة الكويت — الهيئة العامة للقوى العاملة</p>
<p style="text-align:center; margin: 0 0 16px;">إدارة عمل العاصمة</p>

<p style="text-align:center; font-style: italic; color:#555; margin:8px 0;">
Sample Form of an Employment Contract in the Civil Sector<br/>
State of Kuwait · Public Authority for Manpower · Labour Department al asima
</p>
<hr />

<p><strong>الرقم المرجعي:</strong> {{ref_no}} — <strong>Reference:</strong> {{ref_no}}</p>
<p><strong>إنه في يوم:</strong> {{date_today}} — <strong>Dated:</strong> {{date_today}}</p>
<p>تحرر هذا العقد بين كل من: — <em>The present contract was concluded by and between:</em></p>

<h3>الطرف الأول — First Party</h3>
<p>شركة / <strong>{{company_name}}</strong> ({{company_name_en}})<br/>
رقم السجل التجاري / Commercial Registration: {{commercial_reg}}</p>

<h3>الطرف الثاني — Second Party (Worker)</h3>
<p>الاسم / Name: <strong>{{employee_name}}</strong> — {{employee_name_en}}<br/>
الجنسية / Nationality: {{nationality}}<br/>
رقم الجواز / Passport No.: {{passport_number}}<br/>
الرقم المدني / Civil ID: {{civil_id}}</p>

<h3>تمهيد — Preamble</h3>
<p>يمتلك الطرف الأول منشأة باسم شركة <strong>{{company_name}}</strong> ويرغب في التعاقد مع الطرف الثاني للعمل لديه بمهنة <strong>{{job_title}}</strong>. وبعد أن أقر الطرفان بأهليتهما في إبرام هذا العقد، تم الاتفاق على ما يلي:</p>
<p><em>The first party owns a facility called {{company_name}} and wishes to contract with the second party to work for it in the {{job_title}} profession. After both parties acknowledged their eligibility to conclude this contract, the following was agreed upon:</em></p>

<h3>البند الأول — Article One</h3>
<p>يعتبر التمهيد السابق جزءًا لا يتجزأ من هذا العقد.<br/>
<em>The preamble above shall constitute an integral part of the present contract.</em></p>

<h3>البند الثاني — Article Two "طبيعة العمل / Nature of the Work"</h3>
<p>تعاقد الطرف الأول مع الطرف الثاني للعمل لديه بمهنة <strong>{{job_title}}</strong> داخل دولة الكويت.<br/>
<em>The first party contracted with the second party to work for it in the {{job_title}} profession within the State of Kuwait.</em></p>

<h3>البند الثالث — Article Three "فترة التجربة / Probation Period"</h3>
<p>يخضع الطرف الثاني لفترة تجربة لمدة لا تزيد عن <strong>{{probation_days}}</strong> يوم عمل، ويحق لكل طرف إنهاء العقد خلال تلك الفترة دون إخطار.<br/>
<em>The second party shall be subject to a probation period for a term not exceeding {{probation_days}} work days. Each party shall have the right to terminate the contract during the said term without notification.</em></p>

<h3>البند الرابع — Article Four "قيمة الأجر / Wage Value"</h3>
<p>يتقاضى الطرف الثاني عن تنفيذ هذا العقد أجرًا مقداره <strong>{{basic_salary}}</strong> يُدفع في نهاية كل شهر. ولا يجوز للطرف الأول تخفيض الأجر أثناء سريان هذا العقد، ولا يجوز نقل الطرف الثاني إلى الأجر اليومي دون موافقته.<br/>
<em>For executing the present contract, the second party shall receive the wage of {{basic_salary}} to be paid at the end of every month. The first party may not decrease the wage during the term of the contract. It may not transfer the second party to daily wage without his approval.</em></p>

<h3>البند الخامس — Article Five "نفاذ العقد / Contract Coming into Force"</h3>
<p>يبدأ نفاذ العقد اعتبارًا من <strong>{{hire_date}}</strong>. يلتزم الطرف الثاني بالقيام بأداء عمله طوال مدة نفاذه.<br/>
<em>The contract shall come into force on {{hire_date}}. The second party shall execute his work during the entire execution term thereof.</em></p>

<h3>البند السادس — Article Six "مدة العقد / Contract Term"</h3>
<p>هذا العقد <strong>{{contract_type_ar}}</strong> ويبدأ من <strong>{{hire_date}}</strong>{{contract_term_clause_ar}}.<br/>
<em>The present contract is {{contract_type_en}} and shall come into force on {{hire_date}}{{contract_term_clause_en}}.</em></p>
<p style="font-size: 12px; color:#666;">* اعتبار العقد محدد المدة أو غير محدد المدة يخضع لإرادة الطرفين. <em>Considering the contract as having a definite or indefinite term shall be subject to the will of the two parties.</em></p>

<h3>البند السابع — Article Seven "الأجازة السنوية / Annual Leave"</h3>
<p>للطرف الثاني الحق في أجازة سنوية مدفوعة الأجر مدتها <strong>{{annual_leave_days}}</strong> يوما، ولا يستحقها عن السنة الأولى إلا بعد انقضاء مدة تسعة أشهر تحسب من تاريخ نفاذ العقد.<br/>
<em>The second party shall have the right to a paid annual leave with a term of {{annual_leave_days}} days. It shall not be due on the first year save after the expiration of nine months to be calculated from the date of the contract coming into force.</em></p>

<h3>البند الثامن — Article Eight "عدد ساعات العمل / Number of Work Hours"</h3>
<p>لا يجوز للطرف الأول تشغيل الطرف الثاني لمدة تزيد عن ثماني ساعات عمل يوميا تتخللها فترة راحة لا تقل عن ساعة، باستثناء الحالات المقررة قانونا.<br/>
<em>The first party may not require that the second party work for a term exceeding eight daily work hours with rest periods not less than one hour, except for the cases set forth in the law.</em></p>

<h3>البند التاسع — Article Nine "قيمة تذكرة السفر / Ticket Value"</h3>
<p>يتحمل الطرف الأول مصاريف عودة الطرف الثاني إلى بلده عند انتهاء علاقة العمل ومغادرته نهائيا للبلاد.<br/>
<em>The first party shall bear the expenses of the return of the second party to his country after the expiration of the work relationship and his final departure from the country.</em></p>

<h3>البند العاشر — Article Ten "التأمين ضد إصابات وأمراض العمل / Insurance against Injuries and Work Maladies"</h3>
<p>يلتزم الطرف الأول بالتأمين على الطرف الثاني ضد إصابات وأمراض العمل، كما يلتزم بقيمة التأمين الصحي طبقا للقانون رقم 1 لسنة 1999.<br/>
<em>The first party shall insure the second party against injuries and work maladies. It shall also commit to the health insurance value in accordance with the law No. (1) of the year 1999.</em></p>

<h3>البند الحادي عشر — Article Eleven "مكافأة نهاية الخدمة / End of Service Benefit"</h3>
<p>يستحق الطرف الثاني مكافأة نهاية الخدمة المنصوص عليها بالقوانين المنظمة.<br/>
<em>The second party shall be due the end of service benefit as set forth in the regulating laws.</em></p>

<h3>البند الثاني عشر — Article Twelve "القانون الواجب التطبيق / Applicable Law"</h3>
<p>تسري أحكام قانون العمل في القطاع الأهلي رقم 6 لسنة 2010 والقرارات المنفذة له في كل ما لم يرد بشأنه نص في هذا العقد. ويعتبر باطلا كل شرط اتفق عليه مخالفا لأحكام القانون، ما لم يكن أفضل للعامل.<br/>
<em>The provisions of the Labour code in the civil sector No. 6 of 2010 and the decisions executing the same shall apply for all matters not provided for in the present contract. Shall be considered null every condition agreed upon in violation of the provisions of the law, unless the same has a better benefit for the worker.</em></p>

<h3>البند الثالث عشر — Article Thirteen "شروط خاصة / Special Conditions"</h3>
<p>{{special_conditions}}</p>

<h3>البند الرابع عشر — Article Fourteen "المحكمة المختصة / Specialized Court"</h3>
<p>تختص محكمة أول درجة ودوائرها العمالية، طبقا لأحكام القانون رقم 46 لسنة 1987، بنظر أي نزاعات تنشأ عن تنفيذ أو تفسير هذا العقد.<br/>
<em>The court of first instance and its Labour departments, in accordance with the provisions of the law No. 46 of the year 1987, shall be competent to peruse any conflicts resulting from the execution or interpretation of the present contract.</em></p>

<h3>البند الخامس عشر — Article Fifteen "لغة العقد / Contract Language"</h3>
<p>حرر هذا العقد باللغتين العربية والإنجليزية، وتسود النصوص العربية في حالة أي تعارض بينهما.<br/>
<em>The present contract was made in Arabic and English. The Arabic texts shall prevail in the case of any conflict between them.</em></p>

<h3>البند السادس عشر — Article Sixteen "نسخ العقد / Contract Copies"</h3>
<p>حرر هذا العقد من ثلاث نسخ، واحدة لكل طرف للعمل بها، وتودع النسخة الثالثة لدى الهيئة العامة للقوى العاملة.<br/>
<em>The present contract was made in three copies, one for each party to work in accordance therewith. The third copy shall be deposited at the Public Authority for Manpower.</em></p>

<div style="display:flex; justify-content: space-between; margin-top: 50px; text-align: center;">
<div style="flex: 1;">
<p><strong>الطرف الأول — First Party</strong></p>
<p>....................................<br/>
{{company_name}}</p>
</div>
<div style="flex: 1;">
<p><strong>الطرف الثاني — Second Party</strong></p>
<p>....................................<br/>
{{employee_name}}</p>
</div>
</div>
</div>"""


_RENEWAL_BODY = _HIRE_BODY.replace(
    'نموذج عقد عمل استرشادى فى القطاع الأهلى',
    'عقد عمل — تجديد إقامة (استرشادي — القطاع الأهلي)'
).replace(
    'Sample Form of an Employment Contract in the Civil Sector',
    'Employment Contract — Residency Renewal (Sample, Civil Sector)'
)


def upgrade() -> None:
    conn = op.get_bind()
    for code, name, name_en, body in [
        ("GOV-CONTRACT-HIRE", "العقد الحكومي — تعيين جديد",
         "Government Contract — New Hire", _HIRE_BODY),
        ("GOV-CONTRACT-RENEWAL", "العقد الحكومي — تجديد إقامة",
         "Government Contract — Residency Renewal", _RENEWAL_BODY),
    ]:
        # UPDATE إذا موجود، INSERT إذا مش موجود
        exists = conn.execute(
            text("SELECT id, version FROM document_templates WHERE code = :c LIMIT 1"),
            {"c": code},
        ).first()
        if exists:
            conn.execute(text("""
                UPDATE document_templates
                SET name = :name, name_en = :name_en, body_html = :body,
                    version = COALESCE(version, 1) + 1
                WHERE code = :c
            """), {"c": code, "name": name, "name_en": name_en, "body": body})
        else:
            conn.execute(text("""
                INSERT INTO document_templates
                    (company_id, code, name, name_en, category, body_html,
                     is_active, version, created_at)
                VALUES
                    (NULL, :c, :name, :name_en, 'عقود', :body, TRUE, 1, CURRENT_TIMESTAMP)
            """), {"c": code, "name": name, "name_en": name_en, "body": body})


def downgrade() -> None:
    # لا نُرجع النص القديم — الإدارة تعيد التعديل يدويًا لو احتاج
    pass
