---
name: hrms-error-observability-audit
description: مراجعة معالجة الأخطاء والتدقيق والمراقبة في Kuwait HRMS — تسريب المعلومات في رسائل الخطأ، اكتمال سجل التدقيق، ومنع تسجيل النجاح عند الفشل. استخدم هذا السكيل كسابع مرحلة في مراجعة الباكند، وعند أي عمل على معالجة الأخطاء أو اللوجات أو سجل التدقيق.
---

# مراجعة الأخطاء والتدقيق والمراقبة

## 1. تسريب المعلومات في الأخطاء
افتعل أخطاء متنوعة واقرأ الرد كاملا:
```bash
curl "$B/api/employees/999999" -H "..."          # غير موجود
curl "$B/api/employees/abc" -H "..."             # نوع خاطئ
curl -X POST "$B/api/requests" -d '{bad json'    # JSON تالف
curl "$B/api/employees?sort=x'" -H "..."         # يفتعل خطأ استعلام
curl "$B/api/x" -H "Authorization: Bearer bad"   # توكن غير صالح
```

**ممنوع في جسم أي خطأ:**
```
stack trace · مسار ملف على الخادم · استعلام SQL · اسم جدول أو عمود
اسم الإطار وإصداره · متغيرات بيئة · اتصال قاعدة البيانات
أسماء أو أرقام أشخاص لا يملك الطالب رؤيتهم
```

**تسريب خبيث شائع:** رسالة تفرّق بين «المستخدم غير موجود» و«كلمة سر خاطئة» تكشف الحسابات الموجودة. الصحيح: رسالة واحدة.

وكذلك: `403` لسجل موجود مقابل `404` لغير موجود **يكشف الوجود**. في البيانات الحساسة، وحّدهما على `404`.

## 2. أكواد الحالة
```
200 نجاح فعلي          ← لا تُرجع 200 مع رسالة خطأ في الجسم
201 إنشاء
400/422 مدخل خاطئ      ← يسمّي الحقل
401 غير مصادق
403 مصادق وغير مخوّل
404 غير موجود
409 تعارض حالة         ← يشرح المرحلة والسبب والناقص
429 تجاوز الحد
500 خطأ خادم           ← لا يُخفى بـ catch
```

**بلاغ موثق:** `GET /api/employees` يرجع 500 على GUF و 200 على MUF، والتوجيه كان صريحا: **ممنوع إخفاء الـ 500 من الواجهة أو ابتلاعه بـ catch.**

ابحث في الكود عن `catch` بلا إعادة رمي وبلا تسجيل — كل واحد منها عطل مخفي.

## 3. سجل التدقيق — الاكتمال
كل حدث يجب أن يحمل:
```
actor · original_actor · impersonated_user · role · company · branch
entity · action · result · before · after · reason
IP · user_agent · correlation_id · timestamp
```

```sql
SELECT action, COUNT(*) FROM audit_log
WHERE actor_id IS NULL OR ip IS NULL GROUP BY 1 ORDER BY 2 DESC;
```
**بلاغ موثق:** `request_completed` بلا Actor وبلا IP. الاكتمال الآلي يُسجَّل باسم النظام **مع سبب التشغيل** — لا حقل فارغ.

## 4. لا نجاح عند الفشل
```sql
SELECT id, action, result FROM audit_log
WHERE result='success' AND error_message IS NOT NULL;
```
**اختبار عملي:** افتعل فشلا في عملية (رفض تحقق مثلا) وافحص: هل سُجِّل حدث نجاح؟ هل نشأ Task أو Notification؟

البلاغ الموثق ينص: «فشل الطلب لا ينشئ Request أو Task أو Notification أو Audit نجاح ناقص».

## 5. الأحداث المطلوبة
```
Employee/User Create/Update/Archive · Request Actions (approve/reject/return/resubmit)
Attendance · Payroll · Renewal · Signature · Template
Document Generate/Issue/Print/File/Download · Export
Forbidden Access · Role/Permission Changes · Login/Logout/Impersonation
```
**محاولات الوصول المرفوضة تُسجَّل** — بدونها لن تعرف أن أحدا يحاول.

## 6. اللوجات
```
[ ] لا كلمات سر ولا توكنات ولا أرقام مدنية كاملة في اللوج
[ ] لوجات مهيكلة قابلة للبحث
[ ] correlation id يربط الطلب عبر الطبقات
[ ] مستوى مناسب — لا debug في الإنتاج
[ ] لا تُفقد أحداث تدقيق أثناء النشر أو الـ migration
```

## 7. المراقبة والوظائف المجدولة
```
[ ] Health check يعكس حالة القاعدة والتخزين فعلا لا "OK" ثابت
[ ] تنبيه عند فشل: Daily Scan · Notification · PDF Generation · Backup · Payroll
[ ] جهة استقبال التنبيه محددة بالاسم لا "الفريق"
[ ] الـ job لا يعمل مرتين مع تعدد النسخ (قفل موزّع + idempotency)
[ ] فشل الـ job مرئي لا صامت
```

## 8. الوقت
```
[ ] التخزين UTC · العرض بتوقيت الكويت
[ ] ساعة الخادم مضبوطة بـ NTP
```
**بلاغ موثق:** 2FA فشل بسبب فرق 111 ثانية في ساعة الخادم. افحص الفرق فعليا:
```bash
curl -sI "$B/" | grep -i '^date:'   # قارنه بوقتك
```

## التسجيل
- stack trace أو بيانات في رسالة خطأ → `critical`
- تسريب وجود سجل عبر اختلاف 403/404 → `high`
- تدقيق ناقص الحقول → `high`
- نجاح مسجّل لعملية فاشلة → `high`
- كلمة سر في لوج → `critical`
