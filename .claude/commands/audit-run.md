---
description: نفّذ المراجعة الشاملة بالمراحل السبع
---

اقرأ سكيل `hrms-backend-audit-method` ونفّذ بالترتيب. **لا تصلح شيئا أثناء المراجعة** — سجّل واستمر.

## المرحلة 1 — جرد سطح الـ API
سكيل `hrms-api-surface-inventory`
```bash
bash .claude/hrms/scripts/discover.sh .
```
شغّل أمر الستاك للحصول على القائمة الدقيقة، واكتبها في `.claude/hrms/audit/endpoints.json`.
اعرض: العدد · كم بلا حارس · كم مهجور.

## المرحلة 2 — الصلاحيات والعزل
سكيل `hrms-authz-matrix-audit`
```bash
source .claude/hrms/scripts/env.sh
python3 .claude/hrms/scripts/probe_matrix.py --all
python3 .claude/hrms/scripts/findings.py --import-probe
```
**كل نتيجة مستوردة تحتاج تأكيدا يدويا** — الأداة تشير ولا تحكم.
أكّد بـ `--set <ID> confirmed` أو استبعد بـ `false_positive`.
ثم نفّذ الفحوص اليدوية في السكيل: IDOR بالتفصيل · العزل · تجاوز المراحل · المصادقة.

## المرحلة 3 — التحقق من المدخلات
سكيل `hrms-input-validation-audit` — على Staging فقط.

## المرحلة 4 — طبقة البيانات
سكيل `hrms-data-layer-audit` — قراءة فقط.

## المرحلة 5 — سلامة المسارات
سكيل `hrms-workflow-integrity-audit` — ركّز على **الأثر الفعلي** لا الحالة.

## المرحلة 6 — الملفات والتوقيع
سكيل `hrms-file-upload-audit`
```bash
python3 .claude/hrms/scripts/make_signature.py -o /tmp/AUDIT_sig_v1.png
python3 .claude/hrms/scripts/make_signature.py -o /tmp/AUDIT_sig_v2.png --seed 7
```
نفّذ سيناريو التوقيع التسعة ومسار مستندات التجديد.

## المرحلة 7 — الأخطاء والتدقيق
سكيل `hrms-error-observability-audit`

## في كل مرحلة
- على **GUF و MUF**
- سجّل كل شذوذ فورا بدليل
- الأدلة في `.claude/hrms/audit/evidence/`

## في النهاية
```bash
python3 .claude/hrms/scripts/findings.py --roots
python3 .claude/hrms/scripts/findings.py --report > audit-report.md
```
