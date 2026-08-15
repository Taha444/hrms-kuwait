---
description: جهّز بيئة الاختبار الحي وتحقق من الجاهزية
---

اقرأ سكيل `hrms-live-testing` ثم:

1. **اسأل الأسئلة الأربعة** إن لم تكن الإجابات معروفة: الرابط والبيئة · حسابات كل دور · نوع البيانات · الأداة المتاحة.

2. **افحص الأدوات المتاحة**: هل Playwright مثبت؟ متصفح MCP متصل؟ curl و jq موجودان؟ اعرض ما وجدته واقترح الأنسب.

3. **جهّز ملف البيئة**:
```bash
cp .claude/hrms/scripts/env.example.sh .claude/hrms/scripts/env.sh
```
اطلب من المستخدم ملأه بنفسه. **لا تكتب أي كلمة سر في أي ملف أو رسالة.**
تأكد أن `.claude/hrms/scripts/env.sh` مضاف إلى `.gitignore`.

4. **حذّر إن كانت البيئة هي نسخة العميل**: عمليات الكتابة ممنوعة، وستُنفَّذ القراءة والفحص الأمني فقط.

5. **ابدأ الجولة**:
```bash
python3 .claude/hrms/scripts/testrun.py --new "<وصف>" --build <v> --commit <sha> --env <بيئة>
```

6. شغّل الـ Smoke:
```bash
source .claude/hrms/scripts/env.sh && bash .claude/hrms/scripts/smoke.sh
```

اعرض النتيجة وحدد: هل نكمل أم يوجد ما يمنع؟
