# HRMS Claude Code Kit — V2.2

## التركيب
انسخ محتوى هذا المجلد إلى جذر مشروع HRMS:

```bash
cp -r .claude CLAUDE.md /path/to/hrms-project/
cd /path/to/hrms-project
python3 .claude/hrms/scripts/check.py --init
```

## البنية
```
CLAUDE.md                          المرجع الحاكم — يُقرأ تلقائيا كل جلسة
.claude/
  skills/                          8 سكيلز مقسّمة حسب طبقة المواصفة
    hrms-workflow-engine/          §3 §7 §8 §10
    hrms-request-catalog/          §5 §6 §12  (+ مرجع WF-001..029)
    hrms-permissions-sod/          §4.5 §11
    hrms-document-output/          §19-§24 §28 §29  (+ كتالوج OD/RPT/SYS)
    hrms-document-templates/       §22 §25-§27 §31
    hrms-ui-actions/               §9 §29
    hrms-acceptance-verification/  §13 §14 §30
    hrms-legacy-migration/         §24.5 §12
  commands/                        10 أوامر تحقق
  hrms/
    compliance.json                60 بندا مرجعيا (لا يُعدَّل)
    status.json                    الحالة الفعلية (يُحدَّث)
    scripts/check.py               تقرير الامتثال
    scripts/antipattern-scan.sh    فحص 11 نمطا ممنوعا
```

## سير العمل اليومي
```
/hrms-status        →  أين نحن؟
/hrms-next          →  نفّذ البند التالي
/hrms-review-pr     →  قبل الدمج
```

## أول جلسة مقترحة
1. `/hrms-status` — خط الأساس
2. `/hrms-verify-catalog` — كم نوعا فعلا؟
3. `/hrms-verify-permissions` — هل الصلاحية عامة؟
النتيجتان الأخيرتان تحددان حجم العمل الحقيقي قبل أي كود جديد.
