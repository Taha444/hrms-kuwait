---
name: hrms-exit-eos-lifecycle
description: دورة خروج الموظف في Kuwait HRMS — إيقاف الخدمة الذاتية للموظف المؤرشف، توحيد الاستقالة والإنهاء ونهاية الخدمة في Case واحد، وتايملاين خروج واضح. استخدم هذا السكيل عند أي عمل على الاستقالة أو إنهاء الخدمة أو إخلاء الطرف أو أرشفة موظف.
---

# Package 6 — دورة الخروج ونهاية الخدمة

## P6-26 — الموظف المؤرشف ما زال يملك خدمة ذاتية

### الدليل
Employee 20: `status = archived`
لكن `/auth/me` ما زال يعطي `submit_request`، و `/requests/types` يعرض 27 نوعا، وما زالت الـ Daily Digests تتولد له.

### ملاحظة على الخطورة
لم يُنفَّذ POST حقيقي من الحساب المؤرشف، **لكن مجرد إعطائه permission وكتالوج مشكلة gating يجب إصلاحها.** لا تؤجلها لأن الاستغلال لم يُثبت.

### المطلوب عند Final Exit/Archive
```
[ ] stop submit_request
[ ] hide new-request catalog
[ ] stop attendance recording
[ ] stop recurring digests/reminders غير المطلوبة
[ ] close employment-related active tasks
[ ] revoke operational access حسب السياسة
```

**الاحتفاظ التاريخي بالوصول والمستندات حسب قاعدة العمل — لا يُشال عشوائيا.** الموظف المؤرشف قد يحتاج شهادة خبرة لاحقا.

### التحقق الإلزامي — بند `V-G`
> بعد إصلاح الـ gating، تأكد أن **الـ backend POST نفسه يرفض** أي طلب جديد من موظف مؤرشف — **مش الـ UI بس.**

اضرب `POST /api/requests` بتوكن الحساب المؤرشف مباشرة. المتوقع 403.

## P6-27 — مسار خروج واحد

### الوضع
ثلاث عائلات منفصلة:
```
employees/terminate*
eos/cases*
REQRESIGN / REQEOS / REQCLR
```

> **المكونات نفسها مفيدة — لا تحذفها عشوائيا.** المطلوب orchestration واحد يربطها.

### الشكل النهائي
```
Resignation OR Termination initiated → required approvals
→ last working date confirmed → attendance finalized
→ leave/balance finalized → EOS calculated → financial approval
→ clearance → employee acknowledgement where required
→ settlement/payment evidence → required documents generated/signed/filed
→ access/self-service closed → employee status changed → archived
→ all employment tasks closed → complete timeline/audit
```

### قرار مطلوب
> اختيار أي module يكون master **داخليا** يحتاج Business/Engineering decision.
> لكن **للمستخدم لازم يظهر Process واحد.**

اعرض الخيارات (EOS case كـ master؟ أم Exit case جديد يستدعي الباقي؟) واطلب القرار. **لا تختر من عندك.**

أي شاشة من المكونات الحالية تشير لنفس Exit Case بدل Process مستقل.

## P6-28 — تايملاين الخروج
الموظف المؤرشف الحالي لا يظهر في timeline قصة خروج واضحة.

بعد التوحيد:
> **لا يمكن أن يصبح Employee مؤرشفا بلا audit/timeline event واضح يبيّن:**
> `who / when / reason / case / final status`

اجعل الأرشفة **لا تحدث إلا عبر Exit Case** — لا تحديث مباشر لحقل الحالة.

## القبول
`DOD-09` `DOD-10`
