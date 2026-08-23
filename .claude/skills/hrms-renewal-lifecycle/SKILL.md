---
name: hrms-renewal-lifecycle
description: دورة حياة معاملة تجديد الإقامة الكاملة في Kuwait HRMS — من اكتشاف قرب الانتهاء إلى إغلاق المعاملة، عبر 15 حالة وثلاث نسخ للعقد الحكومي وأربعة فاعلين. استخدم هذا السكيل إلزاميا عند أي عمل على تجديد الإقامة أو معاملات المندوب أو شاشة Renewals أو مركز العمليات، وقبل كتابة أي كود يمس renewal_case. استخدمه أولا قبل بقية سكيلز التجديد لأنه يحدد الإطار الذي تعمل داخله.
---

# Residency Renewal — دورة الحياة الكاملة

## المبدأ الحاكم
> نحن لا نبني تذكيرا بانتهاء الإقامة ولا قائمة مراجعة للمندوب.
> نبني **Case Management Workflow كامل**: قرب الانتهاء → المندوب → الموظف → المندوب والإجراءات الحكومية → المستندات النهائية و OCR → تحديث ملف الموظف → إغلاق.

معيار النجاح النهائي: **لما تفتح معاملة مكتملة، تعرف القصة كلها من أول التنبيه لحد المستند النهائي.**

## المرجع
`.claude/hrms/renewal/workflow.json` — آلة الحالات و 24 معيار قبول.
**اقرأه قبل أي تنفيذ**، وشغّل:
```bash
python3 .claude/hrms/scripts/renewal.py --states     # آلة الحالات
python3 .claude/hrms/scripts/renewal.py --show RENEWAL_STARTED
python3 .claude/hrms/scripts/renewal.py --accept     # معايير القبول
```

## المسار الكامل
```
Expiry Detection            [نظام]    ← تنبيه محسوب، ليس معاملة
  → PRO starts Renewal      [مندوب]   ← هنا يولد case_no
  → Generate Gov Contract   [مندوب]
  → PRO reviews data        [مندوب]
  → Send to Employee        [مندوب]
  → Employee views/prints   [موظف]
  → Employee signs by hand  [موظف — خارج النظام]
  → Employee uploads copy   [موظف]
  → Returned to PRO         [مندوب]
  → Owner/Signatory signs   [خارج النظام]
  → Government Processing   [مندوب]
  → Final package upload    [مندوب]
  → OCR                     [نظام]
  → Data confirmed          [مندوب]
  → Employee Docs updated   [نظام]
  → New expiry applied      [نظام]
  → Final Verification      [HR]
  → Alerts/tasks closed     [نظام]
  → Employee notified       [نظام]
  → COMPLETED
```

## الفارق الجوهري: تنبيه ≠ معاملة
| | تنبيه انتهاء | معاملة تجديد |
|---|---|---|
| المصدر | محسوب من `expiry_date` | سجل `renewal_case` حقيقي |
| له رقم؟ | لا | نعم، `case_no` |
| قابل للتحرير؟ | لا | نعم |
| يختفي متى؟ | عند بدء المعاملة أو تجاوز التاريخ | عند الإغلاق |

**هذا هو أصل العطل الحالي:** البطاقة في مجموعة «تستحق التجديد ولم يُفتح لها ملف» هي تنبيه بلا `case_id`، فالضغط عليها لا يجد شيئا يفتحه. التفاصيل في سكيل `hrms-renewal-alert-to-case`.

## العقد: ثلاث نسخ لا نسخة واحدة
| النسخة | النوع | من يرفعها | متى |
|---|---|---|---|
| 1 | `GOV_CONTRACT_GENERATED` | النظام | بعد التوليد — بلا توقيع |
| 2 | `GOV_CONTRACT_EMPLOYEE_SIGNED` | الموظف | بعد الطباعة والتوقيع اليدوي |
| 3 | `GOV_CONTRACT_FINAL` | المندوب | بعد توقيع الطرفين |

**الثلاثة محفوظة ومرتبطة بنفس المعاملة.** النسخة 2 لا تُعتبر نهائية، والنسخة 3 لا تستبدل ما قبلها.

## قاعدة العقد في التجديد
```
New Hire         → Company Employment Contract + Government Contract
Residency Renewal → Government Contract فقط
```
**لا يُنشأ عقد عمل شركة جديد في كل تجديد.** لو الكود الحالي يفعل ذلك، هذا عطل.

## الفاعلون ومسؤولياتهم
| الفاعل | ما يفعله | ما لا يفعله |
|---|---|---|
| النظام | يكتشف · يولّد · يقرأ OCR · ينشر الأثر · يغلق التنبيهات | لا يحدّث بيانات بلا تأكيد بشري |
| المندوب | يبدأ · يراجع · يرسل · يستلم · ينفّذ حكوميا · يرفع النهائي · يؤكد البيانات | لا يرى الرواتب · لا يقرر إجازة · لا يغلق بلا اكتمال |
| الموظف | يفتح · ينزّل · يطبع · يوقّع يدويا · يرفع | لا يوافق ولا يعتمد — إجراؤه رفع لا قرار |
| HR | المراجعة النهائية | لا يعيد تنفيذ عمل المندوب |

## قواعد لا تُكسر
1. **المعاملة لا تُغلق بضغطة «تم»** — الإغلاق مشروط بفحص اكتمال يسمّي الناقص.
2. **OCR لا يعمل تحديثا صامتا** — القيم تُعرض وتُؤكَّد قبل تطبيقها.
3. **النسخ القديمة لا تُحذف** — تتحول History وتبقى قابلة للتنزيل.
4. **تاريخ الانتهاء الجديد يُطبَّق في كل مكان دفعة واحدة** — لا شاشة ترى القديم وأخرى الجديد.
5. **النظام لا يولّد مستندا حكوميا بشعار حكومي** — يحفظ الملف الحقيقي المرفوع.
6. **مهمة واحدة نشطة لكل إقامة** — تشغيل الفحص اليومي مرتين لا ينشئ تكرارا.
7. **بعد الإغلاق: الموظف يتلقى إشعارا لا مهمة** — لأنه لم يعد مطلوبا منه شيء.

## Timeline الإلزامي
كل حدث يسجّل: `Actor · Role · Timestamp · Employee · Company · Renewal ID · المرجع/المستند المرتبط`.

الأحداث المطلوبة كاملة:
```
Expiry Detected → Renewal Started by PRO → Government Contract Generated
→ Contract Reviewed by PRO → Sent to Employee for Signature
→ Employee Downloaded/Viewed → Employee Uploaded Signed Contract
→ Returned to PRO → Government Processing Started
→ Final Government Contract Uploaded → New Work Permit Uploaded
→ Other Final Documents Uploaded → OCR Processed
→ Extracted Data Reviewed/Confirmed → Employee Documents Updated
→ New Expiry Date Applied → Final Verification → Employee Notified
→ Renewal Completed
```

## ترتيب البناء
لا تبنِ كل شيء دفعة واحدة. الترتيب بالاعتماد:
```
1. alert-to-case      ← بدونه لا توجد معاملة أصلا (العطل الحالي)
2. contract-signing   ← قلب المسار
3. ocr-verification   ← بعد وجود مستندات نهائية
4. propagation        ← بعد وجود بيانات مؤكدة
5. testing            ← بعد كل مرحلة، لا في النهاية
```
شغّل `python3 .claude/hrms/scripts/renewal.py --next` لمعرفة المرحلة التالية.
