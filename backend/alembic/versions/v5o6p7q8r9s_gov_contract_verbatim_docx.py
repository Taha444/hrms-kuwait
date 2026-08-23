# -*- coding: utf-8 -*-
"""العقد الحكومي — نسخ حرفي من ملف الوورد الرسمي

الترحيل n7g8h9i0j1k وضع النص بصياغة متشابكة: كل بند عربي يليه مقابله
الإنجليزي في نفس الفقرة. العميل يريد التخطيط كما في الملف الرسمي بالضبط:
كتلة إنجليزية كاملة ثم كتلة عربية كاملة، بنفس ترتيب الصفحات ونفس النصوص.

النص منسوخ حرفيًا من "عقد عربي انجليزي s.docx" (نموذج الهيئة العامة للقوى
العاملة). الأرقام المتغيّرة وحدها استُبدلت بـplaceholders — لا إعادة صياغة
ولا تصحيح لغوي، بناءً على طلب صريح: "كوبي بيست بدون تعديلات".

Revision ID: v5o6p7q8r9s
Revises: u4n5o6p7q8r
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "v5o6p7q8r9s"
down_revision: Union[str, None] = "u4n5o6p7q8r"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── الكتلة الإنجليزية — الصفحة الأولى ────────────────────────────────────────
_EN_PAGE1 = """
<div class="contract-en" dir="ltr" style="text-align:left">
<p style="text-align:center"><strong>The Public Authority For Manpower</strong><br/>
Sample Form of an Employment Contract in the Civil Sector<br/>
State of Kuwait<br/>
Public Authority for Manpower Labour Department al asima</p>

<p>On {{day_name_en}} Corresponding to {{contract_date}} the present contract was concluded by and between:</p>

<p>Company : {{company_name_en}}<br/>
Name :  {{company_rep_name_en}}<br/>
Civil Card: {{company_rep_civil_id}}<br/>
<strong>(First Party)</strong></p>

<p>Name: {{employee_name_en}}<br/>
Nationality   :   {{nationality_en}}<br/>
PASS PORT  :  {{passport_number}}<br/>
Residence    : {{residency_number}}<br/>
<strong>(Second Party) Preamble</strong></p>

<p>The first party owns a facility called {{company_name_en}} and wishes to contract with
the second party to work for it in the {{job_title_en}} profession. After both parties
acknowledged their eligibility to conclude this contract, the following was agreed upon:</p>

<p><strong>Article One</strong><br/>
The preamble above shall constitute an integral part of the present contract.</p>

<p><strong>Article Two "Nature of the work"</strong><br/>
The first party contracted with the second party to work for it in the {{job_title_en}}
profession within the State of Kuwait</p>

<p><strong>Article Three</strong><br/>
<strong>"Probation Period"</strong><br/>
The second party shall be subject to a probation period for a term not exceeding
{{probation_days}} work days. Each party shall have the right to terminate the contract
during the said term without notification.</p>

<p><strong>Article Four "Lease Value"</strong><br/>
Tor executing the present contract, the second party shall receive the wage of
{{basic_salary}} KD to be paid at the end of every month . The first party may not
decrease the wage during the term of the contract. It may not transfer the second party
to daily wage without his approval.</p>

<p><strong>Article Five "Contract Term"</strong><br/>
The contract shall come into force on  {{hire_date}}he second
party shall execute his work during the entire execution term thereof.</p>

<p><strong>Article Six "Contract Term"</strong><br/>
The present contract has a definite term. It shall come into force on  {{hire_date}}for a
term of {{contract_years_en}}. The contract may be renewed with the approval of the
parties for similar terms not exceeding five years.<br/>
The present contract has an indefinite term and it shall come into force on   {{hire_date}}</p>

<p>*Considering the contract as having a definite or indefinite term shall be subject to
the will of the two parties.</p>
</div>
"""

# ── الكتلة العربية — الصفحة الأولى ───────────────────────────────────────────
_AR_PAGE1 = """
<div class="contract-ar" dir="rtl" style="text-align:right">
<p style="text-align:center">نموذج عقد عمل استرشادى فى القطاع الاهلى<br/>
دولة الكويت<br/>
الهيئة العامة للقوى العاملة / إدارة عمل العاصمة</p>

<p>إنه في يوم {{day_name_ar}} الموافق {{contract_date}}<br/>
تحرر هذا العقد بين كل من :</p>

<p>شركة /   {{company_name}} ويمثلها في التوقيع على العقد<br/>
الاسم      : {{company_rep_name}}<br/>
رقم مدني : {{company_rep_civil_id}}<br/>
<strong>" طرف أول "</strong></p>

<p>الاسم      :   {{employee_name}}<br/>
الجنسية   :    {{nationality}}<br/>
رقم الجواز :     {{passport_number}}<br/>
رقم مدني :     {{civil_id}}<br/>
<strong>" طرف ثانى "</strong></p>

<p><strong>تمهيد</strong><br/>
يمتلك الطرف الأول منشأة باسم  شركة {{company_name}} ويرغب في التعاقد مع الطرف    الثاني
للعمل لديه بمهنة  {{job_title}}    وبعد ان أقر الطرفان بأهليتهما في إبرام هذا   العقد تم
الاتفاق على ما يلي :</p>

<p style="text-align:center"><strong>البند الأول</strong></p>
<p>يعتبر التمهيد السابق جزء لا يتجزا  من هذا العقد . .</p>

<p style="text-align:center"><strong>البند الثاني</strong><br/><strong>" طبيعة العمل "</strong></p>
<p>تعاقد الطرف الأول مع الطرف الثاني للعمل لديه بمهنة {{job_title}} داخل دولة الكويت</p>

<p style="text-align:center"><strong>البند الثالث</strong><br/><strong>" فترة التجربة "</strong></p>
<p>يخضع الطرف الثاني لفترة تجربة لمدة لا تزيد عن {{probation_days}} يوم عمل ، ويحق لكل طرف
إنهاء العقد خلال تلك الفترة دون اخطار .</p>

<p style="text-align:center"><strong>البند الرابع</strong><br/><strong>" قيمة الأجر "</strong></p>
<p>يتقاضى الطرف الثانى عن تنفيذ هذا العقد اجرا مقدراه {{basic_salary}} دينار يدفع فى نهاية كل شهر<br/>
ولا يجوز للطرف الأول تخفيض الأجر أثناء سريان هذا القعد ، ولا يجوز نقل الطرف الثاني إلى
الأجر اليومي دون موافقته .</p>

<p style="text-align:center"><strong>البند الخامس</strong><br/><strong>" نفاذ العقد "</strong></p>
<p>يبدأ نفاذ العقد اعتبارا من  {{hire_date}}<br/>
يلتزم الطرف الثاني بالقيام بأداء عمله طوال مدة نفاذه .</p>

<p style="text-align:center"><strong>البند السادس</strong><br/><strong>" مدة العقد "</strong></p>
<p>هذا العقد محدد المدة ويبدأ من  {{hire_date}} ولمدة {{contract_years_ar}} ويجوز تجديد العقد
بموافقة الطرفين.<br/>
لمدد مماثلة بحد أقصى خمس سنوات ميلادية<br/>
هذا العقد غير محدد المدة ويبدأ اعتبارا من {{hire_date}}</p>

<p>هذا العقد محدد المدة او غير محدد المدة يخضع لادراه الطرفين .</p>
</div>
"""

# ── الكتلة الإنجليزية — الصفحة الثانية ───────────────────────────────────────
_EN_PAGE2 = """
<div class="contract-en" dir="ltr" style="text-align:left; page-break-before:always">
<p style="text-align:center"><strong>The Public Authority For Manpower الهيئة العامة للقوى العاملة</strong></p>

<p><strong>Article Seven</strong><br/>
<strong>"Annual Leave"</strong><br/>
The second party shall have the right to a paid annual leave with a term of
{{annual_leave_days}} days. It shall not be due on the first year save after the
expiration of nine months to be calculated from the date of the contract coming into force.</p>

<p><strong>Article Eight "Number of Work Hours "</strong><br/>
The first party may not require that the second party work for a term exceeding eight
daily work hours with rest periods not less than one hour, except for
the cases set forth in the law.</p>

<p><strong>Article Nine "Ticket Value"</strong><br/>
The first party shall bear the expenses of the return of the second party to his country
after the expiration of the work relationship and his final departure from the country.</p>

<p><strong>Article Ten</strong><br/>
<strong>"Insurance against Injuries and Work Maladies "</strong><br/>
The first party shall insure the second party against injuries and work maladies. It
shall also commit to the health insurance value in accordance with the
law No. (1) of the year 1999.</p>

<p><strong>Article Eleven "End of Service Benefit"</strong><br/>
The second party shall be due the end of service benefit as set forth in the regulating laws.</p>

<p><strong>Article Twelve "Applicable Law"</strong><br/>
The provisions of the Labour code in the civil sector No. 6 of 2010 and the decisions
executing the same shall apply for all matters not provided for in the present contract.
Shall be considered null every condition agreed upon in violation of the provisions of
the law, unless the same has a better benefit for the worker.</p>

<p><strong>Article Thirteen "Special Conditions"</strong><br/>
1. {{special_condition_1}}<br/>
2. {{special_condition_2}}<br/>
3. {{special_condition_3}}</p>

<p><strong>Article Fourteen "Specialized Court"</strong><br/>
The court of first instance and its Labour departments, in accordance with the provisions
of the law No. 46 of the year 1987, shall be competent to peruse any conflicts resulting
from the execution or interpretation of the present contract.</p>

<p><strong>Article Fifteen "Contract Language"</strong><br/>
The present contract was made in Arabic and English . The Arabic texts shall prevail in
the case of any conflict between them.</p>

<p><strong>Article Sixteen "Contract Copies"</strong><br/>
The present contract was made in three copies, one for each party to work in accordance
therewith. The third copy shall be deposited at the Public Authority for Manpower.</p>

<table style="width:100%; margin-top:40px; border:none">
  <tr>
    <td style="border:none; text-align:left"><strong>First Party</strong><br/><br/>
      {{company_signature}}</td>
    <td style="border:none; text-align:right"><strong>Second Party</strong><br/><br/>
      {{employee_signature}}</td>
  </tr>
</table>
</div>
"""

# ── الكتلة العربية — الصفحة الثانية ──────────────────────────────────────────
_AR_PAGE2 = """
<div class="contract-ar" dir="rtl" style="text-align:right; page-break-before:always">
<p style="text-align:center"><strong>البند السابع</strong><br/><strong>" الأجازة السنوية "</strong></p>
<p>للطرف الثاني الحق في أجازة سنوية مدفوعة الأجر مدتها ..... {{annual_leave_days}} .... يوما ،
ولا يستحقها عن السنة الأولى إلا بعد انقضاء مدة تسعة أشهر تحسب من تاريخ نفاذ العقد .</p>

<p style="text-align:center"><strong>البند الثامن</strong><br/><strong>" عدد ساعات العمل "</strong></p>
<p>لا يجوز للطرف الأول تشغيل  الطرف الثاني لمدة تزيد عن ثماني ساعات عمل يوميا تتخللها فترة
راحة لا تقلعن ساعة باستثناء الحالات المقررة قانونا .</p>

<p style="text-align:center"><strong>البند التاسع</strong><br/><strong>" قيمة تذكرة السفر "</strong></p>
<p>تحمل الطرف الأول مصاريف عودة الطرف الثاني إلى بلد عند انتهاء علاقة العمل ومغاادرته
نهائيا للبلاد .</p>

<p style="text-align:center"><strong>البند العاشر</strong><br/>
<strong>" التأمين ضد إصابات وأمراض العمل "</strong></p>
<p>يلتزم الطرف الأول بالتأمين على الطرف الثاني ضد إصابات وأمراض العمل ، كما يلتزم بقيمة
التأمين الصحي طبقا للقانون رقم 1 لسنة 1999.</p>

<p style="text-align:center"><strong>البند الحادي عشر</strong><br/><strong>" مكافأة نهاية الخدمة "</strong></p>
<p>يستحق الطرف الثاني مكافأة نهاية الخدمة المنصوص عليها بالقوانين المنظمة .</p>

<p style="text-align:center"><strong>البند الثاني عشر</strong><br/><strong>" القانون الواجب التطبيق "</strong></p>
<p>تسععرى أحكام قانون العمل في القطالأ الأهلي رقم 6 لسنة 2010 والقرارات المنفذة له فيما لم
يرد بشأنه نص ي هذا العقد ، ويقع باطلا كل شرط  م الاتفاق عليه<br/>
بالمخالفة لأحكام القانون ، ما لم يكن فيه ميزة أفضل للعامل .</p>

<p style="text-align:center"><strong>البند الثالث عشر</strong><br/><strong>شروط خاصة</strong></p>
<p>1- ................{{special_condition_1}}.... .........<br/>
2- ...............{{special_condition_2}}..............<br/>
3- ...............{{special_condition_3}} .............</p>

<p style="text-align:center"><strong>البند الرابع عشر</strong><br/><strong>" المحكمة المختصة "</strong></p>
<p>تخت المحكمة الكلية ودوائرها العمالية طبقعا لأحكام القعانون رقم 46 لسنة 1987 ، بنظر كافة
المنازعات الناشئة عن تطبيق أو تفسير هذا العقد</p>

<p style="text-align:center"><strong>البند الخامس عشر</strong><br/><strong>" لغة العقد "</strong></p>
<p>حرر هذا العقد باللاتين العربية و الإنجليزية ، ويعتد بنصوص اللاة العربية عند وقولأ أي
تعارع بينهما .</p>

<p style="text-align:center"><strong>البند السادس عشر</strong><br/><strong>" نسخ العقد "</strong></p>
<p>حرر هذا العقد من ثلان نسخ كل طرف نسخة للعمل بموجبهعا والثالثة  تودع لدى الهيئة العامة
للقوى العاملة .</p>

<table style="width:100%; margin-top:40px; border:none">
  <tr>
    <td style="border:none; text-align:right"><strong>الطرف الاول</strong><br/><br/>
      {{company_signature}}</td>
    <td style="border:none; text-align:left"><strong>الطرف الثانى</strong><br/><br/>
      {{employee_signature}}</td>
  </tr>
</table>
</div>
"""

_BODY = _EN_PAGE1 + _AR_PAGE1 + _EN_PAGE2 + _AR_PAGE2


def upgrade() -> None:
    conn = op.get_bind()
    for code, name, name_en in [
        ("GOV-CONTRACT-HIRE", "العقد الحكومي — تعيين جديد",
         "Government Contract — New Hire"),
        ("GOV-CONTRACT-RENEWAL", "العقد الحكومي — تجديد إقامة",
         "Government Contract — Residency Renewal"),
    ]:
        exists = conn.execute(
            text("SELECT id FROM document_templates WHERE code = :c LIMIT 1"),
            {"c": code},
        ).first()
        if exists:
            conn.execute(text("""
                UPDATE document_templates
                   SET name = :name, name_en = :name_en, body_html = :body,
                       version = COALESCE(version, 1) + 1
                 WHERE code = :c
            """), {"c": code, "name": name, "name_en": name_en, "body": _BODY})
        else:
            conn.execute(text("""
                INSERT INTO document_templates
                    (company_id, code, name, name_en, category, body_html,
                     is_active, version, created_at)
                VALUES (NULL, :c, :name, :name_en, 'عقود', :body, TRUE, 1, CURRENT_TIMESTAMP)
            """), {"c": code, "name": name, "name_en": name_en, "body": _BODY})


def downgrade() -> None:
    # لا نُرجع النص السابق — الإدارة تعيد التعديل من /templates لو احتاجت
    pass
