---
description: مراجعة الصلاحيات والعزل وحدها
---

اقرأ سكيل `hrms-authz-matrix-audit`.

```bash
source .claude/hrms/scripts/env.sh
python3 .claude/hrms/scripts/probe_matrix.py --read-only
python3 .claude/hrms/scripts/probe_matrix.py --idor
python3 .claude/hrms/scripts/probe_matrix.py --fields
```

ثم يدويا — الأهم أن الأداة لا تكشفه:
1. **IDOR بالتفصيل**: لكل مسار يقبل معرّفا، جرّب سجلا مملوكا وسجلا لزميل وسجلا من الشركة الأخرى ومعرّفا غير موجود
2. **العزل**: بدّل `company_id` في جسم الطلب — هل يُحترم أم يُتجاهل؟ الصحيح: يُتجاهل
3. **الطبقات الثلاث**: UI ثم API ثم **Storage endpoint** — الأخيرة أكثر ما يُنسى
4. **تجاوز المراحل**: غير المعيّن بالرابط المباشر · stale task · اعتماد ذاتي · مرحلتان متتاليتان لنفس الشخص
5. **المصادقة**: الحسابات التجريبية · Rate limit · المستخدم المعطّل · 2FA · التوكن

لكل `200` غير متوقع: **افحص الجسم** — 200 بقائمة فارغة قد يكون سلوكا مقبولا، و200 ببيانات ثغرة.

سجّل كل تأكيد بـ `--sev critical` مع `--repro` كاملا.
