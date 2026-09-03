---
name: hrms-document-storage-lifecycle
description: تخزين المستندات المولّدة ودورة حياتها في Kuwait HRMS — نقلها لتخزين دائم يبقى بعد إعادة النشر، ربط توليد المستند بالـ Canonical WF→OD mapping، والأرشفة التلقائية مع الإصدارات. استخدم هذا السكيل عند أي عمل على توليد أو تخزين أو تنزيل أو أرشفة مستند، وعند أي بلاغ بمستند مفقود أو نوع مستند خاطئ.
---

# Package 1 — التخزين ودورة حياة المستند

## P1-01 — المستندات المولّدة تضيع بعد النشر (P0 BLOCKER)

### الدليل
`/api/health/deep` نفسه يعرض `storage: degraded`.
Request 12 → المستند المولّد يرجع **HTTP 410**: الملف مفقود رغم وجود سجله في قاعدة البيانات.

**ما زال يعمل:** المستندات المرفوعة (200) · العقد الحكومي الذي يُعاد render عند الطلب.
يعني المشكلة في **الملفات المولّدة المخزَّنة** تحديدا.

### المطلوب
```
Generate → permanent/object storage → DB record
→ downloadable permanently → survives redeploy/restart
→ version/archive lifecycle continues normally
```

يشمل كل نوع مولّد بلا استثناء:
`Salary Certificates · Experience/NOC · Leave Decisions · Payslips · EOS documents · Employment Decisions · وأي OD مولّد`

### ممنوع
> **لا يكفي عرض "Regenerate" للمستخدم كحل.**

إعادة التوليد تنتج مستندا **بختم زمني جديد وبيانات قد تكون تغيّرت** — وهذا ليس نفس المستند الذي صدر ووُقّع. المستند الرسمي أصل محفوظ، لا شيء يُعاد إنتاجه عند الطلب.

### التنفيذ
- تخزين كائني (S3 في البنية النهائية) — الحل الصحيح
- ابحث عن **كل** موضع يكتب مستندا مولّدا على القرص، لا مسارا واحدا
- **رحّل الموجود**: كل سجل في القاعدة له مقابل في التخزين
- التحقق:
```sql
SELECT id, template_code, storage_key, created_at FROM document_artifacts
WHERE storage_key IS NOT NULL ORDER BY created_at DESC;
```
قارن القائمة بمحتوى التخزين الفعلي، واحصر المفقود.
- **لا تحذف المسار القديم** قبل التحقق الكامل ونسخة احتياطية
- `/api/health/deep` يجب أن يرجع `storage: ok` بعد الإصلاح — وهذا أول دليل

### القبول
`DOD-11`: ولّد عدة مستندات رسمية → أعد النشر/التشغيل → **كل مستند ما زال قابلا للتنزيل**.

## P1-02 — WF→OD mapping من الـ Canonical Registry فقط (P0)

### الدليل
Request 12 كان Leave / `WF-001` لكنه ولّد `OD-005 — Employment Change Decision`.
الـ registry يحدد: `WF-001 → OD-011 Leave Approval`.

### تحقّق أولا — بند `V-A`
> **السجل المكتشف قديم نسبيا.** لا تفترض أن البناء الحالي ما زال يفعلها.

نفّذ عملية جديدة على البناء الحالي وافحص الـ OD الناتج.
- **ما زال يولّد OD غلط** → مشكلة قبل التسليم، ليست P2
- **يولّد الصحيح** → سجّلها verified واذكر أن الدليل تاريخي

### المطلوب
محرك التوليد يقرأ **canonical WF→OD mapping فقط** — لا mappings قديمة ولا generic fallback.

**افحص كل الـ canonical workflows، لا Leave وحدها.** اكتب جدول: WF → OD المتوقع → OD الفعلي، لكل مسار.

Fallback عام إلى OD افتراضي عند غياب mapping هو الجذر الأرجح — لو وُجد، **احذفه واجعل غياب الـ mapping خطأ صريحا** يمنع التوليد ويسمّي الـ WF.

## P1-03 — الأرشفة التلقائية

### الوضع
`ready_to_print` و `mark-printed` و `mark-filed` ما زالت موجودة رغم وجود Digital Archive + Document Lifecycle.

### المطلوب
المستند النهائي بعد اكتمال الاعتماد/التوقيع **يُحفظ تلقائيا** في مكانه:
```
Employee document → Employee Documents
Company document  → Company Archive
Branch document   → Branch Archive
```
مع Current + Previous Versions.

**الطباعة تصبح Action اختياري للمستخدم — لا شرطا لإتمام الـ workflow**، إلا لو قاعدة عمل أو قانونية تتطلب نسخة ورقية فعلا.

راجع كل نوع مستند وحدد: هل الطباعة مطلوبة قانونا؟ لو لا، أزل الاشتراط واترك الزر.

## P1-04 — الإصدارات (قاعدة حماية)

> **هذا الجزء شغّال حاليا وممنوع يتكسر.**

```
النسخة الجديدة → Current
القديمة        → Previous Version، قابلة للعرض والتنزيل من History
```

**أي تغيير في التخزين أو الأرشفة يجب أن يحافظ على هذا السلوك.**
اختبره بعد كل تعديل في `P1-01` و `P1-03`:
```
ارفع v2 لمستند له v1 → v2 هي Current → v1 في History → v1 تُفتح وتُنزَّل
```

## القبول
`DOD-01` `DOD-03` `DOD-06` `DOD-11` — راجع سكيل `hrms-dod-verification`.
