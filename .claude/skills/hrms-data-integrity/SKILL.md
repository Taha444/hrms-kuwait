---
name: hrms-data-integrity
description: فحوص سلامة البيانات على مستوى قاعدة البيانات في Kuwait HRMS — السجلات اليتيمة، التناقض بين الشاشات، المستخدمون بلا employee_id، المهام المكررة، والقيود الناقصة. استخدم هذا السكيل إلزاميا قبل التسليم، وعند أي تناقض في الأرقام بين شاشتين، وعند سؤال "البيانات سليمة؟". استخدمه أيضا بعد أي ترحيل أو migration.
---

# HRMS Data Integrity Checks

## لماذا هذا السكيل
معظم الأعطال الموثقة في هذا النظام **تناقضات بيانات**، لا أخطاء منطق:
- عدد الموظفين 12 مقابل 13
- رصيد الإجازة 30 مقابل 92.16
- الإقامات السارية 0 رغم وجود مستندات
- العداد 2 والفلتر 0

**الاستعلام المباشر على قاعدة البيانات يكشفها في ثوانٍ**، بينما التصفح اليدوي قد لا يكشفها أبدا.

## قواعد السلامة
- **قراءة فقط.** لا `UPDATE` ولا `DELETE` ولا `DROP` — أبدا، على أي بيئة.
- على نسخة أو Read Replica إن أمكن.
- عند اكتشاف بيانات فاسدة: **بلّغ ولا تصلح مباشرة** — الإصلاح يحتاج migration مراجَعة.

## الفحوص — أسماء الجداول تقديرية، عدّلها حسب المخطط الفعلي

### 1. المستخدمون والموظفون
```sql
-- مستخدمون بدور Employee بلا employee_id  ← ACCESS-01
SELECT id, username, role, company_id FROM users
WHERE role = 'employee' AND (employee_id IS NULL OR employee_id = 0);

-- مستخدمون مربوطون بموظف من شركة أخرى
SELECT u.id, u.company_id, e.company_id FROM users u
JOIN employees e ON e.id = u.employee_id
WHERE u.company_id <> e.company_id;

-- موظفون بلا Employee ID  ← UX-04
SELECT id, full_name, company_id FROM employees
WHERE employee_no IS NULL OR employee_no = '';

-- تكرار Employee ID داخل الشركة
SELECT company_id, employee_no, COUNT(*) FROM employees
WHERE employee_no IS NOT NULL GROUP BY 1,2 HAVING COUNT(*) > 1;

-- تكرار الرقم المدني داخل الشركة
SELECT company_id, civil_id, COUNT(*) FROM employees
GROUP BY 1,2 HAVING COUNT(*) > 1;
```

### 2. تطابق الأعداد — الفحص الأهم
```sql
-- Active Employees مقابل من له سجل حضور مقابل من دخل الراتب  ← ATT-03
SELECT c.name AS company,
  (SELECT COUNT(*) FROM employees WHERE company_id=c.id AND status='active') AS active_emp,
  (SELECT COUNT(DISTINCT employee_id) FROM attendance
     WHERE company_id=c.id AND period='2026-08')                             AS in_attendance,
  (SELECT COUNT(DISTINCT employee_id) FROM payroll_lines pl
     JOIN payroll_runs pr ON pr.id=pl.run_id
     WHERE pr.company_id=c.id AND pr.period='2026-08')                       AS in_payroll
FROM companies c;
-- الأعمدة الثلاثة يجب أن تتطابق، أو يكون الفرق موظفين لهم Exempt Reason موثق

-- الموظفون الساقطون من الحضور بالاسم
SELECT e.id, e.full_name, e.attendance_policy_id, e.exempt_reason
FROM employees e
WHERE e.status='active'
  AND NOT EXISTS (SELECT 1 FROM attendance a WHERE a.employee_id=e.id AND a.period='2026-08');
```

### 3. الحضور والغياب
```sql
-- غياب مسجّل قبل تاريخ التعيين  ← ATT-04
SELECT a.employee_id, e.full_name, e.hire_date, a.date, a.status
FROM attendance a JOIN employees e ON e.id=a.employee_id
WHERE a.date < e.hire_date;

-- سياسة حضور غائبة بلا سبب إعفاء  ← ATT-06
SELECT id, full_name FROM employees
WHERE status='active' AND attendance_policy_id IS NULL
  AND (exempt_reason IS NULL OR exempt_reason='');

-- تسجيلات مكررة لنفس اليوم
SELECT employee_id, date, COUNT(*) FROM attendance
GROUP BY 1,2 HAVING COUNT(*) > 1;
```

### 4. رصيد الإجازات — التناقض الموثق
```sql
-- قارن الرصيد المخزّن بالمحسوب من الحركات  ← EOS-03
SELECT e.id, e.full_name,
       lb.balance_days AS stored_balance,
       (SELECT COALESCE(SUM(days),0) FROM leave_entitlements WHERE employee_id=e.id)
     - (SELECT COALESCE(SUM(days),0) FROM leave_requests
        WHERE employee_id=e.id AND status='completed') AS computed_balance
FROM employees e LEFT JOIN leave_balances lb ON lb.employee_id=e.id
WHERE e.status='active';
-- أي فرق = العطل. حدد أي الرقمين صحيح قبل التوحيد — الرقم يُدفع فعلا في بدل الإجازات
```

### 5. الطلبات والمهام
```sql
-- طلبات Completed بلا أثر تشغيلي  ← WF-04
SELECT r.id, r.type_code, r.completed_at FROM requests r
WHERE r.status='completed'
  AND r.type_code='attendance_correction'
  AND NOT EXISTS (SELECT 1 FROM attendance_corrections ac
                  WHERE ac.request_id=r.id AND ac.applied_at IS NOT NULL);

-- مهام مفتوحة لطلبات منتهية  ← TASK-01
SELECT t.id, t.request_id, r.status FROM tasks t
JOIN requests r ON r.id=t.request_id
WHERE t.status='open' AND r.status IN ('completed','rejected','cancelled');

-- مهام مكررة لنفس الخطوة ونفس المعيّن
SELECT request_id, step_code, assignee_id, COUNT(*) FROM tasks
WHERE status='open' GROUP BY 1,2,3 HAVING COUNT(*) > 1;

-- مهام يتيمة
SELECT t.id FROM tasks t LEFT JOIN requests r ON r.id=t.request_id WHERE r.id IS NULL;

-- طلبات بلا معيّن حالي وهي Pending  ← WF-02
SELECT id, type_code, status, current_assignee_id FROM requests
WHERE status IN ('pending','in_review') AND current_assignee_id IS NULL;

-- طلبات بأنواع Legacy أُنشئت بعد تفعيل Canonical  ← CAT-01
SELECT type_code, COUNT(*), MAX(created_at) FROM requests
WHERE type_code IN (SELECT code FROM request_types WHERE is_legacy=true)
GROUP BY 1 ORDER BY 3 DESC;
```

### 6. المستندات والإقامات
```sql
-- مستندات بلا تاريخ انتهاء رغم أن نوعها يتطلبه  ← PRO-01
SELECT id, document_type, employee_id, created_at FROM employee_documents
WHERE document_type IN ('residency','work_permit','passport','civil_id')
  AND expiry_date IS NULL;

-- إقامات ستنتهي خلال 90 يوما ولا مهمة تجديد لها  ← PRO-02
SELECT d.id, d.employee_id, d.expiry_date FROM employee_documents d
WHERE d.document_type='residency'
  AND d.expiry_date BETWEEN CURRENT_DATE AND CURRENT_DATE + 90
  AND NOT EXISTS (SELECT 1 FROM renewal_cases rc
                  WHERE rc.document_id=d.id AND rc.status <> 'closed');

-- مهام تجديد مكررة لنفس المستند  ← PRO-06
SELECT document_id, COUNT(*) FROM renewal_cases
WHERE status <> 'closed' GROUP BY 1 HAVING COUNT(*) > 1;

-- مستندات مُصدَرة بلا ملف فعلي  ← DOC-01
SELECT id, template_code, status FROM document_artifacts
WHERE status IN ('issued','delivered','filed')
  AND (storage_key IS NULL OR sha256 IS NULL);
```

### 7. الشركات والتدقيق
```sql
-- تكرار السجل التجاري  ← DATA-01
SELECT commercial_registration, COUNT(*) FROM companies
GROUP BY 1 HAVING COUNT(*) > 1;

-- أحداث تدقيق بلا actor أو IP  ← AUDIT-01
SELECT action, COUNT(*) FROM audit_log
WHERE actor_id IS NULL OR ip IS NULL GROUP BY 1 ORDER BY 2 DESC;

-- سجلات نجاح لعمليات فاشلة  ← AUDIT-03
SELECT id, action, result FROM audit_log
WHERE result='success' AND error_message IS NOT NULL;
```

### 8. القيود الناقصة
افحص وجود هذه القيود على مستوى قاعدة البيانات — **لا في الكود فقط**:
```
UNIQUE  companies(commercial_registration)
UNIQUE  employees(company_id, employee_no)
UNIQUE  employees(company_id, civil_id)
UNIQUE  payroll_runs(company_id, period) WHERE status <> 'cancelled'
UNIQUE  tasks(request_id, step_code, assignee_id) WHERE status='open'
CHECK   users: role='employee' ⇒ employee_id IS NOT NULL
FK      كل employee_id و company_id و request_id مع ON DELETE مناسب
```
**قيد في الكود بلا قيد في القاعدة = سيُخترق عبر مسار آخر يوما ما.**

## بعد التنفيذ
لكل استعلام يرجع صفوفا:
1. سجّله كعطل بمعرّف
2. اربطه بالرحلة التي كان يجب أن تكشفه — إن لم توجد، **أضف رحلة**
3. **لا تصلح البيانات يدويا** — الإصلاح يحتاج migration مراجعة وسبب موثق
