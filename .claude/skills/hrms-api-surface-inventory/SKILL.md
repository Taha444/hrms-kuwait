---
name: hrms-api-surface-inventory
description: جرد سطح الـ API كاملا في Kuwait HRMS — استخراج كل مسار من الكود، ربطه بالمتحكم والحارس، وكشف المسارات المهجورة وغير المحمية وغير الموثقة. استخدم هذا السكيل كأول مرحلة في أي مراجعة باكند، وقبل أي فحص صلاحيات، وعند سؤال عن عدد الـ endpoints أو أيها غير مستخدم.
---

# جرد سطح الـ API

## القاعدة
**لا تراجع ما لا تعرف وجوده.** كل مرحلة بعد هذه تعتمد على اكتمال هذا الجرد.

## 1. استخرج المسارات من الكود
حسب الستاك:
```bash
php artisan route:list --json                    # Laravel
rails routes                                     # Rails
grep -rn "router\.\(get\|post\|put\|patch\|delete\)" src/   # Express/Nest
python manage.py show_urls                       # Django
```

لو لم تتوفر أداة، استخرجها بالبحث في ملفات الراوتر. **لا تخمّن المسارات** — ابحث عنها.

## 2. لكل مسار سجّل
```
المسار · الطريقة (GET/POST/PUT/PATCH/DELETE)
المتحكم والدالة · الـ middleware/guards المطبقة
هل يتطلب مصادقة؟ · أي صلاحية؟ · أي نطاق (company/branch/self)؟
هل يقبل معرّفا في المسار؟ (مرشح لـ IDOR)
هل يكتب أم يقرأ؟
```

احفظ الناتج في `.claude/hrms/audit/endpoints.json` — بقية المراحل تقرأ منه.

## 3. صنّف المسارات
| الفئة | العلامة |
|---|---|
| **محمي وموثق** | له حارس وصلاحية ونطاق واضح |
| **بلا حارس** | لا middleware مصادقة — **افحصه فورا، قد يكون تسريبا** |
| **بحارس بلا نطاق** | مصادقة فقط بلا فحص شركة أو ملكية — **مرشح IDOR قوي** |
| **مهجور** | لا تستدعيه الواجهة |
| **غير مسجّل** | موجود في الكود ولا يظهر في أي توثيق |

## 4. ابحث عن المسارات المهجورة
```bash
# لكل مسار، هل تستدعيه الواجهة؟
grep -rn "api/me/signature/history" --include=*.js --include=*.jsx \
  --include=*.ts --include=*.tsx --include=*.vue .
```

**المهجور ليس بريئا.** endpoint حي بلا صلاحية صحيحة **ثغرة** حتى لو لم تستدعه الواجهة — المهاجم لا يحتاج زرا.

بلاغ موثق مرتبط: `/api/me/signature/history` يرجع فارغا، وغير معروف إن كان مستخدما. صنّفه هنا.

## 5. المسارات الحساسة — أفردها بقائمة
```
/api/employees  ·  /api/employees/{id}/passport|civil-id|contract
/api/payroll  ·  /api/payroll/run  ·  /api/eos
/api/documents  ·  /api/signatures  ·  /api/renewals
/api/warnings  ·  /api/grievances  ·  /api/audit
/api/users  ·  /api/permissions  ·  /api/companies  ·  /api/templates
```
عدّلها حسب المسارات الفعلية. هذه القائمة تغذّي مصفوفة الصلاحيات في المرحلة التالية.

## 6. المسارات المكشوفة — فحص فوري
```
/.env · /.git/config · /api/config · /actuator · /debug
/swagger · /api-docs · /backup · /phpinfo.php · /admin
```
أي `200` من هذه = **critical فورا**، لا تنتظر بقية المراجعة.

## 7. تناسق المسارات
- طرق HTTP صحيحة؟ (`GET` لا يكتب · `DELETE` لا يُستخدم للقراءة)
- تسمية متسقة؟ (خليط `snake_case` و `camelCase` في نفس الـ API يسبب أخطاء تكامل)
- ترقيم الصفحات موجود على القوائم الكبيرة؟ (غيابه مشكلة أداء وتسريب حجم)
- إصدار الـ API؟

## الأداة
```bash
bash .claude/hrms/scripts/discover.sh
```
يستخرج ما يستطيع ويطبع ما يحتاج استخراجا يدويا.

## المخرَج
```
عدد المسارات الكلي
كم بلا حارس · كم بحارس بلا نطاق · كم مهجور
قائمة المسارات الحساسة
أي مسار مكشوف (critical فوري)
```
سجّل كل شذوذ في `findings.py`.
