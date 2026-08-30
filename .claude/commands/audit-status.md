---
description: حالة المراجعة والنتائج
---

```bash
python3 .claude/hrms/scripts/findings.py
python3 .claude/hrms/scripts/findings.py --sev critical
python3 .claude/hrms/scripts/findings.py --roots
```

اعرض:
1. عدد النتائج بالخطورة والحالة
2. النتائج `open` المستوردة تلقائيا **التي لم تُؤكَّد بعد** — هذه أولوية، لأن غير المؤكَّد ليس نتيجة
3. الجذور المشتركة وكم بندا يغلق كل جذر
4. أي مرحلة من السبع لم تُنفَّذ بعد
5. الحكم الحالي: صالح للتسليم أم لا ولماذا
