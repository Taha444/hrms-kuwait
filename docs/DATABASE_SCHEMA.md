# مخطط قاعدة البيانات (DLV-44)

> **مولَّد من النماذج** بـ`backend/scripts/db_schema_doc.py` — لا يُحرَّر باليد.
> والترحيلات في `backend/alembic/versions`؛ الإنتاج على PostgreSQL والاختبار على SQLite.

عدد الجداول: **53**.

## الفهرس

- [`allowances`](#allowances) — بدٌل أو ميزة تُضاف إلى أجر الشهر.
- [`appointments`](#appointments) — موعٌد لموظف مرتبط بطلب: وقته ومكانه وحالته.
- [`approval_delegations`](#approval-delegations) — V1.5 Phase 3 — تفويض مؤقت لصلاحية الاعتماد (V2.2 Approver actions: تفويض مؤقت).
- [`attendance_month_closes`](#attendance-month-closes) — V2.2 §17 — قفل شهر حضور: بعد اعتماد كل التصحيحات، يُقفَل الشهر لتأمين مصدر بيانات
- [`attendance_records`](#attendance-records) — سجلُّ حضوٍر ليوم عمل: دخول وخروج بموقعيهما وسيلفي كلٍّ منهما، والمدة والإضافي — سجلٌّ مفتوح واحد لكل موظف.
- [`audit_log`](#audit-log) — سجلُّ التدقيق: من فعل ماذا ومتى وعلى أي كيان، وما قبله وما بعده — لا يُعدَّل ولا يُحذف.
- [`authorized_signatories`](#authorized-signatories) — SEC2-15 — سجل المخوّلين بالتوقيع (Authorized Signatories Registry).
- [`branch_supervisors`](#branch-supervisors) — ربط مسؤولي الفروع بفروعهم (متعدد لمتعدد).
- [`branches`](#branches) — فرُع الشركة: عنوانه ومحافظته وإحداثياته ونطاق السياج ومفتاح شاشة الحضور.
- [`break_glass_sessions`](#break-glass-sessions) — V2.2 §13.5 (AC-05) — نافذة تجاوز طارئة لـSuper Admin، موقّتة وموثّقة.
- [`companies`](#companies) — الشركة (صاحب العمل): بياناتها القانونية وسجلّها التجاري وممثّلها، وإعدادات نهاية الخدمة والإجازة.
- [`company_representatives`](#company-representatives) — GC-11 — ممثّل مفوَّض بالتوقيع عن الشركة، قد يتعدّد لشركة واحدة.
- [`consumed_tokens`](#consumed-tokens) — منع إعادة استخدام رموز QR وتذاكر التسجيل (anti-replay).
- [`deductions`](#deductions) — خصٌم من أجر الموظف بقرار (أو قسط قرض) — يُحتسب في مسيّر شهره.
- [`departments`](#departments) — الإدارة/القسم داخل فرع (الهرم: شركة ← فرع ← إدارة ← موظفون).
- [`device_tokens`](#device-tokens) — جهاز مسجَّل لاستقبال الإشعارات الفورية (FCM).
- [`document_template_versions`](#document-template-versions) — V2.2 §14 — سجل نسخ القوالب: كل تعديل يُنشئ نسخة جديدة والقديمة تُحفظ للأرشيف.
- [`document_templates`](#document-templates) — صيغة/نموذج قابل للتعبئة التلقائية ثم الطباعة (خطابات، شهادات، نماذج).
- [`document_types`](#document-types) — نوُع مستنٍد يُتتبَّع انتهاؤه (إقامة، جواز، ترخيص…) ومهل التنبيه قبله.
- [`documents`](#documents) — مستند بنُسخ/تأريخ — الأحدث is_current=True والقديم محفوظ.
- [`employee_events`](#employee-events) — أحداث الموارد البشرية على الموظف: إنذار/جزاء/مكافأة/ترقية/ملاحظة.
- [`employee_field_changes`](#employee-field-changes) — R3-C §4 — سجل نسخي للتغييرات الحرجة على ملف الموظف.
- [`employees`](#employees) — ملفُّ الموظف: بياناته الشخصية وعقده وراتبه وفرعه وترخيصه وحالته الوظيفية.
- [`eos_cases`](#eos-cases) — QA §6 — دورة حياة إنهاء الخدمة الكاملة (9 مراحل، فصل سلطات).
- [`feature_flags`](#feature-flags) — V1.5 Phase 5 — Feature flag لكل شركة (V1.5 §3 الترحيل الآمن).
- [`gov_logs`](#gov-logs) — سجلّ معاملات المندوب الحكومية: ملاحظات وتجديدات على الإقامات/التراخيص.
- [`government_portals`](#government-portals) — R8 §1 — روابط المواقع الحكومية للمندوب (PRO). قابلة للتعديل من الإدارة بلا كود.
- [`holidays`](#holidays) — عطلةٌ رسمية لشركة — قرار المالك (2026-09-17). انظر ``app/holidays.py``.
- [`job_runs`](#job-runs) — جولة مهمة مجدولة — القفل والدليل في صفّ واحد.
- [`leave_ledger`](#leave-ledger) — سجل حركات رصيد الإجازة السنوية.
- [`leaves`](#leaves) — إجازٌة معتمَدة أو مطلوبة بنوعها وتاريخيها — منها يُحسب الرصيد ويُعفى المسيّر.
- [`licenses`](#licenses) — ترخيٌص تجاري للشركة: رقمه وجهته وانتهاؤه وعدد العمالة المسموح.
- [`notification_preferences`](#notification-preferences) — تفضيل تسليم الإشعارات لكل مستخدم حسب الفئة (قناة مفعّلة أم لا).
- [`notification_templates`](#notification-templates) — قالب إشعار مُسمّى (FIX-004) — 74 قالبًا تغطي كل أحداث دورة حياة الطلبات والنظام.
- [`payroll_runs`](#payroll-runs) — مسيُّر رواتب شهٍر لشركة: يُجهَّز ثم يُعتمد (من غير مُجهِّزه) ثم يُنهى ثم يُقفَل؛ والتصحيح بمسيّر تسوية.
- [`permits`](#permits) — إقامة / إذن عمل.
- [`policy_rules`](#policy-rules) — V2.2 §7 (STR-05) — حدود السياسة بياًنا لا كوًدا.
- [`request_approvals`](#request-approvals) — قراٌر على مرحلٍة من طلب: من قرّر وبأي دور، والقرار وملاحظته — تاريخ الطلب.
- [`request_documents`](#request-documents) — ملفٌّ على طلب: المستند المولَّد، والنسخة الموقّعة، ومرفقات صاحب الطلب والمندوب.
- [`request_types`](#request-types) — نوُع طلب: سلسلة اعتماده ومخرجه وقالبه وظهوره للموظف — يُصالَح من الشيفرة عند كل إقلاع.
- [`requests`](#requests) — طلٌب مقدَّم لموظف: نوعه وحمولته وحالته ومرحلته الحالية في سلسلة الاعتماد.
- [`residency_renewals`](#residency-renewals) — معاملة تجديد الإقامة (مبكر/عادي) بحالاتها المتعددة — DEMO-001/002.
- [`revoked_tokens`](#revoked-tokens) — رمز أُبطل قبل انتهاء صلاحيته.
- [`salary_change_requests`](#salary-change-requests) — R7-G §4 — طلب اعتماد لتغيير الراتب أو تاريخ التعيين أو العقد.
- [`session_activity`](#session-activity) — آخر نشاط **لجلسة بعينها** — لا للمستخدم.
- [`shifts`](#shifts) — ورديُة عمل: بدايتها ونهايتها وأيام العمل ومهلة السماح.
- [`tasks`](#tasks) — محرّك المهام/الإشعارات — كل صلاحية قاربت على الانتهاء = مهمة لها مسؤول.
- [`transfers`](#transfers) — نقل موظف بين شركتين مع سجل تاريخي.
- [`user_company_links`](#user-company-links) — R9 §16 — عضوية user في شركة (لمستخدمي is_cross_company=True).
- [`user_permissions`](#user-permissions) — صلاحيٌة إضافية أُسندت لمستخدمٍ بعينه فوق صلاحيات دوره.
- [`user_signature_versions`](#user-signature-versions) — QA §12 — سجل نسخ التوقيع غير القابل للتعديل (immutable evidence trail).
- [`user_tour_states`](#user-tour-states) — R5 §3 — حالة إكمال الجولة التعليمية لكل (مستخدم × مفتاح جولة).
- [`users`](#users) — حساُب دخول لشخٍص واحد: دوره وشركته وربطه بملف موظف وحالة التحقق الثنائي.

## allowances

النموذج: `models.Allowance` — بدٌل أو ميزة تُضاف إلى أجر الشهر.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER |  |  | `companies.id` |
| `employee_id` | INTEGER |  |  | `employees.id` |
| `request_id` | INTEGER | ✓ |  | `requests.id` |
| `allowance_type` | VARCHAR(40) |  |  |  |
| `amount` | FLOAT |  |  |  |
| `effective_from` | DATE |  |  |  |
| `effective_to` | DATE | ✓ |  |  |
| `is_recurring` | BOOLEAN |  |  |  |
| `reason` | VARCHAR(250) | ✓ |  |  |
| `created_at` | DATETIME |  |  |  |

## appointments

النموذج: `models.Appointment` — موعٌد لموظف مرتبط بطلب: وقته ومكانه وحالته.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER |  |  | `companies.id` |
| `request_id` | INTEGER | ✓ |  | `requests.id` |
| `employee_id` | INTEGER |  |  | `employees.id` |
| `scheduled_at` | DATETIME |  |  |  |
| `location` | VARCHAR(200) | ✓ |  |  |
| `created_by` | INTEGER | ✓ |  | `users.id` |
| `status` | VARCHAR(20) |  |  |  |

## approval_delegations

النموذج: `models.ApprovalDelegation` — V1.5 Phase 3 — تفويض مؤقت لصلاحية الاعتماد (V2.2 Approver actions: تفويض مؤقت).

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER |  |  | `companies.id` |
| `delegator_user_id` | INTEGER |  |  | `users.id` |
| `delegate_user_id` | INTEGER |  |  | `users.id` |
| `reason` | VARCHAR(250) | ✓ |  |  |
| `starts_at` | DATETIME |  |  |  |
| `ends_at` | DATETIME |  |  |  |
| `scope` | VARCHAR(20) |  |  |  |
| `is_active` | BOOLEAN |  |  |  |
| `created_at` | DATETIME |  |  |  |
| `revoked_at` | DATETIME | ✓ |  |  |
| `revoked_by_user_id` | INTEGER | ✓ |  | `users.id` |

## attendance_month_closes

النموذج: `models.AttendanceMonthClose` — V2.2 §17 — قفل شهر حضور: بعد اعتماد كل التصحيحات، يُقفَل الشهر لتأمين مصدر بيانات

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER |  |  | `companies.id` |
| `period` | VARCHAR(7) |  |  |  |
| `status` | VARCHAR(20) |  |  |  |
| `closed_by` | INTEGER | ✓ |  | `users.id` |
| `closed_at` | DATETIME |  |  |  |
| `reopened_by` | INTEGER | ✓ |  | `users.id` |
| `reopened_at` | DATETIME | ✓ |  |  |
| `reopen_reason` | VARCHAR(300) | ✓ |  |  |
| `notes` | TEXT | ✓ |  |  |

قيود التفرّد: (`company_id`, `period`)

## attendance_records

النموذج: `models.AttendanceRecord` — سجلُّ حضوٍر ليوم عمل: دخول وخروج بموقعيهما وسيلفي كلٍّ منهما، والمدة والإضافي — سجلٌّ مفتوح واحد لكل موظف.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER |  |  | `companies.id` |
| `employee_id` | INTEGER |  |  | `employees.id` |
| `branch_id` | INTEGER | ✓ |  | `branches.id` |
| `check_in_at` | DATETIME | ✓ |  |  |
| `check_out_at` | DATETIME | ✓ |  |  |
| `method` | VARCHAR(10) |  |  |  |
| `in_lat` | FLOAT | ✓ |  |  |
| `in_lng` | FLOAT | ✓ |  |  |
| `out_lat` | FLOAT | ✓ |  |  |
| `out_lng` | FLOAT | ✓ |  |  |
| `selfie_in_path` | VARCHAR(400) | ✓ |  |  |
| `selfie_out_path` | VARCHAR(400) | ✓ |  |  |
| `status` | VARCHAR(20) |  |  |  |
| `worked_minutes` | INTEGER |  |  |  |
| `overtime_minutes` | INTEGER |  |  |  |
| `notes` | TEXT | ✓ |  |  |
| `created_at` | DATETIME |  |  |  |

## audit_log

النموذج: `models.AuditLog` — سجلُّ التدقيق: من فعل ماذا ومتى وعلى أي كيان، وما قبله وما بعده — لا يُعدَّل ولا يُحذف.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER | ✓ |  |  |
| `user_id` | INTEGER | ✓ |  |  |
| `action` | VARCHAR(80) |  |  |  |
| `entity_type` | VARCHAR(40) | ✓ |  |  |
| `entity_id` | INTEGER | ✓ |  |  |
| `detail` | TEXT | ✓ |  |  |
| `ip` | VARCHAR(50) | ✓ |  |  |
| `original_user_id` | INTEGER | ✓ |  |  |
| `user_agent` | VARCHAR(400) | ✓ |  |  |
| `actor_role` | VARCHAR(40) | ✓ |  |  |
| `branch_id` | INTEGER | ✓ |  | `branches.id` |
| `result` | VARCHAR(12) | ✓ |  |  |
| `reason` | VARCHAR(500) | ✓ |  |  |
| `correlation_id` | VARCHAR(80) | ✓ |  |  |
| `before_json` | JSON | ✓ |  |  |
| `after_json` | JSON | ✓ |  |  |
| `created_at` | DATETIME |  |  |  |

## authorized_signatories

النموذج: `models.AuthorizedSignatory` — SEC2-15 — سجل المخوّلين بالتوقيع (Authorized Signatories Registry).

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER |  |  | `companies.id` |
| `user_id` | INTEGER |  |  | `users.id` |
| `title_ar` | VARCHAR(120) |  |  |  |
| `title_en` | VARCHAR(120) | ✓ |  |  |
| `scope_type` | VARCHAR(20) |  |  |  |
| `scope_value` | VARCHAR(80) | ✓ |  |  |
| `effective_from` | DATE | ✓ |  |  |
| `effective_to` | DATE | ✓ |  |  |
| `is_active` | BOOLEAN |  |  |  |
| `notes` | TEXT | ✓ |  |  |
| `created_by` | INTEGER | ✓ |  | `users.id` |
| `created_at` | DATETIME |  |  |  |

قيود التفرّد: (`company_id`, `user_id`, `scope_type`, `scope_value`)

## branch_supervisors

النموذج: `models.BranchSupervisor` — ربط مسؤولي الفروع بفروعهم (متعدد لمتعدد).

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER |  |  | `companies.id` |
| `branch_id` | INTEGER |  |  | `branches.id` |
| `user_id` | INTEGER |  |  | `users.id` |

قيود التفرّد: (`branch_id`, `user_id`)

## branches

النموذج: `models.Branch` — فرُع الشركة: عنوانه ومحافظته وإحداثياته ونطاق السياج ومفتاح شاشة الحضور.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER |  |  | `companies.id` |
| `name` | VARCHAR(200) |  |  |  |
| `name_en` | VARCHAR(200) | ✓ |  |  |
| `code` | VARCHAR(6) | ✓ |  |  |
| `latitude` | FLOAT | ✓ |  |  |
| `longitude` | FLOAT | ✓ |  |  |
| `governorate` | VARCHAR(40) | ✓ |  |  |
| `governorate_en` | VARCHAR(40) | ✓ |  |  |
| `geofence_radius_m` | INTEGER |  |  |  |
| `qr_secret` | VARCHAR(64) |  |  |  |
| `kiosk_key` | VARCHAR(64) | ✓ |  |  |
| `auto_checkout_minutes` | INTEGER |  |  |  |
| `address` | VARCHAR(300) | ✓ |  |  |
| `is_headquarters` | BOOLEAN |  |  |  |
| `status` | VARCHAR(20) |  |  |  |
| `created_at` | DATETIME |  |  |  |

## break_glass_sessions

النموذج: `models.BreakGlassSession` — V2.2 §13.5 (AC-05) — نافذة تجاوز طارئة لـSuper Admin، موقّتة وموثّقة.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `user_id` | INTEGER |  |  | `users.id` |
| `company_id` | INTEGER | ✓ |  | `companies.id` |
| `reason` | VARCHAR(400) |  |  |  |
| `started_at` | DATETIME |  |  |  |
| `expires_at` | DATETIME |  |  |  |
| `closed_at` | DATETIME | ✓ |  |  |
| `uses` | INTEGER |  |  |  |

## companies

النموذج: `models.Company` — الشركة (صاحب العمل): بياناتها القانونية وسجلّها التجاري وممثّلها، وإعدادات نهاية الخدمة والإجازة.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `name` | VARCHAR(200) |  |  |  |
| `name_en` | VARCHAR(200) | ✓ |  |  |
| `abbreviation` | VARCHAR(6) | ✓ |  |  |
| `commercial_reg` | VARCHAR(50) | ✓ |  |  |
| `file_number` | VARCHAR(50) | ✓ |  |  |
| `entity_type` | VARCHAR(100) | ✓ |  |  |
| `status` | VARCHAR(20) |  |  |  |
| `representative_name` | VARCHAR(160) | ✓ |  |  |
| `representative_name_en` | VARCHAR(160) | ✓ |  |  |
| `representative_civil_id` | VARCHAR(20) | ✓ |  |  |
| `eos_day_divisor` | INTEGER |  |  |  |
| `eos_max_months` | INTEGER |  |  |  |
| `alert_lead_days` | INTEGER |  |  |  |
| `annual_leave_days` | INTEGER |  |  |  |
| `created_at` | DATETIME |  |  |  |

قيود التفرّد: (`commercial_reg`)

## company_representatives

النموذج: `models.CompanyRepresentative` — GC-11 — ممثّل مفوَّض بالتوقيع عن الشركة، قد يتعدّد لشركة واحدة.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER |  |  | `companies.id` |
| `name` | VARCHAR(160) |  |  |  |
| `name_en` | VARCHAR(160) | ✓ |  |  |
| `civil_id` | VARCHAR(20) | ✓ |  |  |
| `status` | VARCHAR(20) |  |  |  |
| `created_at` | DATETIME |  |  |  |

## consumed_tokens

النموذج: `models.ConsumedToken` — منع إعادة استخدام رموز QR وتذاكر التسجيل (anti-replay).

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `jti` | VARCHAR(64) |  |  |  |
| `kind` | VARCHAR(20) |  |  |  |
| `expires_at` | DATETIME |  |  |  |
| `created_at` | DATETIME |  |  |  |

## deductions

النموذج: `models.Deduction` — خصٌم من أجر الموظف بقرار (أو قسط قرض) — يُحتسب في مسيّر شهره.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER |  |  | `companies.id` |
| `employee_id` | INTEGER |  |  | `employees.id` |
| `amount` | FLOAT |  |  |  |
| `reason` | VARCHAR(250) | ✓ |  |  |
| `ded_type` | VARCHAR(30) |  |  |  |
| `date` | DATE | ✓ |  |  |
| `request_id` | INTEGER | ✓ |  | `requests.id` |

## departments

النموذج: `models.Department` — الإدارة/القسم داخل فرع (الهرم: شركة ← فرع ← إدارة ← موظفون).

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER |  |  | `companies.id` |
| `branch_id` | INTEGER | ✓ |  | `branches.id` |
| `name` | VARCHAR(150) |  |  |  |
| `manager_user_id` | INTEGER | ✓ |  | `users.id` |
| `status` | VARCHAR(20) |  |  |  |
| `created_at` | DATETIME |  |  |  |

## device_tokens

النموذج: `models.DeviceToken` — جهاز مسجَّل لاستقبال الإشعارات الفورية (FCM).

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `user_id` | INTEGER |  |  | `users.id` |
| `token` | VARCHAR(255) |  |  |  |
| `platform` | VARCHAR(20) |  |  |  |
| `label` | VARCHAR(120) | ✓ |  |  |
| `created_at` | DATETIME |  |  |  |
| `last_seen_at` | DATETIME | ✓ |  |  |
| `revoked_at` | DATETIME | ✓ |  |  |
| `revoked_reason` | VARCHAR(60) | ✓ |  |  |

قيود التفرّد: (`token`)

## document_template_versions

النموذج: `models.DocumentTemplateVersion` — V2.2 §14 — سجل نسخ القوالب: كل تعديل يُنشئ نسخة جديدة والقديمة تُحفظ للأرشيف.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `template_id` | INTEGER |  |  | `document_templates.id` |
| `version` | INTEGER |  |  |  |
| `body_html` | TEXT |  |  |  |
| `name` | VARCHAR(200) |  |  |  |
| `category` | VARCHAR(60) |  |  |  |
| `edited_by` | INTEGER | ✓ |  | `users.id` |
| `edited_at` | DATETIME |  |  |  |
| `change_note` | VARCHAR(300) | ✓ |  |  |

قيود التفرّد: (`template_id`, `version`)

## document_templates

النموذج: `models.DocumentTemplate` — صيغة/نموذج قابل للتعبئة التلقائية ثم الطباعة (خطابات، شهادات، نماذج).

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER | ✓ |  | `companies.id` |
| `code` | VARCHAR(50) | ✓ |  |  |
| `name` | VARCHAR(200) |  |  |  |
| `name_en` | VARCHAR(200) | ✓ |  |  |
| `category` | VARCHAR(60) |  |  |  |
| `body_html` | TEXT |  |  |  |
| `is_active` | BOOLEAN |  |  |  |
| `version` | INTEGER |  |  |  |
| `created_by` | INTEGER | ✓ |  | `users.id` |
| `created_at` | DATETIME |  |  |  |

## document_types

النموذج: `models.DocumentType` — نوُع مستنٍد يُتتبَّع انتهاؤه (إقامة، جواز، ترخيص…) ومهل التنبيه قبله.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `code` | VARCHAR(50) |  |  |  |
| `name` | VARCHAR(150) |  |  |  |
| `has_expiry` | BOOLEAN |  |  |  |
| `lead_days_json` | JSON | ✓ |  |  |

قيود التفرّد: (`code`)

## documents

النموذج: `models.Document` — مستند بنُسخ/تأريخ — الأحدث is_current=True والقديم محفوظ.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER |  |  | `companies.id` |
| `entity_type` | VARCHAR(30) |  |  |  |
| `entity_id` | INTEGER |  |  |  |
| `document_type_code` | VARCHAR(50) |  |  |  |
| `title` | VARCHAR(200) | ✓ |  |  |
| `file_path` | VARCHAR(400) | ✓ |  |  |
| `mime` | VARCHAR(100) | ✓ |  |  |
| `issue_date` | DATE | ✓ |  |  |
| `expiry_date` | DATE | ✓ |  |  |
| `extracted_data_json` | JSON | ✓ |  |  |
| `version` | INTEGER |  |  |  |
| `is_current` | BOOLEAN |  |  |  |
| `uploaded_by` | INTEGER | ✓ |  | `users.id` |
| `created_at` | DATETIME |  |  |  |
| `is_issued` | BOOLEAN |  |  |  |
| `reference_no` | VARCHAR(60) | ✓ |  |  |
| `template_version` | INTEGER | ✓ |  |  |
| `checksum_sha256` | VARCHAR(64) | ✓ |  |  |
| `generated_at` | DATETIME | ✓ |  |  |
| `generated_by` | INTEGER | ✓ |  | `users.id` |
| `signature_version` | INTEGER | ✓ |  |  |
| `is_confidential` | BOOLEAN |  |  |  |
| `source_request_id` | INTEGER | ✓ |  | `requests.id` |
| `notify_on_expiry` | BOOLEAN |  |  |  |
| `source_document_id` | INTEGER | ✓ |  | `documents.id` |

## employee_events

النموذج: `models.EmployeeEvent` — أحداث الموارد البشرية على الموظف: إنذار/جزاء/مكافأة/ترقية/ملاحظة.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER |  |  | `companies.id` |
| `employee_id` | INTEGER |  |  | `employees.id` |
| `kind` | VARCHAR(20) |  |  |  |
| `title` | VARCHAR(200) |  |  |  |
| `detail` | TEXT | ✓ |  |  |
| `amount` | FLOAT | ✓ |  |  |
| `date` | DATE | ✓ |  |  |
| `created_by` | INTEGER | ✓ |  | `users.id` |
| `created_at` | DATETIME |  |  |  |

## employee_field_changes

النموذج: `models.EmployeeFieldChange` — R3-C §4 — سجل نسخي للتغييرات الحرجة على ملف الموظف.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER |  |  | `companies.id` |
| `employee_id` | INTEGER |  |  | `employees.id` |
| `field_name` | VARCHAR(40) |  |  |  |
| `old_value` | VARCHAR(200) | ✓ |  |  |
| `new_value` | VARCHAR(200) | ✓ |  |  |
| `effective_date` | DATE |  |  |  |
| `changed_at` | DATETIME |  |  |  |
| `changed_by` | INTEGER | ✓ |  | `users.id` |
| `reason` | TEXT | ✓ |  |  |

## employees

النموذج: `models.Employee` — ملفُّ الموظف: بياناته الشخصية وعقده وراتبه وفرعه وترخيصه وحالته الوظيفية.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER |  |  | `companies.id` |
| `employee_no` | VARCHAR(30) | ✓ |  |  |
| `civil_id` | VARCHAR(20) | ✓ |  |  |
| `name` | VARCHAR(200) |  |  |  |
| `name_en` | VARCHAR(200) | ✓ |  |  |
| `nationality` | VARCHAR(100) | ✓ |  |  |
| `gender` | VARCHAR(10) | ✓ |  |  |
| `date_of_birth` | DATE | ✓ |  |  |
| `marital_status` | VARCHAR(20) | ✓ |  |  |
| `email` | VARCHAR(150) | ✓ |  |  |
| `passport_number` | VARCHAR(40) | ✓ |  |  |
| `passport_expiry` | DATE | ✓ |  |  |
| `health_insurance` | VARCHAR(100) | ✓ |  |  |
| `direct_manager_id` | INTEGER | ✓ |  | `employees.id` |
| `worker_type` | VARCHAR(50) | ✓ |  |  |
| `job_title` | VARCHAR(150) | ✓ |  |  |
| `actual_job_title` | VARCHAR(150) | ✓ |  |  |
| `job_title_en` | VARCHAR(150) | ✓ |  |  |
| `nationality_en` | VARCHAR(80) | ✓ |  |  |
| `basic_salary` | FLOAT |  |  |  |
| `actual_salary` | FLOAT | ✓ |  |  |
| `work_hours_type` | VARCHAR(20) | ✓ |  |  |
| `official_work_hours` | FLOAT | ✓ |  |  |
| `actual_work_hours` | FLOAT | ✓ |  |  |
| `hire_date` | DATE | ✓ |  |  |
| `contract_type` | VARCHAR(20) |  |  |  |
| `status` | VARCHAR(20) |  |  |  |
| `license_id` | INTEGER | ✓ |  | `licenses.id` |
| `actual_license_id` | INTEGER | ✓ |  | `licenses.id` |
| `branch_id` | INTEGER | ✓ |  | `branches.id` |
| `actual_branch_id` | INTEGER | ✓ |  | `branches.id` |
| `created_by` | INTEGER | ✓ |  | `users.id` |
| `department_id` | INTEGER | ✓ |  | `departments.id` |
| `shift_id` | INTEGER | ✓ |  | `shifts.id` |
| `attendance_mode` | VARCHAR(10) |  |  |  |
| `attendance_exempt` | BOOLEAN |  |  |  |
| `attendance_exempt_reason` | VARCHAR(200) | ✓ |  |  |
| `attendance_exempt_approved_by` | INTEGER | ✓ |  | `users.id` |
| `attendance_exempt_approved_at` | DATETIME | ✓ |  |  |
| `annual_leave_balance` | FLOAT |  |  |  |
| `non_payroll` | BOOLEAN |  |  |  |
| `non_payroll_reason` | VARCHAR(200) | ✓ |  |  |
| `phone` | VARCHAR(30) | ✓ |  |  |
| `photo` | VARCHAR(300) | ✓ |  |  |
| `termination_date` | DATE | ✓ |  |  |
| `termination_reason` | VARCHAR(40) | ✓ |  |  |
| `eos_settlement_json` | TEXT | ✓ |  |  |
| `pending_termination_json` | TEXT | ✓ |  |  |
| `pending_termination_prepared_by` | INTEGER | ✓ |  | `users.id` |
| `pending_termination_prepared_at` | DATETIME | ✓ |  |  |
| `pending_termination_approved_by` | INTEGER | ✓ |  | `users.id` |
| `pending_termination_approved_at` | DATETIME | ✓ |  |  |
| `pending_termination_cleared_by` | INTEGER | ✓ |  | `users.id` |
| `pending_termination_cleared_at` | DATETIME | ✓ |  |  |
| `pending_termination_clearance_note` | TEXT | ✓ |  |  |
| `pending_termination_acknowledged_at` | DATETIME | ✓ |  |  |
| `created_at` | DATETIME |  |  |  |

## eos_cases

النموذج: `models.EosCase` — QA §6 — دورة حياة إنهاء الخدمة الكاملة (9 مراحل، فصل سلطات).

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER |  |  | `companies.id` |
| `employee_id` | INTEGER |  |  | `employees.id` |
| `status` | VARCHAR(20) |  |  |  |
| `document_status` | VARCHAR(20) |  |  |  |
| `reference_no` | VARCHAR(60) | ✓ |  |  |
| `termination_date` | DATE | ✓ |  |  |
| `termination_reason` | VARCHAR(40) | ✓ |  |  |
| `used_leave_days` | FLOAT |  |  |  |
| `settlement_json` | JSON | ✓ |  |  |
| `notice_served` | BOOLEAN | ✓ |  |  |
| `notice_served_date` | DATE | ✓ |  |  |
| `initiated_by` | INTEGER | ✓ |  | `users.id` |
| `initiated_at` | DATETIME | ✓ |  |  |
| `calculated_by` | INTEGER | ✓ |  | `users.id` |
| `calculated_at` | DATETIME | ✓ |  |  |
| `approved_by` | INTEGER | ✓ |  | `users.id` |
| `approved_at` | DATETIME | ✓ |  |  |
| `clearance_by` | INTEGER | ✓ |  | `users.id` |
| `clearance_at` | DATETIME | ✓ |  |  |
| `clearance_notes` | TEXT | ✓ |  |  |
| `acknowledged_at` | DATETIME | ✓ |  |  |
| `acknowledgment_note` | TEXT | ✓ |  |  |
| `settled_by` | INTEGER | ✓ |  | `users.id` |
| `settled_at` | DATETIME | ✓ |  |  |
| `payment_reference` | VARCHAR(80) | ✓ |  |  |
| `printed_by` | INTEGER | ✓ |  | `users.id` |
| `printed_at` | DATETIME | ✓ |  |  |
| `filed_by` | INTEGER | ✓ |  | `users.id` |
| `filed_at` | DATETIME | ✓ |  |  |
| `filing_location` | VARCHAR(200) | ✓ |  |  |
| `source_request_id` | INTEGER | ✓ |  | `requests.id` |
| `created_at` | DATETIME |  |  |  |

## feature_flags

النموذج: `models.FeatureFlag` — V1.5 Phase 5 — Feature flag لكل شركة (V1.5 §3 الترحيل الآمن).

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `key` | VARCHAR(60) |  |  |  |
| `company_id` | INTEGER | ✓ |  | `companies.id` |
| `value` | VARCHAR(500) |  |  |  |
| `note` | VARCHAR(250) | ✓ |  |  |
| `updated_at` | DATETIME |  |  |  |
| `updated_by_user_id` | INTEGER | ✓ |  | `users.id` |

قيود التفرّد: (`key`, `company_id`)

## gov_logs

النموذج: `models.GovLog` — سجلّ معاملات المندوب الحكومية: ملاحظات وتجديدات على الإقامات/التراخيص.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER |  |  | `companies.id` |
| `entity_type` | VARCHAR(20) |  |  |  |
| `entity_id` | INTEGER |  |  |  |
| `action` | VARCHAR(20) |  |  |  |
| `note` | TEXT | ✓ |  |  |
| `created_by` | INTEGER | ✓ |  | `users.id` |
| `created_at` | DATETIME |  |  |  |

## government_portals

النموذج: `models.GovernmentPortal` — R8 §1 — روابط المواقع الحكومية للمندوب (PRO). قابلة للتعديل من الإدارة بلا كود.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `name_ar` | VARCHAR(200) |  |  |  |
| `name_en` | VARCHAR(200) | ✓ |  |  |
| `description_ar` | TEXT | ✓ |  |  |
| `description_en` | TEXT | ✓ |  |  |
| `url` | VARCHAR(500) |  |  |  |
| `category` | VARCHAR(30) |  |  |  |
| `icon` | VARCHAR(60) | ✓ |  |  |
| `sort_order` | INTEGER |  |  |  |
| `is_active` | BOOLEAN |  |  |  |
| `created_by` | INTEGER | ✓ |  | `users.id` |
| `created_at` | DATETIME |  |  |  |
| `updated_at` | DATETIME |  |  |  |

## holidays

النموذج: `models.Holiday` — عطلةٌ رسمية لشركة — قرار المالك (2026-09-17). انظر ``app/holidays.py``.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER |  |  | `companies.id` |
| `date` | DATE |  |  |  |
| `name` | VARCHAR(120) |  |  |  |
| `created_by` | INTEGER | ✓ |  | `users.id` |
| `created_at` | DATETIME | ✓ |  |  |

قيود التفرّد: (`company_id`, `date`)

## job_runs

النموذج: `models.JobRun` — جولة مهمة مجدولة — القفل والدليل في صفّ واحد.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `job` | VARCHAR(40) |  | PK |  |
| `run_key` | VARCHAR(40) |  | PK |  |
| `status` | VARCHAR(12) |  |  |  |
| `started_at` | DATETIME | ✓ |  |  |
| `finished_at` | DATETIME | ✓ |  |  |
| `holder` | VARCHAR(80) | ✓ |  |  |
| `recovered` | INTEGER | ✓ |  |  |

## leave_ledger

النموذج: `models.LeaveLedger` — سجل حركات رصيد الإجازة السنوية.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER |  |  |  |
| `employee_id` | INTEGER |  |  | `employees.id` |
| `kind` | VARCHAR(20) |  |  |  |
| `days` | FLOAT |  |  |  |
| `balance_before` | FLOAT |  |  |  |
| `balance_after` | FLOAT |  |  |  |
| `leave_type` | VARCHAR(30) | ✓ |  |  |
| `request_id` | INTEGER | ✓ |  |  |
| `leave_id` | INTEGER | ✓ |  |  |
| `note` | VARCHAR(300) | ✓ |  |  |
| `created_by` | INTEGER | ✓ |  |  |
| `created_at` | DATETIME |  |  |  |

## leaves

النموذج: `models.Leave` — إجازٌة معتمَدة أو مطلوبة بنوعها وتاريخيها — منها يُحسب الرصيد ويُعفى المسيّر.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER |  |  | `companies.id` |
| `employee_id` | INTEGER |  |  | `employees.id` |
| `request_id` | INTEGER | ✓ |  | `requests.id` |
| `leave_type` | VARCHAR(30) |  |  |  |
| `start_date` | DATE |  |  |  |
| `end_date` | DATE |  |  |  |
| `days` | FLOAT |  |  |  |
| `status` | VARCHAR(20) |  |  |  |

## licenses

النموذج: `models.License` — ترخيٌص تجاري للشركة: رقمه وجهته وانتهاؤه وعدد العمالة المسموح.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER |  |  | `companies.id` |
| `name` | VARCHAR(200) |  |  |  |
| `license_no` | VARCHAR(80) | ✓ |  |  |
| `issuing_authority` | VARCHAR(200) | ✓ |  |  |
| `license_type` | VARCHAR(50) | ✓ |  |  |
| `status` | VARCHAR(20) |  |  |  |
| `issue_date` | DATE | ✓ |  |  |
| `expiry_date` | DATE | ✓ |  |  |
| `allowed_workers` | INTEGER |  |  |  |
| `address` | VARCHAR(300) | ✓ |  |  |

## notification_preferences

النموذج: `models.NotificationPreference` — تفضيل تسليم الإشعارات لكل مستخدم حسب الفئة (قناة مفعّلة أم لا).

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `user_id` | INTEGER |  |  | `users.id` |
| `category` | VARCHAR(60) |  |  |  |
| `channel` | VARCHAR(20) |  |  |  |
| `enabled` | BOOLEAN |  |  |  |

قيود التفرّد: (`user_id`, `category`, `channel`)

## notification_templates

النموذج: `models.NotificationTemplate` — قالب إشعار مُسمّى (FIX-004) — 74 قالبًا تغطي كل أحداث دورة حياة الطلبات والنظام.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `code` | VARCHAR(50) |  |  |  |
| `name` | VARCHAR(200) |  |  |  |
| `category` | VARCHAR(60) |  |  |  |
| `event_type` | VARCHAR(40) |  |  |  |
| `channel_default` | VARCHAR(20) |  |  |  |
| `sla_hours` | INTEGER | ✓ |  |  |
| `body_text` | TEXT |  |  |  |
| `is_active` | BOOLEAN |  |  |  |
| `created_at` | DATETIME |  |  |  |

قيود التفرّد: (`code`)

## payroll_runs

النموذج: `models.PayrollRun` — مسيُّر رواتب شهٍر لشركة: يُجهَّز ثم يُعتمد (من غير مُجهِّزه) ثم يُنهى ثم يُقفَل؛ والتصحيح بمسيّر تسوية.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER |  |  | `companies.id` |
| `period` | VARCHAR(30) |  |  |  |
| `status` | VARCHAR(20) |  |  |  |
| `totals_json` | JSON | ✓ |  |  |
| `created_at` | DATETIME |  |  |  |
| `prepared_by_user_id` | INTEGER | ✓ |  | `users.id` |
| `prepared_at` | DATETIME | ✓ |  |  |
| `approved_by_user_id` | INTEGER | ✓ |  | `users.id` |
| `approved_at` | DATETIME | ✓ |  |  |
| `finalized_by_user_id` | INTEGER | ✓ |  | `users.id` |
| `finalized_at` | DATETIME | ✓ |  |  |
| `locked_by_user_id` | INTEGER | ✓ |  | `users.id` |
| `locked_at` | DATETIME | ✓ |  |  |
| `adjustment_of_run_id` | INTEGER | ✓ |  | `payroll_runs.id` |
| `adjustment_reason` | TEXT | ✓ |  |  |

## permits

النموذج: `models.Permit` — إقامة / إذن عمل.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER |  |  | `companies.id` |
| `employee_id` | INTEGER |  |  | `employees.id` |
| `kind` | VARCHAR(30) |  |  |  |
| `number` | VARCHAR(80) | ✓ |  |  |
| `start_date` | DATE | ✓ |  |  |
| `expiry_date` | DATE | ✓ |  |  |
| `status` | VARCHAR(20) |  |  |  |

## policy_rules

النموذج: `models.PolicyRule` — V2.2 §7 (STR-05) — حدود السياسة بياًنا لا كوًدا.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER | ✓ |  | `companies.id` |
| `key` | VARCHAR(80) |  |  |  |
| `value_json` | JSON |  |  |  |
| `version` | INTEGER |  |  |  |
| `is_active` | BOOLEAN |  |  |  |
| `effective_from` | DATE | ✓ |  |  |
| `effective_to` | DATE | ✓ |  |  |
| `note` | VARCHAR(300) | ✓ |  |  |
| `created_by` | INTEGER | ✓ |  | `users.id` |
| `created_at` | DATETIME |  |  |  |

قيود التفرّد: (`company_id`, `key`, `version`)

## request_approvals

النموذج: `models.RequestApproval` — قراٌر على مرحلٍة من طلب: من قرّر وبأي دور، والقرار وملاحظته — تاريخ الطلب.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `request_id` | INTEGER |  |  | `requests.id` |
| `stage_order` | INTEGER |  |  |  |
| `stage_label` | VARCHAR(150) |  |  |  |
| `approver_role` | VARCHAR(30) | ✓ |  |  |
| `approver_user_id` | INTEGER | ✓ |  | `users.id` |
| `original_user_id` | INTEGER | ✓ |  | `users.id` |
| `decision` | VARCHAR(20) |  |  |  |
| `action` | VARCHAR(30) | ✓ |  |  |
| `decided_at` | DATETIME |  |  |  |
| `note` | TEXT | ✓ |  |  |

## request_documents

النموذج: `models.RequestDocument` — ملفٌّ على طلب: المستند المولَّد، والنسخة الموقّعة، ومرفقات صاحب الطلب والمندوب.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `request_id` | INTEGER |  |  | `requests.id` |
| `kind` | VARCHAR(40) |  |  |  |
| `file_path` | VARCHAR(400) | ✓ |  |  |
| `version` | INTEGER |  |  |  |
| `uploaded_by` | INTEGER | ✓ |  | `users.id` |
| `created_at` | DATETIME |  |  |  |
| `print_status` | VARCHAR(20) |  |  |  |
| `printed_at` | DATETIME | ✓ |  |  |
| `printed_by` | INTEGER | ✓ |  | `users.id` |
| `filed_at` | DATETIME | ✓ |  |  |
| `filed_by` | INTEGER | ✓ |  | `users.id` |
| `od_code` | VARCHAR(10) | ✓ |  |  |
| `lifecycle_status` | VARCHAR(20) |  |  |  |
| `checksum_sha256` | VARCHAR(64) | ✓ |  |  |
| `reference_no` | VARCHAR(40) | ✓ |  |  |
| `signature_version` | INTEGER | ✓ |  |  |
| `template_code` | VARCHAR(50) | ✓ |  |  |
| `template_version` | INTEGER | ✓ |  |  |
| `revoked_at` | DATETIME | ✓ |  |  |
| `revoked_by_user_id` | INTEGER | ✓ |  | `users.id` |
| `revocation_reason` | VARCHAR(300) | ✓ |  |  |

## request_types

النموذج: `models.RequestType` — نوُع طلب: سلسلة اعتماده ومخرجه وقالبه وظهوره للموظف — يُصالَح من الشيفرة عند كل إقلاع.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER | ✓ |  | `companies.id` |
| `code` | VARCHAR(50) |  |  |  |
| `name` | VARCHAR(150) |  |  |  |
| `category` | VARCHAR(60) | ✓ |  |  |
| `approval_chain_json` | JSON |  |  |  |
| `requires_physical_signature` | BOOLEAN |  |  |  |
| `produces_document` | BOOLEAN |  |  |  |
| `template_html` | TEXT | ✓ |  |  |
| `is_active` | BOOLEAN |  |  |  |
| `is_confidential` | BOOLEAN |  |  |  |
| `visible_to_employee` | BOOLEAN |  |  |  |
| `default_template_code` | VARCHAR(20) | ✓ |  |  |
| `form_schema_json` | JSON | ✓ |  |  |

## requests

النموذج: `models.Request` — طلٌب مقدَّم لموظف: نوعه وحمولته وحالته ومرحلته الحالية في سلسلة الاعتماد.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER |  |  | `companies.id` |
| `employee_id` | INTEGER |  |  | `employees.id` |
| `requester_user_id` | INTEGER | ✓ |  | `users.id` |
| `request_type_code` | VARCHAR(50) |  |  |  |
| `payload_json` | JSON |  |  |  |
| `policy_snapshot_json` | JSON | ✓ |  |  |
| `status` | VARCHAR(30) |  |  |  |
| `current_stage` | INTEGER |  |  |  |
| `decision_seq` | INTEGER |  |  |  |
| `created_at` | DATETIME |  |  |  |
| `closed_at` | DATETIME | ✓ |  |  |
| `dedup_fingerprint` | VARCHAR(64) | ✓ |  |  |
| `needs_info_note` | TEXT | ✓ |  |  |
| `cancelled_by_user_id` | INTEGER | ✓ |  | `users.id` |
| `cancelled_at` | DATETIME | ✓ |  |  |
| `cancel_reason` | VARCHAR(300) | ✓ |  |  |

## residency_renewals

النموذج: `models.ResidencyRenewal` — معاملة تجديد الإقامة (مبكر/عادي) بحالاتها المتعددة — DEMO-001/002.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER |  |  | `companies.id` |
| `employee_id` | INTEGER |  |  | `employees.id` |
| `permit_id` | INTEGER | ✓ |  | `permits.id` |
| `renewal_type` | VARCHAR(10) |  |  |  |
| `status` | VARCHAR(30) |  |  |  |
| `reason` | TEXT | ✓ |  |  |
| `notes` | TEXT | ✓ |  |  |
| `reject_reason` | TEXT | ✓ |  |  |
| `days_left_at_request` | INTEGER | ✓ |  |  |
| `created_by` | INTEGER | ✓ |  | `users.id` |
| `created_at` | DATETIME |  |  |  |
| `updated_at` | DATETIME |  |  |  |
| `gov_reference_no` | VARCHAR(60) | ✓ |  |  |
| `fees_amount` | FLOAT | ✓ |  |  |
| `fees_receipt_no` | VARCHAR(60) | ✓ |  |  |
| `new_permit_number` | VARCHAR(60) | ✓ |  |  |
| `new_expiry_date` | DATE | ✓ |  |  |
| `finalized_at` | DATETIME | ✓ |  |  |
| `finalized_by` | INTEGER | ✓ |  | `users.id` |
| `hr_verified_at` | DATETIME | ✓ |  |  |
| `hr_verified_by` | INTEGER | ✓ |  | `users.id` |
| `hr_verification_note` | TEXT | ✓ |  |  |
| `confirmed_data_json` | JSON | ✓ |  |  |

## revoked_tokens

النموذج: `models.RevokedToken` — رمز أُبطل قبل انتهاء صلاحيته.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `jti` | VARCHAR(64) |  | PK |  |
| `user_id` | INTEGER | ✓ |  | `users.id` |
| `expires_at` | DATETIME |  |  |  |
| `revoked_at` | DATETIME |  |  |  |
| `reason` | VARCHAR(40) | ✓ |  |  |

## salary_change_requests

النموذج: `models.SalaryChangeRequest` — R7-G §4 — طلب اعتماد لتغيير الراتب أو تاريخ التعيين أو العقد.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER |  |  | `companies.id` |
| `employee_id` | INTEGER |  |  | `employees.id` |
| `field_name` | VARCHAR(40) |  |  |  |
| `old_value` | VARCHAR(200) | ✓ |  |  |
| `new_value` | VARCHAR(200) |  |  |  |
| `effective_date` | DATE |  |  |  |
| `reason` | TEXT |  |  |  |
| `status` | VARCHAR(20) |  |  |  |
| `proposed_by` | INTEGER |  |  | `users.id` |
| `proposed_at` | DATETIME |  |  |  |
| `approved_by` | INTEGER | ✓ |  | `users.id` |
| `approved_at` | DATETIME | ✓ |  |  |
| `rejected_reason` | TEXT | ✓ |  |  |
| `applied_change_id` | INTEGER | ✓ |  | `employee_field_changes.id` |

## session_activity

النموذج: `models.SessionActivity` — آخر نشاط **لجلسة بعينها** — لا للمستخدم.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `jti` | VARCHAR(64) |  | PK |  |
| `user_id` | INTEGER | ✓ |  | `users.id` |
| `last_activity_at` | DATETIME |  |  |  |
| `expires_at` | DATETIME | ✓ |  |  |
| `impersonated` | BOOLEAN |  |  |  |

## shifts

النموذج: `models.Shift` — ورديُة عمل: بدايتها ونهايتها وأيام العمل ومهلة السماح.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER |  |  | `companies.id` |
| `name` | VARCHAR(100) |  |  |  |
| `start_time` | TIME |  |  |  |
| `end_time` | TIME |  |  |  |
| `work_days` | VARCHAR(30) |  |  |  |
| `grace_minutes` | INTEGER |  |  |  |

## tasks

النموذج: `models.Task` — محرّك المهام/الإشعارات — كل صلاحية قاربت على الانتهاء = مهمة لها مسؤول.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER | ✓ |  | `companies.id` |
| `type` | VARCHAR(40) |  |  |  |
| `title` | VARCHAR(250) |  |  |  |
| `detail` | TEXT | ✓ |  |  |
| `assignee_user_id` | INTEGER | ✓ |  | `users.id` |
| `related_entity_type` | VARCHAR(30) | ✓ |  |  |
| `related_entity_id` | INTEGER | ✓ |  |  |
| `status` | VARCHAR(20) |  |  |  |
| `severity` | VARCHAR(20) |  |  |  |
| `due_date` | DATE | ✓ |  |  |
| `dedup_key` | VARCHAR(120) | ✓ |  |  |
| `created_at` | DATETIME |  |  |  |
| `completed_at` | DATETIME | ✓ |  |  |
| `template_code` | VARCHAR(50) | ✓ |  |  |
| `channel` | VARCHAR(20) | ✓ |  |  |
| `claimed_by_user_id` | INTEGER | ✓ |  | `users.id` |
| `claimed_at` | DATETIME | ✓ |  |  |
| `sla_due_at` | DATETIME | ✓ |  |  |
| `escalated_at` | DATETIME | ✓ |  |  |
| `escalation_task_id` | INTEGER | ✓ |  | `tasks.id` |
| `delivery_attempts` | INTEGER |  |  |  |
| `last_delivery_error` | VARCHAR(400) | ✓ |  |  |
| `last_delivery_at` | DATETIME | ✓ |  |  |

## transfers

النموذج: `models.Transfer` — نقل موظف بين شركتين مع سجل تاريخي.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `employee_id` | INTEGER |  |  | `employees.id` |
| `from_company_id` | INTEGER |  |  | `companies.id` |
| `to_company_id` | INTEGER |  |  | `companies.id` |
| `transferred_by` | INTEGER | ✓ |  | `users.id` |
| `note` | TEXT | ✓ |  |  |
| `created_at` | DATETIME |  |  |  |

## user_company_links

النموذج: `models.UserCompanyLink` — R9 §16 — عضوية user في شركة (لمستخدمي is_cross_company=True).

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `user_id` | INTEGER |  |  | `users.id` |
| `company_id` | INTEGER |  |  | `companies.id` |
| `employee_id` | INTEGER |  |  | `employees.id` |
| `role` | VARCHAR(30) |  |  |  |
| `created_at` | DATETIME |  |  |  |
| `created_by` | INTEGER | ✓ |  | `users.id` |

قيود التفرّد: (`user_id`, `company_id`)

## user_permissions

النموذج: `models.UserPermission` — صلاحيٌة إضافية أُسندت لمستخدمٍ بعينه فوق صلاحيات دوره.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `user_id` | INTEGER |  |  | `users.id` |
| `perm_code` | VARCHAR(50) |  |  |  |
| `expires_at` | DATE | ✓ |  |  |

قيود التفرّد: (`user_id`, `perm_code`)

## user_signature_versions

النموذج: `models.UserSignatureVersion` — QA §12 — سجل نسخ التوقيع غير القابل للتعديل (immutable evidence trail).

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `user_id` | INTEGER |  |  | `users.id` |
| `version` | INTEGER |  |  |  |
| `file_path` | VARCHAR(400) | ✓ |  |  |
| `checksum_sha256` | VARCHAR(64) | ✓ |  |  |
| `actor_user_id` | INTEGER | ✓ |  | `users.id` |
| `actor_role` | VARCHAR(30) | ✓ |  |  |
| `company_id` | INTEGER | ✓ |  | `companies.id` |
| `branch_id` | INTEGER | ✓ |  | `branches.id` |
| `stage` | VARCHAR(30) |  |  |  |
| `reason` | VARCHAR(300) | ✓ |  |  |
| `approved_by_user_id` | INTEGER | ✓ |  | `users.id` |
| `approver_role` | VARCHAR(30) | ✓ |  |  |
| `approved_at` | DATETIME | ✓ |  |  |
| `correlation_id` | VARCHAR(80) | ✓ |  |  |
| `reference_no` | VARCHAR(60) | ✓ |  |  |
| `before_json` | JSON | ✓ |  |  |
| `after_json` | JSON | ✓ |  |  |
| `created_at` | DATETIME |  |  |  |

قيود التفرّد: (`user_id`, `version`)

## user_tour_states

النموذج: `models.UserTourState` — R5 §3 — حالة إكمال الجولة التعليمية لكل (مستخدم × مفتاح جولة).

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `user_id` | INTEGER |  |  | `users.id` |
| `tour_key` | VARCHAR(60) |  |  |  |
| `completed_at` | DATETIME |  |  |  |
| `skipped` | BOOLEAN |  |  |  |
| `step_reached` | INTEGER | ✓ |  |  |

قيود التفرّد: (`user_id`, `tour_key`)

## users

النموذج: `models.User` — حساُب دخول لشخٍص واحد: دوره وشركته وربطه بملف موظف وحالة التحقق الثنائي.

| العمود | النوع | فارغ؟ | مفتاح | يشير إلى |
|---|---|:-:|:-:|---|
| `id` | INTEGER |  | PK |  |
| `company_id` | INTEGER | ✓ |  | `companies.id` |
| `civil_id` | VARCHAR(20) |  |  |  |
| `password_hash` | VARCHAR(255) |  |  |  |
| `full_name` | VARCHAR(200) | ✓ |  |  |
| `email` | VARCHAR(200) | ✓ |  |  |
| `phone` | VARCHAR(30) | ✓ |  |  |
| `role` | VARCHAR(30) |  |  |  |
| `scope_level` | VARCHAR(10) |  |  |  |
| `scope_branch_id` | INTEGER | ✓ |  | `branches.id` |
| `employee_id` | INTEGER | ✓ |  | `employees.id` |
| `is_active` | BOOLEAN |  |  |  |
| `status` | VARCHAR(20) |  |  |  |
| `must_change_password` | BOOLEAN |  |  |  |
| `failed_attempts` | INTEGER |  |  |  |
| `locked_until` | DATETIME | ✓ |  |  |
| `last_login` | DATETIME | ✓ |  |  |
| `tokens_valid_after` | DATETIME | ✓ |  |  |
| `last_activity_at` | DATETIME | ✓ |  |  |
| `totp_secret` | VARCHAR(64) | ✓ |  |  |
| `totp_confirmed` | BOOLEAN |  |  |  |
| `totp_recovery_hashes` | JSON | ✓ |  |  |
| `totp_last_used_at` | DATETIME | ✓ |  |  |
| `created_at` | DATETIME |  |  |  |
| `signature_path` | VARCHAR(400) | ✓ |  |  |
| `signature_updated_at` | DATETIME | ✓ |  |  |
| `pending_signature_path` | VARCHAR(400) | ✓ |  |  |
| `pending_signature_uploaded_at` | DATETIME | ✓ |  |  |
| `pending_signature_reason` | VARCHAR(300) | ✓ |  |  |
| `signature_version` | INTEGER |  |  |  |
| `is_cross_company` | BOOLEAN |  |  |  |
| `avatar_path` | VARCHAR(400) | ✓ |  |  |
| `avatar_updated_at` | DATETIME | ✓ |  |  |
