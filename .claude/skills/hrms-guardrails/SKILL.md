---
name: hrms-guardrails
description: القواعد المتفق عليها التي يُمنع كسرها في Kuwait HRMS، والبنود التي يُمنع إصلاحها بافتراض قبل التحقق، والمناطق التي لم تُغطَّ بالمراجعة فلا تُعتبر سليمة. اقرأ هذا السكيل إلزاميا في بداية أي جلسة عمل وقبل أي إصلاح، مهما بدا البند بسيطا. استخدمه أيضا عند أي شك في أن سلوكا ما عطل أم قرار مقصود.
---

# قواعد الحماية — اقرأها قبل أي كود

هذا أول سكيل يُقرأ في كل جلسة. سببه: **جولة تنظيف تكسر قرارات متفق عليها أسوأ من ألا تحدث.**

## 1. عشرون قاعدة يُمنع كسرها
هذه **قرارات مقصودة**، وليست أعطالا. أي «إصلاح» يخالفها انحدار لا تحسين:

```
1.  Multi-company architecture مقصودة
2.  Owner portfolio / All Companies visibility مقصودة حسب الصلاحية
3.  PRO/Delegate مسند لـ GUF + MUF يجوز له العمل في الاثنين
4.  Secondary PRO assignment لا تدخل Payroll/EOS/financial counts
5.  PRO يرى البيانات الحكومية اللازمة — وليس Payroll ولا private HR data
6.  Employee leave-date privacy الحالية مقصودة
7.  Branch Supervisor salary/documents visibility مقبولة
8.  Manager Users/Permissions داخل شركته مقبولة
9.  Super Admin ليس مطلوبا منه رؤية كل requests
10. Government Links للـ PRO/Delegate فقط
11. Normal Leave لا يدخل PRO
12. Government official documents لا يصدرها النظام بدل الجهة
13. closure-check في Residency Renewal يظل mandatory
14. OCR low confidence لا يعمل silent authoritative update
15. Current/Previous Document Versions behavior الحالي يُحافظ عليه
16. 2FA behavior الحالي مقصود للأدوار المعتمدة
17. Auto Logout ~10 دقائق للأدوار الحساسة مقصود
18. Signature replacement: القديم يظل Active حتى الموافقة
19. First Login/password behavior للحسابات الحقيقية لا يُعاد تغييره
20. لا تغيير في Payroll/RBAC أثناء التنظيف إلا بـ Finding مثبت وموافق عليه
```

**قبل أي تعديل، اسأل: هل يمس واحدة من العشرين؟** لو نعم — توقّف واطلب موافقة صريحة.

### حالتان لافتتان
- **`closure-check` صحيح وممنوع إزالته** (`P4-17`). العطل ليس فيه، بل في أن الـ workflow سمح للمعاملة تصل حالة متقدمة بلا بيانات. **لا تعالج المشكلة بتعطيل الفحص.**
- **`Current/Previous Versions` شغّال** (`P1-04`). أي تغيير في التخزين أو الأرشيف **يجب أن يحافظ عليه**. اختبره بعد كل تعديل في تلك المنطقة.

## 2. سبعة بنود يُمنع إصلاحها بافتراض
هذه **تحقيقات لا إصلاحات**. الدليل الموجود تاريخي أو ناقص:

| البند | السؤال الذي يُجاب أولا |
|---|---|
| `V-A` WF→OD Mapping | السجل يثبت mismatch **تاريخي**. هل البناء **الحالي** ما زال يولّد OD غلط؟ اختبر E2E جديدة |
| `V-B` تكرار توليد العقد | 5 توليدات تاريخية. هل السلوك الحالي ما زال يسمح؟ |
| `V-C` Travel routing | تأكد من `travel_required=true` تحديدا. **true ولم يدخل WF-002 = عطل routing** · **false رغم بيانات السفر = عطل form/validation**. عطلان مختلفان تماما |
| `V-D` Authorized Signatories | `/api/signatories = []` — هل مجرد **إعداد شركة ناقص** أم فجوة تكامل؟ |
| `V-E` قنوات الإشعارات | هل WhatsApp/SMS/Email **موصولة فعلا**؟ لا تعتبرها عطلا قبل الإثبات |
| `V-F` REQSHIFT | إعداد ناقص أم workflow غير قابل للاستخدام؟ |
| `V-G` Archived Employee | بعد إصلاح الـ gating، تأكد أن **الـ backend POST نفسه يرفض** — لا الواجهة فقط |

**الحكم قبل التحقق يهدر يوما أو يكسر شيئا سليما.**

## 3. بيانات الاختبار ليست عطلا في المنتج
`P7-30` — لا تصلح بيانات اختبار مختلطة بتغيير منطق العمل.

أمثلة صنّفها **Data Cleanup فقط**: أسماء فروع/شركات مختلطة · departments/shifts فارغة · records قديمة.

**لكن:** لو نقص البيانات يجعل ميزة حقيقية مستحيلة، الواجهة تعرض **Setup Required مفهوم** بدل form مكسور:
```
لا توجد ورديات مُعرّفة — قم بتعريف الورديات أولا
```
موجّه للدور المناسب، لا رسالة خطأ عامة.

## 4. مناطق لم تُغطَّ — لا تُعتبر سليمة
المراجعة الحالية **لم تختبر** هذه حيا لعدم توفر حسابات أو بسبب 403:

```
Payroll · Attendance management · Onboarding · EOS case lifecycle
Templates Management · Users/Permissions · Impersonation · Audit Log
HR UI · Manager UI · Accountant UI · Branch Supervisor UI · Owner UI
```

> **الإصلاحات الحالية ليست إثباتا أن هذه المناطق سليمة.**

بعد توفير حسابات QA مناسبة، **Retest منفصل إلزامي قبل الإطلاق النهائي**.

**وبالذات Impersonation:** كان هناك Finding سابق بخطورة عالية — توكن انتحال جديد لمستخدم خامل يرجع 401 فورا بسبب وراثة نشاط قديم. **لا يوجد دليل أنه أُصلح.** لا تعتبره ناجحا لمجرد أن الدور غير متاح للاختبار الآن.

## 5. تعريف الإنجاز
```
endpoint = 200        ليس إنجازا
button works          ليس إنجازا
record saved          ليس إنجازا
```
**المطلوب E2E operational verification.** التفاصيل في سكيل `hrms-dod-verification` و12 سيناريو إلزامي.

## 6. قبل أي إصلاح — أربعة أسئلة
```
1. هل يمس واحدة من العشرين؟          → توقّف واطلب موافقة
2. هل هو من السبعة؟                  → تحقّق أولا، لا تصلح
3. هل هو بيانات اختبار أم منتج؟       → صنّف قبل التعديل
4. كيف سأثبت الإنجاز E2E؟             → حدّد قبل الكتابة
```

## الأداة
```bash
python3 .claude/hrms/scripts/ops.py --guards      # القواعد العشرون
python3 .claude/hrms/scripts/ops.py --verify      # السبعة
python3 .claude/hrms/scripts/ops.py --uncovered   # المناطق غير المغطاة
```
