---
name: hrms-dod-verification
description: تعريف الإنجاز والتحقق النهائي في Kuwait HRMS — 12 سيناريو E2E إلزامي، وقاعدة أن endpoint 200 ليس إثباتا، والتجربة النهائية المطلوبة للمستخدم. استخدم هذا السكيل قبل تعليم أي بند مُنجزا، وعند التخطيط للـ Retest، وعند سؤال هل الجولة اكتملت.
---

# تعريف الإنجاز والتحقق النهائي

## القاعدة الحاكمة
> **لا تعتبر أي بند Fixed لمجرد:**
> ```
> endpoint = 200
> button works
> record saved
> ```
> **المطلوب E2E operational verification.**

الفرق: `200` يعني أن الطلب مرّ. الـ E2E يعني أن **الأثر التشغيلي وقع، والمستند بقي، والمهام أُغلقت، والأرقام تطابقت**.

## السيناريوهات الاثنا عشر

```bash
python3 .claude/hrms/scripts/ops.py --dod
python3 .claude/hrms/scripts/ops.py --dod-show DOD-05
```

| # | السيناريو | المسار المطلوب إثباته |
|---|---|---|
| `DOD-01` | Normal Leave | Submit → correct approvers → correct WF → **correct OD** → signature حسب السياسة → **permanent download** → archive → tasks closed → notification correct |
| `DOD-02` | Travel Leave | Travel clearly selected → correct routing → PRO/government stage **حسب Business Rule فقط** → no ambiguity |
| `DOD-03` | Salary Certificate | **خيار واحد فقط** → approval chain الصحيحة → correct document → signatory policy → permanent download → archive |
| `DOD-04` | Signature Replacement | reason required → pending → **old remains active** → HR approve/reject → correct version/history/audit |
| `DOD-05` | Residency Renewal | expiry → **one task** → contract → employee signature → government processing → final docs → **OCR success OR manual fallback** → gov data → HR verification → completed → **new expiry everywhere** → old tasks/reminders closed |
| `DOD-06` | Document Renewal | old current → replacement → new current → old previous version → **expiry engine watches new only** |
| `DOD-07` | Tasks/Notifications | actionable only in count → **digest doesn't inflate** → completed/cancelled leaves no stale action |
| `DOD-08` | Cross-company PRO | switch GUF/MUF → every selected-company counter/list consistent → global items **clearly labeled** |
| `DOD-09` | Archived Employee | cannot submit → no attendance action → no recurring work notifications → retention per policy only |
| `DOD-10` | Exit/EOS | **one connected case** from resignation/termination through settlement/clearance/archive/access closure |
| `DOD-11` | Storage | generate several official documents → **redeploy/restart** → every document remains downloadable |
| `DOD-12` | Counters | **every** Dashboard/Card number manually reconciled with rows opened from it |

### ملاحظات على التنفيذ
- `DOD-11` يحتاج **إعادة نشر فعلية** لا إعادة تشغيل عملية. هذا هو الاختبار الوحيد الذي يثبت `P1-01`.
- `DOD-12` يدوي بطبيعته: اضغط كل رقم وعُدّ الصفوف. لا تختصره.
- `DOD-05` أطول سيناريو ويغطي Package 4 كاملة — نفّذه بثلاثة حسابات: PRO والموظف وHR.
- `DOD-02` لا يُنفَّذ قبل تثبيت قاعدة العمل: متى يحتاج السفر مرحلة PRO؟

## التجربة النهائية المطلوبة للمستخدم
المعيار ليس «الأعطال أُصلحت» بل **«النظام يُحس كـ Process واحد مترابط»**:

```
قدّم Request     →  خيار واحد صحيح → form منطقي → approvals صحيحة
                   → document صحيح → signature صحيحة → archive
                   → tasks close → notification → complete

PRO جدّد إقامة   →  task واحدة → renewal واحدة → contract → employee signature
                   → government processing → final docs → OCR/manual confirmation
                   → HR verify → new expiry → archive/versioning
                   → old alerts close → complete

Document انتهت   →  reminder واحدة → renewal/replace → new Current
                   → old History → reminder closes

موظف خرج         →  resignation/termination → EOS → clearance → settlement
                   → documents → access closed → archive → no future tasks/digests
```

وفي الشاشات:
```
Dashboard      →  الأرقام تطابق القوائم فعلا
Tasks          →  فقط ما هو مطلوب منه
Notifications  →  معلومات، لا backlog مزيف من "مهام"
تنزيل مستند    →  ينزل حتى بعد redeploy
معلومة معروفة  →  لا تُطلب مرة ثانية بلا داعٍ
OCR فشل        →  يكمل يدويا بدل ما العملية تقف
توقيع إلكتروني →  لا Print/Sign/Scan بلا سبب
```

## قبل إعلان اكتمال الجولة
```
[ ] كل بند P0 مغلق بدليل E2E
[ ] السيناريوهات الاثنا عشر نُفِّذت على البناء الحالي
[ ] السبعة تحقيقات (V-A..V-G) حُسمت — مؤكدة أو مستبعدة بدليل
[ ] لا قاعدة من العشرين انكسرت — أعد اختبار المناطق التي مسستها
[ ] `/api/health/deep` يرجع storage: ok
[ ] المناطق غير المغطاة مذكورة صراحة كـ"لم تُختبر" لا كـ"سليمة"
```

## المناطق التي لا تُعلَن سليمة
```
Payroll · Attendance · Onboarding · EOS case lifecycle · Templates Management
Users/Permissions · Impersonation · Audit Log
HR UI · Manager UI · Accountant UI · Branch Supervisor UI · Owner UI
```
> **الإصلاحات الحالية ليست إثباتا أن هذه سليمة.** Retest منفصل بعد توفير حسابات QA.

**وبالذات Impersonation** — Finding سابق بخطورة عالية بلا دليل إصلاح. لا يُعتبر ناجحا لمجرد أن الدور غير متاح.

## التسجيل
```bash
python3 .claude/hrms/scripts/ops.py --set P1-01 done --note "commit abc / DOD-11 نُفِّذ بإعادة نشر فعلية"
python3 .claude/hrms/scripts/ops.py --dod-set DOD-11 pass --note "6 مستندات · redeploy · كلها نزلت"
```
السكريبت **يرفض** الإغلاق بلا دليل.
