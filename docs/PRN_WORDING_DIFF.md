# PRN Wording Diff Report — V1.4 spec vs seed.py

| Code | Name (seed) | Similarity | Missing placeholders | Notes |
| --- | --- | --- | --- | --- |
| PRN-001 | شهادة راتب | 0.00 | — | **REVIEW** — significant divergence |
| PRN-002 | شهادة لمن يهمه الأمر | 0.08 | — | **REVIEW** — significant divergence |
| PRN-003 | شهادة خبرة | 0.06 | — | **REVIEW** — significant divergence |
| PRN-004 | شهادة حالة وظيفية | 0.10 | `{{bank_name}}`, `{{gross_salary}}`, `{{hire_date}}`, `{{job_title}}` | **REVIEW** — significant divergence |
| PRN-005 | خطاب عدم ممانعة | 0.05 | `{{allowances}}`, `{{basic_salary}}`, `{{candidate_name}}`, `{{job_title}}`, `{{start_date}}` | **REVIEW** — significant divergence |
| PRN-006 | بيان بيانات موظف | 0.06 | `{{annual_leave_days}}`, `{{basic_salary}}`, `{{contract_end}}`, `{{contract_start}}`, `{{working_hours}}` | **REVIEW** — significant divergence |
| PRN-007 | شهادة مدة خدمة | 0.07 | `{{effective_date}}`, `{{new_location}}`, `{{old_location}}`, `{{transfer_type}}` | **REVIEW** — significant divergence |
| PRN-008 | خطاب تحويل راتب للبنك | 0.06 | `{{effective_date}}`, `{{new_title}}`, `{{old_title}}` | **REVIEW** — significant divergence |
| PRN-009 | إفادة استمرارية راتب | 0.09 | `{{effective_date}}`, `{{new_salary}}`, `{{old_salary}}`, `{{reason}}` | **REVIEW** — significant divergence |
| PRN-010 | خطاب موجه لجهة رسمية | 0.06 | `{{incident_date}}`, `{{incident_summary}}` | **REVIEW** — significant divergence |
| PRN-011 | خطاب عرض وظيفي | 0.03 | `{{attendees}}`, `{{employee_name}}`, `{{investigation_date}}`, `{{result}}`, `{{subject}}` | **REVIEW** — significant divergence |
| PRN-012 | إشعار تجديد عقد | 0.08 | `{{deduction_amount}}` | **REVIEW** — significant divergence |
| PRN-013 | إشعار عدم تجديد عقد | 0.07 | `{{action_taken}}`, `{{incident_date}}`, `{{policy_reference}}`, `{{violation_details}}` | **REVIEW** — significant divergence |
| PRN-014 | قبول استقالة | 0.05 | `{{received_at}}`, `{{warning_reference}}` | **REVIEW** — significant divergence |
| PRN-015 | قرار إنهاء خدمة | 0.10 | `{{balance_after}}`, `{{balance_before}}`, `{{days_count}}`, `{{end_date}}`, `{{leave_type}}`, `{{replacement_employee}}`, `{{return_date}}`, `{{start_date}}` | **REVIEW** — significant divergence |
| PRN-016 | قرار نقل موظف | 0.09 | `{{approved_at}}`, `{{finance_notes}}`, `{{financial_status}}` | **REVIEW** — significant divergence |
| PRN-017 | قرار تكليف بفرع أو موقع عمل | 0.07 | `{{legal_status}}`, `{{missing_documents}}`, `{{passport_expiry}}`, `{{residency_expiry}}` | **REVIEW** — significant divergence |
| PRN-018 | قرار ترقية | 0.00 | — | **REVIEW** — significant divergence |
| PRN-019 | قرار تعديل راتب | 0.05 | `{{delegate_name}}`, `{{documents_list}}`, `{{due_date}}`, `{{employee_or_company}}`, `{{government_entity}}`, `{{transaction_type}}` | **REVIEW** — significant divergence |
| PRN-020 | قرار بدل أو مكافأة | 0.06 | `{{deadline}}`, `{{missing_documents}}`, `{{submission_method}}` | **REVIEW** — significant divergence |
| PRN-021 | قرار خصم | 0.08 | `{{civil_id}}`, `{{delegate_name}}`, `{{expiry_date}}`, `{{reason}}`, `{{renewal_type}}`, `{{residency_no}}` | **REVIEW** — significant divergence |
| PRN-022 | إنذار موظف | 0.00 | — | **REVIEW** — significant divergence |
| PRN-023 | إنذار نهائي | 0.00 | — | **REVIEW** — significant divergence |
| PRN-024 | استدعاء للتحقيق الإداري | 0.00 | — | **REVIEW** — significant divergence |
| PRN-025 | قرار إيقاف مؤقت لحين التحقيق | 0.00 | — | **REVIEW** — significant divergence |
| PRN-026 | تكليف واعتماد عمل إضافي | 0.00 | — | **REVIEW** — significant divergence |
| PRN-027 | قرار اعتماد إجازة | 0.06 | `{{deductions_total}}`, `{{entitlements_total}}`, `{{hire_date}}`, `{{last_working_day}}`, `{{net_amount}}`, `{{salary_basis}}` | **REVIEW** — significant divergence |
| PRN-028 | إشعار عودة من إجازة | 0.04 | `{{deductions_total}}`, `{{entitlements_total}}`, `{{net_amount}}` | **REVIEW** — significant divergence |
| PRN-029 | بيان رصيد الإجازات | 0.12 | — | **REVIEW** — significant divergence |
| PRN-030 | كشف حضور شهري | 0.10 | `{{absence_days}}` | **REVIEW** — significant divergence |
| PRN-031 | تأكيد تعديل سجل حضور | 0.03 | `{{period}}` | **REVIEW** — significant divergence |
| PRN-032 | كشف راتب شهري مبسط | 0.08 | — | **REVIEW** — significant divergence |
| PRN-033 | إشعار نقص مستندات | 0.07 | `{{amount}}`, `{{approval_status}}`, `{{deduction_reference}}`, `{{payroll_effect}}`, `{{period}}`, `{{reason}}` | **REVIEW** — significant divergence |
| PRN-034 | تفويض تجديد إقامة | 0.02 | `{{assets_list}}` | **REVIEW** — significant divergence |
| PRN-035 | تفويض تجديد إذن عمل | 0.05 | `{{assets_list}}`, `{{issues}}`, `{{return_condition}}` | **REVIEW** — significant divergence |
| PRN-036 | إشعار تحديث البطاقة المدنية أو الجواز | 0.04 | `{{end_date}}`, `{{location}}`, `{{manager_name}}`, `{{mission_purpose}}`, `{{start_date}}` | **REVIEW** — significant divergence |
| PRN-037 | تكليف مندوب بمعاملة حكومية | 0.03 | `{{effective_date}}`, `{{employee_name}}`, `{{new_shift}}`, `{{old_shift}}`, `{{reason}}` | **REVIEW** — significant divergence |
| PRN-038 | التسوية النهائية ونهاية الخدمة | 0.05 | `{{hours}}`, `{{overtime_date}}`, `{{rate_or_amount}}`, `{{reason}}` | **REVIEW** — significant divergence |
| PRN-039 | شهادة إخلاء طرف | 0.00 | — | **REVIEW** — significant divergence |
| PRN-040 | محضر تسليم عهدة | 0.01 | `{{document_hash}}`, `{{document_reference}}`, `{{signers}}`, `{{technical_metadata}}`, `{{timestamps}}` | **REVIEW** — significant divergence |
| PRN-041 | محضر استلام وتسليم مستندات | 0.06 | — | **REVIEW** — significant divergence |
| PRN-042 | سجل اعتماد التوقيع الإلكتروني | 0.01 | `{{employee_name}}` | **REVIEW** — significant divergence |

## Summary
- ≈Identical (≥0.9): **0**
- Close (0.5–0.9): **0**
- Diverges (<0.5): **42**
- Missing in seed: **0**
- Missing in spec extract: **0**
- Seed templates with **zero** `{{placeholders}}`: **0 / 42**

## Root-cause finding

الفرق الأكبر بين seed.py وV1.4 spec ليس صياغة النص — بل أن **قوالب seed تستخدم تسميات عربية حرفية** مثل `اسم الشركة` و `اسم الموظف` في مواضع كان يجب أن تحتوي على placeholders `{{company_name}}` و `{{employee_name}}`. النتيجة: عند الطباعة لا يحدث أي استبدال بالبيانات الفعلية للموظف/الشركة، ويطبع النص كما هو لأي موظف. الـ spec يذكر هذا صراحة في P0-PDF-01 (Templates & Wording, ص 26): `placeholders يعتمد renderer` — استخدم placeholders، لا نصًا ثابتًا.

**الحل المقترح:** استبدل التسميات الحرفية في قوالب seed.py بالـ placeholders الصحيحة (`{{employee_name}}`, `{{company_name}}`, `{{civil_id}}`, `{{job_title}}`, `{{hire_date}}`, `{{basic_salary}}`, `{{allowances_total}}`, `{{gross_salary}}`, إلخ). محرك templates.py يقوم بالفعل باستبدال `{{key}}` عند طباعة القالب (راجع `_TOKEN_RE` و`_build_context` في `app/routers/templates.py`)، فالتعديل عمل نصي بحت على seed.py يليه إعادة seed.

_ملاحظة تقنية: النص المستخرَج من PDF spec يظهر بترتيب RTL معكوس (`}key{` بدل `{{key}}`) — التطبيع يعالجه قبل المقارنة، لكن للفحص البصري لأي صف REVIEW يُنصح بمراجعة الـ spec الأصلي مباشرة._

## Detailed diffs (rows marked REVIEW)

### PRN-001 — شهادة راتب

**Spec operational text (extracted):**

```

```

**Current seed body (stripped HTML):**

```
تشهد شركة {{company_name}} بأن السيد/السيدة {{employee_name}}، حامل الرقم المدني {{civil_id}}، يعمل لديها بوظيفة {{job_title}} منذ تاريخ {{hire_date}}، ويتقاضى راتبًا أساسيًا قدره {{basic_salary}} د.ك، وبدلات {{allowances_total}} د.ك، بإجمالي شهري {{gross_salary}} د.ك. صدرت هذه الشهادة بناءً على طلبه لتقديمها إلى {{target_entity}} دون أدنى مسؤولية على الشركة تجاه الغير. {{company_name}} certifies that Mr./Ms. {{employee_name}}, Civil ID {{civil_id}}, has been employed as {{job_title}} since {{hire_date}} and receives a basic salary of KWD {{basic_salary}}, allowances of KWD {{allowances_total}}, totaling KWD {{gross_salary}} monthly. This certificate is issued upon request for submission to {{target_entity}} without liability to third parties. [____] /KWD البدلات [____] /KWD الراتب الأساسي د.ك د.ك Basic Salary Allowances [Bank/Embassy/Other] الجهة الموجه إليها [____] /KWD الإجمالي د.ك Total Salary Addressed To Prepared by HR إعداد الموارد البشرية .................... التوقيع والتاريخ / Signature &amp; Date Manager Review مراجعة المدير .................... التوقيع والتاريخ / Signature &amp; Date Authorized Signatory المخول بالتوقيع .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders in seed not mentioned by spec:** allowances_total, basic_salary, civil_id, company_name, employee_name, gross_salary, hire_date, job_title, since, target_entity

### PRN-002 — شهادة لمن يهمه الأمر

**Spec operational text (extracted):**

```
وما زال على رأس عمله حتى تاريخ}hire_date{ منذ}job_title{ يعمل لديها بوظيفة}employee_name{السيدة/ بأن السيد}company_name{ تشهد شركة .}purpose{ لغرض}target_entity{إصدار هذا الخطاب. وقد صدرت هذه الإفادة بناءً على طلبه لتقديمها إلى
```

**Current seed body (stripped HTML):**

```
إلى من يهمه الأمر: تشهد شركة {{company_name}} بأن السيد/السيدة {{employee_name}} يعمل لديها بوظيفة {{job_title}} منذ {{hire_date}} وما زال على رأس عمله حتى تاريخ إصدار هذا الخطاب. صدرت هذه الإفادة بناءً على طلبه لتقديمها إلى {{target_entity}} لغرض {{purpose}}. To whom it may concern: {{company_name}} confirms that Mr./Ms. {{employee_name}} is employed as {{job_title}} since {{hire_date}} and remains actively employed as of the issue date. Issued upon request for submission to {{target_entity}} for the purpose of {{purpose}}. [Fixed/Unlimited] نوع العقد [DD/MM/YYYY] تاريخ التعيين Joining Date Contract Type [ ] الغرض [Active] حالة الموظف Employment Status Purpose Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders in seed not mentioned by spec:** since

### PRN-003 — شهادة خبرة

**Spec operational text (extracted):**

```
إلى}service_start{ خلال الفترة من}job_title{ قد عمل لديها بوظيفة}employee_name{السيدة/ بأن السيد}company_name{ تشهد شركة . وقد أدى مهامه خلال مدة خدمته وفق سجلات الشركة، وصدرت هذه الشهادة بناءً على طلبه. }service_end{
```

**Current seed body (stripped HTML):**

```
تشهد شركة {{company_name}} بأن السيد/السيدة {{employee_name}} قد عمل لديها خلال الفترة من {{service_start}} إلى {{service_end}} بوظيفة {{job_title}}، وأدى المهام الموكلة إليه وفق سجلات الشركة. صدرت هذه الشهادة بناءً على طلبه. {{company_name}} certifies that Mr./Ms. {{employee_name}} worked from {{service_start}} to {{service_end}} as {{job_title}} and performed the assigned duties according to company records. Issued upon request. [ ] القسم الأخير [From] [To] فترة الخدمة Service Period Last Department [Optional] التقييم العام [ ] سبب انتهاء الخدمة Reason for Leaving General Rating Prepared by HR إعداد الموارد البشرية .................... التوقيع والتاريخ / Signature &amp; Date Legal Review مراجعة الشؤون القانونية .................... التوقيع والتاريخ / Signature &amp; Date Authorized Signatory المخول بالتوقيع .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders in seed not mentioned by spec:** as, to

### PRN-004 — شهادة حالة وظيفية

**Spec operational text (extracted):**

```
،}hire_date{ منذ}job_title{ بوظيفة}company_name{ يعمل لدى}employee_name{السيدة/ المحترمون، نفيدكم بأن السيد}bank_name{ / السادة د.ك. صدر الخطاب بناءً على طلب الموظف ودون التزام مالي على الشركة تجاه البنك. }gross_salary{ويتقاضى إجمالي راتب شهري قدره
```

**Current seed body (stripped HTML):**

```
تفيد شركة {{company_name}} بأن بيانات الحالة الوظيفية للموظف/ة {{employee_name}} (رقم مدني {{civil_id}}) كما هي مبينة في هذا المستند حتى تاريخ إصداره، وتم استخراجها مباشرة من نظام الموارد البشرية. {{company_name}} confirms that the employment status of {{employee_name}} (Civil ID {{civil_id}}) shown in this document is accurate as of the issue date and has been extracted from the HRMS. Active/Leave/Suspended/[ [DD/MM/YYYY] تاريخ بداية الحالة الحالة Status ]Ended Status Start Date [ ] المسؤول المباشر [Fulltime/Parttime] الدوام Work Schedule Line Manager Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** bank_name, gross_salary, hire_date, job_title
**Placeholders in seed not mentioned by spec:** civil_id

### PRN-005 — خطاب عدم ممانعة

**Spec operational text (extracted):**

```
، براتب أساسي}start_date{ اعتبارًا من }job_title{ عرضًا للعمل بوظيفة }candidate_name{السيدة/ أن تقدم للسيد}company_name{ يسر شركة . يخضع العرض لاستكمال المستندات والتوقيع على عقد العمل وسياسات الشركة.}allowances{د.ك وبدلات}basic_salary{
```

**Current seed body (stripped HTML):**

```
تشهد شركة {{company_name}} بأنها لا تمانع في {{purpose}} للموظف/ة {{employee_name}}، بشرط عدم تعارضه مع التزاماته الوظيفية وسياسات الشركة، ودون ترتيب أي التزام مالي أو قانوني إضافي على الشركة ما لم يذكر خلاف ذلك صراحة. {{company_name}} has no objection to {{purpose}} for {{employee_name}}, provided it does not conflict with employment obligations or company policy and creates no additional financial or legal liability unless expressly stated. [From] [To] الفترة [ ] الغرض Purpose Period [ ] الجهة المستفيدة [ ] الشروط Conditions Beneficiary Entity Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Legal Review مراجعة قانونية .................... التوقيع والتاريخ / Signature &amp; Date Manager Approval اعتماد المدير .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** allowances, basic_salary, candidate_name, job_title, start_date
**Placeholders in seed not mentioned by spec:** employee_name, for, purpose

### PRN-006 — بيان بيانات موظف

**Spec operational text (extracted):**

```
، الوظيفة}contract_end{، تاريخ النهاية}contract_start{، تاريخ البداية}contract_type{: نوع العقد}employee_name{ ملخص بيانات عقد الموظف يومًا. هذا الملخص لا يغني عن العقد الموقع. }annual_leave_days{، والإجازة السنوية}working_hours{ د.ك، ساعات العمل}basic_salary{، الراتب الأساسي}job_title{
```

**Current seed body (stripped HTML):**

```
بيان بيانات الموظف/ة {{employee_name}} (رقم مدني {{civil_id}}، وظيفة {{job_title}}، تاريخ التعيين {{hire_date}}، نوع العقد {{contract_type}}) مستخرج من نظام الموارد البشرية ويعرض البيانات المسجلة وقت الإصدار. أي تعديل لاحق يخضع لسجل التدقيق والصلاحيات المعتمدة. Employee data statement for {{employee_name}} (Civil ID {{civil_id}}, Job {{job_title}}, Hire Date {{hire_date}}, Contract {{contract_type}}) generated from the HRMS at issue time. Subsequent changes are subject to audit logs and approved permissions. [ ] نوع العقد [DD/MM/YYYY] تاريخ التعيين Joining Date Contract Type [____] /KWD الراتب الفعلي [____] /KWD الراتب الرسمي د.ك د.ك Official Salary Actual Salary [ ] مكان العمل الفعلي [ ] مكان العمل الرسمي Official Work Location Actual Work Location [DD/MM/YYYY] انتهاء الإقامة [ ] رقم الإقامة . Residency No Residency Expiry Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** annual_leave_days, basic_salary, contract_end, contract_start, working_hours
**Placeholders in seed not mentioned by spec:** civil_id, hire_date

### PRN-007 — شهادة مدة خدمة

**Spec operational text (extracted):**

```
. يلتزم الموظف}transfer_type{، بصفة}effective_date{ اعتبارًا من }new_location{ إلى}old_location{ من}employee_name{السيدة/ تقرر نقل السيد بتسليم الأعمال والعهد حسب الإجراءات المعتمدة، ويظل باقي شروط العمل دون تغيير ما لم يذكر خلاف ذلك.
```

**Current seed body (stripped HTML):**

```
تشهد شركة {{company_name}} بأن مدة خدمة الموظف/ة {{employee_name}} المحتسبة وفق سجلات الشركة تمتد من {{hire_date}} حتى {{as_of_date}}، بإجمالي {{service_duration}} من الخدمة الفعلية. {{company_name}} certifies that {{employee_name}} has completed service from {{hire_date}} to {{as_of_date}}, totaling {{service_duration}} of actual service according to company records. [DD/MM/YYYY] تاريخ االحتساب [DD/MM/YYYY] تاريخ بداية الخدمة Service Start Calculation Date [None/Details] فترات االنقطاع [Y/M/D] مدة الخدمة Service Length Excluded Periods Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** effective_date, new_location, old_location, transfer_type
**Placeholders in seed not mentioned by spec:** as_of_date, company_name, hire_date, service_duration, to

### PRN-008 — خطاب تحويل راتب للبنك

**Spec operational text (extracted):**

```
. ويطبق أثر الدرجة والراتب وفق الاعتماد}effective_date{ اعتبارًا من }new_title{ إلى}old_title{ من وظيفة}employee_name{السيدة/ تقرر ترقية السيد المالي المرفق، مع استمرار باقي شروط العقد.
```

**Current seed body (stripped HTML):**

```
السادة {{bank_name}} المحترمين، نفيدكم بأن الموظف/ة {{employee_name}} يعمل لدى شركة {{company_name}} بوظيفة {{job_title}} منذ {{hire_date}} وبإجمالي راتب شهري {{gross_salary}} د.ك، وقد تقرر تحويل راتبه الشهري إلى الحساب رقم {{iban}} اعتبارًا من راتب شهر {{effective_month}}، وذلك دون التزام مالي إضافي على الشركة تجاه البنك. Dear {{bank_name}}, we confirm that {{employee_name}} is employed by {{company_name}} as {{job_title}} since {{hire_date}} with a total monthly salary of KWD {{gross_salary}}. The monthly salary shall be transferred to account {{iban}} effective from payroll month {{effective_month}}, without additional liability on the company toward the bank. [ ] اسم البنك IBAN/ [ ] رقم الحساب Bank Name Account / IBAN [DD/MM/YYYY] تاريخ البدء [____] /KWD راتب التحويل د.ك Transfer Salary Effective Date Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** effective_date, new_title, old_title
**Placeholders in seed not mentioned by spec:** as, bank_name, company_name, effective_month, gross_salary, hire_date, iban, job_title, since

### PRN-009 — إفادة استمرارية راتب

**Spec operational text (extracted):**

```
. يعتمد}reason{، وذلك بسبب}effective_date{ د.ك اعتبارًا من }new_salary{ د.ك إلى}old_salary{ من}employee_name{السيدة/ تقرر تعديل راتب السيد القرار من الإدارة والموارد البشرية والمالية، ويثبت التغيير في سجل التدقيق.
```

**Current seed body (stripped HTML):**

```
تفيد شركة {{company_name}} بأن الموظف/ة {{employee_name}} ما زال على رأس عمله، وأن راتبه يصرف وفق دورة الرواتب المعتمدة بالشركة، مع خضوع أي تغيير لاحق للقرارات والسياسات الداخلية. {{company_name}} confirms that {{employee_name}} remains actively employed and receives salary according to the company payroll cycle. Any future change is subject to internal decisions and policies. [Bank/Cash] طريقة الصرف [Monthly] دورة الصرف Payroll Cycle Payment Method [Active] الحالة [MM/YYYY] آخر راتب مصروف Last Payroll Month Status Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** effective_date, new_salary, old_salary, reason
**Placeholders in seed not mentioned by spec:** company_name

### PRN-010 — خطاب موجه لجهة رسمية

**Spec operational text (extracted):**

```
هذا الإنذار بضرورة الالتزام}employee_name{السيدة/، يوجه إلى السيد}incident_summary{ والمتعلقة بـ}incident_date{ بالإشارة إلى الواقعة بتاريخ بسياسات العمل والتعليمات المعتمدة. ويعد تكرار المخالفة سببًا لاتخاذ الإجراء المناسب وفق النظام. توقيع الموظف أدناه يفيد العلم والاستلام ولا يعد إقرارًا بصحة الواقعة.
```

**Current seed body (stripped HTML):**

```
السادة {{target_entity}} المحترمين، بالإشارة إلى طلبكم بشأن {{subject}}، نفيدكم بأن بيانات الموظف/ة {{employee_name}} (رقم مدني {{civil_id}}، وظيفة {{job_title}}) صحيحة وفق سجلات شركة {{company_name}} حتى تاريخ إصدار هذا الخطاب. وتفضلوا بقبول فائق الاحترام. Dear {{target_entity}}, with reference to your request regarding {{subject}}, we confirm that the information of {{employee_name}} (Civil ID {{civil_id}}, Job {{job_title}}) is accurate per {{company_name}} records as of the issue date. Yours faithfully. [ ] الموضوع [ ] الجهة Entity Subject [ ] المرفقات [ ] رقم المرجع الخارجي External Reference Attachments Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** incident_date, incident_summary
**Placeholders in seed not mentioned by spec:** civil_id, company_name, job_title, subject, target_entity

### PRN-011 — خطاب عرض وظيفي

**Spec operational text (extracted):**

```
بالوقائع وسماع}employee_name{، وتمت مواجهة الموظف}attendees{. حضر كل من}subject{ تم فتح محضر تحقيق بشأن}investigation_date{ بتاريخ ، وترفع التوصية للجهة المختصة لاتخاذ القرار.}result{أقواله ودفاعه وإرفاق ما قدمه من مستندات. خلصت اللجنة إلى
```

**Current seed body (stripped HTML):**

```
يسر شركة {{company_name}} أن تقدم للسيد/السيدة {{candidate_name}} عرضًا للعمل بوظيفة {{job_title}} في {{location}} اعتبارًا من {{start_date}}، براتب أساسي {{basic_salary}} د.ك وبدلات {{allowances}} د.ك، وفق الشروط الموضحة أدناه. يصبح العرض نافذًا بعد توقيع الطرفين واستكمال المستندات والموافقات المطلوبة. {{company_name}} is pleased to offer Mr./Ms. {{candidate_name}} employment as {{job_title}} at {{location}} effective {{start_date}}, with a basic salary of KWD {{basic_salary}} and allowances of KWD {{allowances}}, subject to the terms below. The offer becomes effective upon signature by both parties and completion of required documents and approvals. [____] /KWD إجمالي الراتب [____] /KWD الراتب الأساسي د.ك د.ك Basic Salary Total Package [DD/MM/YYYY] تاريخ المباشرة [ ] فترة التجربة Probation Start Date [DD/MM/YYYY] مدة صلاحية العرض [ ] ساعات العمل Working Hours Offer Validity الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared by HR إعداد الموارد البشرية .................... التوقيع والتاريخ / Signature &amp; Date Manager Approval اعتماد المدير .................... التوقيع والتاريخ / Signature &amp; Date Candidate Acceptance قبول المرشح .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** attendees, employee_name, investigation_date, result, subject
**Placeholders in seed not mentioned by spec:** allowances, at, basic_salary, candidate_name, company_name, effective, job_title, location, start_date

### PRN-012 — إشعار تجديد عقد

**Spec operational text (extracted):**

```
عن شهر}employee_name{السيدة/ د.ك من مستحقات السيد}deduction_amount{ بعد مراجعة الواقعة والمستندات و
```

**Current seed body (stripped HTML):**

```
نحيط الموظف/ة {{employee_name}} علمًا بأن الشركة ترغب في تجديد عقد العمل اعتبارًا من {{start_date}} ولمدة {{duration}}، وفق الشروط والتعديلات الموضحة أدناه. يرجى إبداء الموافقة أو الملاحظات خلال {{response_days}} أيام عمل. {{employee_name}} is notified that the company intends to renew the employment contract effective {{start_date}} for {{duration}}, subject to the terms and amendments below. Please confirm acceptance or comments within {{response_days}} working days. [____] /KWD الراتب الجديد [ ] مدة التجديد د.ك ........................ Renewal Period New Salary [ ] مكان العمل [ ] المسمى الوظيفي Job Title Work Location [ ] مالحظات [DD/MM/YYYY] آخر موعد للرد Response Deadline Notes الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** deduction_amount
**Placeholders in seed not mentioned by spec:** duration, for, response_days, start_date

### PRN-013 — إشعار عدم تجديد عقد

**Spec operational text (extracted):**

```
. تقرر اتخاذ}violation_details{ والمتمثلة في}incident_date{ بتاريخ}policy_reference{ للسياسة رقم}employee_name{السيدة/ ثبتت مخالفة السيد بعد مراجعة أقوال الموظف والمستندات ذات الصلة.}action_taken{الإجراء
```

**Current seed body (stripped HTML):**

```
يُخطر الموظف/ة {{employee_name}} بأن عقد العمل الحالي لن يتم تجديده بعد تاريخ انتهائه في {{expiry_date}}. يستمر الموظف في أداء واجباته وتسليم العهد والمستندات حتى آخر يوم عمل، مع استكمال إجراءات التسوية وإخلاء الطرف. {{employee_name}} is notified that the current employment contract will not be renewed after its expiry on {{expiry_date}}. Duties, handover, final settlement, and clearance procedures must be completed through the last working day. [DD/MM/YYYY] آخر يوم عمل [DD/MM/YYYY] تاريخ انتهاء العقد Contract Expiry Last Working Day [ ] إجراءات التسليم [ ] فترة الإشعار Notice Period Handover Requirements الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** action_taken, incident_date, policy_reference, violation_details
**Placeholders in seed not mentioned by spec:** expiry_date

### PRN-014 — قبول استقالة

**Spec operational text (extracted):**

```
، وأن توقيعي يفيد العلم بمحتواه فقط دون أن يسقط حقي في}received_at{ بتاريخ}warning_reference{ باستلام الإنذار رقم}employee_name{ أقر أنا تقديم رد أو اعتراض خلال المدة المحددة.
```

**Current seed body (stripped HTML):**

```
بالإشارة إلى الاستقالة المقدمة من الموظف/ة {{employee_name}} بتاريخ {{resignation_date}}، تقرر قبولها على أن يكون آخر يوم عمل هو {{last_working_day}} بعد تطبيق فترة الإخطار {{notice_period}}. يبدأ فورًا مسار إخلاء الطرف وتسوية المستحقات وفق الإجراءات المعتمدة. With reference to the resignation submitted by {{employee_name}} on {{resignation_date}}, the resignation is accepted and the last working day shall be {{last_working_day}} after applying the notice period {{notice_period}}. Clearance and final settlement procedures begin immediately. [DD/MM/YYYY] آخر يوم عمل [DD/MM/YYYY] تاريخ تقديم االستقالة Resignation Date Last Working Day [Pending/Completed] حالة التسوية [ ] فترة الإشعار Notice Period Settlement Status الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** received_at, warning_reference
**Placeholders in seed not mentioned by spec:** last_working_day, notice_period, on, resignation_date

### PRN-015 — قرار إنهاء خدمة

**Spec operational text (extracted):**

```
يومًا. الرصيد }days_count{ بإجمالي}end_date{ إلى}start_date{ خلال الفترة من}leave_type{ من نوع}employee_name{السيدة/ اعتمدت إجازة السيد إن وجد.}replacement_employee{. تم اعتماد البديل}return_date{ يومًا، وتاريخ العودة المتوقع }balance_after{ يومًا وبعدها }balance_before{قبل الإجازة
```

**Current seed body (stripped HTML):**

```
استنادًا إلى الصلاحيات المعتمدة ونتيجة {{termination_reason}} (مرجع {{reference}})، تقرر إنهاء خدمة الموظف/ة {{employee_name}} اعتبارًا من {{effective_date}}. تستكمل إجراءات التسليم والتسوية النهائية وإخلاء الطرف، مع حفظ حق الموظف في التظلم وفق سياسة الشركة. Based on approved authority and {{termination_reason}} (ref {{reference}}), the employment of {{employee_name}} is terminated effective {{effective_date}}. Handover, final settlement, and clearance shall be completed while preserving the employee&#x27;s right to appeal under company policy. Decision/Investigation/[ المرجع [ ] سبب الإنهاء Reason Reference ]Contract [DD/MM/YYYY] حق التظلم حتى [DD/MM/YYYY] تاريخ النفاذ Effective Date Appeal Deadline الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared by HR إعداد الموارد البشرية .................... التوقيع والتاريخ / Signature &amp; Date Legal Review مراجعة الشؤون القانونية .................... التوقيع والتاريخ / Signature &amp; Date Authorized Approval اعتماد صاحب الصلاحية .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** balance_after, balance_before, days_count, end_date, leave_type, replacement_employee, return_date, start_date
**Placeholders in seed not mentioned by spec:** effective_date, reference, termination_reason

### PRN-016 — قرار نقل موظف

**Spec operational text (extracted):**

```
. لا مانع مالي من استكمال}financial_status{، تبين أن موقف السلف والقروض والعهد المالية هو}employee_name{ بعد المراجعة المالية لطلب سفر الموظف .}approved_at{. يعتمد هذا الإفادة المحاسب المخول بتاريخ}finance_notes{توجد الملاحظات التالية/الإجراء
```

**Current seed body (stripped HTML):**

```
تقرر نقل الموظف/ة {{employee_name}} من {{old_location}} إلى {{new_location}} بصفة {{transfer_type}} اعتبارًا من {{effective_date}}. يتم تحديث المسؤول المباشر ومكان العمل الفعلي والصلاحيات والعهد المرتبطة بالوظيفة الجديدة، ويظل باقي شروط العمل دون تغيير ما لم يذكر خلاف ذلك. {{employee_name}} is transferred from {{old_location}} to {{new_location}} as {{transfer_type}} effective {{effective_date}}. Reporting line, actual work location, permissions, and assigned assets shall be updated accordingly; other terms remain unchanged unless stated otherwise. [Department/Branch] إلى [Department/Branch] من From To [DD/MM/YYYY] تاريخ النفاذ [ ] المسؤول الجديد New Line Manager Effective Date [ ] مالحظات [____ No/Yes] تغيير الراتب : ........................ Salary Change Notes الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** approved_at, finance_notes, financial_status
**Placeholders in seed not mentioned by spec:** as, effective, effective_date, new_location, old_location, to, transfer_type

### PRN-017 — قرار تكليف بفرع أو موقع عمل

**Spec operational text (extracted):**

```
. الموقف}residency_expiry{ والإقامة صالحة حتى}passport_expiry{، تبين أن الجواز صالح حتى}employee_name{ بعد فحص مستندات سفر الموظف .}missing_documents{، والمستندات الناقصة إن وجدت}legal_status{المستندي/القانوني
```

**Current seed body (stripped HTML):**

```
يُكلف الموظف/ة {{employee_name}} بالعمل في {{location}} خلال الفترة من {{start_date}} إلى {{end_date}}، تحت إشراف {{manager_name}}، مع الالتزام بساعات العمل والتعليمات الخاصة بالموقع. {{employee_name}} is assigned to work at {{location}} from {{start_date}} to {{end_date}} under the supervision of {{manager_name}}, subject to the location&#x27;s working hours and instructions. [ ] الموقع الفعلي [ ] الموقع الرسمي Official Location Actual Location [ ] المسؤول [From] [To] فترة التكليف Assignment Period Supervisor الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** legal_status, missing_documents, passport_expiry, residency_expiry
**Placeholders in seed not mentioned by spec:** end_date, from, location, manager_name, start_date, to

### PRN-018 — قرار ترقية

**Spec operational text (extracted):**

```

```

**Current seed body (stripped HTML):**

```
تقديرًا للأداء والكفاءة، تقرر ترقية الموظف/ة {{employee_name}} من وظيفة {{old_title}} إلى وظيفة {{new_title}} اعتبارًا من {{effective_date}}. يطبق أثر الدرجة والراتب وفق الاعتماد المالي المرفق، مع استمرار باقي شروط العقد. In recognition of performance and competence, {{employee_name}} is promoted from {{old_title}} to {{new_title}} effective {{effective_date}}. Grade and salary impact apply per the attached financial approval; other contract terms continue. [ ] المسمى الجديد [ ] المسمى السابق Previous Title New Title [____] /KWD الراتب الجديد [____] /KWD الراتب السابق د.ك د.ك Previous Salary New Salary [DD/MM/YYYY] تاريخ النفاذ [ ] الدرجة المستوى Grade / Level Effective Date الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders in seed not mentioned by spec:** effective, effective_date, employee_name, new_title, old_title, to

### PRN-019 — قرار تعديل راتب

**Spec operational text (extracted):**

```
. المستندات}government_entity{ لدى}employee_or_company{ الخاصة بـ}transaction_type{ بمتابعة معاملة}delegate_name{ يكلف المندوب . يلتزم المندوب بتحديث حالة المعاملة وإرفاق إيصالاتها.}due_date{، والموعد المستهدف}documents_list{المسلمة
```

**Current seed body (stripped HTML):**

```
تقرر تعديل راتب الموظف/ة {{employee_name}} من {{old_salary}} د.ك إلى {{new_salary}} د.ك اعتبارًا من {{effective_date}}، وذلك بسبب {{reason}}. يعتمد القرار من الإدارة والموارد البشرية والمالية، ويثبت التغيير في سجل التدقيق (before/after). The salary of {{employee_name}} is adjusted from KWD {{old_salary}} to KWD {{new_salary}} effective {{effective_date}}, due to {{reason}}. Approved by Management, HR, and Finance, with the change recorded in the audit log (before/after). [____] الراتب الرسمي الجديد [____] الراتب الرسمي السابق د.ك د.ك Previous Official Salary New Official Salary [____] الراتب الفعلي الجديد [____] الراتب الفعلي السابق د.ك د.ك Previous Actual Salary New Actual Salary [MM/YYYY] شهر التطبيق [ ] سبب التعديل Reason Payroll Month الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** delegate_name, documents_list, due_date, employee_or_company, government_entity, transaction_type
**Placeholders in seed not mentioned by spec:** effective, effective_date, employee_name, new_salary, old_salary, reason

### PRN-020 — قرار بدل أو مكافأة

**Spec operational text (extracted):**

```
من خلال}deadline{. يرجى رفعها قبل}missing_documents{ علمًا بأن ملفه يحتاج إلى المستندات التالية }employee_name{السيدة/ نحيط السيد ، وإلا قد يتعذر استكمال المعاملة المرتبطة.}submission_method{
```

**Current seed body (stripped HTML):**

```
تقرر منح الموظف/ة {{employee_name}} بدل/مكافأة بقيمة {{amount}} د.ك عن {{reason}} خلال الفترة {{period}}، على أن تُصرف وفق دورة الرواتب والإجراءات المالية المعتمدة. {{employee_name}} is granted an allowance/bonus of KWD {{amount}} for {{reason}} during the period {{period}}, payable per the approved payroll and finance process. [____] /KWD القيمة [Allowance/Bonus] النوع د.ك Type Amount [Payroll/Separate] طريقة الصرف [ ] الفترة Period Payment Method [Yes/No] خاضع لالستقطاع [ ] السبب Reason Subject to Deduction Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** deadline, missing_documents, submission_method
**Placeholders in seed not mentioned by spec:** amount, for, period, reason

### PRN-021 — قرار خصم

**Spec operational text (extracted):**

```
. نوع التجديد}expiry_date{ والمنتهية في}residency_no{، إقامة رقم}civil_id{، رقم مدني}employee_name{ يرجى اتخاذ إجراءات تجديد إقامة الموظف .}delegate_name{. تعتمد المعاملة وفق المسار المحدد ثم تسند إلى المندوب}reason{وسببه}renewal_type{
```

**Current seed body (stripped HTML):**

```
بناءً على المرجع/المخالفة {{reference}} وبعد مراجعة المستندات، تقرر خصم مبلغ {{amount}} د.ك من مستحقات الموظف/ة {{employee_name}}، على أن ينفذ في راتب شهر {{payroll_month}}، مع إتاحة حق التظلم وفق السياسة المعتمدة. Based on {{reference}} and review of supporting records, a deduction of KWD {{amount}} is imposed on {{employee_name}}, to be applied in payroll month {{payroll_month}}, with the right to appeal under approved policy. [ ] القيمة [Amount/Days] نوع الخصم Deduction Type Value [MM/YYYY] شهر التنفيذ [ ] المرجع Reference Payroll Month [None/Submitted] حالة التظلم [DD/MM/YYYY] آخر موعد للتظلم Appeal Deadline Appeal Status الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared by Admin إعداد الشؤون الإدارية .................... التوقيع والتاريخ / Signature &amp; Date Legal Review مراجعة قانونية .................... التوقيع والتاريخ / Signature &amp; Date Manager Approval اعتماد المدير .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** civil_id, delegate_name, expiry_date, reason, renewal_type, residency_no
**Placeholders in seed not mentioned by spec:** amount, payroll_month, reference

### PRN-022 — إنذار موظف

**Spec operational text (extracted):**

```

```

**Current seed body (stripped HTML):**

```
بالإشارة إلى الواقعة بتاريخ {{incident_date}} المتعلقة بـ {{incident_summary}}، يوجه إلى الموظف/ة {{employee_name}} هذا الإنذار بضرورة الالتزام بسياسات العمل والتعليمات المعتمدة. تكرار المخالفة سبب لاتخاذ الإجراء المناسب وفق النظام. توقيع الموظف أدناه يفيد العلم والاستلام ولا يعد إقرارًا بصحة الواقعة. With reference to the incident on {{incident_date}} related to {{incident_summary}}, {{employee_name}} is issued this warning to comply with company policies and instructions. Recurrence justifies further action per the internal rules. The employee&#x27;s signature acknowledges receipt only and does not constitute admission of the incident. [DD/MM/YYYY] تاريخ الواقعة [First/Second] نوع الإنذار Warning Level Incident Date [ ] الإجراء التصحيحي [ ] المخالفة Violation Corrective Action [ ] مرجع السياسة [ ] فترة المتابعة Monitoring Period Policy Reference الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders in seed not mentioned by spec:** employee_name, incident_date, incident_summary

### PRN-023 — إنذار نهائي

**Spec operational text (extracted):**

```

```

**Current seed body (stripped HTML):**

```
نظرًا لتكرار/جسامة المخالفة الموضحة أدناه (المرجع {{reference}})، يوجه إلى الموظف/ة {{employee_name}} إنذار نهائي. ويعد أي تكرار أو عدم التزام خلال فترة المتابعة سببًا لاتخاذ إجراء أشد وفق القرارات والسياسات المعتمدة. Due to the repeated/serious violation detailed below (ref {{reference}}), {{employee_name}} is issued a final warning. Any recurrence or failure to comply during the monitoring period may result in stronger action under approved policies. [ ] المخالفة الحالية [References] الإنذارات السابقة Previous Warnings Current Violation [ ] فترة المتابعة [ ] الإجراء المطلوب Required Action Monitoring Period [ ] مرجع التحقيق [ ] نتيجة عدم االلتزام Consequence . Investigation Ref الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders in seed not mentioned by spec:** employee_name, reference

### PRN-024 — استدعاء للتحقيق الإداري

**Spec operational text (extracted):**

```

```

**Current seed body (stripped HTML):**

```
يطلب من الموظف/ة {{employee_name}} الحضور أمام {{investigator}} في {{investigation_date}} بمكان {{location}} لمناقشة موضوع {{subject}}. يحق للموظف تقديم مستنداته وإفادته، ويثبت عدم الحضور دون عذر في سجل التحقيق. {{employee_name}} is required to attend an administrative investigation before {{investigator}} on {{investigation_date}} at {{location}} regarding {{subject}}. The employee may submit documents and statements; absence without valid reason shall be recorded. [DD/MM/YYYYHHMM] التاريخ والوقت [ ] موضوع التحقيق ........................ : Subject Date &amp; Time [ ] المحقق اللجنة [ ] المكان Location Investigator / Committee [ ] رقم القضية [ ] المستندات المطلوبة Required Documents . Case No الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders in seed not mentioned by spec:** at, employee_name, investigation_date, investigator, location, on, regarding, subject

### PRN-025 — قرار إيقاف مؤقت لحين التحقيق

**Spec operational text (extracted):**

```

```

**Current seed body (stripped HTML):**

```
تقرر إيقاف الموظف/ة {{employee_name}} مؤقتًا عن {{suspension_scope}} اعتبارًا من {{start_date}} وحتى {{end_date}} أو انتهاء التحقيق، حفاظًا على سير التحقيق والمصلحة التشغيلية، دون اعتبار القرار حسمًا للنتيجة النهائية. {{employee_name}} is temporarily suspended from {{suspension_scope}} effective {{start_date}} until {{end_date}} or investigation completion, to protect the investigation and operations. This does not predetermine the final outcome. [DD/MM/YYYY] تاريخ البدء [Full/Partial] نطاق الإيقاف Suspension Scope Start Date [Asapproved] الوضع المالي [ ] المدة المتوقعة Expected Duration Pay Status [ ] مرجع التحقيق [Suspend/Retain] العهد الصلاحيات Assets / Access . Investigation Ref الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Legal Review مراجعة قانونية .................... التوقيع والتاريخ / Signature &amp; Date Authorized Approval اعتماد صاحب الصلاحية .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders in seed not mentioned by spec:** effective, employee_name, end_date, start_date, suspension_scope, until

### PRN-026 — تكليف واعتماد عمل إضافي

**Spec operational text (extracted):**

```

```

**Current seed body (stripped HTML):**

```
اعتمد عمل إضافي للموظف/ة {{employee_name}} بتاريخ {{overtime_date}} لمدة {{hours}} ساعة بسبب {{reason}}. معدل/قيمة الاستحقاق {{rate_or_amount}}. لا تحتسب الساعات إلا بعد التحقق من الحضور، ولا ترحّل للراتب قبل اعتماد المدير والمالية. Overtime for {{employee_name}} is approved on {{overtime_date}} for {{hours}} hours due to {{reason}}. Rate/entitlement: {{rate_or_amount}}. Hours are recognized only after attendance verification, and shall not be posted to payroll before manager and finance approval. [HHMM HHMM] من - إلى [DD/MM/YYYY] التاريخ : - : Date From - To [ ] سبب العمل الإضافي [____] عدد الساعات Hours Reason [____] الساعات المعتمدة [Payment/TimeOff] طريقة التعويض Compensation Approved Hours الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Line Manager Request طلب المسؤول المباشر .................... التوقيع والتاريخ / Signature &amp; Date Attendance Verification تحقق الحضور .................... التوقيع والتاريخ / Signature &amp; Date Final Approval االعتماد النهائي .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders in seed not mentioned by spec:** employee_name, for, hours, overtime_date, rate_or_amount, reason

### PRN-027 — قرار اعتماد إجازة

**Spec operational text (extracted):**

```
. أساس الاحتساب}last_working_day{ إلى}hire_date{ عن مدة الخدمة من}employee_name{السيدة/ هذه تسوية مبدئية لمستحقات نهاية خدمة السيد د.ك، وتخضع للمراجعة والاعتماد.}net_amount{ د.ك، والصافي المبدئي}deductions_total{ د.ك، الخصومات}entitlements_total{د.ك، المستحقات}salary_basis{
```

**Current seed body (stripped HTML):**

```
اعتمدت إجازة الموظف/ة {{employee_name}} من نوع {{leave_type}} خلال الفترة من {{start_date}} إلى {{end_date}} بإجمالي {{days_count}} يومًا. الرصيد قبل الإجازة {{balance_before}} يومًا وبعدها {{balance_after}} يومًا، وتاريخ العودة المتوقع {{return_date}}. البديل المعتمد إن وجد: {{replacement_employee}}. Leave for {{employee_name}} of type {{leave_type}} is approved from {{start_date}} to {{end_date}}, total {{days_count}} days. Balance before: {{balance_before}} days, after: {{balance_after}} days. Expected return: {{return_date}}. Approved replacement (if any): {{replacement_employee}}. [DD/MM/YYYY] من تاريخ [Annual/Sick/Other] نوع الإجازة Leave Type From Date [____] عدد األيام [DD/MM/YYYY] إلى تاريخ To Date Number of Days [____] الرصيد بعد [____] الرصيد قبل Balance Before Balance After الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** deductions_total, entitlements_total, hire_date, last_working_day, net_amount, salary_basis
**Placeholders in seed not mentioned by spec:** balance_after, balance_before, days_count, end_date, leave_type, replacement_employee, return_date, start_date, to

### PRN-028 — إشعار عودة من إجازة

**Spec operational text (extracted):**

```
د.ك، إجمالي الخصومات}entitlements_total{: إجمالي المستحقات}employee_name{السيدة/ اعتمدت التسوية النهائية لمستحقات نهاية خدمة السيد د.ك. يقر الموظف بالاستلام بعد بيان التفاصيل، مع حفظ الحقوق النظامية التي لا يجوز التنازل عنها.}net_amount{د.ك، وصافي المستحق}deductions_total{
```

**Current seed body (stripped HTML):**

```
يفيد هذا الإشعار بأن الموظف/ة {{employee_name}} باشر العمل بعد الإجازة بتاريخ {{return_date}} في الساعة {{return_time}}. تحدث حالته الوظيفية والحضور وفق سجل المباشرة. This notice confirms that {{employee_name}} resumed work after leave on {{return_date}} at {{return_time}}. Employment and attendance status shall be updated accordingly. [DD/MM/YYYY] الإجازة إلى [DD/MM/YYYY] الإجازة من Leave From Leave To [DD/MM/YYYY] تاريخ المباشرة الفعلي [DD/MM/YYYY] تاريخ المباشرة المتوقع Expected Return Actual Return [ ] مالحظات المسؤول [ ] التأخير إن وجد Delay, if any Manager Notes الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** deductions_total, entitlements_total, net_amount
**Placeholders in seed not mentioned by spec:** at, return_date, return_time

### PRN-029 — بيان رصيد الإجازات

**Spec operational text (extracted):**

```
يومًا، }consumed_days{ يومًا، المستهلك }entitled_days{: الرصيد المستحق}as_of_date{ حتى تاريخ}employee_name{ بيان رصيد إجازات الموظف يومًا. أي رصيد سالب أو استثناء يجب أن يظهر معه سبب وسياسة المعالجة. }remaining_days{والمتبقي
```

**Current seed body (stripped HTML):**

```
بيان رصيد إجازات الموظف/ة {{employee_name}} حتى تاريخ {{as_of_date}}: الرصيد المستحق {{entitled_days}} يومًا، المستهلك {{consumed_days}} يومًا، والمتبقي {{remaining_days}} يومًا. أي رصيد سالب أو استثناء يظهر معه سبب وسياسة المعالجة. Leave balance for {{employee_name}} as of {{as_of_date}}: entitled {{entitled_days}} days, used {{consumed_days}} days, remaining {{remaining_days}} days. Any negative balance or exception is shown with its reason and policy handling. [____] /syaD استحقاق السنة [____] /syaD الرصيد المرحل يوم يوم Carried Forward Annual Entitlement [____] /syaD المعلق [____] /syaD المستخدم يوم يوم Used Pending [____] /syaD الرصيد المتاح [____ /+] التعديالت يوم - Adjustments Available Balance Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```


### PRN-030 — كشف حضور شهري

**Spec operational text (extracted):**

```
، التأخير}absence_days{، الغياب}present_days{، الحضور}working_days{: أيام العمل}period{الموظفين عن الفترة/ كشف حضور الموظف ساعة. يعتمد بعد مراجعة الاستثناءات.}overtime_hours{ دقيقة، والعمل الإضافي}early_minutes{دقيقة، الخروج المبكر}late_minutes{
```

**Current seed body (stripped HTML):**

```
كشف حضور الموظف/ة {{employee_name}} عن الفترة {{period}}: أيام العمل {{working_days}}، الحضور {{present_days}}، الغياب {{absent_days}}، التأخير {{late_minutes}} دقيقة، الخروج المبكر {{early_minutes}} دقيقة، والعمل الإضافي {{overtime_hours}} ساعة. يعتمد بعد مراجعة الاستثناءات. Attendance for {{employee_name}} for period {{period}}: workdays {{working_days}}, present {{present_days}}, absent {{absent_days}}, late {{late_minutes}} min, early departure {{early_minutes}} min, overtime {{overtime_hours}} hrs. Approved after reviewing exceptions. [____] أيام الحضور [____] أيام العمل Working Days Present Days [____] مرات التأخير [____] أيام الغياب Absent Days Late Occurrences [____] الساعات الإضافية [____] الخروج المبكر Early Departures Overtime Hours [____] المخالفات المفتوحة [____] إجمالي ساعات العمل Total Worked Hours Open Exceptions System Generated إعداد النظام .................... التوقيع والتاريخ / Signature &amp; Date Supervisor Review مراجعة المشرف .................... التوقيع والتاريخ / Signature &amp; Date HR Approval اعتماد الموارد البشرية .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** absence_days
**Placeholders in seed not mentioned by spec:** absent_days, employee_name

### PRN-031 — تأكيد تعديل سجل حضور

**Spec operational text (extracted):**

```
، متضمنًا التاريخ والحالة والمدة والسبب وقرار التصحيح. لا يحول أي يوم إلى خصم قبل اكتمال المراجعة}period{ كشف تفصيلي بحالات التأخير والغياب عن الفترة والاعتماد.
```

**Current seed body (stripped HTML):**

```
تم تعديل سجل الحضور الخاص بالموظف/ة {{employee_name}} عن تاريخ {{date}} بناءً على الطلب رقم {{request_no}} والمرجع {{reference}}، مع الاحتفاظ بالقيمة السابقة {{old_value}} والجديدة {{new_value}} في سجل التدقيق. سبب التعديل: {{reason}}. The attendance record for {{employee_name}} on {{date}} has been adjusted per request {{request_no}} and reference {{reference}}. Previous value {{old_value}} and new value {{new_value}} are retained in the audit log. Reason: {{reason}}. Checkin/Checkout/[ [ ] القيمة السابقة نوع التعديل Adjustment Type ]Absence Previous Value [ ] سبب التعديل [ ] القيمة الجديدة New Value Reason [ ] المرفق الداعم [ ] رقم الطلب . Request No Supporting Attachment Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** period
**Placeholders in seed not mentioned by spec:** date, employee_name, new_value, old_value, on, reason, reference, request_no

### PRN-032 — كشف راتب شهري مبسط

**Spec operational text (extracted):**

```
،}absence_deduction{، خصم الغياب}overtime_total{، الإضافي}allowances_total{، البدلات}basic_total{: الأساسي}period{ كشف رواتب الفترة .}payroll_status{. حالة المسير}net_total{، وصافي الرواتب}other_deductions{، الخصومات الأخرى}loan_deductions{الأقساط/السلف
```

**Current seed body (stripped HTML):**

```
كشف رواتب الفترة {{period}}: الأساسي {{basic_total}} د.ك، البدلات {{allowances_total}} د.ك، الإضافي {{overtime_total}} د.ك، خصم الغياب {{absence_deduction}} د.ك، السلف/الأقساط {{loan_deductions}} د.ك، الخصومات الأخرى {{other_deductions}} د.ك، وصافي الرواتب {{net_total}} د.ك. حالة المسيّر: {{payroll_status}}. Payroll statement for {{period}}: basic {{basic_total}} KWD, allowances {{allowances_total}} KWD, overtime {{overtime_total}} KWD, absence deduction {{absence_deduction}} KWD, loans {{loan_deductions}} KWD, other deductions {{other_deductions}} KWD, net {{net_total}} KWD. Payroll status: {{payroll_status}}. [____] البدلات [____] الراتب الأساسي د.ك د.ك Basic Salary Allowances [____] المكافآت [____] العمل الإضافي د.ك د.ك Overtime Bonuses [____] السلف [____] الخصومات د.ك د.ك Deductions Advances [Bank/Cash] طريقة الدفع [____] صافي الراتب د.ك Net Salary Payment Method Prepared by Accounts إعداد المحاسبة .................... التوقيع والتاريخ / Signature &amp; Date HR Review مراجعة الموارد البشرية .................... التوقيع والتاريخ / Signature &amp; Date Manager Approval اعتماد المدير .................... التوقيع والتاريخ / Signature &amp; Date
```


### PRN-033 — إشعار نقص مستندات

**Spec operational text (extracted):**

```
، حالة الاعتماد}amount{، المبلغ}reason{، السبب}deduction_reference{: المرجع}period{ عن الفترة}employee_name{ كشف خصومات الموظف .}payroll_effect{، وأثره على مسير الراتب}approval_status{
```

**Current seed body (stripped HTML):**

```
نحيط الموظف/ة {{employee_name}} علمًا بأن ملفه يحتاج إلى المستندات التالية: {{missing_documents}}. يرجى رفعها قبل {{deadline}} من خلال {{submission_method}}، وإلا قد يتعذر استكمال المعاملة المرتبطة. {{employee_name}} is notified that the file requires the following documents: {{missing_documents}}. Please upload or submit them by {{deadline}} via {{submission_method}}, otherwise the related transaction may be suspended. [ ] المستندات الناقصة [ ] نوع المعاملة Transaction Type Missing Documents [HRMS/Physical] طريقة التسليم [DD/MM/YYYY] آخر موعد Deadline Submission Method [AwaitingDocuments] حالة المعاملة [ ] المسؤول Responsible Officer Transaction Status الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** amount, approval_status, deduction_reference, payroll_effect, period, reason
**Placeholders in seed not mentioned by spec:** deadline, missing_documents, submission_method, via

### PRN-034 — تفويض تجديد إقامة

**Spec operational text (extracted):**

```
. أتعهد بالمحافظة عليها واستخدامها لأغراض العمل وإعادتها عند الطلب أو انتهاء الخدمة،}assets_list{ باستلام العهد التالية بحالة سليمة}employee_name{ أقر أنا مع إثبات الرقم التسلسلي والحالة.
```

**Current seed body (stripped HTML):**

```
تفوض شركة {{company_name}} المندوب {{delegate_name}} باستكمال إجراءات تجديد إقامة الموظف/ة {{employee_name}} (رقم مدني {{civil_id}}، إقامة رقم {{residency_no}} المنتهية في {{expiry_date}}). نوع التجديد {{renewal_type}} وسببه {{reason}}، تحت ملف الشركة رقم {{company_file_no}}. {{company_name}} authorizes delegate {{delegate_name}} to complete the residency renewal of {{employee_name}} (Civil ID {{civil_id}}, Residency {{residency_no}} expiring {{expiry_date}}). Renewal type: {{renewal_type}}, reason: {{reason}}, under company file {{company_file_no}}. Early days/Normal[ 30-90 [DD/MM/YYYY] انتهاء الإقامة نوع التجديد Renewal Type ]&lt;= days Residency Expiry 30 [ ] رقم ملف الشركة [ ] مدة التجديد Renewal Period . Company File No Passport/Permit/Photo/[ المرفقات [ ] المندوب المكلف Assigned Delegate Attachments ]Other Legal Affairs الشؤون القانونية .................... التوقيع والتاريخ / Signature &amp; Date Company Manager مدير الشركة .................... التوقيع والتاريخ / Signature &amp; Date Delegate المندوب .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** assets_list
**Placeholders in seed not mentioned by spec:** civil_id, company_file_no, company_name, delegate_name, expiring, expiry_date, reason, renewal_type, residency_no

### PRN-035 — تفويض تجديد إذن عمل

**Spec operational text (extracted):**

```
. يحال أي أثر مالي إلى}issues{الأضرار/ والنواقص}return_condition{. حالة الإرجاع}assets_list{ :}employee_name{ تم استلام العهد التالية من الموظف المالية قبل إغلاق إخلاء الطرف.
```

**Current seed body (stripped HTML):**

```
يرجى تجديد إذن العمل رقم {{permit_no}} للموظف/ة {{employee_name}} قبل تاريخ {{expiry_date}} تحت ملف الشركة {{company_file_no}}. الجهة الحكومية {{government_entity}} والرسوم المقدرة {{estimated_fees}}. يكلف المندوب {{delegate_name}} برفع المستندات والنتيجة النهائية في النظام. Please renew work permit {{permit_no}} for {{employee_name}} before {{expiry_date}} under company file {{company_file_no}}. Government entity: {{government_entity}}, estimated fees: {{estimated_fees}}. Delegate {{delegate_name}} shall upload documents and final outcome. [DD/MM/YYYY] تاريخ االنتهاء [ ] رقم إذن العمل . Work Permit No Expiry Date [ ] الترخيص [ ] ملف الشركة Company File License [DD/MM/YYYY] موعد الإنجاز [ ] المندوب Delegate Target Completion | / | | Employee/Legal شؤون الموظفين القانونية .................... التوقيع والتاريخ / Signature &amp; Date Manager Approval اعتماد المدير .................... التوقيع والتاريخ / Signature &amp; Date Delegate Execution تنفيذ المندوب .................... التوقيع والتاريخ / Signature &amp; Date Affairs .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** assets_list, issues, return_condition
**Placeholders in seed not mentioned by spec:** before, company_file_no, delegate_name, estimated_fees, expiry_date, for, government_entity, permit_no

### PRN-036 — إشعار تحديث البطاقة المدنية أو الجواز

**Spec operational text (extracted):**

```
. يتحمل}mission_purpose{ لغرض}end_date{ - }start_date{ خلال الفترة}location{ بمهمة عمل خارجية إلى}employee_name{السيدة/ يكلف السيد متابعة التنفيذ، وتطبق المصروفات المعتمدة إن وجدت.}manager_name{المسؤول
```

**Current seed body (stripped HTML):**

```
تم استلام جواز/بطاقة جديدة للموظف/ة {{employee_name}} بدل {{old_passport_no}}. الرقم الجديد {{new_passport_no}}، تاريخ الإصدار {{issue_date}} والانتهاء {{expiry_date}}. يرجى تقديم النسخة قبل {{deadline}} وتحديث الملف الإلكتروني، وفحص أثر التغيير على الإقامة والتصاريح. New passport/civil ID received for {{employee_name}} replacing {{old_passport_no}}. New number {{new_passport_no}}, issued {{issue_date}}, expiring {{expiry_date}}. Please submit the copy by {{deadline}}, update the electronic file, and check the impact on residency and permits. [ ] الرقم الحالي [CivilID/Passport] نوع المستند Document Type Current Number [Upload/SubmitOriginal] المطلوب [DD/MM/YYYY] تاريخ االنتهاء Expiry Date Required Action [Pending/Received] حالة االستالم [DD/MM/YYYY] آخر موعد Deadline Receipt Status الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** end_date, location, manager_name, mission_purpose, start_date
**Placeholders in seed not mentioned by spec:** deadline, expiry_date, issue_date, new_passport_no, old_passport_no, replacing

### PRN-037 — تكليف مندوب بمعاملة حكومية

**Spec operational text (extracted):**

```
. يتم تحديث نظام الحضور}reason{ بسبب}effective_date{ اعتبارًا من }new_shift{ إلى}old_shift{ من}employee_name{ تقرر تغيير وردية الموظف وإبلاغ الموظف والمشرف.
```

**Current seed body (stripped HTML):**

```
يكلف المندوب {{delegate_name}} بمتابعة معاملة {{transaction_type}} الخاصة بـ {{employee_or_company}} لدى {{government_entity}}، مرجع رقم {{reference}}. المستندات المسلمة: {{documents_list}}، الموعد المستهدف {{due_date}}. يلتزم المندوب بتحديث حالة المعاملة وإرفاق إيصالاتها والمستند النهائي وإعادة أي عهد. Delegate {{delegate_name}} is assigned transaction {{transaction_type}} for {{employee_or_company}} at {{government_entity}}, ref {{reference}}. Delivered documents: {{documents_list}}, target date {{due_date}}. The delegate shall update status, attach receipts and final documents, and return any originals or assets. [ ] الجهة الحكومية [ ] نوع المعاملة Transaction Type Government Entity [DD/MM/YYYY] الموعد النهائي [ ] رقم المرجع . Reference No Deadline [ ] النتيجة المطلوبة [ ] العهد المبالغ Assets / Amounts Required Outcome الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Task Creator إنشاء المهمة .................... التوقيع والتاريخ / Signature &amp; Date Delegate Acceptance استلام المندوب .................... التوقيع والتاريخ / Signature &amp; Date Closure Approval اعتماد الإغالق .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** effective_date, employee_name, new_shift, old_shift, reason
**Placeholders in seed not mentioned by spec:** at, delegate_name, documents_list, due_date, employee_or_company, for, government_entity, reference, transaction_type

### PRN-038 — التسوية النهائية ونهاية الخدمة

**Spec operational text (extracted):**

```
،}rate_or_amount{قيمة الاستحقاق/. معدل}reason{ ساعة بسبب}hours{ لمدة}overtime_date{ بتاريخ}employee_name{ اعتمد عمل إضافي للموظف ولا يرحل للراتب قبل اعتماد المدير والمالية.
```

**Current seed body (stripped HTML):**

```
التسوية النهائية للموظف/ة {{employee_name}} حتى آخر يوم عمل {{last_working_day}}. أساس الاحتساب {{salary_basis}} د.ك، إجمالي المستحقات {{entitlements_total}} د.ك، الخصومات {{deductions_total}} د.ك، وصافي المستحق {{net_amount}} د.ك. يقر الموظف بالاستلام بعد بيان التفاصيل، مع حفظ الحقوق النظامية. Final settlement for {{employee_name}} through last working day {{last_working_day}}. Salary basis {{salary_basis}} KWD, total entitlements {{entitlements_total}} KWD, deductions {{deductions_total}} KWD, net payable {{net_amount}} KWD. The employee acknowledges receipt after detailing, preserving statutory rights. [____] راتب مستحق [____] مكافأة نهاية الخدمة د.ك د.ك End of Service Benefit Outstanding Salary [____] مستحقات أخرى [____] بدل إجازات د.ك د.ك Leave Encashment Other Entitlements [____] سلف متبقية [____] خصومات عهد د.ك د.ك Deductions / Assets Outstanding Advances [____] الصافي النهائي [____] إجمالي المستحق د.ك د.ك Gross Payable Net Settlement الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared by HR إعداد الموارد البشرية .................... التوقيع والتاريخ / Signature &amp; Date Accounts Review مراجعة المحاسبة .................... التوقيع والتاريخ / Signature &amp; Date Approval &amp; Payment االعتماد والصرف .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** hours, overtime_date, rate_or_amount, reason
**Placeholders in seed not mentioned by spec:** deductions_total, entitlements_total, last_working_day, net_amount, salary_basis

### PRN-039 — شهادة إخلاء طرف

**Spec operational text (extracted):**

```

```

**Current seed body (stripped HTML):**

```
تفيد الإدارات الموضحة أدناه بأن الموظف/ة {{employee_name}} قد سلّم العهد {{assets_list}} والمستندات وأنهى الالتزامات المسجلة. الحالة المالية: {{finance_status}}. توقيعات الأقسام: {{department_signoffs}}. يعتمد إخلاء الطرف بعد اكتمال جميع الجهات دون استثناء. The departments below confirm that {{employee_name}} has returned assigned assets {{assets_list}} and documents and settled recorded obligations. Finance status: {{finance_status}}. Department signoffs: {{department_signoffs}}. Final clearance is approved only after all sections are completed. [Cleared/Pending] المحاسبة [Cleared/Pending] تقنية المعلومات IT Accounts [Cleared/Pending] الفرع الإدارة [Cleared/Pending] المخازن العهد Assets / Stores Branch / Department [Cleared/Pending] الموارد البشرية [Cleared/Pending] الشؤون القانونية Legal Affairs HR الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Department Officer مسؤول القسم .................... التوقيع والتاريخ / Signature &amp; Date HR Review مراجعة الموارد البشرية .................... التوقيع والتاريخ / Signature &amp; Date Final Clearance اعتماد الإخلاء .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders in seed not mentioned by spec:** assets_list, department_signoffs, employee_name, finance_status

### PRN-040 — محضر تسليم عهدة

**Spec operational text (extracted):**

```
الأجهزة عند توفرها/، وعناوين الشبكة}timestamps{، أوقات التوقيع}signers{: الموقعون}document_reference{ سجل التوقيع الإلكتروني للمستند منفصلة عن متن المستند.}document_hash{. تحفظ بصمة المستند}technical_metadata{
```

**Current seed body (stripped HTML):**

```
بتاريخ {{date}} تم تسليم/استلام العهد التالية {{assets_list}} بين الطرفين، بعد معاينتها بحالة {{return_condition}}. المستلم {{employee_name}} يتحمل مسؤولية المحافظة عليها واستخدامها لأغراض العمل، وإعادتها عند الطلب أو انتهاء الخدمة. الأضرار/النواقص: {{issues}}. On {{date}}, the assets {{assets_list}} were handed over/received between the parties after inspection with condition {{return_condition}}. Recipient {{employee_name}} is responsible for safekeeping and business use, and shall return them on request or end of service. Damages/shortages: {{issues}}. [ ] الرقم التسلسلي [Laptop/Phone/Keys/Other] نوع العهدة Asset Type . Serial No [ ] الملحقات [New/Good/Damaged] الحالة عند التسليم Condition Accessories [ ] إلى الموظف [ ] من الموظف From Employee To Employee الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Handed Over By المسلم .................... التوقيع والتاريخ / Signature &amp; Date Received By المستلم .................... التوقيع والتاريخ / Signature &amp; Date Asset Controller مسؤول العهد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** document_hash, document_reference, signers, technical_metadata, timestamps
**Placeholders in seed not mentioned by spec:** assets_list, date, employee_name, issues, return_condition

### PRN-041 — محضر استلام وتسليم مستندات

**Spec operational text (extracted):**

```
.}requested_opinion{، والمطلوب}attachments{. المرفقات}review_reason{ بسبب}subject_or_document{ يرجى من الشؤون القانونية مراجعة تسجل النتيجة والتوصية والقيود على الاطلاع في الملف.
```

**Current seed body (stripped HTML):**

```
يرجى من الشؤون القانونية مراجعة {{subject_or_document}} بسبب {{review_reason}}. المرفقات {{attachments}}، والمطلوب {{requested_opinion}}. تسجل النتيجة والتوصية والقيود على الاطلاع في الملف. Please have Legal Affairs review {{subject_or_document}} for {{review_reason}}. Attachments: {{attachments}}, requested opinion: {{requested_opinion}}. Result, recommendation, and access restrictions shall be recorded in the file. Passport/CivilID/Contract/[ [ ] الرقم نوع المستند Document Type ]Other . Document No [ ] الغرض [ ] أصل أم نسخة Original / Copy Purpose [DD/MM/YYYY] موعد الإعادة [DD/MM/YYYY] تاريخ االستالم Receipt Date Return Date الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Handed Over By المسلم .................... التوقيع والتاريخ / Signature &amp; Date Received By المستلم .................... التوقيع والتاريخ / Signature &amp; Date Witness / Reviewer الشاهد / المراجع .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders in seed not mentioned by spec:** for

### PRN-042 — سجل اعتماد التوقيع الإلكتروني

**Spec operational text (extracted):**

```
البيانات الشخصية والوظيفية والحكومية، العقد، الراتب وفق الصلاحية، المستندات وصلاحيتها، الأرصدة، الطلبات المفتوحة،}employee_name{ ملخص ملف الموظف التنبيهات والعهد. يجب إخفاء الحقول غير المصرح بها وإظهار نسبة اكتمال الملف.
```

**Current seed body (stripped HTML):**

```
سجل التوقيع الإلكتروني للمستند {{document_reference}} (بصمة {{document_hash}}): الموقعون {{signers}}، أوقات التوقيع {{timestamps}}، وعناوين الأجهزة/الجلسة {{technical_metadata}} عند توفرها. لا يعتد بأي تعديل لاحق دون إنشاء إصدار جديد. Electronic signature record for document {{document_reference}} (hash {{document_hash}}): signers {{signers}}, timestamps {{timestamps}}, and session/device metadata {{technical_metadata}} where available. Subsequent changes require a new version. [ ] رقم المستند [ ] نوع المستند Document Type . Document No [ ] رمز التحقق [ ] الإصدار 1.0 ........................ Version Verification Code [Approved/Rejected] حالة االعتماد [DD/MM/YYYYHHMM] تاريخ الإنشاء : Created At Approval Status Electronic Creator منشئ إلكتروني .................... التوقيع والتاريخ / Signature &amp; Date Electronic Reviewer المراجع الإلكتروني .................... التوقيع والتاريخ / Signature &amp; Date Electronic Approver المعتمد الإلكتروني .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** employee_name
**Placeholders in seed not mentioned by spec:** document_hash, document_reference, signers, technical_metadata, timestamps

