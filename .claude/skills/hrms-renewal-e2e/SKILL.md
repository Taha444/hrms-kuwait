---
name: hrms-renewal-e2e
description: مسار تجديد الإقامة الكامل في Kuwait HRMS — إصلاح الحالة العالقة في pending_hr_verify، تنفيذ المسار المعتمد، جعل فشل OCR مسارا عاديا، منع تكرار توليد العقد، والتايملاين الكامل. استخدم هذا السكيل عند أي عمل على معاملة التجديد أو مراحلها أو العقد الحكومي أو الـ OCR.
---

# Package 4 — تجديد الإقامة من طرف إلى طرف

## P4-17 — الحالة العالقة (P0)

### الدليل
Renewal 1 وصلت `pending_hr_verify` بينما:
```
gov_reference_no = null · new_expiry_date = null · new_permit/residency number = null
closure-check can_close = false · OCR فشل confidence = 0.0
```

### التشخيص الصحيح — انتبه
> **المشكلة ليست في closure-check. الـ closure-check صحيح وممنوع إزالته.**

المشكلة أن **الـ workflow سمح للمعاملة تصل حالة متقدمة قبل استكمال البيانات**، وبعدها لا يملك المستخدم مسارا واضحا لإدخالها.

**قاعدة حماية 13:** `closure-check` يظل mandatory. أي «حل» يعطّله أو يتجاوزه مرفوض.

### الإصلاح — شقّان
**أ. المنع:** بوابة على الخادم تمنع الانتقال إلى `pending_hr_verify` قبل اكتمال البيانات الحكومية الإلزامية.

**ب. الإنقاذ:** المعاملات العالقة الآن لن تنقذها البوابة. لازم مسار خروج:
- السماح بإدخال بيانات الحكومة **من نفس المرحلة** عبر شاشة واضحة ومسموح بها (الأنظف)، **أو**
- إرجاع مضبوط بسبب مسجّل ثم استكمال ثم عودة

اعرض الخيارين واسأل قبل التنفيذ.

### احصر العالق
```sql
SELECT id, case_no, status, gov_reference_no, new_expiry_date, updated_at
FROM renewal_cases
WHERE status='pending_hr_verify'
  AND (gov_reference_no IS NULL OR new_expiry_date IS NULL);
```

## P4-20 — البيانات الحكومية قبل التحقق النهائي
الحقول التي يحتاجها `closure-check` تُدخل:
```
إما قبل الانتقال إلى pending_hr_verify
أو داخل نفس المرحلة من شاشة واضحة ومسموح بها
```
> **ممنوع transition يدخل المعاملة State لا يوجد منها طريق منطقي للأمام.**

راجع **كل** الانتقالات في المسار بهذا المعيار، لا هذا الانتقال وحده.

## P4-19 — فشل OCR مسار عادي
OCR له **ثلاث نتائج، كلها مسارات صالحة**:
```
High confidence  →  القيم مستخرجة → المستخدم يؤكد
Low confidence   →  القيم مميّزة بصريا → المستخدم يصحح/يؤكد
Failed           →  نموذج إدخال يدوي واضح → المستخدم يدخل القيم المطلوبة
```
> **OCR مساعد، وليس prerequisite يمنع المعاملة.**

**قاعدة حماية 14:** لا silent update لبيانات حساسة عند ثقة غير موثوقة.

الحالة الموثقة `confidence=0.0` مع معاملة عالقة تثبت أن الفشل يُعامل حاليا كحاجز. **الفشل يجب أن يفتح نموذج الإدخال اليدوي فورا، لا أن يوقف كل شيء.**

## P4-18 — المسار المعتمد كاملا
```
Expiry detected → ONE PRO task → Renewal Case Started
→ Government Contract generated → PRO reviews → Send to Employee
→ Employee views/downloads → Employee signs physically where required
→ Employee uploads signed copy into SAME renewal → PRO receives signed copy
→ company authorized signature / external government processing
→ Government processing details entered → Final Government Contract uploaded
→ New Work Permit uploaded → New Residency/final document uploaded
→ Civil ID if applicable → OCR → Review/Confirm/Correct extracted data
→ new expiry/document numbers confirmed → Employee Documents updated/versioned
→ HR Final Verification → Completed
→ old tasks/alerts closed → employee notification
→ all screens agree on new expiry
```

**ONE PRO task** — واحدة، مرتبط بـ `P2-05`.
**into SAME renewal** — النسخة الموقّعة تُربط بنفس المعاملة، ليست مستندا عشوائيا.

## P4-21 — تكرار توليد العقد
Renewal 1 timeline فيه **5 توليدات** (`...0001` → `...0005`).

**تحقّق أولا (بند `V-B`):** هل السلوك الحالي ما زال يسمح؟ الدليل تاريخي.

لو نعم، أحد خيارين:
- Generate مرة واحدة، ثم **Regenerate ينشئ version جديدة ويعمل supersede للقديمة**
- أو **تأكيد قبل إعادة التوليد**

> المستخدم لا ينتهي عنده 5 عقود "Current" لنفس المعاملة.

**الأول أفضل**: يحافظ على تاريخ التوليد ويترك نسخة واحدة نشطة — ومتسق مع سلوك الإصدارات في `P1-04`.

## P4-22 — التايملاين الكامل
19 حدثا على الأقل:
```
Expiry Detected · Renewal Started · Government Contract Generated
Sent to Employee · Employee Viewed/Downloaded · Employee Signed/Uploaded
Returned to PRO · Government Processing · Final Contract Uploaded
Work Permit Uploaded · Residency/Civil ID Uploaded · OCR Run
OCR Reviewed/Corrected · Government Data Confirmed · Employee Documents Updated
HR Verified · New Expiry Applied · Employee Notified · Completed
```
كل حدث بـ: `actor / role / timestamp / employee / company / renewal / document references`.

## القبول
`DOD-05` — والمعيار النهائي: **كل الشاشات تتفق على تاريخ الانتهاء الجديد.**
