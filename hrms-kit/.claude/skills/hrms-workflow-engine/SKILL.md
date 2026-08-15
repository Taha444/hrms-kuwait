---
name: hrms-workflow-engine
description: محرك المهام والمسارات في Kuwait HRMS — أنواع الخطوات (DECISION/VALIDATION/EXECUTION/ACKNOWLEDGEMENT/NOTIFICATION/AUTOMATION)، دورة الحالة الموحدة، الـ Dynamic Resolver، Claim/ONE_OF/ALL_OF، التفويض، SLA، وقواعد السياسة القابلة للإصدار. استخدم هذا السكيل إلزاميا عند أي عمل على workflow، مسار طلب، خطوة، مهمة، task inbox، approval، حالة طلب، policy rule، أو أي كود يمس request_instance / task_instance / workflow_definition / workflow_step. استخدمه حتى لو كان الطلب يبدو بسيطا مثل "أضف خطوة موافقة" أو "غيّر حالة الطلب" — لأن الغلط في هذه الطبقة يعيد إنتاج مشكلة الموافقات الشكلية.
---

# HRMS Workflow Engine (V2.2 §3، §7، §8، §10)

## المبدأ الحاكم
الطلب ليس "شاشة تمر على أشخاص". هو **Case Management داخلي ينتهي إلى أثر عمل + وثيقة مستقلة عند الحاجة**.
الموافقة تمنح السلطة لإتمام الأثر — المستند يثبت النتيجة — سجل التدقيق يثبت كيف وصل النظام إليها. **ثلاثة كائنات، وليست ملفا واحدا.**

## القاعدة الأولى قبل كتابة أي كود
لا تُصلح المسارات الحالية واحدا واحدا مع الإبقاء على نموذج الصلاحيات نفسه. ابنِ المحرك أولا (نوع الخطوة + المعيّن + الشرط + النطاق)، ثم انقل المسارات إليه على مراحل.

## 1. أنواع الخطوات — ممنوع اختزالها في Approve
| Step Type | متى يُستخدم | الأفعال المسموحة |
|---|---|---|
| `DECISION` | اختيار إداري/مالي يتحمل صاحبه المسؤولية | Approve, Reject, Needs Info |
| `VALIDATION` | فحص حقيقة أو سياسة أو مستند | Valid, Invalid, Return for Correction |
| `EXECUTION` | تنفيذ أثر بعد القرار | Start, Complete, Cannot Complete |
| `ACKNOWLEDGEMENT` | إثبات علم/استلام — **ليس حق تعطيل القرار** | Acknowledge, Acknowledge with Comment, Dispute (إن سمحت السياسة) |
| `NOTIFICATION` | إبلاغ بلا مهمة قرار | — |
| `AUTOMATION` | قاعدة حتمية بلا تدخل بشري | — |

**فحص ذاتي:** لو وجدت نفسك تكتب `if (action === 'approve')` لخطوة تحقق أو تنفيذ — توقف. هذا هو الخطأ الأصلي.

## 2. أنواع المشاركة (Participation)
`Requester` · `Approver` · `Validator` · `Executor` · `Contributor` · `CC/Acknowledger` · `Admin System`
- `Validator` لا يقرر خارج اختصاصه.
- `Contributor` يضيف رأيا أو مستندا **دون امتلاك القرار**.
- `Admin System` يدير الكتالوج والمسارات — **لا يعتمد أعمالا افتراضيا**.

## 3. دورة الحالة الموحدة
```
DRAFT → SUBMITTED → IN_REVIEW → NEEDS_INFO → APPROVED → IN_EXECUTION → COMPLETED
حالات نهائية بديلة: REJECTED, CANCELLED, EXPIRED
```
- `NEEDS_INFO` يعود **لنفس المرحلة وبنفس الرقم** بعد الاستكمال. **ممنوع إنشاء طلب جديد.** لا تضيع الملاحظات ولا سجل التدقيق.
- **دورة المستند منفصلة تماما** ولا تُدمج هنا: `NOT_REQUIRED → QUEUED → GENERATED → DELIVERED → ACKNOWLEDGED/FILED`.
- فشل توليد PDF **لا** يحوّل الطلب إلى `COMPLETED`، **ولا** يسجل نجاح طباعة.
- ممنوع نهائيا: حالات الطباعة (`PRINT_TO_READY`, `PRINTED`, `FILED`) داخل حالة الطلب.

## 4. التدفق العام
1. يرسل المستخدم نوعا **مسموحا له فقط**.
2. تحقق من الحقول والهوية والتكرار والسياسة الأساسية.
3. يقيّم محرك القواعد: الشركة، الفرع، القيمة، المدة، نوع الاستثناء.
4. **ينشئ فقط المهام المطلوبة** — بالتتابع أو بالتوازي حسب الاعتماد الحقيقي، لا حسب عادة تنظيمية.
5. يرى صاحب المهمة الحالية أزراره فقط؛ الباقون قراءة أو إشعار.
6. بعد اكتمال الأثر التشغيلي، يولد المستند أو الإشعار ثم يغلق الطلب.

## 5. التعيين والمجموعات والتفويض (§8)
- المعيّن **ديناميكي** من علاقة الموظف: `Direct Manager` / `Branch Manager` / وظيفة مالية أو HR معتمدة. لا تُثبّت أسماء.
- مهام المجموعة: `Claim` + `ONE_OF` — أول عضو مخوّل يتسلم المهمة، والباقون **يفقدون الـ action**.
- `ALL_OF` فقط عند لزوم توقيع كل جهة فعلا (مثل أصول محددة في إخلاء الطرف).
- **تخطي الموافق المكرر تلقائيا** — لا يُطلب من الشخص نفسه اعتماد مرحلتين متتاليتين للسبب نفسه.
- التفويض مؤقت ومؤرخ، ويُمنع تفويض مقدم الطلب لنفسه أو لشخص في تعارض مصالح.
- عند غياب المعيّن: `fallback` واضح (بديل منصب / مجموعة / تصعيد). **لا تبقى مهمة بلا مالك.**

## 6. قواعد القرار الشرطي (§7) — لا تكتب الحدود في الكود
تُحفظ في `policy_rule` قابلة للإصدار حسب الشركة والفرع:
```
leave_hr_review_days · leave_blackout_rule · negative_balance_allowed
expense_second_approval_amount · loan_signatory_amount · training_budget_amount
salary_change_percent_threshold · eos_signatory_amount
early_renewal_days · exception_fee_threshold
manager_required_for_certificate_subtype
```
**كل طلب يحتفظ بنسخة من `policy_version` و `workflow_version` وقت الإرسال** — تعديل السياسة لاحقا لا يغيّر مسار طلب قائم تاريخيا.

## 7. النموذج التقني (§10) — الحقول الجوهرية
```
request_type          code, category, requester_roles, visibility_policy,
                      schema_version, active, contextual_only
workflow_definition   code, version, company_scope, effective_from/to, status
workflow_step         step_type, resolver, assignment_mode, completion_mode,
                      condition, due_in, fallback, allowed_actions, field_permissions
request_instance      requester, subject, company, payload, current_state,
                      workflow_version, policy_version
task_instance         step, assignee/group, claimed_by, status, due_at,
                      completed_by, outcome, comment
decision_log          actor, original_actor, impersonated_actor, action, reason,
                      before/after, timestamp, IP
document_instance     template_code/version, request_id, generation_status,
                      checksum, delivered_at, filed_at
delegation            delegator, delegate, scope, valid_from/to, conflict_check
```

## 8. قواعد إلزامية على الخادم
- كل انتقال حالة **idempotent** — الضغط مرتين على Complete ينتج أثرا واحدا وسجلا واحدا.
- الخادم يمنع: `self-approval`, `double action`, `stale task`, `direct URL action`.
- **الواجهة ليست طبقة الأمان الوحيدة** — أي فحص في الـ UI يجب أن يكون مكررا في الـ API.

## 9. ممنوعات (§15)
- زر Approve/Reject عام في كل تفاصيل طلب.
- Super Admin كموافق افتراضي عند غياب الدور.
- HR/Finance/Manager كخطوات ثابتة في كل طلب.
- حالة `Pending` بلا `current step` و `assignee` و `SLA`.
- اعتبار إقرار الموظف موافقة، أو منحه حق إصدار الإجراء ضد نفسه.
- إنشاء طلب جديد عند كل إعادة معلومات.

## التحقق
بعد أي تعديل هنا، شغّل `/hrms-verify-engine` — يفحص المعايير `AC-02, AC-06, AC-07, AC-08, AC-09` والاختبارات `RW-01, RW-08, RW-09, RW-10, RW-16, RW-17, RW-18`.
تفاصيل تلك الاختبارات في سكيل `hrms-acceptance-verification`.
