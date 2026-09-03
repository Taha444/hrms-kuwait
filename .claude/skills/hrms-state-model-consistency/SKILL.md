---
name: hrms-state-model-consistency
description: اتساق نموذج الحالات في Kuwait HRMS — لا حالة ميتة أو بلا مخرج، والتفريق بين الإقرار والاعتماد حيث المعنى مختلف فعلا. استخدم هذا السكيل عند مراجعة آلة الحالات أو الانتقالات أو أنواع الخطوات.
---

# Package 11 — نموذج الحالات

## P11-34 — كل حالة لها دخول وخروج منطقي

راجع الـ workflows بحيث **لا يوجد**:
```
dead state
state بدون allowed action
final state مع tasks مفتوحة
cancelled state مع approvals معلقة
returned request يبدأ workflow جديد بدل resume
completed workflow بدون timeline closure
```

### المنهج
لكل حالة في كل workflow، اكتب:
```
شروط الدخول · من يملك كل مخرج · المخارج المتاحة
هل يوجد سيناريو تصبح فيه بلا مخرج؟
```

**الحالة الموثقة `pending_hr_verify` في التجديد (`P4-17`) نموذج لهذا العطل** — ابحث عن نظائرها في كل مسار، لا في التجديد وحده.

### فحوص قاعدة البيانات
```sql
-- حالات نهائية بمهام مفتوحة
SELECT r.id, r.status, COUNT(t.id) FROM requests r
JOIN tasks t ON t.request_id=r.id AND t.status='open'
WHERE r.status IN ('completed','rejected','cancelled') GROUP BY 1,2;

-- طلبات في حالة بلا معيّن
SELECT id, status FROM requests
WHERE status NOT IN ('completed','rejected','cancelled','draft')
  AND current_assignee_id IS NULL;

-- طلبات مُرجَعة أنشأت سجلا جديدا بدل الاستئناف
SELECT parent_request_id, COUNT(*) FROM requests
WHERE parent_request_id IS NOT NULL GROUP BY 1 HAVING COUNT(*)>1;
```

## P11-35 — الإقرار ليس اعتمادا

### الوضع
نموذج الحالات عنده `ACKNOWLEDGEMENT · EXECUTION · AUTOMATION · NOTIFICATION`، لكن workflows كثيرة تستخدم `DECISION/VALIDATION` فقط.

### التحذير المهم
> **لا تعيد تصميم كل النظام لمجرد استخدام كل enum.**
> راجع فقط الحالات التي المعنى فيها **فعلا غلط**.

المثال الصريح:
```
"الموظف يقر أنه استلم/اطلع على إنذار"
  →  Acknowledgement
  ✗  ليست Approval للإنذار
```

الفرق قانوني لا تقني: **إقرار الاستلام لا يعني الموافقة على الواقعة ولا التنازل عن حق الرد أو التظلم.** لو النظام يسجّلها كـ Approval، فهو يوثّق شيئا لم يحدث.

### القاعدة
> **لو الـ implementation الحالي يؤدي المعنى القانوني الصحيح بالفعل، لا تغيّره لمجرد اسم enum.**

المعيار: **ما الذي يوثّقه السجل؟** لا: أي enum مستخدم.

راجع الحالات ذات الأثر القانوني أولا: الإنذار · الخصم · نهاية الخدمة · إخلاء الطرف · التظلم.

## القبول
`DOD-07` — والمعيار: workflow منتهٍ لا يترك أثرا معلقا.
