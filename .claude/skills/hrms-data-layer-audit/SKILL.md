---
name: hrms-data-layer-audit
description: مراجعة طبقة البيانات في Kuwait HRMS — القيود على مستوى قاعدة البيانات، المعاملات والتراجع، السجلات اليتيمة والمكررة، والفهارس والأداء. استخدم هذا السكيل كرابع مرحلة في مراجعة الباكند، وعند أي تناقض في الأرقام أو شك في سلامة البيانات.
---

# مراجعة طبقة البيانات

## قاعدة السلامة
**قراءة فقط.** لا `UPDATE` ولا `DELETE` ولا `DROP` على أي بيئة.
عند اكتشاف بيانات فاسدة: **بلّغ ولا تصلح** — الإصلاح يحتاج migration مراجَعة.

## 1. القيود على مستوى القاعدة
**قيد في الكود بلا قيد في القاعدة سيُخترق عبر مسار آخر يوما ما.**

افحص وجود:
```
UNIQUE  companies(commercial_registration)
UNIQUE  employees(company_id, employee_no)
UNIQUE  employees(company_id, civil_id)
UNIQUE  payroll_runs(company_id, period) WHERE status <> 'cancelled'
UNIQUE  tasks(entity_type, entity_id, step_code, assignee_id) WHERE status='open'
UNIQUE  renewal_cases(current_document_id) WHERE status NOT IN ('COMPLETED','CANCELLED')
CHECK   users: role='employee' ⇒ employee_id IS NOT NULL
NOT NULL على كل حقل تعتمد عليه قاعدة عمل
FK      كل employee_id / company_id / request_id مع ON DELETE مناسب
```

```sql
-- عرض القيود الفعلية (PostgreSQL)
SELECT conrelid::regclass AS tbl, conname, pg_get_constraintdef(oid)
FROM pg_constraint WHERE connamespace = 'public'::regnamespace ORDER BY 1;
```

## 2. سلامة السجلات
```sql
-- مستخدمون بدور employee بلا employee_id
SELECT id, username FROM users WHERE role='employee' AND employee_id IS NULL;

-- مستخدم مربوط بموظف من شركة أخرى
SELECT u.id FROM users u JOIN employees e ON e.id=u.employee_id
WHERE u.company_id <> e.company_id;

-- تطابق الأعداد: نشط / حضور / رواتب
SELECT c.name,
 (SELECT COUNT(*) FROM employees WHERE company_id=c.id AND status='active'),
 (SELECT COUNT(DISTINCT employee_id) FROM attendance WHERE company_id=c.id AND period=:p),
 (SELECT COUNT(DISTINCT employee_id) FROM payroll_lines pl
    JOIN payroll_runs pr ON pr.id=pl.run_id WHERE pr.company_id=c.id AND pr.period=:p)
FROM companies c;

-- مهام مفتوحة لمعاملات منتهية
SELECT t.id FROM tasks t JOIN requests r ON r.id=t.request_id
WHERE t.status='open' AND r.status IN ('completed','rejected','cancelled');

-- مهام مكررة
SELECT entity_type, entity_id, step_code, assignee_id, COUNT(*)
FROM tasks WHERE status='open' GROUP BY 1,2,3,4 HAVING COUNT(*)>1;

-- طلبات Pending بلا معيّن
SELECT id, type_code FROM requests
WHERE status IN ('pending','in_review') AND current_assignee_id IS NULL;

-- غياب قبل التعيين
SELECT a.employee_id, e.hire_date, a.date FROM attendance a
JOIN employees e ON e.id=a.employee_id WHERE a.date < e.hire_date;

-- مستندات مُصدَرة بلا ملف
SELECT id, template_code FROM document_artifacts
WHERE status IN ('issued','delivered','filed') AND (storage_key IS NULL OR sha256 IS NULL);

-- معاملات تجديد عالقة في القفلة
SELECT id, case_no, status FROM renewal_cases
WHERE status='pending_hr_verify'
  AND (new_expiry_date IS NULL OR new_residency_number IS NULL OR gov_reference IS NULL);

-- سجلات يتيمة
SELECT t.id FROM tasks t LEFT JOIN requests r ON r.id=t.request_id WHERE r.id IS NULL;
```
عدّل أسماء الجداول حسب المخطط الفعلي — **اقرأه ولا تخمّنه**.

## 3. المعاملات والتراجع
افحص في الكود أن هذه العمليات **داخل transaction واحدة**:
```
إنشاء موظف + مستخدم + ربط
تطبيق تصحيح الحضور + الانتقال إلى Completed
Payroll: احتساب + حفظ الأسطر + تغيير الحالة
إصدار مستند + تسجيله + تحديث حالة الطلب
معاملة التجديد: تحديث المستندات + تطبيق تاريخ الانتهاء + إغلاق التنبيهات
```

**اختبار عملي:** أوقف العملية في منتصفها (خطأ متعمد) وافحص هل بقيت بيانات جزئية.

**البلاغ الموثق:** طلب تصحيح حضور وصل `Completed` بلا تطبيق التصحيح — أي أن الانتقال والتطبيق ليسا في معاملة واحدة.

## 4. الأثر مقابل الحالة
الفحص الأهم في هذا النظام: **هل الأثر التشغيلي وقع فعلا؟**

```sql
-- طلبات تصحيح حضور مكتملة بلا تطبيق
SELECT r.id FROM requests r WHERE r.status='completed' AND r.type_code='attendance_correction'
AND NOT EXISTS (SELECT 1 FROM attendance_corrections ac
                WHERE ac.request_id=r.id AND ac.applied_at IS NOT NULL);

-- إجازات معتمدة بلا خصم رصيد
-- سلف معتمدة بلا جدول سداد
-- معاملات تجديد مكتملة بلا تاريخ انتهاء جديد
```
**حالة `Completed` ليست دليلا على شيء.**

## 5. مصدر البيانات الواحد
البلاغات الموثقة تتكرر في هذا: رصيد الإجازة 30 مقابل 92.16 · الإقامات السارية 0 رغم وجود مستندات · العداد 21 والفلتر 7.

لكل رقم يظهر في أكثر من شاشة: **هل يأتي من نفس الاستعلام؟**
اكتب استعلام المقارنة وشغّله. أي فرق = نتيجة.

## 6. الأداء
```
N+1: افحص الاستعلامات في القوائم — كم استعلاما لصفحة واحدة؟
فهارس: على كل FK وكل عمود يُفلتر أو يُرتّب به
ترقيم: قائمة بلا LIMIT تتحول لمشكلة مع نمو البيانات
SELECT *: يجلب حقولا حساسة بلا حاجة ويصعّب تتبع التسريب
```

## 7. الميجريشنز
```
هل تعمل من صفر على قاعدة فارغة؟
هل لكل واحدة تراجع (down)؟
هل توجد migration معدّلة بعد تطبيقها؟ (خطر على البيئات)
هل تفقد بيانات تدقيق أثناء التطبيق؟
Migration Version ظاهر في النظام؟
```

## التسجيل
- قيد ناقص يسمح بفساد بيانات → `high`
- عملية بلا transaction تترك بيانات جزئية → `high`
- حالة بلا أثر → `high`
- تناقض بين شاشتين → `high`
- N+1 أو فهرس ناقص → `medium`
