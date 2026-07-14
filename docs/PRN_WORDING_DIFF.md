# PRN Wording Diff Report — V1.4 spec vs seed.py

| Code | Name (seed) | Similarity | Missing placeholders | Notes |
| --- | --- | --- | --- | --- |
| PRN-001 | شهادة راتب | 0.00 | — | **REVIEW** — significant divergence |
| PRN-002 | شهادة لمن يهمه الأمر | 0.07 | `{{company_name}}`, `{{employee_name}}`, `{{hire_date}}`, `{{job_title}}`, `{{purpose}}`, `{{target_entity}}` | **REVIEW** — significant divergence |
| PRN-003 | شهادة خبرة | 0.14 | `{{company_name}}`, `{{employee_name}}`, `{{job_title}}`, `{{service_end}}`, `{{service_start}}` | **REVIEW** — significant divergence |
| PRN-004 | شهادة حالة وظيفية | 0.04 | `{{bank_name}}`, `{{company_name}}`, `{{employee_name}}`, `{{gross_salary}}`, `{{hire_date}}`, `{{job_title}}` | **REVIEW** — significant divergence |
| PRN-005 | خطاب عدم ممانعة | 0.02 | `{{allowances}}`, `{{basic_salary}}`, `{{candidate_name}}`, `{{company_name}}`, `{{job_title}}`, `{{start_date}}` | **REVIEW** — significant divergence |
| PRN-006 | بيان بيانات موظف | 0.03 | `{{annual_leave_days}}`, `{{basic_salary}}`, `{{contract_end}}`, `{{contract_start}}`, `{{contract_type}}`, `{{employee_name}}`, `{{job_title}}`, `{{working_hours}}` | **REVIEW** — significant divergence |
| PRN-007 | شهادة مدة خدمة | 0.04 | `{{effective_date}}`, `{{employee_name}}`, `{{new_location}}`, `{{old_location}}`, `{{transfer_type}}` | **REVIEW** — significant divergence |
| PRN-008 | خطاب تحويل راتب للبنك | 0.03 | `{{effective_date}}`, `{{employee_name}}`, `{{new_title}}`, `{{old_title}}` | **REVIEW** — significant divergence |
| PRN-009 | إفادة استمرارية راتب | 0.01 | `{{effective_date}}`, `{{employee_name}}`, `{{new_salary}}`, `{{old_salary}}`, `{{reason}}` | **REVIEW** — significant divergence |
| PRN-010 | خطاب موجه لجهة رسمية | 0.05 | `{{employee_name}}`, `{{incident_date}}`, `{{incident_summary}}` | **REVIEW** — significant divergence |
| PRN-011 | خطاب عرض وظيفي | 0.02 | `{{attendees}}`, `{{employee_name}}`, `{{investigation_date}}`, `{{result}}`, `{{subject}}` | **REVIEW** — significant divergence |
| PRN-012 | إشعار تجديد عقد | 0.02 | `{{deduction_amount}}`, `{{employee_name}}` | **REVIEW** — significant divergence |
| PRN-013 | إشعار عدم تجديد عقد | 0.02 | `{{action_taken}}`, `{{employee_name}}`, `{{incident_date}}`, `{{policy_reference}}`, `{{violation_details}}` | **REVIEW** — significant divergence |
| PRN-014 | قبول استقالة | 0.04 | `{{employee_name}}`, `{{received_at}}`, `{{warning_reference}}` | **REVIEW** — significant divergence |
| PRN-015 | قرار إنهاء خدمة | 0.01 | `{{balance_after}}`, `{{balance_before}}`, `{{days_count}}`, `{{employee_name}}`, `{{end_date}}`, `{{leave_type}}`, `{{replacement_employee}}`, `{{return_date}}`, `{{start_date}}` | **REVIEW** — significant divergence |
| PRN-016 | قرار نقل موظف | 0.04 | `{{approved_at}}`, `{{employee_name}}`, `{{finance_notes}}`, `{{financial_status}}` | **REVIEW** — significant divergence |
| PRN-017 | قرار تكليف بفرع أو موقع عمل | 0.04 | `{{employee_name}}`, `{{legal_status}}`, `{{missing_documents}}`, `{{passport_expiry}}`, `{{residency_expiry}}` | **REVIEW** — significant divergence |
| PRN-018 | قرار ترقية | 0.00 | — | **REVIEW** — significant divergence |
| PRN-019 | قرار تعديل راتب | 0.02 | `{{delegate_name}}`, `{{documents_list}}`, `{{due_date}}`, `{{employee_or_company}}`, `{{government_entity}}`, `{{transaction_type}}` | **REVIEW** — significant divergence |
| PRN-020 | قرار بدل أو مكافأة | 0.03 | `{{deadline}}`, `{{employee_name}}`, `{{missing_documents}}`, `{{submission_method}}` | **REVIEW** — significant divergence |
| PRN-021 | قرار خصم | 0.05 | `{{civil_id}}`, `{{delegate_name}}`, `{{employee_name}}`, `{{expiry_date}}`, `{{reason}}`, `{{renewal_type}}`, `{{residency_no}}` | **REVIEW** — significant divergence |
| PRN-022 | إنذار موظف | 0.00 | — | **REVIEW** — significant divergence |
| PRN-023 | إنذار نهائي | 0.00 | — | **REVIEW** — significant divergence |
| PRN-024 | استدعاء للتحقيق الإداري | 0.00 | — | **REVIEW** — significant divergence |
| PRN-025 | قرار إيقاف مؤقت لحين التحقيق | 0.00 | — | **REVIEW** — significant divergence |
| PRN-026 | تكليف واعتماد عمل إضافي | 0.00 | — | **REVIEW** — significant divergence |
| PRN-027 | قرار اعتماد إجازة | 0.02 | `{{deductions_total}}`, `{{employee_name}}`, `{{entitlements_total}}`, `{{hire_date}}`, `{{last_working_day}}`, `{{net_amount}}`, `{{salary_basis}}` | **REVIEW** — significant divergence |
| PRN-028 | إشعار عودة من إجازة | 0.05 | `{{deductions_total}}`, `{{employee_name}}`, `{{entitlements_total}}`, `{{net_amount}}` | **REVIEW** — significant divergence |
| PRN-029 | بيان رصيد الإجازات | 0.08 | `{{as_of_date}}`, `{{consumed_days}}`, `{{employee_name}}`, `{{entitled_days}}`, `{{remaining_days}}` | **REVIEW** — significant divergence |
| PRN-030 | كشف حضور شهري | 0.08 | `{{absence_days}}`, `{{early_minutes}}`, `{{late_minutes}}`, `{{overtime_hours}}`, `{{period}}`, `{{present_days}}`, `{{working_days}}` | **REVIEW** — significant divergence |
| PRN-031 | تأكيد تعديل سجل حضور | 0.04 | `{{period}}` | **REVIEW** — significant divergence |
| PRN-032 | كشف راتب شهري مبسط | 0.02 | `{{absence_deduction}}`, `{{allowances_total}}`, `{{basic_total}}`, `{{loan_deductions}}`, `{{net_total}}`, `{{other_deductions}}`, `{{overtime_total}}`, `{{payroll_status}}`, `{{period}}` | **REVIEW** — significant divergence |
| PRN-033 | إشعار نقص مستندات | 0.03 | `{{amount}}`, `{{approval_status}}`, `{{deduction_reference}}`, `{{employee_name}}`, `{{payroll_effect}}`, `{{period}}`, `{{reason}}` | **REVIEW** — significant divergence |
| PRN-034 | تفويض تجديد إقامة | 0.02 | `{{assets_list}}`, `{{employee_name}}` | **REVIEW** — significant divergence |
| PRN-035 | تفويض تجديد إذن عمل | 0.01 | `{{assets_list}}`, `{{employee_name}}`, `{{issues}}`, `{{return_condition}}` | **REVIEW** — significant divergence |
| PRN-036 | إشعار تحديث البطاقة المدنية أو الجواز | 0.01 | `{{employee_name}}`, `{{end_date}}`, `{{location}}`, `{{manager_name}}`, `{{mission_purpose}}`, `{{start_date}}` | **REVIEW** — significant divergence |
| PRN-037 | تكليف مندوب بمعاملة حكومية | 0.03 | `{{effective_date}}`, `{{employee_name}}`, `{{new_shift}}`, `{{old_shift}}`, `{{reason}}` | **REVIEW** — significant divergence |
| PRN-038 | التسوية النهائية ونهاية الخدمة | 0.03 | `{{employee_name}}`, `{{hours}}`, `{{overtime_date}}`, `{{rate_or_amount}}`, `{{reason}}` | **REVIEW** — significant divergence |
| PRN-039 | شهادة إخلاء طرف | 0.00 | — | **REVIEW** — significant divergence |
| PRN-040 | محضر تسليم عهدة | 0.06 | `{{document_hash}}`, `{{document_reference}}`, `{{signers}}`, `{{technical_metadata}}`, `{{timestamps}}` | **REVIEW** — significant divergence |
| PRN-041 | محضر استلام وتسليم مستندات | 0.04 | `{{attachments}}`, `{{requested_opinion}}`, `{{review_reason}}`, `{{subject_or_document}}` | **REVIEW** — significant divergence |
| PRN-042 | سجل اعتماد التوقيع الإلكتروني | 0.03 | `{{employee_name}}` | **REVIEW** — significant divergence |

## Summary
- ≈Identical (≥0.9): **0**
- Close (0.5–0.9): **0**
- Diverges (<0.5): **42**
- Missing in seed: **0**
- Missing in spec extract: **0**
- Seed templates with **zero** `{{placeholders}}`: **42 / 42**

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
تشهد شركة اسم الشركة بأن السيد السيدة اسم الموظف ، حامل الرقم المدني الرقم المدني ، يعمل لديها بوظيفة المسمى الوظيفي منذ تاريخ تاريخ التعيين ، ويتقاضى راتبا شهريا إجماليا قدره المبلغ د.ك. وقد أصدرت هذه الشهادة بناء على طلبه طلبها دون أدنى مسؤولية على الشركة تجاه الغير. certifies that Mr./Ms. ]Employee Name[, Civil ID ]Civil ID[, has been employed as ]Job Title[ since ]Joining Date[ and receives a total monthly salary of KWD ]Amount[. This Company Name certificate is issued upon request without liability to third parties [____] /KWD البدلات [____] /KWD الراتب الأساسي د.ك د.ك Basic Salary Allowances [Bank/Embassy/Other] الجهة الموجه إليها [____] /KWD الإجمالي د.ك Total Salary Addressed To Prepared by HR إعداد الموارد البشرية .................... التوقيع والتاريخ / Signature &amp; Date Manager Review مراجعة المدير .................... التوقيع والتاريخ / Signature &amp; Date Authorized Signatory المخول بالتوقيع .................... التوقيع والتاريخ / Signature &amp; Date
```


### PRN-002 — شهادة لمن يهمه الأمر

**Spec operational text (extracted):**

```
وما زال على رأس عمله حتى تاريخ}hire_date{ منذ}job_title{ يعمل لديها بوظيفة}employee_name{السيدة/ بأن السيد}company_name{ تشهد شركة .}purpose{ لغرض}target_entity{إصدار هذا الخطاب. وقد صدرت هذه الإفادة بناءً على طلبه لتقديمها إلى
```

**Current seed body (stripped HTML):**

```
إلى من يهمه الأمر، تفيد شركة اسم الشركة بأن السيد السيدة اسم الموظف يعمل لديها بصفة المسمى الوظيفي ، وأن علاقته الوظيفية قائمة حتى تاريخ إصدار هذه الشهادة. أعطيت له لها بناء على طلبه طلبها لاستخدامها فيما خصصت له. / / s To whom it may concern, ]Company Name[ confirms that Mr./Ms. ]Employee Name[ is employed as ]Job Title[ and remains actively employed as of the issue date. Issued upon request for its intended purpose [Fixed/Unlimited] نوع العقد [DD/MM/YYYY] تاريخ التعيين Joining Date Contract Type [ ] الغرض [Active] حالة الموظف Employment Status Purpose Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** company_name, employee_name, hire_date, job_title, purpose, target_entity

### PRN-003 — شهادة خبرة

**Spec operational text (extracted):**

```
إلى}service_start{ خلال الفترة من}job_title{ قد عمل لديها بوظيفة}employee_name{السيدة/ بأن السيد}company_name{ تشهد شركة . وقد أدى مهامه خلال مدة خدمته وفق سجلات الشركة، وصدرت هذه الشهادة بناءً على طلبه. }service_end{
```

**Current seed body (stripped HTML):**

```
تشهد شركة اسم الشركة بأن السيد السيدة اسم الموظف قد عمل لديها خلال الفترة من من إلى إلى بوظيفة المسمى الوظيفي . وقد أدى أدت المهام الموكلة إليه إليها وفق سجلات الشركة. أصدرت هذه الشهادة بناء على طلبه طلبها. s / / ] [ . ] [ certifies that Mr./Ms. ]Employee Name[ worked from ]From[ to ]To[ as ]Job Title[ and performed the assigned duties according to company records. Issued upon request Company Name [ ] القسم الأخير [From] [To] فترة الخدمة Service Period Last Department [Optional] التقييم العام [ ] سبب انتهاء الخدمة Reason for Leaving General Rating Prepared by HR إعداد الموارد البشرية .................... التوقيع والتاريخ / Signature &amp; Date Legal Review مراجعة الشؤون القانونية .................... التوقيع والتاريخ / Signature &amp; Date Authorized Signatory المخول بالتوقيع .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** company_name, employee_name, job_title, service_end, service_start

### PRN-004 — شهادة حالة وظيفية

**Spec operational text (extracted):**

```
،}hire_date{ منذ}job_title{ بوظيفة}company_name{ يعمل لدى}employee_name{السيدة/ المحترمون، نفيدكم بأن السيد}bank_name{ / السادة د.ك. صدر الخطاب بناءً على طلب الموظف ودون التزام مالي على الشركة تجاه البنك. }gross_salary{ويتقاضى إجمالي راتب شهري قدره
```

**Current seed body (stripped HTML):**

```
تفيد شركة اسم الشركة بأن بيانات الحالة الوظيفية للموظف الموضح أعاله كما هي مبينة في هذا المستند حتى تاريخ الإصدار، وقد تم استخراجها من نظام الموارد البشرية. . ] [ confirms that the employment status shown in this document is accurate as of the issue date and has been extracted from the HRMS Company Name Active/Leave/Suspended/[ [DD/MM/YYYY] تاريخ بداية الحالة الحالة Status ]Ended Status Start Date [ ] المسؤول المباشر [Fulltime/Parttime] الدوام Work Schedule Line Manager Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** bank_name, company_name, employee_name, gross_salary, hire_date, job_title

### PRN-005 — خطاب عدم ممانعة

**Spec operational text (extracted):**

```
، براتب أساسي}start_date{ اعتبارًا من }job_title{ عرضًا للعمل بوظيفة }candidate_name{السيدة/ أن تقدم للسيد}company_name{ يسر شركة . يخضع العرض لاستكمال المستندات والتوقيع على عقد العمل وسياسات الشركة.}allowances{د.ك وبدلات}basic_salary{
```

**Current seed body (stripped HTML):**

```
تشهد شركة اسم الشركة بأنها لا تمانع في وصف الغرض للموظف اسم الموظف ، وذلك بشرط عدم تعارضه مع التزاماته الوظيفية وسياسات الشركة، ودون ترتيب أي التزام مالي أو قانوني إضافي على الشركة ما لم يذكر خالف ذلك صراحة. has no objection to ]Purpose[ for ]Employee Name[, provided it does not conflict with employment obligations or company policy and creates no additional financial or legal Company Name liability unless expressly stated [From] [To] الفترة [ ] الغرض Purpose Period [ ] الجهة المستفيدة [ ] الشروط Conditions Beneficiary Entity Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Legal Review مراجعة قانونية .................... التوقيع والتاريخ / Signature &amp; Date Manager Approval اعتماد المدير .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** allowances, basic_salary, candidate_name, company_name, job_title, start_date

### PRN-006 — بيان بيانات موظف

**Spec operational text (extracted):**

```
، الوظيفة}contract_end{، تاريخ النهاية}contract_start{، تاريخ البداية}contract_type{: نوع العقد}employee_name{ ملخص بيانات عقد الموظف يومًا. هذا الملخص لا يغني عن العقد الموقع. }annual_leave_days{، والإجازة السنوية}working_hours{ د.ك، ساعات العمل}basic_salary{، الراتب الأساسي}job_title{
```

**Current seed body (stripped HTML):**

```
هذا البيان مستخرج من ملف الموظف في نظام الموارد البشرية ويعرض البيانات المسجلة وقت الإصدار. أي تعديل الحق يخضع لسجل التدقيق والصلاحيات المعتمدة. This statement is generated from the employee file in the HRMS and reflects the data recorded at the time of issue. Subsequent changes are subject to audit logs and approved permissions [ ] نوع العقد [DD/MM/YYYY] تاريخ التعيين Joining Date Contract Type [____] /KWD الراتب الفعلي [____] /KWD الراتب الرسمي د.ك د.ك Official Salary Actual Salary [ ] مكان العمل الفعلي [ ] مكان العمل الرسمي Official Work Location Actual Work Location [DD/MM/YYYY] انتهاء الإقامة [ ] رقم الإقامة . Residency No Residency Expiry Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** annual_leave_days, basic_salary, contract_end, contract_start, contract_type, employee_name, job_title, working_hours

### PRN-007 — شهادة مدة خدمة

**Spec operational text (extracted):**

```
. يلتزم الموظف}transfer_type{، بصفة}effective_date{ اعتبارًا من }new_location{ إلى}old_location{ من}employee_name{السيدة/ تقرر نقل السيد بتسليم الأعمال والعهد حسب الإجراءات المعتمدة، ويظل باقي شروط العمل دون تغيير ما لم يذكر خلاف ذلك.
```

**Current seed body (stripped HTML):**

```
تشهد شركة اسم الشركة بأن مدة خدمة الموظف اسم الموظف المحتسبة وفق سجلات الشركة تمتد من تاريخ التعيين حتى تاريخ االحتساب ، بإجمالي مدة قدرها السنوات األشهر األيام . . ] [ certifies that ]Employee Name[ has completed service from ]Joining Date[ to ]Calculation Date[, totaling ]Years/Months/Days[ according to company records Company Name [DD/MM/YYYY] تاريخ االحتساب [DD/MM/YYYY] تاريخ بداية الخدمة Service Start Calculation Date [None/Details] فترات االنقطاع [Y/M/D] مدة الخدمة Service Length Excluded Periods Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** effective_date, employee_name, new_location, old_location, transfer_type

### PRN-008 — خطاب تحويل راتب للبنك

**Spec operational text (extracted):**

```
. ويطبق أثر الدرجة والراتب وفق الاعتماد}effective_date{ اعتبارًا من }new_title{ إلى}old_title{ من وظيفة}employee_name{السيدة/ تقرر ترقية السيد المالي المرفق، مع استمرار باقي شروط العقد.
```

**Current seed body (stripped HTML):**

```
السادة اسم البنك المحترمون، نحيطكم علما بأن الموظف اسم الموظف يعمل لدى شركة اسم الشركة ، وقد تقرر تحويل راتبه الشهري إلى الحساب الموضح أدناه اعتبارا من راتب شهر الشهر السنة ، وذلك وفق الإجراءات الداخلية المعتمدة. Dear ]Bank Name[, please be informed that ]Employee Name[ is employed by ]Company Name[. The monthly salary shall be transferred to the account below effective from the payroll month ]Month/Year[, subject to approved internal procedures [ ] اسم البنك IBAN/ [ ] رقم الحساب Bank Name Account / IBAN [DD/MM/YYYY] تاريخ البدء [____] /KWD راتب التحويل د.ك Transfer Salary Effective Date Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** effective_date, employee_name, new_title, old_title

### PRN-009 — إفادة استمرارية راتب

**Spec operational text (extracted):**

```
. يعتمد}reason{، وذلك بسبب}effective_date{ د.ك اعتبارًا من }new_salary{ د.ك إلى}old_salary{ من}employee_name{السيدة/ تقرر تعديل راتب السيد القرار من الإدارة والموارد البشرية والمالية، ويثبت التغيير في سجل التدقيق.
```

**Current seed body (stripped HTML):**

```
تفيد شركة اسم الشركة بأن الموظف اسم الموظف ما زال على رأس عمله، وأن راتبه يصرف وفق دورة الرواتب المعتمدة بالشركة، مع خضوع أي تغيير الحق للقرارات والسياسات الداخلية. confirms that ]Employee Name[ remains actively employed and receives salary according to the company payroll cycle. Any future change is subject to internal decisions and Company Name policies [Bank/Cash] طريقة الصرف [Monthly] دورة الصرف Payroll Cycle Payment Method [Active] الحالة [MM/YYYY] آخر راتب مصروف Last Payroll Month Status Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** effective_date, employee_name, new_salary, old_salary, reason

### PRN-010 — خطاب موجه لجهة رسمية

**Spec operational text (extracted):**

```
هذا الإنذار بضرورة الالتزام}employee_name{السيدة/، يوجه إلى السيد}incident_summary{ والمتعلقة بـ}incident_date{ بالإشارة إلى الواقعة بتاريخ بسياسات العمل والتعليمات المعتمدة. ويعد تكرار المخالفة سببًا لاتخاذ الإجراء المناسب وفق النظام. توقيع الموظف أدناه يفيد العلم والاستلام ولا يعد إقرارًا بصحة الواقعة.
```

**Current seed body (stripped HTML):**

```
السادة اسم الجهة المحترمون، بالإشارة إلى طلبكم موضوع الموضوع ، نفيدكم بأن بيانات الموظف الموضح أعاله صحيحة وفق سجلات شركة اسم الشركة حتى تاريخ إصدار هذا الخطاب. وتفضلوا بقبول فائق االحترام. Dear ]Entity Name[, with reference to ]Subject[, we confirm that the above employee information is accurate according to ]Company Name[ records as of the issue date. Yours faithfully [ ] الموضوع [ ] الجهة Entity Subject [ ] المرفقات [ ] رقم المرجع الخارجي External Reference Attachments Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** employee_name, incident_date, incident_summary

### PRN-011 — خطاب عرض وظيفي

**Spec operational text (extracted):**

```
بالوقائع وسماع}employee_name{، وتمت مواجهة الموظف}attendees{. حضر كل من}subject{ تم فتح محضر تحقيق بشأن}investigation_date{ بتاريخ ، وترفع التوصية للجهة المختصة لاتخاذ القرار.}result{أقواله ودفاعه وإرفاق ما قدمه من مستندات. خلصت اللجنة إلى
```

**Current seed body (stripped HTML):**

```
يسر شركة اسم الشركة أن تقدم للسيد السيدة اسم المرشح عرضا للعمل بوظيفة المسمى الوظيفي في مكان العمل ، وفق الشروط الموضحة أدناه. يصبح العرض نافذا بعد توقيع الطرفين واستكمال المستندات والموافقات المطلوبة. is pleased to offer Mr./Ms. ]Candidate Name[ employment as ]Job Title[ at ]Work Location[, subject to the terms below. The offer becomes effective upon signature by both Company Name parties and completion of required documents and approvals [____] /KWD إجمالي الراتب [____] /KWD الراتب الأساسي د.ك د.ك Basic Salary Total Package [DD/MM/YYYY] تاريخ المباشرة [ ] فترة التجربة Probation Start Date [DD/MM/YYYY] مدة صلاحية العرض [ ] ساعات العمل Working Hours Offer Validity الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared by HR إعداد الموارد البشرية .................... التوقيع والتاريخ / Signature &amp; Date Manager Approval اعتماد المدير .................... التوقيع والتاريخ / Signature &amp; Date Candidate Acceptance قبول المرشح .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** attendees, employee_name, investigation_date, result, subject

### PRN-012 — إشعار تجديد عقد

**Spec operational text (extracted):**

```
عن شهر}employee_name{السيدة/ د.ك من مستحقات السيد}deduction_amount{ بعد مراجعة الواقعة والمستندات و
```

**Current seed body (stripped HTML):**

```
نحيط الموظف اسم الموظف علما بأن الشركة ترغب في تجديد عقد العمل اعتبارا من تاريخ البدء ولمدة المدة ، وفق الشروط والتعديالت الموضحة أدناه. يرجى إبداء الموافقة أو الملاحظات خلال عدد أيام عمل. is hereby notified that the company intends to renew the employment contract effective ]Start Date[ for ]Duration[, subject to the terms and amendments below. Please confirm Employee Name acceptance or comments within ]Number[ working days [____] /KWD الراتب الجديد [ ] مدة التجديد د.ك ........................ Renewal Period New Salary [ ] مكان العمل [ ] المسمى الوظيفي Job Title Work Location [ ] مالحظات [DD/MM/YYYY] آخر موعد للرد Response Deadline Notes الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** deduction_amount, employee_name

### PRN-013 — إشعار عدم تجديد عقد

**Spec operational text (extracted):**

```
. تقرر اتخاذ}violation_details{ والمتمثلة في}incident_date{ بتاريخ}policy_reference{ للسياسة رقم}employee_name{السيدة/ ثبتت مخالفة السيد بعد مراجعة أقوال الموظف والمستندات ذات الصلة.}action_taken{الإجراء
```

**Current seed body (stripped HTML):**

```
يخطر الموظف اسم الموظف بأن عقد العمل الحالي لن يتم تجديده بعد تاريخ انتهائه في تاريخ االنتهاء . ويستمر الموظف في أداء واجباته وتسليم العهد والمستندات حتى آخر يوم عمل، مع استكمال إجراءات التسوية وإخلاء الطرف. is notified that the current employment contract will not be renewed after its expiry on ]Expiry Date[. Duties, handover, final settlement, and clearance procedures must be Employee Name completed through the last working day [DD/MM/YYYY] آخر يوم عمل [DD/MM/YYYY] تاريخ انتهاء العقد Contract Expiry Last Working Day [ ] إجراءات التسليم [ ] فترة الإشعار Notice Period Handover Requirements الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** action_taken, employee_name, incident_date, policy_reference, violation_details

### PRN-014 — قبول استقالة

**Spec operational text (extracted):**

```
، وأن توقيعي يفيد العلم بمحتواه فقط دون أن يسقط حقي في}received_at{ بتاريخ}warning_reference{ باستلام الإنذار رقم}employee_name{ أقر أنا تقديم رد أو اعتراض خلال المدة المحددة.
```

**Current seed body (stripped HTML):**

```
بالإشارة إلى االستقالة المقدمة من الموظف اسم الموظف بتاريخ تاريخ الطلب ، تقرر قبولها، على أن يكون آخر يوم عمل هو التاريخ . ويلتزم الموظف باستكمال التسليم وإخلاء الطرف وتسوية المستحقات وفق الإجراءات المعتمدة. With reference to the resignation submitted by ]Employee Name[ on ]Request Date[, the resignation is accepted and the last working day shall be ]Date[. Handover, clearance, and final settlement must be completed under approved procedures [DD/MM/YYYY] آخر يوم عمل [DD/MM/YYYY] تاريخ تقديم االستقالة Resignation Date Last Working Day [Pending/Completed] حالة التسوية [ ] فترة الإشعار Notice Period Settlement Status الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** employee_name, received_at, warning_reference

### PRN-015 — قرار إنهاء خدمة

**Spec operational text (extracted):**

```
يومًا. الرصيد }days_count{ بإجمالي}end_date{ إلى}start_date{ خلال الفترة من}leave_type{ من نوع}employee_name{السيدة/ اعتمدت إجازة السيد إن وجد.}replacement_employee{. تم اعتماد البديل}return_date{ يومًا، وتاريخ العودة المتوقع }balance_after{ يومًا وبعدها }balance_before{قبل الإجازة
```

**Current seed body (stripped HTML):**

```
استنادا إلى الصلاحيات المعتمدة ونتيجة سبب الإنهاء المرجع ، تقرر إنهاء خدمة الموظف اسم الموظف اعتبارا من التاريخ . تستكمل إجراءات التسليم والتسوية النهائية وإخلاء الطرف، مع حفظ حق الموظف في التظلم وفق سياسة الشركة. Based on approved authority and ]Reason/Reference[, the employment of ]Employee Name[ is terminated effective ]Date[. Handover, final settlement, and clearance shall be completed, while preserving the employee’s right to appeal under company policy Decision/Investigation/[ المرجع [ ] سبب الإنهاء Reason Reference ]Contract [DD/MM/YYYY] حق التظلم حتى [DD/MM/YYYY] تاريخ النفاذ Effective Date Appeal Deadline الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared by HR إعداد الموارد البشرية .................... التوقيع والتاريخ / Signature &amp; Date Legal Review مراجعة الشؤون القانونية .................... التوقيع والتاريخ / Signature &amp; Date Authorized Approval اعتماد صاحب الصلاحية .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** balance_after, balance_before, days_count, employee_name, end_date, leave_type, replacement_employee, return_date, start_date

### PRN-016 — قرار نقل موظف

**Spec operational text (extracted):**

```
. لا مانع مالي من استكمال}financial_status{، تبين أن موقف السلف والقروض والعهد المالية هو}employee_name{ بعد المراجعة المالية لطلب سفر الموظف .}approved_at{. يعتمد هذا الإفادة المحاسب المخول بتاريخ}finance_notes{توجد الملاحظات التالية/الإجراء
```

**Current seed body (stripped HTML):**

```
تقرر نقل الموظف اسم الموظف من القسم الفرع الحالي إلى القسم الفرع الجديد اعتبارا من التاريخ ، مع تحديث المسؤول المباشر ومكان العمل الفعلي والصلاحيات والعهد المرتبطة بالوظيفة الجديدة. is transferred from ]Current Department/Branch[ to ]New Department/Branch[ effective ]Date[. Reporting line, actual work location, permissions, and assigned assets shall be Employee Name updated accordingly [Department/Branch] إلى [Department/Branch] من From To [DD/MM/YYYY] تاريخ النفاذ [ ] المسؤول الجديد New Line Manager Effective Date [ ] مالحظات [____ No/Yes] تغيير الراتب : ........................ Salary Change Notes الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** approved_at, employee_name, finance_notes, financial_status

### PRN-017 — قرار تكليف بفرع أو موقع عمل

**Spec operational text (extracted):**

```
. الموقف}residency_expiry{ والإقامة صالحة حتى}passport_expiry{، تبين أن الجواز صالح حتى}employee_name{ بعد فحص مستندات سفر الموظف .}missing_documents{، والمستندات الناقصة إن وجدت}legal_status{المستندي/القانوني
```

**Current seed body (stripped HTML):**

```
يكلف الموظف اسم الموظف بالعمل في الفرع الموقع خلال الفترة من من إلى إلى ، تحت إشراف اسم المسؤول ، مع االلتزام بساعات العمل والتعليمات الخاصة بالموقع. . ] [ is assigned to work at ]Branch/Location[ from ]From[ to ]To[ under the supervision of ]Manager Name[, subject to the location’s working hours and instructions Employee Name [ ] الموقع الفعلي [ ] الموقع الرسمي Official Location Actual Location [ ] المسؤول [From] [To] فترة التكليف Assignment Period Supervisor الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** employee_name, legal_status, missing_documents, passport_expiry, residency_expiry

### PRN-018 — قرار ترقية

**Spec operational text (extracted):**

```

```

**Current seed body (stripped HTML):**

```
تقديرا للأداء والكفاءة، تقرر ترقية الموظف اسم الموظف من وظيفة الحالية إلى وظيفة الجديدة اعتبارا من التاريخ ، وتُعدَّل البيانات الوظيفية والمالية والصلاحيات وفق التفاصيل أدناه. In recognition of performance and competence, ]Employee Name[ is promoted from ]Current Role[ to ]New Role[ effective ]Date[. Employment data, compensation, and permissions shall be updated as detailed below [ ] المسمى الجديد [ ] المسمى السابق Previous Title New Title [____] /KWD الراتب الجديد [____] /KWD الراتب السابق د.ك د.ك Previous Salary New Salary [DD/MM/YYYY] تاريخ النفاذ [ ] الدرجة المستوى Grade / Level Effective Date الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```


### PRN-019 — قرار تعديل راتب

**Spec operational text (extracted):**

```
. المستندات}government_entity{ لدى}employee_or_company{ الخاصة بـ}transaction_type{ بمتابعة معاملة}delegate_name{ يكلف المندوب . يلتزم المندوب بتحديث حالة المعاملة وإرفاق إيصالاتها.}due_date{، والموعد المستهدف}documents_list{المسلمة
```

**Current seed body (stripped HTML):**

```
تقرر تعديل راتب الموظف اسم الموظف اعتبارا من التاريخ وفق التفاصيل أدناه. يطبق التعديل في دورة الرواتب المحددة بعد اكتمال االعتماد، مع توثيق الراتب الرسمي والراتب الفعلي كلٌّ على حدة. The salary of ]Employee Name[ is adjusted effective ]Date[ as detailed below. The change shall be applied in the designated payroll cycle after approval, with official and actual salary recorded separately [____] الراتب الرسمي الجديد [____] الراتب الرسمي السابق د.ك د.ك Previous Official Salary New Official Salary [____] الراتب الفعلي الجديد [____] الراتب الفعلي السابق د.ك د.ك Previous Actual Salary New Actual Salary [MM/YYYY] شهر التطبيق [ ] سبب التعديل Reason Payroll Month الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** delegate_name, documents_list, due_date, employee_or_company, government_entity, transaction_type

### PRN-020 — قرار بدل أو مكافأة

**Spec operational text (extracted):**

```
من خلال}deadline{. يرجى رفعها قبل}missing_documents{ علمًا بأن ملفه يحتاج إلى المستندات التالية }employee_name{السيدة/ نحيط السيد ، وإلا قد يتعذر استكمال المعاملة المرتبطة.}submission_method{
```

**Current seed body (stripped HTML):**

```
تقرر منح الموظف اسم الموظف بدل مكافأة بقيمة المبلغ د.ك، وذلك عن السبب الفترة ، على أن تصرف وفق دورة الرواتب والإجراءات المالية المعتمدة. . ] [ is granted an ]Allowance/Bonus[ of KWD ]Amount[ for ]Reason/Period[, payable according to the approved payroll and finance process Employee Name [____] /KWD القيمة [Allowance/Bonus] النوع د.ك Type Amount [Payroll/Separate] طريقة الصرف [ ] الفترة Period Payment Method [Yes/No] خاضع لالستقطاع [ ] السبب Reason Subject to Deduction Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** deadline, employee_name, missing_documents, submission_method

### PRN-021 — قرار خصم

**Spec operational text (extracted):**

```
. نوع التجديد}expiry_date{ والمنتهية في}residency_no{، إقامة رقم}civil_id{، رقم مدني}employee_name{ يرجى اتخاذ إجراءات تجديد إقامة الموظف .}delegate_name{. تعتمد المعاملة وفق المسار المحدد ثم تسند إلى المندوب}reason{وسببه}renewal_type{
```

**Current seed body (stripped HTML):**

```
بناء على المرجع المخالفة وبعد مراجعة المستندات، تقرر خصم مبلغ المبلغ د.ك عدد األيام من مستحقات الموظف اسم الموظف ، على أن ينفذ في راتب شهر الشهر ، مع إتاحة حق التظلم وفق السياسة المعتمدة. Based on ]Reference/Violation[ and review of supporting records, a deduction of KWD ]Amount[ / ]Days[ is imposed on ]Employee Name[, to be applied in payroll month ]Month[, with the right to appeal under approved policy [ ] القيمة [Amount/Days] نوع الخصم Deduction Type Value [MM/YYYY] شهر التنفيذ [ ] المرجع Reference Payroll Month [None/Submitted] حالة التظلم [DD/MM/YYYY] آخر موعد للتظلم Appeal Deadline Appeal Status الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared by Admin إعداد الشؤون الإدارية .................... التوقيع والتاريخ / Signature &amp; Date Legal Review مراجعة قانونية .................... التوقيع والتاريخ / Signature &amp; Date Manager Approval اعتماد المدير .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** civil_id, delegate_name, employee_name, expiry_date, reason, renewal_type, residency_no

### PRN-022 — إنذار موظف

**Spec operational text (extracted):**

```

```

**Current seed body (stripped HTML):**

```
يوجه إلى الموظف اسم الموظف إنذار بسبب وصف المخالفة الواقعة بتاريخ التاريخ . يطلب االلتزام بالتعليمات والسياسات وعدم تكرار المخالفة، وإال قد تتخذ إجراءات تصاعدية وفق النظام الداخلي. is issued a warning for ]Violation Description[ occurring on ]Date[. The employee must comply with company policies and avoid recurrence; otherwise, progressive action may Employee Name be taken under internal rules [DD/MM/YYYY] تاريخ الواقعة [First/Second] نوع الإنذار Warning Level Incident Date [ ] الإجراء التصحيحي [ ] المخالفة Violation Corrective Action [ ] مرجع السياسة [ ] فترة المتابعة Monitoring Period Policy Reference الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```


### PRN-023 — إنذار نهائي

**Spec operational text (extracted):**

```

```

**Current seed body (stripped HTML):**

```
نظرا لتكرار جسامة المخالفة الموضحة أدناه، يوجه إلى الموظف اسم الموظف إنذار نهائي. ويعد أي تكرار أو عدم التزام خلال فترة المتابعة سببا التخاذ إجراء أشد وفق القرارات والسياسات المعتمدة. Due to the repeated/serious violation detailed below, ]Employee Name[ is issued a final warning. Any recurrence or failure to comply during the monitoring period may result in stronger action under approved policies [ ] المخالفة الحالية [References] الإنذارات السابقة Previous Warnings Current Violation [ ] فترة المتابعة [ ] الإجراء المطلوب Required Action Monitoring Period [ ] مرجع التحقيق [ ] نتيجة عدم االلتزام Consequence . Investigation Ref الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```


### PRN-024 — استدعاء للتحقيق الإداري

**Spec operational text (extracted):**

```

```

**Current seed body (stripped HTML):**

```
يطلب من الموظف اسم الموظف الحضور أمام لجنة مسؤول التحقيق في التاريخ والمكان المحددين أدناه لمناقشة موضوع الموضوع . يجوز للموظف تقديم مستنداته وإفادته، ويثبت عدم الحضور دون عذر في سجل التحقيق. is required to attend an administrative investigation at the date and place below regarding ]Subject[. The employee may submit documents and statements; absence without Employee Name valid reason shall be recorded [DD/MM/YYYYHHMM] التاريخ والوقت [ ] موضوع التحقيق ........................ : Subject Date &amp; Time [ ] المحقق اللجنة [ ] المكان Location Investigator / Committee [ ] رقم القضية [ ] المستندات المطلوبة Required Documents . Case No الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```


### PRN-025 — قرار إيقاف مؤقت لحين التحقيق

**Spec operational text (extracted):**

```

```

**Current seed body (stripped HTML):**

```
تقرر إيقاف الموظف اسم الموظف مؤقتا عن العمل بعض الصلاحيات اعتبارا من التاريخ وحتى التاريخ انتهاء التحقيق ، حفاظا على سير التحقيق والمصلحة التشغيلية، دون اعتبار القرار حسما للنتيجة النهائية. is temporarily suspended from ]Work/Specific Permissions[ effective ]Date[ until ]Date/Investigation Completion[ to protect the investigation and operations. This does not Employee Name predetermine the final outcome [DD/MM/YYYY] تاريخ البدء [Full/Partial] نطاق الإيقاف Suspension Scope Start Date [Asapproved] الوضع المالي [ ] المدة المتوقعة Expected Duration Pay Status [ ] مرجع التحقيق [Suspend/Retain] العهد الصلاحيات Assets / Access . Investigation Ref الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Legal Review مراجعة قانونية .................... التوقيع والتاريخ / Signature &amp; Date Authorized Approval اعتماد صاحب الصلاحية .................... التوقيع والتاريخ / Signature &amp; Date
```


### PRN-026 — تكليف واعتماد عمل إضافي

**Spec operational text (extracted):**

```

```

**Current seed body (stripped HTML):**

```
يكلف الموظف اسم الموظف بأداء عمل إضافي في التاريخ الفترة المحددة لتنفيذ المهمة . لا تحتسب الساعات إال بعد التحقق من الحضور واعتماد المسؤول المباشر والجهة المخولة. is assigned overtime during the specified date/period to perform ]Task[. Hours are recognized only after attendance verification and approval by the line manager and Employee Name authorized party [HHMM HHMM] من - إلى [DD/MM/YYYY] التاريخ : - : Date From - To [ ] سبب العمل الإضافي [____] عدد الساعات Hours Reason [____] الساعات المعتمدة [Payment/TimeOff] طريقة التعويض Compensation Approved Hours الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Line Manager Request طلب المسؤول المباشر .................... التوقيع والتاريخ / Signature &amp; Date Attendance Verification تحقق الحضور .................... التوقيع والتاريخ / Signature &amp; Date Final Approval االعتماد النهائي .................... التوقيع والتاريخ / Signature &amp; Date
```


### PRN-027 — قرار اعتماد إجازة

**Spec operational text (extracted):**

```
. أساس الاحتساب}last_working_day{ إلى}hire_date{ عن مدة الخدمة من}employee_name{السيدة/ هذه تسوية مبدئية لمستحقات نهاية خدمة السيد د.ك، وتخضع للمراجعة والاعتماد.}net_amount{ د.ك، والصافي المبدئي}deductions_total{ د.ك، الخصومات}entitlements_total{د.ك، المستحقات}salary_basis{
```

**Current seed body (stripped HTML):**

```
تمت الموافقة على إجازة الموظف اسم الموظف وفق النوع والفترة الموضحين أدناه. يلتزم الموظف بتسليم األعمال قبل المغادرة والعودة في الموعد المحدد، ويحدث رصيد الإجازة تلقائيا بعد االعتماد. The leave request of ]Employee Name[ is approved according to the type and period below. Work handover must be completed before departure and the employee must return on time. Leave balance shall be updated upon approval [DD/MM/YYYY] من تاريخ [Annual/Sick/Other] نوع الإجازة Leave Type From Date [____] عدد األيام [DD/MM/YYYY] إلى تاريخ To Date Number of Days [____] الرصيد بعد [____] الرصيد قبل Balance Before Balance After الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** deductions_total, employee_name, entitlements_total, hire_date, last_working_day, net_amount, salary_basis

### PRN-028 — إشعار عودة من إجازة

**Spec operational text (extracted):**

```
د.ك، إجمالي الخصومات}entitlements_total{: إجمالي المستحقات}employee_name{السيدة/ اعتمدت التسوية النهائية لمستحقات نهاية خدمة السيد د.ك. يقر الموظف بالاستلام بعد بيان التفاصيل، مع حفظ الحقوق النظامية التي لا يجوز التنازل عنها.}net_amount{د.ك، وصافي المستحق}deductions_total{
```

**Current seed body (stripped HTML):**

```
يفيد هذا الإشعار بأن الموظف اسم الموظف قد باشر العمل بعد الإجازة بتاريخ التاريخ في الساعة الوقت . تح Cدث حالته الوظيفية والحضور وفق سجل المباشرة. This notice confirms that ]Employee Name[ resumed work after leave on ]Date[ at ]Time[. Employment and attendance status shall be updated accordingly [DD/MM/YYYY] الإجازة إلى [DD/MM/YYYY] الإجازة من Leave From Leave To [DD/MM/YYYY] تاريخ المباشرة الفعلي [DD/MM/YYYY] تاريخ المباشرة المتوقع Expected Return Actual Return [ ] مالحظات المسؤول [ ] التأخير إن وجد Delay, if any Manager Notes الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** deductions_total, employee_name, entitlements_total, net_amount

### PRN-029 — بيان رصيد الإجازات

**Spec operational text (extracted):**

```
يومًا، }consumed_days{ يومًا، المستهلك }entitled_days{: الرصيد المستحق}as_of_date{ حتى تاريخ}employee_name{ بيان رصيد إجازات الموظف يومًا. أي رصيد سالب أو استثناء يجب أن يظهر معه سبب وسياسة المعالجة. }remaining_days{والمتبقي
```

**Current seed body (stripped HTML):**

```
هذا البيان يوضح رصيد إجازات الموظف حتى تاريخ تاريخ االحتساب وفق السجلات المعتمدة في النظام. أي طلبات معلقة أو تعديالت قيد المراجعة تظهر بشكل منفصل. This statement shows the employee leave balance as of ]Calculation Date[ according to approved HRMS records. Pending requests or adjustments are shown separately [____] /syaD استحقاق السنة [____] /syaD الرصيد المرحل يوم يوم Carried Forward Annual Entitlement [____] /syaD المعلق [____] /syaD المستخدم يوم يوم Used Pending [____] /syaD الرصيد المتاح [____ /+] التعديالت يوم - Adjustments Available Balance Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** as_of_date, consumed_days, employee_name, entitled_days, remaining_days

### PRN-030 — كشف حضور شهري

**Spec operational text (extracted):**

```
، التأخير}absence_days{، الغياب}present_days{، الحضور}working_days{: أيام العمل}period{الموظفين عن الفترة/ كشف حضور الموظف ساعة. يعتمد بعد مراجعة الاستثناءات.}overtime_hours{ دقيقة، والعمل الإضافي}early_minutes{دقيقة، الخروج المبكر}late_minutes{
```

**Current seed body (stripped HTML):**

```
كشف حضور الموظف عن شهر الشهر السنة مستخرج من سجلات الحضور المعتمدة، ويشمل أيام العمل والغياب والتأخير والخروج المبكر والعمل الإضافي. Monthly attendance statement for ]Month/Year[ generated from approved attendance records, including workdays, absence, lateness, early departure, and overtime [____] أيام الحضور [____] أيام العمل Working Days Present Days [____] مرات التأخير [____] أيام الغياب Absent Days Late Occurrences [____] الساعات الإضافية [____] الخروج المبكر Early Departures Overtime Hours [____] المخالفات المفتوحة [____] إجمالي ساعات العمل Total Worked Hours Open Exceptions System Generated إعداد النظام .................... التوقيع والتاريخ / Signature &amp; Date Supervisor Review مراجعة المشرف .................... التوقيع والتاريخ / Signature &amp; Date HR Approval اعتماد الموارد البشرية .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** absence_days, early_minutes, late_minutes, overtime_hours, period, present_days, working_days

### PRN-031 — تأكيد تعديل سجل حضور

**Spec operational text (extracted):**

```
، متضمنًا التاريخ والحالة والمدة والسبب وقرار التصحيح. لا يحول أي يوم إلى خصم قبل اكتمال المراجعة}period{ كشف تفصيلي بحالات التأخير والغياب عن الفترة والاعتماد.
```

**Current seed body (stripped HTML):**

```
تم تعديل سجل الحضور الخاص بالموظف اسم الموظف عن تاريخ التاريخ بناء على الطلب والمرجع الموضحين أدناه، مع االحتفاظ بالقيم قبل وبعد التعديل في سجل التدقيق. The attendance record for ]Employee Name[ on ]Date[ has been adjusted based on the approved request and reference below. Previous and new values are retained in the audit log Checkin/Checkout/[ [ ] القيمة السابقة نوع التعديل Adjustment Type ]Absence Previous Value [ ] سبب التعديل [ ] القيمة الجديدة New Value Reason [ ] المرفق الداعم [ ] رقم الطلب . Request No Supporting Attachment Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** period

### PRN-032 — كشف راتب شهري مبسط

**Spec operational text (extracted):**

```
،}absence_deduction{، خصم الغياب}overtime_total{، الإضافي}allowances_total{، البدلات}basic_total{: الأساسي}period{ كشف رواتب الفترة .}payroll_status{. حالة المسير}net_total{، وصافي الرواتب}other_deductions{، الخصومات الأخرى}loan_deductions{الأقساط/السلف
```

**Current seed body (stripped HTML):**

```
هذا الكشف يوضح عناصر راتب الموظف عن شهر الشهر السنة كما تم اعتمادها في دورة الرواتب. لا يعد مستندا مصرفيا إال بعد توقيع وختم الجهة المخولة. This statement shows the approved payroll components for ]Month/Year[. It is not a bank document unless signed and stamped by the authorized party [____] البدلات [____] الراتب الأساسي د.ك د.ك Basic Salary Allowances [____] المكافآت [____] العمل الإضافي د.ك د.ك Overtime Bonuses [____] السلف [____] الخصومات د.ك د.ك Deductions Advances [Bank/Cash] طريقة الدفع [____] صافي الراتب د.ك Net Salary Payment Method Prepared by Accounts إعداد المحاسبة .................... التوقيع والتاريخ / Signature &amp; Date HR Review مراجعة الموارد البشرية .................... التوقيع والتاريخ / Signature &amp; Date Manager Approval اعتماد المدير .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** absence_deduction, allowances_total, basic_total, loan_deductions, net_total, other_deductions, overtime_total, payroll_status, period

### PRN-033 — إشعار نقص مستندات

**Spec operational text (extracted):**

```
، حالة الاعتماد}amount{، المبلغ}reason{، السبب}deduction_reference{: المرجع}period{ عن الفترة}employee_name{ كشف خصومات الموظف .}payroll_effect{، وأثره على مسير الراتب}approval_status{
```

**Current seed body (stripped HTML):**

```
نحيط الموظف اسم الموظف علما بأن ملفه معاملته رقم المرجع ينقصها المستندات الموضحة أدناه. يرجى رفع أو تسليم المستندات قبل الموعد لتجنب تأخير المعاملة أو توقفها. . ] [ is notified that file/transaction ]Reference[ is missing the documents listed below. Please upload or submit them by ]Deadline[ to avoid delay or suspension of the transaction Employee Name [ ] المستندات الناقصة [ ] نوع المعاملة Transaction Type Missing Documents [HRMS/Physical] طريقة التسليم [DD/MM/YYYY] آخر موعد Deadline Submission Method [AwaitingDocuments] حالة المعاملة [ ] المسؤول Responsible Officer Transaction Status الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** amount, approval_status, deduction_reference, employee_name, payroll_effect, period, reason

### PRN-034 — تفويض تجديد إقامة

**Spec operational text (extracted):**

```
. أتعهد بالمحافظة عليها واستخدامها لأغراض العمل وإعادتها عند الطلب أو انتهاء الخدمة،}assets_list{ باستلام العهد التالية بحالة سليمة}employee_name{ أقر أنا مع إثبات الرقم التسلسلي والحالة.
```

**Current seed body (stripped HTML):**

```
تفوض شركة اسم الشركة الجهة المندوب الموضح أدناه باستكمال إجراءات تجديد إقامة الموظف اسم الموظف ، وفق مدة الصلاحية والمستندات المعتمدة، مع تحديث النظام عند كل مرحلة من مراحل المعاملة. authorizes the party/delegate below to complete the residency renewal of ]Employee Name[ based on approved validity and documents, with HRMS status updated at each Company Name stage Early days/Normal[ 30-90 [DD/MM/YYYY] انتهاء الإقامة نوع التجديد Renewal Type ]&lt;= days Residency Expiry 30 [ ] رقم ملف الشركة [ ] مدة التجديد Renewal Period . Company File No Passport/Permit/Photo/[ المرفقات [ ] المندوب المكلف Assigned Delegate Attachments ]Other Legal Affairs الشؤون القانونية .................... التوقيع والتاريخ / Signature &amp; Date Company Manager مدير الشركة .................... التوقيع والتاريخ / Signature &amp; Date Delegate المندوب .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** assets_list, employee_name

### PRN-035 — تفويض تجديد إذن عمل

**Spec operational text (extracted):**

```
. يحال أي أثر مالي إلى}issues{الأضرار/ والنواقص}return_condition{. حالة الإرجاع}assets_list{ :}employee_name{ تم استلام العهد التالية من الموظف المالية قبل إغلاق إخلاء الطرف.
```

**Current seed body (stripped HTML):**

```
تعتمد مباشرة إجراءات تجديد إذن العمل الخاص بالموظف اسم الموظف وفق الملف والترخيص المبينين أدناه، ويكلف المندوب برفع المستندات والنتيجة النهائية في النظام. The work permit renewal process for ]Employee Name[ is authorized under the company file and license below. The delegate shall upload supporting documents and final outcome to the HRMS [DD/MM/YYYY] تاريخ االنتهاء [ ] رقم إذن العمل . Work Permit No Expiry Date [ ] الترخيص [ ] ملف الشركة Company File License [DD/MM/YYYY] موعد الإنجاز [ ] المندوب Delegate Target Completion | / | | Employee/Legal شؤون الموظفين القانونية .................... التوقيع والتاريخ / Signature &amp; Date Manager Approval اعتماد المدير .................... التوقيع والتاريخ / Signature &amp; Date Delegate Execution تنفيذ المندوب .................... التوقيع والتاريخ / Signature &amp; Date Affairs .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** assets_list, employee_name, issues, return_condition

### PRN-036 — إشعار تحديث البطاقة المدنية أو الجواز

**Spec operational text (extracted):**

```
. يتحمل}mission_purpose{ لغرض}end_date{ - }start_date{ خلال الفترة}location{ بمهمة عمل خارجية إلى}employee_name{السيدة/ يكلف السيد متابعة التنفيذ، وتطبق المصروفات المعتمدة إن وجدت.}manager_name{المسؤول
```

**Current seed body (stripped HTML):**

```
يلزم تحديث بيانات البطاقة المدنية جواز السفر للموظف اسم الموظف بسبب انتهاء تغيير بيانات إصدار جديد . يرجى تقديم النسخة الجديدة قبل التاريخ وتحديث الملف الإلكتروني. . ] [ must update ]Civil ID/Passport[ details due to ]Expiry/Data Change/New Issue[. Please submit the new copy by ]Date[ and update the electronic employee file Employee Name [ ] الرقم الحالي [CivilID/Passport] نوع المستند Document Type Current Number [Upload/SubmitOriginal] المطلوب [DD/MM/YYYY] تاريخ االنتهاء Expiry Date Required Action [Pending/Received] حالة االستالم [DD/MM/YYYY] آخر موعد Deadline Receipt Status الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared By إعداد .................... التوقيع والتاريخ / Signature &amp; Date Reviewed By مراجعة .................... التوقيع والتاريخ / Signature &amp; Date Approved By اعتماد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** employee_name, end_date, location, manager_name, mission_purpose, start_date

### PRN-037 — تكليف مندوب بمعاملة حكومية

**Spec operational text (extracted):**

```
. يتم تحديث نظام الحضور}reason{ بسبب}effective_date{ اعتبارًا من }new_shift{ إلى}old_shift{ من}employee_name{ تقرر تغيير وردية الموظف وإبلاغ الموظف والمشرف.
```

**Current seed body (stripped HTML):**

```
يكلف المندوب اسم المندوب بتنفيذ المعاملة الحكومية الموضحة أدناه لصالح الشركة الموظف ، مع االلتزام بتحديث حالة المهمة، وإرفاق الإيصاالت والمستند النهائي، وإعادة أي عهد أو مستندات أصلية. is assigned to complete the government transaction below for ]Company/Employee[, update task status, attach receipts and final documents, and return any originals or Delegate Name assigned assets [ ] الجهة الحكومية [ ] نوع المعاملة Transaction Type Government Entity [DD/MM/YYYY] الموعد النهائي [ ] رقم المرجع . Reference No Deadline [ ] النتيجة المطلوبة [ ] العهد المبالغ Assets / Amounts Required Outcome الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Task Creator إنشاء المهمة .................... التوقيع والتاريخ / Signature &amp; Date Delegate Acceptance استلام المندوب .................... التوقيع والتاريخ / Signature &amp; Date Closure Approval اعتماد الإغالق .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** effective_date, employee_name, new_shift, old_shift, reason

### PRN-038 — التسوية النهائية ونهاية الخدمة

**Spec operational text (extracted):**

```
،}rate_or_amount{قيمة الاستحقاق/. معدل}reason{ ساعة بسبب}hours{ لمدة}overtime_date{ بتاريخ}employee_name{ اعتمد عمل إضافي للموظف ولا يرحل للراتب قبل اعتماد المدير والمالية.
```

**Current seed body (stripped HTML):**

```
يوضح هذا المستند التسوية النهائية للموظف اسم الموظف حتى آخر يوم عمل التاريخ . تم احتساب البنود وفق البيانات المعتمدة في النظام، على أن تخضع المبالغ للمراجعة النهائية والتوقيعات المخولة قبل الصرف. This document summarizes the final settlement of ]Employee Name[ through the last working day ]Date[. Amounts are calculated from approved HRMS data and remain subject to final review and authorized signatures before payment [____] راتب مستحق [____] مكافأة نهاية الخدمة د.ك د.ك End of Service Benefit Outstanding Salary [____] مستحقات أخرى [____] بدل إجازات د.ك د.ك Leave Encashment Other Entitlements [____] سلف متبقية [____] خصومات عهد د.ك د.ك Deductions / Assets Outstanding Advances [____] الصافي النهائي [____] إجمالي المستحق د.ك د.ك Gross Payable Net Settlement الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Prepared by HR إعداد الموارد البشرية .................... التوقيع والتاريخ / Signature &amp; Date Accounts Review مراجعة المحاسبة .................... التوقيع والتاريخ / Signature &amp; Date Approval &amp; Payment االعتماد والصرف .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** employee_name, hours, overtime_date, rate_or_amount, reason

### PRN-039 — شهادة إخلاء طرف

**Spec operational text (extracted):**

```

```

**Current seed body (stripped HTML):**

```
تفيد الإدارات الموضحة أدناه بإتمام الموظف اسم الموظف تسليم العهد والمستندات وإغالق االلتزامات المسجلة عليه، ويعتمد إخلاء الطرف النهائي بعد اكتمال جميع األقسام دون استثناء. The departments below confirm that ]Employee Name[ has returned assigned assets and documents and settled recorded obligations. Final clearance is approved only after all sections are completed [Cleared/Pending] المحاسبة [Cleared/Pending] تقنية المعلومات IT Accounts [Cleared/Pending] الفرع الإدارة [Cleared/Pending] المخازن العهد Assets / Stores Branch / Department [Cleared/Pending] الموارد البشرية [Cleared/Pending] الشؤون القانونية Legal Affairs HR الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Department Officer مسؤول القسم .................... التوقيع والتاريخ / Signature &amp; Date HR Review مراجعة الموارد البشرية .................... التوقيع والتاريخ / Signature &amp; Date Final Clearance اعتماد الإخلاء .................... التوقيع والتاريخ / Signature &amp; Date
```


### PRN-040 — محضر تسليم عهدة

**Spec operational text (extracted):**

```
الأجهزة عند توفرها/، وعناوين الشبكة}timestamps{، أوقات التوقيع}signers{: الموقعون}document_reference{ سجل التوقيع الإلكتروني للمستند منفصلة عن متن المستند.}document_hash{. تحفظ بصمة المستند}technical_metadata{
```

**Current seed body (stripped HTML):**

```
تم في التاريخ الموضح تسليم استلام العهد المبينة أدناه بين الطرفين، بعد معاينتها وإثبات حالتها. يتحمل المستلم مسؤولية المحافظة عليها واستخدامها في أغراض العمل وإعادتها عند الطلب. On the date shown, the assets below were handed over/received between the parties after inspection and condition recording. The recipient is responsible for proper business use, safekeeping, and return upon request [ ] الرقم التسلسلي [Laptop/Phone/Keys/Other] نوع العهدة Asset Type . Serial No [ ] الملحقات [New/Good/Damaged] الحالة عند التسليم Condition Accessories [ ] إلى الموظف [ ] من الموظف From Employee To Employee الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Handed Over By المسلم .................... التوقيع والتاريخ / Signature &amp; Date Received By المستلم .................... التوقيع والتاريخ / Signature &amp; Date Asset Controller مسؤول العهد .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** document_hash, document_reference, signers, technical_metadata, timestamps

### PRN-041 — محضر استلام وتسليم مستندات

**Spec operational text (extracted):**

```
.}requested_opinion{، والمطلوب}attachments{. المرفقات}review_reason{ بسبب}subject_or_document{ يرجى من الشؤون القانونية مراجعة تسجل النتيجة والتوصية والقيود على الاطلاع في الملف.
```

**Current seed body (stripped HTML):**

```
يثبت هذا المحضر استلام تسليم المستندات األصلية أو النسخ الموضحة أدناه. لا يجوز استخدام المستندات إال للغرض المحدد، ويجب إعادتها أو حفظها وفق سياسة إدارة الوثائق. This record confirms receipt/handover of the original documents or copies listed below. Documents may only be used for the stated purpose and must be returned or stored according to document management policy Passport/CivilID/Contract/[ [ ] الرقم نوع المستند Document Type ]Other . Document No [ ] الغرض [ ] أصل أم نسخة Original / Copy Purpose [DD/MM/YYYY] موعد الإعادة [DD/MM/YYYY] تاريخ االستالم Receipt Date Return Date الإقرار / Acknowledgment: أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / I acknowledge the accuracy of the information above and my commitment to it. Handed Over By المسلم .................... التوقيع والتاريخ / Signature &amp; Date Received By المستلم .................... التوقيع والتاريخ / Signature &amp; Date Witness / Reviewer الشاهد / المراجع .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** attachments, requested_opinion, review_reason, subject_or_document

### PRN-042 — سجل اعتماد التوقيع الإلكتروني

**Spec operational text (extracted):**

```
البيانات الشخصية والوظيفية والحكومية، العقد، الراتب وفق الصلاحية، المستندات وصلاحيتها، الأرصدة، الطلبات المفتوحة،}employee_name{ ملخص ملف الموظف التنبيهات والعهد. يجب إخفاء الحقول غير المصرح بها وإظهار نسبة اكتمال الملف.
```

**Current seed body (stripped HTML):**

```
يوثق هذا السجل اعتماد المستند إلكترونيا من أصحاب الصلاحية الموضحين أدناه. يرتبط كل اعتماد بهوية المستخدم والتاريخ والوقت وعنوان الجهاز الجلسة ورمز التحقق، وال يعتد بأي تعديل الحق دون إنشاء إصدار جديد. This record documents electronic approval by the authorized users below. Each approval is linked to user identity, date/time, session/device reference, and verification code. Subsequent changes require a new version [ ] رقم المستند [ ] نوع المستند Document Type . Document No [ ] رمز التحقق [ ] الإصدار 1.0 ........................ Version Verification Code [Approved/Rejected] حالة االعتماد [DD/MM/YYYYHHMM] تاريخ الإنشاء : Created At Approval Status Electronic Creator منشئ إلكتروني .................... التوقيع والتاريخ / Signature &amp; Date Electronic Reviewer المراجع الإلكتروني .................... التوقيع والتاريخ / Signature &amp; Date Electronic Approver المعتمد الإلكتروني .................... التوقيع والتاريخ / Signature &amp; Date
```

**Placeholders missing in seed:** employee_name

