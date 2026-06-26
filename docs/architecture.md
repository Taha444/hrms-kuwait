# المعمارية (Architecture)

## القرار المعماري الأساسي
سيرفر مركزي واحد + قاعدة بيانات واحدة = **مصدر حقيقة واحد**. التطبيق ويب يُثبَّت كـ
**PWA** (يصل للكاميرا والـ GPS)؛ لا توجد قواعد بيانات محلية على الأجهزة. اختياريًا يمكن
لفّ قشرة سطح مكتب (Tauri) تتصل بنفس السيرفر.

## الطبقات
```
React PWA (RTL/i18n)  ──HTTP/JSON──▶  FastAPI Routers  ──▶  Services/Engines  ──▶  SQLAlchemy ORM  ──▶  PostgreSQL/SQLite
                                       (auth/deps)          (workflow,             (models.py)
                                                             notifications,
                                                             eos, qr, ocr)
```

## العزل بين الشركات (Multi-Tenancy)
- كل كيان تشغيلي يحمل `company_id`.
- التبعيات في `app/deps.py` تفرض النطاق:
  - `scope_company_id()` تُجبر غير الإدارة العليا على `company_id` الخاص بهم.
  - `assert_same_company()` تُعيد 404 لأي كيان خارج نطاق المستخدم (تُخفي الوجود).
- `super_admin` فقط يتجاوز العزل؛ `company_owner` مرتبط بشركته.

## الصلاحيات (RBAC + Permission-based)
- `app/permissions.py`: كتالوج أفعال + صلاحيات افتراضية لكل دور + قوالب.
- الصلاحيات الفعّالة = الافتراضية للدور + المُسندة صراحةً (غير المنتهية).
- تُفرض عبر `require_perm("...")` على كل نقطة API حسّاسة.

## محرّك الطلبات (`workflow.py`)
- كل نوع طلب = سلسلة مراحل (`approval_chain_json`) قابلة للتهيئة دون كود.
- أنواع المراحل: `approval`، `hr_review` (توليد مستند + موعد + انتظار توقيع)، `delegate_exit` (إذن المغادرة)، `pickup` (الاستلام).
- يُسجّل كل قرار في `request_approvals` (تُبنى منها عبارة «اعتمد من قبل…»).
- المدير العام/صاحب الشركة/الإدارة العليا يلغون في أي مرحلة → إشعار كل الأطراف.

## محرّك المهام (`notifications.py`)
- `create_task` مع `dedup_key` لمنع التكرار.
- `notify_roles` / `notify_employee_self` لتوجيه نفس الحدث لعدة مستلِمين بصياغات مناسبة.
- `daily_scan` (يستدعيه APScheduler يوميًا 6 صباحًا) يفحص الإقامات/المستندات/التراخيص.

## الحضور (`qr.py` + `routers/attendance.py`)
- رمز QR متغيّر TOTP-like مشتق من `branch.qr_secret` يتجدد كل 60 ثانية (نافذة تحقق ±1).
- السيلفي إلزامي (يُرفض التسجيل بدونه)؛ Geofence عبر مسافة Haversine مقابل `geofence_radius_m`.
- حساب التأخير/الخروج المبكر/الإضافي من الوردية (`shifts`).

## مكافأة نهاية الخدمة (`eos.py`)
منقولة كما هي من النسخة الأولية المعتمَدة ومُختبَرة بأمثلة القانون (راجع `tests/test_eos.py`).

## الكيانات الأساسية
companies, users, user_permissions, branches, branch_supervisors, shifts, employees,
licenses, permits, document_types, documents, tasks, request_types, requests,
request_approvals, request_documents, appointments, attendance_records, leaves,
deductions, payroll_runs, transfers, audit_log.
