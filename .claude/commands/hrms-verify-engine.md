---
description: تحقق من محرك المسارات مقابل بنود المواصفة
---

اقرأ سكيل `hrms-workflow-engine`، ثم افحص الكود فعليا (لا من الذاكرة) وأجب لكل بند بـ pass/fail/pending مع مسار الملف كدليل:

- **AC-06** — أثبت من الكود أن الخادم يمنع الأربعة: self-approval، double action، stale task، direct URL action. اعرض السطر المسؤول عن كل واحد.
- **AC-07 / RW-10** — تتبّع مسار NEEDS_INFO: هل يعود بنفس `request_id`؟ هل الـ Timeline محفوظ؟ هل يرجع لنفس المراجع؟
- **AC-08 / RW-18** — هل `policy_version` و `workflow_version` تُلتقط عند الإرسال وتُستخدم لاحقا؟
- **AC-09 / RW-09** — منطق تخطي الموافق المكرر: موجود؟ يحترم SoD؟
- **RW-08** — Claim/ONE_OF: هل الباقون يفقدون الـ action فعلا؟ اختبر التزامن.
- **RW-16** — تفويض منته: هل يُرفض؟ هل fallback/escalation يعملان؟
- **RW-17** — idempotency على كل transition، وليس على Complete فقط.
- **STR-05** — ابحث عن حدود مكتوبة في الكود بدل `policy_rule`.

ثم شغّل `bash .claude/hrms/scripts/antipattern-scan.sh .` وحلل نتائج AP-01، AP-03، AP-04، AP-05، AP-07.

اختم بتحديث الحالة: `python3 .claude/hrms/scripts/check.py --set <ID> <status> --note "<الدليل>"` لكل بند حسمته.
