---
description: نفّذ مسار التجديد كاملا بالترتيب الصحيح
---

اقرأ سكيل `hrms-renewal-lifecycle` أولا، ثم:
```bash
python3 .claude/hrms/scripts/renewal.py --init    # أول مرة
python3 .claude/hrms/scripts/renewal.py --flow
python3 .claude/hrms/scripts/renewal.py --pending
```

نفّذ بهذا الترتيب — **لا تقفز**، كل مرحلة تعتمد على ما قبلها:

## المرحلة 1 — من تنبيه إلى معاملة
سكيل `hrms-renewal-alert-to-case` · البنود `RNW-01` إلى `RNW-04`
هذه أولا لأن **لا شيء في المسار يعمل بدون وجود معاملة أصلا**.
اختبر: البطاقة تفتح · زر البدء يعمل · idempotent · الشاشات متطابقة.

## المرحلة 2 — العقد ودورة التوقيع
سكيل `hrms-renewal-contract-signing` · البنود `RNW-05` إلى `RNW-11`
التوليد → المراجعة → الإرسال للموظف → توقيعه ورفعه → عودته للمندوب → الحكومي.

## المرحلة 3 — OCR والتحقق
سكيل `hrms-renewal-ocr-verification` · البنود `RNW-12` و `RNW-13`

## المرحلة 4 — نشر الأثر والإغلاق
سكيل `hrms-renewal-propagation` · البنود `RNW-14` إلى `RNW-21`

## المرحلة 5 — الاختبار الشامل
سكيل `hrms-renewal-testing` · البنود `RNW-22` إلى `RNW-24`

## بعد كل مرحلة
- شغّل اختبارها من سكيل الاختبار **قبل الانتقال للتالية**
- سجّل البنود بدليل:
```bash
python3 .claude/hrms/scripts/renewal.py --set RNW-0X done --note "<commit / اختبار / مخرَج>"
```
- اعرض التقدم: `--pending`

**لا تنتقل لمرحلة والسابقة فيها blocker مفتوح.**
