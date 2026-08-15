---
description: تحقق من طبقة المخرجات ودورة حياة المستند
---

اقرأ سكيل `hrms-document-output` ومرجعه `references/document-catalog.md`، ثم:

1. **عدّ الملفات فعليا**: كم ملف Layout؟ كم تعريف مستند؟ كم تقرير؟ (المستهدف 9 / 25 / 6 / 2) → `STR-01`, `STR-02`
2. تأكد أن `document_artifact` و `request_output` و `government_artifact` موجودة بالحقول المذكورة في السكيل. اذكر أي حقل ناقص بالاسم.
3. تأكد من القيد الفريد: **Primary output نشط واحد** لكل طلب/إصدار.
4. افحص دورة حياة المستند: هل السبع حالات + الخمس الاستثنائية موجودة؟ هل مستقلة عن حالة الطلب؟
5. اختبر `AC-12` / `RW-15` / `DOC-18`: احقن فشلا في مولّد PDF وتأكد أن الطلب **لا** ينتقل إلى COMPLETED/DELIVERED/FILED.
6. `DOC-04` / `DOC-20` — تحقق من `supersedes_document_id` وثبات hash النسخة القديمة.
7. `DOC-06` — اضغط Generate مرتين بنفس `request_id + template_version + snapshot_hash` → Artifact واحد.
8. `DOC-11` — تأكد أن النظام **لا يولّد** إقامة/مدني/إذن عمل بشعار حكومي، وأن `government_artifact` يتطلب رفعا حقيقيا.
9. `DOC-12` — إخلاء طرف بجهة OPEN لا ينتج FINAL CLEARED.
10. `STR-06` — افحص مسار التوليد: server-side؟ allowlist للـ placeholders؟ بلا HTML/JS حر؟
11. `DOC-01` — تأكد أن الزر الأساسي بعد الاكتمال ينزّل المستند لا سجل الطلب.

حدّث `status.json`.
