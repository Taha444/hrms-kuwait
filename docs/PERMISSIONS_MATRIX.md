# مصفوفة الصلاحيات (DLV-46)

> **مولَّدة من الشيفرة** بـ`backend/scripts/permissions_matrix.py` — لا تُحرَّر باليد.
> ويحرسها اختبارٌ يسقط إن خالفت الشيفرة: من يغيّر صلاحيةً يُعيد التوليد.

الصلاحيات أدناه **افتراضية لكل دور**؛ ويمكن إسناد صلاحيةٍ إضافية لمستخدمٍ
بعينه من شاشة المستخدمين. والعزل بين الشركات ونطاق الفروع يُفرضان فوقها على الخادم.

## 1. الأدوار × الصلاحيات

| الصلاحية | صاحب الشركة | المدير العام | المحاسب | المسؤول المباشر | شؤون الموظفين/القانونية | المندوب | admin_employee | الموظف | الإدارة العليا |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| اعتماد الشهادات والخطابات (`approve_certificate`) |  | ✓ |  |  | ✓ |  |  |  | ✓ |
| اعتماد العقود وإنهاء الخدمة (`approve_exit`) |  | ✓ | ✓ |  | ✓ |  |  |  | ✓ |
| اعتماد الطلبات المالية (`approve_finance`) |  | ✓ | ✓ | ✓ |  |  |  |  | ✓ |
| اعتماد الطلبات العامة والنماذج الإدارية (`approve_general`) |  | ✓ | ✓ | ✓ | ✓ | ✓ |  |  | ✓ |
| اعتماد المعاملات الحكومية والإقامات (`approve_government`) |  | ✓ |  | ✓ | ✓ | ✓ |  |  | ✓ |
| اعتماد الشكاوى والتظلمات (`approve_grievance`) |  | ✓ |  |  | ✓ |  |  |  | ✓ |
| اعتماد الحضور والإجازات (`approve_leave`) |  | ✓ | ✓ | ✓ | ✓ | ✓ |  |  | ✓ |
| اعتماد وإقفال وقفل مسيّر الرواتب (`approve_payroll`) |  | ✓ | ✓ |  |  |  |  |  | ✓ |
| اعتماد بيانات الموظف والتطوير الوظيفي (`approve_personnel`) |  | ✓ | ✓ | ✓ | ✓ |  |  |  | ✓ |
| اعتماد الطلبات (عام — مهجور) (`approve_request`) |  |  |  |  |  |  |  |  | ✓ |
| اعتماد إنهاء خدمة موظف (سلطة مستقلة عن التحضير) (`approve_termination`) |  | ✓ | ✓ |  |  |  |  |  | ✓ |
| حساب مكافأة نهاية الخدمة (`calculate_eos`) |  |  | ✓ |  | ✓ |  |  |  | ✓ |
| إتمام خطوات التحقق (`complete_validation`) |  | ✓ | ✓ | ✓ | ✓ |  |  |  | ✓ |
| إضافة موظف (`create_employee`) |  | ✓ |  |  | ✓ |  |  |  | ✓ |
| حذف موظف (`delete_employee`) |  | ✓ |  |  |  |  |  |  | ✓ |
| تعديل الراتب الفعلي (`edit_actual_salary`) |  |  | ✓ |  |  |  |  |  | ✓ |
| تعديل موظف (`edit_employee`) |  | ✓ |  |  | ✓ |  |  |  | ✓ |
| تصدير التقارير (`export_reports`) | ✓ | ✓ | ✓ | ✓ |  |  |  |  | ✓ |
| إدارة الحضور والانصراف (`manage_attendance`) |  |  |  |  | ✓ |  |  |  | ✓ |
| إدارة الفروع والمواقع (`manage_branches`) |  | ✓ |  |  |  |  |  |  | ✓ |
| إدارة جميع الشركات (إدارة عليا) (`manage_companies`) |  |  |  |  |  |  |  |  | ✓ |
| إدارة بيانات الشركة (`manage_company`) | ✓ | ✓ |  |  |  |  |  |  | ✓ |
| إدارة الخصومات (`manage_deductions`) |  |  | ✓ |  | ✓ |  |  |  | ✓ |
| إدارة الإدارات/الأقسام (`manage_departments`) |  | ✓ |  |  |  |  |  |  | ✓ |
| إدارة الإجازات (`manage_leaves`) |  | ✓ |  |  | ✓ |  |  |  | ✓ |
| إدارة التراخيص (`manage_licenses`) |  |  |  |  |  | ✓ |  |  | ✓ |
| إدارة الإقامات وأذونات العمل (`manage_permits`) |  |  |  |  |  | ✓ |  |  | ✓ |
| إدارة أنواع الطلبات وسلاسل الموافقات (`manage_request_types`) |  |  |  |  |  |  |  |  | ✓ |
| إدارة المهام (`manage_tasks`) |  | ✓ |  |  |  | ✓ |  |  | ✓ |
| إدارة الصيغ والنماذج وطباعتها (`manage_templates`) |  |  |  |  | ✓ |  |  |  | ✓ |
| إدارة المستخدمين والصلاحيات (`manage_users`) |  | ✓ |  |  |  |  |  |  | ✓ |
| تجاوز إداري: اعتماد مرحلة ليست لصاحبها (يُسجَّل) (`override_approval`) |  |  |  |  |  |  |  |  | ✓ |
| إجراءات المندوب (تجديد/إذن مغادرة) (`process_delegate_tasks`) |  |  |  |  |  | ✓ |  |  | ✓ |
| تسجيل الحضور (خدمة ذاتية) (`record_attendance`) |  |  | ✓ | ✓ |  |  |  | ✓ | ✓ |
| تشغيل مسيّر الرواتب (`run_payroll`) |  |  | ✓ |  |  |  |  |  | ✓ |
| تقديم الطلبات (خدمة ذاتية) (`submit_request`) |  |  | ✓ | ✓ | ✓ | ✓ |  | ✓ | ✓ |
| إنهاء خدمة موظف (`terminate_employee`) |  |  |  |  | ✓ |  |  |  | ✓ |
| نقل موظف بين الشركات (`transfer_employee`) |  |  |  |  |  |  |  |  | ✓ |
| رفع المستندات (`upload_documents`) |  | ✓ |  |  | ✓ | ✓ |  |  | ✓ |
| عرض الراتب الفعلي (`view_actual_salary`) | ✓ |  | ✓ |  |  |  |  |  | ✓ |
| عرض الحضور (`view_attendance`) | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  | ✓ |
| عرض سجل التدقيق (`view_audit`) | ✓ |  |  |  |  |  |  |  | ✓ |
| عرض وتنزيل المستندات (`view_documents`) | ✓ | ✓ |  |  | ✓ | ✓ |  |  | ✓ |
| عرض الموظفين (`view_employee`) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |  | ✓ |
| عرض الرواتب (`view_payroll`) | ✓ | ✓ | ✓ |  |  |  |  |  | ✓ |
| عرض التقارير (`view_reports`) | ✓ | ✓ | ✓ | ✓ |  |  |  |  | ✓ |
| عرض المهام والتنبيهات (`view_tasks`) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  | ✓ | ✓ |

## 2. قواعد الأدوار الخاصة

- **التقديم نيابةً عن موظف:** المندوب، شؤون الموظفين/القانونية
- **العابرون للشركات:** صاحب الشركة، الإدارة العليا
- **التحقق الثنائي إلزامي:** صاحب الشركة
- **لا اعتماد ذاتي لأي دور** (قرار المالك 2026-09-17)، ومنه super_admin.
- **مسؤول الفرع** مقيَّدٌ بفروعه على الخادم في القوائم والبحث والحضور والمهام.

## 3. النقاط المقيَّدة بدورٍ لا بصلاحية

### الإدارة العليا التقنية وحدها (super_admin)

- `DELETE /api/feature-flags/{flag_id}`
- `DELETE /api/templates/{tpl_id}`
- `GET /api/admin/break-glass`
- `GET /api/admin/db-status`
- `GET /api/admin/reset-status`
- `GET /api/admin/system-info`
- `GET /api/feature-flags/raw`
- `GET /api/feature-flags/registry`
- `GET /api/feature-flags`
- `POST /api/admin/break-glass/close`
- `POST /api/admin/break-glass`
- `POST /api/admin/ensure-catalog`
- `POST /api/admin/reset-demo-data`
- `POST /api/eos/calculate`
- `POST /api/feature-flags`
- `POST /api/payroll/runs/{run_id}/reopen`
- `POST /api/users/{user_id}/impersonate`

### صاحب الشركات (ومعه super_admin)

- `DELETE /api/users/{user_id}/company-links/{link_id}`
- `POST /api/companies/{company_id}/status`
- `POST /api/companies`
- `POST /api/templates/{tpl_id}/apply-system-version`
- `POST /api/users/{user_id}/2fa/reset`
- `POST /api/users/{user_id}/company-links`
- `POST /api/users/{user_id}/enable-cross-company`

### صاحب الشركات أو من يملك «إدارة المستخدمين»

- `GET /api/users/{user_id}/company-links`

## 4. النقاط التي تحرسها كل صلاحية

### اعتماد الشهادات والخطابات (`approve_certificate`)

- `GET /api/requests/inbox` (أيٌّ منها)
- `POST /api/requests/{req_id}/appointment` (أيٌّ منها)
- `POST /api/requests/{req_id}/decide` (أيٌّ منها)
- `POST /api/requests/{req_id}/received` (أيٌّ منها)

### اعتماد العقود وإنهاء الخدمة (`approve_exit`)

- `GET /api/requests/inbox` (أيٌّ منها)
- `POST /api/requests/{req_id}/appointment` (أيٌّ منها)
- `POST /api/requests/{req_id}/decide` (أيٌّ منها)
- `POST /api/requests/{req_id}/received` (أيٌّ منها)

### اعتماد الطلبات المالية (`approve_finance`)

- `GET /api/requests/inbox` (أيٌّ منها)
- `POST /api/requests/{req_id}/appointment` (أيٌّ منها)
- `POST /api/requests/{req_id}/decide` (أيٌّ منها)
- `POST /api/requests/{req_id}/received` (أيٌّ منها)

### اعتماد الطلبات العامة والنماذج الإدارية (`approve_general`)

- `GET /api/requests/inbox` (أيٌّ منها)
- `POST /api/requests/{req_id}/appointment` (أيٌّ منها)
- `POST /api/requests/{req_id}/decide` (أيٌّ منها)
- `POST /api/requests/{req_id}/received` (أيٌّ منها)

### اعتماد المعاملات الحكومية والإقامات (`approve_government`)

- `GET /api/requests/inbox` (أيٌّ منها)
- `POST /api/requests/{req_id}/appointment` (أيٌّ منها)
- `POST /api/requests/{req_id}/decide` (أيٌّ منها)
- `POST /api/requests/{req_id}/received` (أيٌّ منها)

### اعتماد الشكاوى والتظلمات (`approve_grievance`)

- `GET /api/requests/inbox` (أيٌّ منها)
- `POST /api/requests/{req_id}/appointment` (أيٌّ منها)
- `POST /api/requests/{req_id}/decide` (أيٌّ منها)
- `POST /api/requests/{req_id}/received` (أيٌّ منها)

### اعتماد الحضور والإجازات (`approve_leave`)

- `GET /api/requests/inbox` (أيٌّ منها)
- `POST /api/requests/{req_id}/appointment` (أيٌّ منها)
- `POST /api/requests/{req_id}/decide` (أيٌّ منها)
- `POST /api/requests/{req_id}/received` (أيٌّ منها)

### اعتماد وإقفال وقفل مسيّر الرواتب (`approve_payroll`)

- `POST /api/payroll/runs/{run_id}/approve`
- `POST /api/payroll/runs/{run_id}/finalize`
- `POST /api/payroll/runs/{run_id}/lock`

### اعتماد بيانات الموظف والتطوير الوظيفي (`approve_personnel`)

- `GET /api/requests/inbox` (أيٌّ منها)
- `POST /api/requests/{req_id}/appointment` (أيٌّ منها)
- `POST /api/requests/{req_id}/decide` (أيٌّ منها)
- `POST /api/requests/{req_id}/received` (أيٌّ منها)

### اعتماد الطلبات (عام — مهجور) (`approve_request`)

- `GET /api/requests/inbox` (أيٌّ منها)
- `POST /api/requests/{req_id}/appointment` (أيٌّ منها)
- `POST /api/requests/{req_id}/decide` (أيٌّ منها)
- `POST /api/requests/{req_id}/received` (أيٌّ منها)

### اعتماد إنهاء خدمة موظف (سلطة مستقلة عن التحضير) (`approve_termination`)

- `POST /api/employees/{emp_id}/terminate/approve`
- `POST /api/eos/cases/{case_id}/approve`

### حساب مكافأة نهاية الخدمة (`calculate_eos`)

- `GET /api/reports/eos/{emp_id}`
- `POST /api/eos/cases/{case_id}/calculate`
- `POST /api/eos/for-employee`
- `POST /api/eos/leave-balance`

### إتمام خطوات التحقق (`complete_validation`)

- `GET /api/requests/inbox` (أيٌّ منها)
- `POST /api/requests/{req_id}/appointment` (أيٌّ منها)
- `POST /api/requests/{req_id}/decide` (أيٌّ منها)
- `POST /api/requests/{req_id}/received` (أيٌّ منها)

### إضافة موظف (`create_employee`)

- `POST /api/employees`

### حذف موظف (`delete_employee`)

- — لا نقطة تحرسها مباشرةً (تُقرأ داخل النقاط أو في الواجهة).

### تعديل الراتب الفعلي (`edit_actual_salary`)

- `POST /api/employees/{emp_id}/actual-salary`

### تعديل موظف (`edit_employee`)

- `GET /api/employees/{emp_id}/license-options`
- `POST /api/employees/{emp_id}/apply-ocr`
- `POST /api/employees/{emp_id}/events`
- `POST /api/employees/{emp_id}/salary-change-request`
- `POST /api/employees/{emp_id}/status`
- `PUT /api/employees/{emp_id}`

### تصدير التقارير (`export_reports`)

- `GET /api/reports/attendance`
- `GET /api/reports/employees`

### إدارة الحضور والانصراف (`manage_attendance`)

- `DELETE /api/attendance/holidays/{holiday_id}`
- `POST /api/attendance/close-month`
- `POST /api/attendance/holidays`
- `POST /api/attendance/reopen-month`
- `POST /api/employees/{emp_id}/attendance-mode`
- `POST /api/employees/{emp_id}/attendance-policy`
- `POST /api/shifts`
- `PUT /api/attendance/{record_id}/correct`
- `PUT /api/shifts/{shift_id}`

### إدارة الفروع والمواقع (`manage_branches`)

- `DELETE /api/branches/{branch_id}`
- `GET /api/branches/{branch_id}/kiosk-url`
- `POST /api/branches/{branch_id}/archive`
- `POST /api/branches/{branch_id}/kiosk-key/rotate`
- `POST /api/branches/{branch_id}/restore`
- `POST /api/branches/{branch_id}/supervisors/{user_id}`
- `POST /api/branches`
- `POST /api/companies/{company_id}/headquarters`
- `PUT /api/branches/{branch_id}`

### إدارة جميع الشركات (إدارة عليا) (`manage_companies`)

- — لا نقطة تحرسها مباشرةً (تُقرأ داخل النقاط أو في الواجهة).

### إدارة بيانات الشركة (`manage_company`)

- `PUT /api/archive/company/info`
- `PUT /api/companies/{company_id}`

### إدارة الخصومات (`manage_deductions`)

- — لا نقطة تحرسها مباشرةً (تُقرأ داخل النقاط أو في الواجهة).

### إدارة الإدارات/الأقسام (`manage_departments`)

- `POST /api/departments`

### إدارة الإجازات (`manage_leaves`)

- — لا نقطة تحرسها مباشرةً (تُقرأ داخل النقاط أو في الواجهة).

### إدارة التراخيص (`manage_licenses`)

- `GET /api/licenses`
- `GET /api/pro/government`
- `POST /api/licenses`
- `POST /api/pro/licenses/{license_id}/renew`

### إدارة الإقامات وأذونات العمل (`manage_permits`)

- `GET /api/pro/notes`
- `GET /api/pro/permits`
- `POST /api/employees/{emp_id}/permits`
- `POST /api/pro/permits/{permit_id}/renew`

### إدارة أنواع الطلبات وسلاسل الموافقات (`manage_request_types`)

- `POST /api/requests/types`

### إدارة المهام (`manage_tasks`)

- `POST /api/tasks/cleanup-orphans`
- `POST /api/tasks/run-digest`
- `POST /api/tasks/run-scan`
- `POST /api/tasks/run-sla-scan`
- `POST /api/tasks/{task_id}/retry-delivery`

### إدارة الصيغ والنماذج وطباعتها (`manage_templates`)

- `GET /api/templates/placeholders`
- `POST /api/documents/requests/{doc_id}/revoke`
- `POST /api/templates/{tpl_id}/company-generate`
- `POST /api/templates/{tpl_id}/company-preview`
- `POST /api/templates/{tpl_id}/generate`
- `POST /api/templates/{tpl_id}/preview`
- `POST /api/templates/{tpl_id}/render`

### إدارة المستخدمين والصلاحيات (`manage_users`)

- `DELETE /api/signatories/{sig_id}`
- `DELETE /api/users/{user_id}/permissions/{perm_code}`
- `GET /api/users/catalog`
- `GET /api/users/orphaned`
- `GET /api/users/permission-matrix`
- `GET /api/users/{user_id}/matrix`
- `GET /api/users/{user_id}/permissions`
- `GET /api/users`
- `POST /api/auth/reset-password`
- `POST /api/employees/backfill-employee-no`
- `POST /api/signatories`
- `POST /api/users/apply-template/{user_id}/{template_code}`
- `POST /api/users/auto-link-employees`
- `POST /api/users/copy-permissions`
- `POST /api/users/{user_id}/identity`
- `POST /api/users/{user_id}/link-employee`
- `POST /api/users/{user_id}/matrix/reset`
- `POST /api/users/{user_id}/matrix`
- `POST /api/users/{user_id}/permissions`
- `POST /api/users/{user_id}/scope`
- `POST /api/users/{user_id}/status`
- `POST /api/users/{user_id}/toggle`
- `POST /api/users`
- `PUT /api/signatories/{sig_id}`

### تجاوز إداري: اعتماد مرحلة ليست لصاحبها (يُسجَّل) (`override_approval`)

- — لا نقطة تحرسها مباشرةً (تُقرأ داخل النقاط أو في الواجهة).

### إجراءات المندوب (تجديد/إذن مغادرة) (`process_delegate_tasks`)

- `GET /api/requests/inbox` (أيٌّ منها)
- `POST /api/pro/notes`
- `POST /api/requests/{req_id}/decide` (أيٌّ منها)

### تسجيل الحضور (خدمة ذاتية) (`record_attendance`)

- `POST /api/attendance/check-in`
- `POST /api/attendance/validate-gps`
- `POST /api/attendance/validate-qr`

### تشغيل مسيّر الرواتب (`run_payroll`)

- `POST /api/eos/cases/{case_id}/settle`
- `POST /api/payroll/run`
- `POST /api/payroll/runs/{run_id}/adjustment`
- `POST /api/payroll/runs/{run_id}/cancel`

### تقديم الطلبات (خدمة ذاتية) (`submit_request`)

- `POST /api/requests`

### إنهاء خدمة موظف (`terminate_employee`)

- `POST /api/employees/{emp_id}/terminate/cancel`
- `POST /api/employees/{emp_id}/terminate/clearance`
- `POST /api/employees/{emp_id}/terminate/execute`
- `POST /api/employees/{emp_id}/terminate`
- `POST /api/eos/cases/{case_id}/clearance`
- `POST /api/eos/cases/{case_id}/file`
- `POST /api/eos/cases/{case_id}/notice`
- `POST /api/eos/cases/{case_id}/print`
- `POST /api/eos/cases`

### نقل موظف بين الشركات (`transfer_employee`)

- `POST /api/employees/{emp_id}/transfer`

### رفع المستندات (`upload_documents`)

- `DELETE /api/archive/custom-doc/{doc_id}`
- `GET /api/documents/ocr-status`
- `GET /api/employees/gov-contract-readiness`
- `PATCH /api/documents/{doc_id}/expiry`
- `POST /api/archive/custom-doc/{doc_id}/replace`
- `POST /api/archive/custom-doc`
- `POST /api/documents/ocr-preview`
- `POST /api/documents/upload`
- `POST /api/employees/{emp_id}/company-contract/generate`
- `POST /api/employees/{emp_id}/gov-contract/generate`
- `POST /api/requests/{req_id}/document/{kind}/mark-filed`
- `PUT /api/archive/custom-doc/{doc_id}`

### عرض الراتب الفعلي (`view_actual_salary`)

- — لا نقطة تحرسها مباشرةً (تُقرأ داخل النقاط أو في الواجهة).

### عرض الحضور (`view_attendance`)

- `GET /api/attendance/branch/{branch_id}`
- `GET /api/attendance/close-status`
- `GET /api/attendance/holidays`
- `GET /api/attendance/review`
- `GET /api/employees/attendance-policy/pending`

### عرض سجل التدقيق (`view_audit`)

- `GET /api/audit`

### عرض وتنزيل المستندات (`view_documents`)

- `GET /api/archive/branch/{branch_id}`
- `GET /api/archive/company`
- `GET /api/archive/custom-doc/{doc_id}/download`
- `GET /api/archive/custom-doc/{doc_id}/history`
- `GET /api/documents/history`
- `GET /api/documents/latest`
- `GET /api/documents/{doc_id}/download`
- `GET /api/signatories/resolve`
- `GET /api/signatories`

### عرض الموظفين (`view_employee`)

- `GET /api/employees/license-mismatch`
- `GET /api/employees/salary-change-requests/pending`
- `GET /api/employees/{emp_id}/change-history`
- `GET /api/employees/{emp_id}/events`
- `GET /api/employees/{emp_id}/profile`
- `GET /api/employees/{emp_id}/salary-change-requests`
- `GET /api/employees/{emp_id}/timeline`
- `GET /api/employees/{emp_id}`
- `GET /api/employees`
- `GET /api/eos/cases/{case_id}`
- `GET /api/eos/cases`

### عرض الرواتب (`view_payroll`)

- `GET /api/payroll/preview`
- `GET /api/payroll/runs/{run_id}`
- `GET /api/payroll/runs`
- `GET /api/reports/payroll/{run_id}`

### عرض التقارير (`view_reports`)

- `GET /api/reports/workflow-operations`

### عرض المهام والتنبيهات (`view_tasks`)

- — لا نقطة تحرسها مباشرةً (تُقرأ داخل النقاط أو في الواجهة).
