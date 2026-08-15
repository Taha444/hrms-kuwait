---
description: مراجعة عنقود واحد بالتفصيل — مرّر اسم العنقود كوسيط
---

العنقود المطلوب: $ARGUMENTS
(المتاح: ACCESS · WF · CAT · ATT · PAY · EOS · PRO · DOC · SIG · TASK · AUDIT · UX · DATA · API · OPS)

```bash
python3 .claude/hrms/scripts/defects.py --cluster $ARGUMENTS
```

اقرأ السكيل المختص بهذا العنقود:
- ACCESS → `hrms-identity-access`
- ATT / PAY / EOS → `hrms-attendance-payroll`
- PRO → `hrms-pro-residency`
- TASK / AUDIT → `hrms-tasks-notifications`
- UX / DATA / OPS → `hrms-release-readiness`
- WF / CAT / DOC / SIG / API → استخدم `hrms-defect-triage` مع سكيلز مواصفة V2.2 إن كانت مثبتة

ثم لكل بند في العنقود:
1. اعرض تفاصيله: `--show <ID>`
2. **افحص الكود الفعلي** — الملف والدالة المسؤولة، لا تخمين
3. احكم: مؤكد مكسور / ثبت سليم / يحتاج اختبارا يدويا (واذكر خطواته بالضبط)
4. حدد الجذر المشترك مع بنود أخرى

اختم بـ:
- جدول الحالة لكل بند في العنقود
- ترتيب الإصلاح داخل العنقود حسب الاعتماد التقني لا حسب الرقم
- ما الذي يعتمد على عنقود آخر ويجب انتظاره

حدّث الحالات في السجل بما تحققت منه فقط.
