---
description: نفّذ جولة اختبار كاملة بالترتيب الصحيح
---

اقرأ سكيلي `hrms-live-testing` و `hrms-test-journeys`، ثم نفّذ الجولة بالترتيب الإلزامي:

## 1. Smoke
```bash
source .claude/hrms/scripts/env.sh && bash .claude/hrms/scripts/smoke.sh
```
أي فشل هنا يوقف الجولة — أبلغ فورا ولا تكمل.

## 2. الأمان أولا
```bash
bash .claude/hrms/scripts/rbac-probe.sh
```
ثم رحلات `SEC-01` إلى `SEC-05`.
**السبب**: لو الصلاحيات مكسورة، نتائج رحلات الأدوار غير موثوقة.

## 3. رحلات الأدوار
بالترتيب: Employee → BranchSupervisor → Manager → HR → Accountant → PRO → Owner.
لكل رحلة:
```bash
python3 .claude/hrms/scripts/testrun.py --show <ID>
```
نفّذ خطواتها **على الشركتين GUF و MUF**، والتقط الأدلة، ثم:
```bash
python3 .claude/hrms/scripts/testrun.py --result <ID> <pass|fail|partial> --note "..." --evidence "..."
```

## 4. المستندات وسلامة البيانات والتدقيق
رحلات DOC و DAT و AUD، ثم فحوص سكيل `hrms-data-integrity`.

## 5. الواجهة
رحلات UX-01 إلى UX-03.

## قواعد أثناء الجولة
- **لا تصلح شيئا** — سجّل واستمر. الإصلاح يفسد خط الأساس.
- `pass` على شركة واحدة = سجّلها `partial`.
- تحقق من **الأثر** لا من حالة الطلب.
- كل فشل يحتاج خطوات قابلة للتكرار.

## في النهاية
```bash
python3 .claude/hrms/scripts/testrun.py --report
```
اعرض: ما نجح · ما فشل مع الأدلة · الـ blockers · الترتيب المقترح للإصلاح.
