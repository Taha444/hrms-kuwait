---
description: اختبر مسار التوقيع كاملا بتوليد توقيع ورفعه
---

اقرأ سكيل `hrms-file-upload-audit` — قسم مسار التوقيع.

**Staging فقط.** كل ملف يبدأ بـ `AUDIT_` ليسهل تنظيفه.

```bash
python3 .claude/hrms/scripts/make_signature.py -o /tmp/AUDIT_sig_v1.png
python3 .claude/hrms/scripts/make_signature.py -o /tmp/AUDIT_sig_v2.png --seed 7
```

نفّذ السيناريو التسعة في السكيل:
أول رفع مباشر · محاولة استبدال مباشر (يجب أن تُرفض) · طلب استبدال بسبب · رفض HR · موافقة HR · سجل التاريخ · صلاحية PRO · الرابط المباشر.

**انتبه للخطوة 7**: `/api/me/signature/history` — بلاغ موثق أنه يرجع فارغا رغم وجود الإصدارات. تحقق منه تحديدا.

ثم افحص قواعد التوقيع السبعة، وبالذات:
- المستند المُصدَر سابقا يحتفظ بنسخة التوقيع وقت إصداره
- التوقيع يُضاف عند Approval فقط لا عند Reject أو Needs Info أو المشاهدة

## التنظيف
```sql
SELECT id, storage_key FROM document_artifacts WHERE storage_key LIKE '%AUDIT_%';
```
اعرض القائمة **واطلب الإذن** قبل الحذف.
