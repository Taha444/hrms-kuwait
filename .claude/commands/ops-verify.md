---
description: احسم التحقيقات السبعة قبل أي إصلاح
---

```bash
python3 .claude/hrms/scripts/ops.py --verify
```

هذه **تحقيقات لا إصلاحات**. الدليل الموجود تاريخي أو ناقص، والحكم قبل التحقق يهدر يوما أو يكسر شيئا سليما.

لكل بند من السبعة:
1. اقرأ ملاحظته والسكيل المرتبط
2. **نفّذ فحصا على البناء الحالي** — لا تعتمد على أي تقرير
3. احسم بدليل:
```bash
python3 .claude/hrms/scripts/ops.py --verify-set V-C confirmed --note "travel_required=true ولم يدخل WF-002"
python3 .claude/hrms/scripts/ops.py --verify-set V-D setup_only --note "الجدول موجود وفارغ — إعداد شركة ناقص"
python3 .claude/hrms/scripts/ops.py --verify-set V-A not_reproducible --note "البناء الحالي ولّد OD-011 صحيحا"
```

انتبه خصيصا:
- **`V-C` Travel**: `true` ولم يدخل WF-002 = عطل routing · `false` رغم بيانات السفر = عطل form. **عطلان مختلفان تماما وإصلاحهما مختلف**
- **`V-D` Signatories**: إعداد ناقص أم فجوة تكامل؟ الحل مختلف كليا
- **`V-A` WF→OD**: الدليل تاريخي — لو البناء الحالي سليم، سجّلها ولا تعدّل

اختم بجدول: البند | ما فحصته | النتيجة | الإصلاح المطلوب (إن وُجد)
