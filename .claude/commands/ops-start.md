---
description: ابدأ جلسة التنظيف — اقرأ الحماية واعرف الحالة
---

**اقرأ سكيل `hrms-guardrails` كاملا قبل أي شيء.** هذا ليس اختياريا.

```bash
python3 .claude/hrms/scripts/ops.py --init      # أول مرة
python3 .claude/hrms/scripts/ops.py --guards
python3 .claude/hrms/scripts/ops.py --verify
python3 .claude/hrms/scripts/ops.py --uncovered
python3 .claude/hrms/scripts/ops.py --prio P0
```

اعرض:
1. **القواعد العشرون** التي يُمنع كسرها — لخّص أخطرها في سياق العمل الحالي
2. **السبعة تحقيقات** غير المحسومة — هذه أول شغل، قبل أي إصلاح
3. **المناطق غير المغطاة** — تُذكر صراحة كـ«لم تُختبر»
4. عدد بنود P0 المفتوحة
5. **الترتيب المقترح** ولماذا

**لا تبدأ إصلاحا في هذا الأمر.** اقرأ واعرض الحالة فقط.
