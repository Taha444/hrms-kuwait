---
name: hrms-tasks-notifications
description: محرك المهام والإشعارات وسجل التدقيق في Kuwait HRMS — التفريق بين Task و Notification، منع المهام المكررة واليتيمة، الإغلاق التلقائي، تسليم الإشعارات الفعلي، وحقول الـ Audit الكاملة. استخدم هذا السكيل إلزاميا عند أي عمل على المهام، الإشعارات، العدادات، أو سجل التدقيق. استخدمه أيضا عند أي بلاغ عن مهمة لا تُغلق أو عداد لا يطابق أو حدث بلا Actor.
---

# HRMS Tasks · Notifications · Audit (عناقيد TASK + AUDIT — 7 بنود)

## 1. القاعدة الفاصلة — `TASK-02`
```
Task         = مطلوب من المستخدم إجراء
Notification = معلومة فقط
```
ظهر فعليا كمهام بأزرار «إنجاز/تجاهل»: «تم إلغاء طلب» · «تم رفض طلب» · «ملخص اليوم».
**هذه إشعارات، ليست مهاما.** أي شيء لا يتطلب قرارا أو تنفيذا لا يدخل صندوق المهام.

## 2. عيوب المهام الموثقة — `TASK-01`
| العطل | القاعدة |
|---|---|
| 4 مهام اعتماد متطابقة رغم أن الطلبات أقل | **مهمة واحدة لكل Action** — قيد فريد على (request, step, assignee) |
| مهمة اعتمدها المدير ولسه مفتوحة | **Auto Close** عند الاكتمال أو الرفض أو الإلغاء |
| لا رابط يفتح الطلب من المهمة | كل مهمة مرتبطة بالطلب برابط فعّال |
| نص «طلب طلب إجازة» | البادئة تُضاف في القالب والقيمة تحملها أصلا — أزل إحداهما |
| مهمة قرار مصنفة «معلومة» | التصنيف من `step_type` لا ثابتا |

قواعد إضافية: منع Orphan Tasks · منع Duplicate Tasks · **العداد يتغير فورا** · لا تبقى مهام مفتوحة لطلبات منتهية.

## 3. نطاق المهام — `TASK-04`
- Task **للمسؤول الحالي فقط** — لا لكل من يرى الطلب.
- Scope حسب الشركة والفرع والدور.
- Bulk Complete/Dismiss حسب الصلاحية.
- Audit لكل عملية.

## 4. محرك الإشعارات — `TASK-03`
**تحذير: وجود الأيقونة لا يعني التسليم.** المطلوب التحقق من الوصول الفعلي.

المكونات: `Templates · Notifications · Deliveries · Preferences · Channels · Read/Unread · Retry · Mandatory · SLA Reminders · Escalation · Digest · Idempotency`

الأحداث المطلوبة:
```
إنشاء الطلب · انتقال المرحلة · Needs Info · Return · Approval · Rejection
Completion · Ready to Print · Printed · Filed · Attendance Correction Applied
Payroll · Signature Replacement · Document Expiry · Residency
Missing Documents · Security Events
```
وبعد اكتمال أي طلب رسمي: إشعار للمسؤول بأن **النموذج جاهز للطباعة والحفظ في الملف الورقي**.

## 5. سجل التدقيق — `AUDIT-01` `AUDIT-02` `AUDIT-03`

### العطل المحدد
حدث `request_completed` ظهر **بلا Actor وبلا IP**.
القاعدة: الحدث يرتبط بالمستخدم أو الإجراء الذي أدى للاكتمال. إن كان اكتمالا آليا، يُسجَّل النظام كـ actor **مع سبب التشغيل** — لا حقل فارغ.

### الحقول الكاملة
```
Actor · Original Actor · Impersonated User · Role · Company · Branch
Entity · Action · Result · Before · After · Reason
IP · User Agent · Correlation ID · Timestamp
```

### الأحداث الكاملة
```
Employee/User Create/Update/Archive · Request Actions · Attendance · Payroll
Renewal · Signature · Template · Document Generate/Issue/Print/File/Download
Export · Forbidden Access · Role/Permission Changes
```

### قواعد صارمة
- **لا يُسجَّل Success عند فشل العملية.** هذه تظهر في أكثر من بلاغ (طلب فشل ينشئ Audit نجاح ناقص).
- **عدم فقد Audit Events** أثناء النشر أو Migration على نفس قاعدة البيانات.
- التخزين UTC · **العرض بتوقيت الكويت** (`AUDIT-03`).

## التحقق
- شغّل طلبا كاملا وعُدّ المهام المنشأة — أي تكرار = fail.
- اتخذ قرارا وتحقق أن المهمة أُغلقت **والعداد تغيّر فورا**.
- أرسل إشعارا وتتبّع وصوله فعليا للقناة.
- افحص صفا حقيقيا من `decision_log` وتأكد من الحقول الستة عشر.
