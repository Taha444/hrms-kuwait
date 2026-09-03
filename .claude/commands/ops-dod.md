---
description: نفّذ سيناريوهات التحقق النهائي
---

اقرأ سكيل `hrms-dod-verification`.

```bash
python3 .claude/hrms/scripts/ops.py --dod
python3 .claude/hrms/scripts/ops.py --dod-show DOD-05
```

**Staging أو بيانات Demo فقط** — هذه سيناريوهات كتابة كاملة.

## ملاحظات على التنفيذ
- **`DOD-11`** يحتاج **إعادة نشر فعلية**، لا إعادة تشغيل عملية. هو الاختبار الوحيد الذي يثبت `P1-01`
- **`DOD-12`** يدوي بطبيعته: اضغط كل رقم في كل Dashboard وعُدّ الصفوف. لا تختصره
- **`DOD-05`** أطول سيناريو — نفّذه بثلاثة حسابات: PRO والموظف وHR
- **`DOD-02`** لا يُنفَّذ قبل تثبيت قاعدة العمل: متى يحتاج السفر مرحلة PRO؟

## لكل سيناريو
اذكر: ما نفّذته خطوة بخطوة · ما توقعته · ما حدث · الدليل
```bash
python3 .claude/hrms/scripts/ops.py --dod-set DOD-11 pass --note "6 مستندات · redeploy فعلي · كلها نزلت"
python3 .claude/hrms/scripts/ops.py --dod-set DOD-12 fail --note "Operations Center 24 والقائمة 8"
```

## عند الفشل
سجّل الفشل، وحلّل: هل الإصلاح جزئي؟ أم كسره تغيير آخر؟ أم البند لم يُصلح أصلا؟
