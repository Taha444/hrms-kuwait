---
name: hrms-tasks-counters-expiry
description: محرك المهام والإشعارات والعدادات ومحرك تواريخ الانتهاء في Kuwait HRMS — منع المهام المكررة، إغلاقها عند تغير المرحلة، فصل المهام عن الإشعارات، وتوحيد كل عدّاد مع القائمة التي يفتحها. استخدم هذا السكيل عند أي عمل على المهام أو الإشعارات أو الـ Digest أو العدادات أو مركز العمليات أو تنبيهات الانتهاء.
---

# Package 2 — المهام والإشعارات والعدادات والانتهاء

## الأدلة المؤكدة
```
permit 1 مُجدَّد فعلا إلى 2027-08-21 وما زالت له renewal tasks مفتوحة
permit 2 له أكثر من renew_residency task
renewal 1 عنده في نفس الوقت: "بانتظار رفع العقود" و "تم رفع العقود الموقعة"
Operations Center يعرض 24 government task والعناصر الحقيقية ~8
Employee 20: open=17 أغلبها Digests وإشعارات قديمة
نفس الـ PRO: Dashboard 7 · Tasks/Bell 22 · Operations Center 24
الإشعارات: Dashboard 2 · Tasks API 15
```

**الثمانية بنود جذر واحد: لا يوجد تعريف واضح لما هو مهمة، ولا مفتاح تفرّد، ولا إغلاق عند تغير المرحلة.**
رتّبهم معا. إصلاح العدّاد وحده يعطي رقما مضبوطا على بيانات مكررة.

## P2-05 — منع التكرار (P0)

### القاعدة
```
Active Task واحدة فقط لكل:  entity + task_type + active workflow/case
```
**قيد فريد على مستوى قاعدة البيانات** — لا فحص في الكود فقط. الفحص في الكود يُخترق عند التزامن، وهذا ما يحدث مع الـ scan المتكرر أو تعدد النسخ.

### دورة الحياة
```
تغير المرحلة  →  old stage task = closed/resolved
              →  new stage task = created if action required
اكتمال الحدث  →  كل Tasks المتعلقة بالغرض القديم تُغلق
```
مثال صريح: **Residency renewed → old permit expiry/renewal tasks تُغلق تلقائيا.**

الحالة الموثقة «بانتظار رفع العقود» + «تم رفع العقود الموقعة» معا تعني أن **إنشاء مهمة المرحلة الجديدة لا يُغلق السابقة**. هذا هو الإصلاح المحوري.

### احصر القائم
```sql
SELECT entity_type, entity_id, task_type, COUNT(*) FROM tasks
WHERE status='open' GROUP BY 1,2,3 HAVING COUNT(*)>1;

SELECT t.id, t.task_type, p.expiry_date FROM tasks t
JOIN permits p ON p.id = t.entity_id
WHERE t.status='open' AND t.task_type LIKE '%renew%' AND p.expiry_date > CURRENT_DATE + 180;
```
نظّف القائم بـ migration مراجَعة **بعد** إضافة القيد.

## P2-06 — محرك الانتهاء يراقب Current فقط (P0)
```
تجديد المستند → القديمة historical/superseded · الجديدة Current
              → expiry engine يراقب Current فقط
              → old reminders تتوقف · old tasks تُغلق
              → new expiry هو مصدر الحقيقة في كل مكان
```
> **ممنوع أن تستمر النسخة القديمة في توليد reminders بعد وجود Current جديدة.**

التنفيذ: اربط التنبيه بـ `document_version_id` لا بـ `employee_id` أو `document_type` فقط.

## P2-07 · P2-08 — المهام مقابل الإشعارات
```
TASK          = user action required
NOTIFICATION  = information only
```
- **Daily Digest لا يدخل actionable task count** — informational/transient
- لا يبني backlog مفتوحا · لا يكرر نفس المهام بداخله بسبب مصادر مكررة · لا يظل يؤثر على Dashboard بعد أيام
- Notification لا تتحول Task إلا لو فيها Action فعلي

**التصنيف نقل لا حذف.** الإشعارات القديمة تنتقل لمكانها الصحيح ولا تُمسح من التاريخ.

## P2-09 — الحالات النهائية تُغلق آثارها
عند `Completed / Rejected / Cancelled`:
```
actionable tasks المتعلقة  →  تُغلق
pending actions            →  تُلغى
notifications القديمة      →  history/read، خارج open-work count
```
> لا يبقى طلب انتهى والنظام يقول للمستخدم إن عليه Action بسببه.

## P2-10 — توحيد العدادات (P0)

### التعريفات
```
My Open Tasks        = actionable tasks assigned to this user
Notifications        = unread/informational حسب السياسة
Government Operations = actual active government cases/tasks بعد dedup
```

### القاعدة الحاسمة
> **الرقم على الـ Card = القائمة التي تفتح عند الضغط عليه.**
> لو الـ Card تقول 8، القائمة تعرض نفس الـ8.

**التنفيذ:** العدّاد يُشتق من **نفس استعلام القائمة** — لا استعلام مستقل. أي عدّاد له استعلام خاص سينحرف.

اختبار القبول `DOD-12`: اضغط كل رقم في كل Dashboard وقارنه بالصفوف يدويا.

## P2-11 — نطاق العدادات عبر الشركات
الوضع: باختيار MUF (لا renewals فيها) يبقى `my_open_tasks=7` وهي مهام GUF، بينما `gov_tasks` صارت 0 بشكل صحيح.

**بعض الـ Cards scoped وبعضها global بلا توضيح — هذه هي المشكلة، لا الرقم نفسه.**

```
Dashboard context = selected company  →  كل company-specific counters تتقيد بها
"My Tasks Across All Companies"       →  يُسمّى صراحة ومنفصل عن counters الشركة
```
اختر السياسة، طبّقها على **كل** الـ Cards، واذكرها في الواجهة.

**تذكير:** PRO مسند لـ GUF + MUF **مقصود** (قاعدة حماية 3). لا تعالج هذا بمنعه من إحداهما.

## P2-12 — مركز العمليات يعرض العمل الحقيقي
بعد إصلاح ما سبق:
```
لا duplicates · لا stale tasks · لا completed entities
لا old-version expiry tasks · لا notification rows داخل actionable work
```
> الـ PRO يفتح الشاشة صباحا فيجد **فقط** ما هو مطلوب منه الآن.

## القبول
`DOD-05` `DOD-07` `DOD-08` `DOD-12`
