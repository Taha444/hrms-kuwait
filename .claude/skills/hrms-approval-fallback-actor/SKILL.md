---
name: hrms-approval-fallback-actor
description: بديل الاعتماد عند غياب مسؤول الفرع في Kuwait HRMS، وعرض الفاعل الحقيقي في التايملاين. استخدم هذا السكيل عند العمل على مراحل الاعتماد أو التايملاين أو عند فرع بلا مسؤول أو عند تسمية مرحلة لا تطابق من نفّذها.
---

# Packages 8 و 36 — البديل والفاعل الحقيقي

## P8-31 — فروع بلا مسؤول

### الوضع
فروع فيها موظفون ولا مسؤول مسند، بينما الـ workflows تبدأ بـ `branch_supervisor`.
في سجل موجود، **Company Manager اعتمد كـ fallback لكن الـ stage label ظل «اعتماد مسؤول الفرع»**.

### المطلوب — شقّان
**أ. راجع الـ fallback الحالي واجعله رسميا.**
لو السياسة فعلا `No Branch Supervisor → Company Manager acts as fallback`:
```
اجعلها behavior رسميا ومتسقا — لا صدفة تعتمد على من فتح الشاشة
عرّفها في مكان واحد · طبّقها على كل الـworkflows التي تبدأ بـbranch_supervisor
سجّلها كقاعدة معلنة
```

**ب. الواجهة والتايملاين تقولان الحقيقة.**
```
✗  "مسؤول الفرع اعتمد"        بينما الفاعل هو Manager
✓  "اعتماد مسؤول الفرع — نُفِّذ بواسطة مدير الشركة لعدم وجود مسؤول مُعيَّن للفرع"
```

هذه ليست تجميلا: سجل يقول إن شخصا اعتمد وهو لم يفعل **يفسد التدقيق**، وقد يكون له أثر قانوني لو تعلق بقرار على موظف.

### فحص إضافي
احصر الفروع بلا مسؤول:
```sql
SELECT b.id, b.name, b.company_id, COUNT(e.id) AS employees
FROM branches b LEFT JOIN employees e ON e.branch_id=b.id AND e.status='active'
WHERE b.supervisor_id IS NULL GROUP BY 1,2,3 HAVING COUNT(e.id) > 0;
```
لو العدد كبير، فالحل الحقيقي **تعيين مسؤولين** لا الاعتماد على الـ fallback دائما. اعرض القائمة على العميل.

## P11-36 — التايملاين يعكس الفاعل الحقيقي

```
stage role = Branch Supervisor لكن الفاعل Manager
  →  Timeline تعرض Manager كـactor الحقيقي وتوضح سبب الـfallback

Automation  →  actor = System
Employee    →  actor = Employee
```

> **لا يوجد generic أو misleading actor.**

### التطبيق العام
كل حدث في أي تايملاين يحمل:
```
actor الحقيقي · original_actor عند الانتحال · الدور الذي تصرّف به
سبب الـfallback إن وُجد · timestamp
```

اكتمال آلي يُسجَّل باسم النظام **مع سبب التشغيل** — لا حقل فارغ ولا اسم آخر مستخدم لمس السجل.

## القبول
`DOD-01` — المعتمدون الصحيحون، والتايملاين يطابق من نفّذ فعلا.
