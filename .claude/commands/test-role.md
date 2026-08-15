---
description: اختبر دورا واحدا بكل رحلاته — مرّر اسم الدور
---

الدور: $ARGUMENTS
(Employee · BranchSupervisor · Manager · HR · Accountant · PRO · Owner · SuperAdmin)

```bash
python3 .claude/hrms/scripts/testrun.py --list --role $ARGUMENTS
```

اقرأ سكيل `hrms-test-journeys`، ثم لكل رحلة:
1. `--show <ID>` لقراءة الخطوات والمتوقع
2. نفّذها فعليا على **GUF ثم MUF**
3. اختبر بالطبقات الثلاث: الواجهة → الـ API → الأثر
4. سجّل النتيجة بدليل

انتبه للرحلات المصنّفة `[B]` — أي فشل فيها = NO-GO.

اختم بملخص: ما يعمل · ما لا يعمل · أي فرق بين الشركتين · ما يحتاج بيانات أو قرارا من العميل.
