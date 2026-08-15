---
name: hrms-attendance-payroll
description: طبقة الحضور والرواتب ونهاية الخدمة في Kuwait HRMS — صلاحيات مراجعة الحضور، الغياب قبل التعيين، تطابق عدد الموظفين، Attendance Close، دورة اعتماد الرواتب، ورصيد الإجازات المتناقض مع EOS. استخدم هذا السكيل إلزاميا عند أي عمل على الحضور، الغياب، تصحيح الحضور، مسير الرواتب، الخصومات، رصيد الإجازات، أو نهاية الخدمة. استخدمه أيضا عند أي بلاغ عن عدد موظفين غير مطابق بين شاشتين.
---

# HRMS Attendance · Payroll · EOS (عناقيد ATT + PAY + EOS — 19 بندا)

## القاعدة الحاكمة للعنقود كله
**مصدر بيانات واحد.** كل عطل تقريبا في هذه الطبقة سببه أن كل شاشة تحسب بنفسها:
- `ATT-04`: الغياب قبل التعيين أُصلح في Payroll Preview وبقي في Attendance Review.
- `EOS-03`: رصيد الإجازة 30 في ملف الموظف و 92.16 في EOS — والرقم الثاني دخل فعلا في بدل الإجازات.
- `ATT-03`: Manager يرى 12 موظفا والشركة فيها 13.

**قبل أي إصلاح في هذه الطبقة: حدد مصدر الحقيقة، وأصلحه هناك، ثم اجعل كل الشاشات تقرأ منه.**

## 1. صلاحيات مراجعة الحضور — `ATT-01` `ATT-02` `ATT-03`
| الدور | ما يراجعه |
|---|---|
| HR | موظفي شركته |
| Branch Supervisor | الفروع المسندة له فقط |
| Manager | نطاقه — وبعدد مطابق للـ Active Employees |
| Accountant | البيانات المطلوبة للرواتب فقط |
| Employee | My Attendance فقط — ممنوع من المراجعة العامة |

قاعدة العدد: **كل Active Employee يظهر في Attendance Review أو له Attendance Policy / Exempt Reason واضح.**
العدد يطابق Employees و Payroll **بدون سقوط موظف**.
عند وجود فرق: **حدد الموظف الساقط بالاسم وسبب سقوطه** — لا تكتفِ بإصلاح العدد.

## 2. الغياب — قاعدتان لا تُخلطان
- `ATT-04` **(blocker)**: أي يوم **قبل تاريخ التعيين** لا يدخل في الحضور أو الغياب أصلا. مثال موثق: تعيين 2026-08-10 وظهر غياب في 2،3،4،5،6،9 أغسطس.
- `ATT-05` **(تناقض CONF-01)**: عدم وجود تسجيل حضور لا يتحول تلقائيا لغياب وخصم. **قائمة الـ Retest تقول إن هذه نجحت** — تحقق من البناء الحالي قبل أي تعديل.
- `PAY-09` **(CONF-08)**: الأيام بعد تاريخ المعاينة — **لا تُعدَّل إطلاقا** إلا لو ظهر Regression جديد. المصدر ينص على ذلك صراحة.

## 3. سياسة الحضور — `ATT-06`
كل Active Employee له Attendance Policy أو Exempt بسبب وموافقة.
**إزالة None كقيمة افتراضية صامتة** — هذه هي التي تُسقط الموظفين من الشاشات.
Check-in/Check-out مع منع التكرار · ربط الفرع والسياسة · Audit لأي تعديل.

## 4. Attendance Close — `ATT-07` (blocker)
الرواتب تُشغَّل حاليا بلا ضمان صحة الحضور. المطلوب:
```
Attendance Reviewed → Attendance Closed → Approved Input Set → Payroll
```
تصحيح الحضور المعتمد **ينعكس قبل احتساب الراتب** لا بعده.
تطابق Attendance population و Payroll population إلزامي.

## 5. تصحيح الحضور — `WF-04` و `CAT-03`
الطلب يصل Completed بلا تطبيق. القواعد:
- **تطبيق التعديل والانتقال إلى Completed في Transaction واحدة.**
- ممنوع الوصول إلى Completed لو التعديل لم يُطبق.
- عند الفشل: حالة صريحة `Failed` أو `Not Applied`.
- النموذج المستقل: Attendance Date, Correction Type, Existing Check-in/out, Requested Check-in/out, Reason, Attachment.
- **إزالة Amount KWD ونصوص الإجازة** من النموذج.
- إظهار Before/After للموافق · Audit فيه Before/After واسم الموافق ووقت التطبيق.

## 6. دورة الرواتب — `PAY-01` إلى `PAY-05`
الوضع الحالي: `Run & Save` ينتج Finalized مباشرة. غير آمن.

الدورة المطلوبة:
```
Draft/Preview → Attendance Reviewed → Attendance Closed
→ Prepared → Approved → Finalized → Locked
```

القواعد:
- `company_id` واحد صريح · **ممنوع Run من All Companies** · Owner لا يستطيع Preview أثناء All Companies.
- **Maker-Checker**: فصل من يجهّز عن من يعتمد نهائيا. Manager له مسار واضح في الاعتماد.
- منع Duplicate Run لنفس الشركة والفترة.
- منع الحفظ النهائي لو الحضور غير معتمد.
- Reopen يحتاج صلاحية وسببا و Audit.
- بعد Lock: **لا تعديل على الراتب القديم — Adjustment Run فقط.**
- Breakdown كامل: Basic · Allowances · Overtime · Absence · Advance/Loan · Deductions · Net.
- استبعاد Archived Employees.
- **أي دورة غير مكتملة قبل الإطلاق: أغلق `Run & Save` الخاص بها** بدل تركها تنفّذ راتبا غير معتمد.

## 7. حالة خاصة: PRO في شركتين — `PAY-06`
محمد فاروق موجود في GUF و MUF **عمدا**. سجل الشركة الثانية مجرد Assignment للعمل كمندوب.
- **يظل مربوطا بالشركتين ويعمل كمندوب فيهما** — لا تفصله.
- الـ secondary assignment **لا يدخل** في Payroll أو EOS أو financial count، حتى لو براتب صفر.

## 8. نهاية الخدمة — `EOS-01` `EOS-02` `EOS-03`
الوضع: صفحة Demo Calculator، و End Service ينفّذ مباشرة من ملف الموظف بلا Workflow.

المسار المطلوب:
```
HR Initiate/Review → Finance Calculation and Verification
→ Manager/Authorized Final Approval → Clearance
→ Employee Acknowledgment → Final Settlement
→ Ready to Print → Printed → Filed/Closed
```

- **إلغاء التنفيذ المباشر** · ممنوع إنهاء موظف من مستخدم واحد بلا موافقات.
- فصل Preview EOS عن قرار إنهاء الخدمة.
- إزالة القيم التجريبية الافتراضية · موظف حقيقي وبيانات من النظام.
- رفض `salary <= 0` · رفض End Date قبل Hire Date.
- حساب رصيد الإجازات والمستحقات والخصومات والعهدة.
- مستند مبدئي ونهائي · Before/After Audit.

### رصيد الإجازات — `EOS-03` (blocker)
أمثلة موثقة: رامين 30 مقابل 92.16 · QA Retest Aug14 30 مقابل 1.72 · QA Employee Final Test 30 مقابل 2.46.
الرقم 30 الثابت في ملف الموظف على الأرجح **استحقاق سنوي وليس رصيدا فعليا**.
**حدد أي الرقمين صحيح قبل التوحيد** — التوحيد على الرقم الخاطئ أسوأ من التناقض، لأن الرقم يدخل في بدل الإجازات المدفوع.

## التحقق
بعد أي إصلاح: اختبر على **الشركتين**، وتحقق أن **الأثر وقع فعلا** على السجل لا على الحالة فقط.
