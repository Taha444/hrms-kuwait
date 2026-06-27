// نظام ترجمة ثنائي اللغة (عربي/إنجليزي) — تبديل اللغة يقلب الواجهة بالكامل (RTL/LTR)
import { createContext, useContext, useEffect, useState, ReactNode } from "react";

type Lang = "ar" | "en";

const dict: Record<string, { ar: string; en: string }> = {
  app_name: { ar: "نظام الموارد البشرية", en: "HRMS Kuwait" },
  app_tagline: { ar: "الكويت · منصّة متعددة الشركات", en: "Kuwait · Multi-company Platform" },
  login: { ar: "تسجيل الدخول", en: "Login" },
  logout: { ar: "تسجيل الخروج", en: "Logout" },
  civil_id: { ar: "الرقم المدني", en: "Civil ID" },
  password: { ar: "كلمة المرور", en: "Password" },
  login_failed: { ar: "تعذّر تسجيل الدخول", en: "Login failed" },
  demo_hint: { ar: "تجريبي — إدارة عليا:", en: "Demo — Super Admin:" },
  // الأقسام والتنقّل
  main_section: { ar: "الرئيسية", en: "Main" },
  resources_section: { ar: "الموارد", en: "Resources" },
  admin_section: { ar: "الإدارة", en: "Administration" },
  dashboard: { ar: "لوحة التحكم", en: "Dashboard" },
  tasks: { ar: "المهام", en: "Tasks" },
  requests: { ar: "الطلبات", en: "Requests" },
  employees: { ar: "الموظفون", en: "Employees" },
  structure: { ar: "هيكل الشركة", en: "Company Structure" },
  pro: { ar: "معاملات المندوب", en: "PRO Transactions" },
  branch_qr: { ar: "الفروع وشاشات QR", en: "Branches & Kiosk" },
  templates_nav: { ar: "الصيغ والنماذج", en: "Templates" },
  payroll: { ar: "الرواتب", en: "Payroll" },
  eos: { ar: "نهاية الخدمة", en: "End of Service" },
  reports: { ar: "التقارير", en: "Reports" },
  archive: { ar: "الأرشيف", en: "Archive" },
  attendance: { ar: "الحضور", en: "Attendance" },
  attendance_review: { ar: "مراجعة الحضور", en: "Attendance Review" },
  audit: { ar: "سجل التدقيق", en: "Audit Log" },
  operations: { ar: "مركز العمليات", en: "Operations Center" },
  companies: { ar: "الشركات", en: "Companies" },
  users: { ar: "المستخدمون والصلاحيات", en: "Users & Permissions" },
  change_password: { ar: "تغيير كلمة المرور", en: "Change Password" },
  // أفعال شائعة
  save: { ar: "حفظ", en: "Save" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  submit: { ar: "إرسال", en: "Submit" },
  search: { ar: "بحث", en: "Search" },
  add: { ar: "إضافة", en: "Add" },
  edit: { ar: "تعديل", en: "Edit" },
  delete: { ar: "حذف", en: "Delete" },
  view: { ar: "عرض", en: "View" },
  loading: { ar: "جارِ التحميل…", en: "Loading…" },
  no_data: { ar: "لا توجد بيانات", en: "No data" },
  status: { ar: "الحالة", en: "Status" },
  language: { ar: "اللغة", en: "Language" },
  // لوحة التحكم
  dash_eyebrow: { ar: "لوحة التحكم", en: "Dashboard" },
  dash_welcome: { ar: "مرحبًا", en: "Welcome" },
  dash_sub: { ar: "نظرة سريعة على المؤشرات الخاصة بنطاقك", en: "A quick look at your key indicators" },
  kpi_companies: { ar: "عدد الشركات", en: "Companies" },
  kpi_employees: { ar: "الموظفون النشطون", en: "Active Employees" },
  kpi_branches: { ar: "الفروع", en: "Branches" },
  kpi_expiring_permits: { ar: "إقامات/أذونات قرب الانتهاء", en: "Permits Expiring Soon" },
  kpi_expiring_residencies: { ar: "إقامات قرب الانتهاء", en: "Residencies Expiring" },
  kpi_expiring_work_permits: { ar: "أذونات عمل قرب الانتهاء", en: "Work Permits Expiring" },
  kpi_expiring_licenses: { ar: "تراخيص قرب الانتهاء", en: "Licenses Expiring" },
  kpi_pending_requests: { ar: "طلبات بانتظار الاعتماد", en: "Pending Requests" },
  kpi_on_leave: { ar: "في إجازة اليوم", en: "On Leave Today" },
  kpi_open_tasks: { ar: "مهامي المفتوحة", en: "My Open Tasks" },
  kpi_my_tasks: { ar: "مهامي وإشعاراتي", en: "My Tasks & Notifications" },
  kpi_my_requests: { ar: "طلباتي النشطة", en: "My Active Requests" },
  emp_portal_sub: { ar: "بوابتك الشخصية — مهامك وطلباتك وإشعاراتك", en: "Your portal — tasks, requests and notifications" },
  new_request: { ar: "تقديم طلب", en: "New Request" },
  new_request_sub: { ar: "إجازة · شهادة راتب", en: "Leave · Salary Certificate" },
  // المهام
  tasks_run_scan: { ar: "تشغيل المسح اليومي", en: "Run Daily Scan" },
  tasks_all_categories: { ar: "كل التصنيفات", en: "All Categories" },
  tasks_open: { ar: "المفتوحة", en: "Open" },
  tasks_done: { ar: "المنجزة", en: "Done" },
  tasks_dismissed: { ar: "المتجاهَلة", en: "Dismissed" },
  col_type: { ar: "النوع", en: "Type" },
  col_title: { ar: "العنوان", en: "Title" },
  col_detail: { ar: "التفاصيل", en: "Detail" },
  col_severity: { ar: "الأهمية", en: "Severity" },
  act_complete: { ar: "إنجاز", en: "Complete" },
  act_dismiss: { ar: "تجاهل", en: "Dismiss" },
  cat_system: { ar: "النظام", en: "System" },
  cat_government: { ar: "حكومية", en: "Government" },
  cat_hr: { ar: "موارد بشرية", en: "HR" },
  cat_approvals: { ar: "موافقات", en: "Approvals" },
  scan_generated: { ar: "تم توليد {n} مهمة", en: "Generated {n} tasks" },
  // الشركة المختارة
  pick_company: { ar: "اختر الشركة", en: "Select Company" },
  all_companies: { ar: "كل الشركات", en: "All Companies" },
  all_branches: { ar: "كل الفروع", en: "All Branches" },
  all_departments: { ar: "كل الإدارات", en: "All Departments" },
  // الموظفون
  emp_new: { ar: "موظف جديد", en: "New Employee" },
  emp_search_ph: { ar: "بحث: الاسم / الرقم المدني / رقم الموظف / رقم الإقامة", en: "Search: name / civil ID / employee no / residency no" },
  add_department: { ar: "+ إدارة", en: "+ Department" },
  add_department_prompt: { ar: "اسم الإدارة/القسم الجديد:", en: "New department name:" },
  col_name: { ar: "الاسم", en: "Name" },
  col_job: { ar: "المسمى", en: "Job Title" },
  col_nationality: { ar: "الجنسية", en: "Nationality" },
  col_salary: { ar: "الراتب", en: "Salary" },
  col_attendance: { ar: "الحضور", en: "Attendance" },
  col_profile: { ar: "الملف", en: "Profile" },
  col_employee: { ar: "الموظف", en: "Employee" },
  col_number: { ar: "الرقم", en: "Number" },
  col_expiry: { ar: "الانتهاء", en: "Expiry" },
  col_remaining: { ar: "المتبقّي", en: "Remaining" },
  fld_basic_salary: { ar: "الراتب الأساسي", en: "Basic Salary" },
  fld_job_title: { ar: "المسمى الوظيفي", en: "Job Title" },
  fld_hire_date: { ar: "تاريخ التعيين", en: "Hire Date" },
  fld_att_mode: { ar: "نمط الحضور", en: "Attendance Mode" },
  fld_branch: { ar: "الفرع", en: "Branch" },
  fld_department: { ar: "الإدارة/القسم", en: "Department" },
  fld_gender: { ar: "الجنس", en: "Gender" },
  fld_dob: { ar: "تاريخ الميلاد", en: "Date of Birth" },
  fld_passport: { ar: "رقم الجواز", en: "Passport No" },
  opt_choose: { ar: "— اختر —", en: "— Select —" },
  att_none: { ar: "بدون", en: "None" }, att_both: { ar: "كلاهما", en: "Both" },
  gender_male: { ar: "ذكر", en: "Male" }, gender_female: { ar: "أنثى", en: "Female" },
  page_prev: { ar: "السابق", en: "Previous" }, page_next: { ar: "التالي", en: "Next" },
  page_of: { ar: "صفحة {p} من {n}", en: "Page {p} of {n}" },
  // الطلبات
  my_requests: { ar: "طلباتي", en: "My Requests" },
  approval_inbox: { ar: "بانتظار موافقتي", en: "Approval Inbox" },
  req_path: { ar: "المسار", en: "Progress" },
  req_type: { ar: "نوع الطلب", en: "Request Type" },
  req_from: { ar: "من تاريخ", en: "From" }, req_to: { ar: "إلى تاريخ", en: "To" },
  req_days: { ar: "عدد الأيام", en: "Days" }, req_reason: { ar: "السبب", en: "Reason" },
  req_addressed: { ar: "الجهة المستفيدة (موجَّه إلى)", en: "Addressed To" },
  req_purpose: { ar: "الغرض", en: "Purpose" },
  // مركز العمليات
  ops_eyebrow: { ar: "المتابعة والامتثال", en: "Compliance & Monitoring" },
  ops_sub: { ar: "كل ما يحتاج إجراءً في مكان واحد — إقامات وتراخيص وطلبات ومهام", en: "Everything needing action in one place" },
  ops_expired: { ar: "منتهية (مخالفة)", en: "Expired (violation)" },
  ops_critical: { ar: "حرجة (≤30 يوم)", en: "Critical (≤30 days)" },
  ops_warning: { ar: "تحذير (≤90 يوم)", en: "Warning (≤90 days)" },
  ops_gov_tasks: { ar: "مهام حكومية مفتوحة", en: "Open Government Tasks" },
  ops_permits_title: { ar: "الإقامات وأذونات العمل القريبة من الانتهاء", en: "Permits Expiring Soon" },
  ops_licenses_title: { ar: "التراخيص القريبة من الانتهاء", en: "Licenses Expiring Soon" },
  ops_manage: { ar: "إدارة المعاملات ←", en: "Manage Transactions →" },
  none_good: { ar: "لا يوجد ✓", en: "None ✓" },
  kind_residency: { ar: "إقامة", en: "Residency" }, kind_work_permit: { ar: "إذن عمل", en: "Work Permit" },
  col_license: { ar: "الترخيص", en: "License" },
  days_unit: { ar: "يوم", en: "days" }, expired_since: { ar: "منتهية منذ {n} يوم", en: "expired {n} days ago" },
  saved: { ar: "تم الحفظ", en: "Saved" }, error: { ar: "خطأ", en: "Error" },
  close: { ar: "إغلاق", en: "Close" }, refresh: { ar: "تحديث", en: "Refresh" },
  none_dash: { ar: "لا يوجد", en: "None" }, confirm: { ar: "تأكيد", en: "Confirm" },
  download: { ar: "تنزيل", en: "Download" }, print: { ar: "طباعة", en: "Print" },
  export: { ar: "تصدير", en: "Export" }, optional: { ar: "اختياري", en: "optional" },

  // تغيير كلمة المرور
  pw_first_login: { ar: "يلزم تعيين كلمة مرور جديدة لأول دخول", en: "Set a new password on first login" },
  pw_current: { ar: "كلمة المرور الحالية", en: "Current Password" },
  pw_new: { ar: "كلمة المرور الجديدة", en: "New Password" },
  pw_changed: { ar: "تم التغيير بنجاح", en: "Password changed" },

  // الطلبات (تفصيلي)
  request: { ar: "طلب", en: "Request" }, req_employee: { ar: "الموظف", en: "Employee" },
  req_stage: { ar: "المرحلة", en: "Stage" }, req_path_title: { ar: "مسار الطلب", en: "Request Path" },
  req_actions: { ar: "الإجراءات", en: "Actions" }, req_note: { ar: "ملاحظة (اختياري)", en: "Note (optional)" },
  req_approve: { ar: "✓ اعتماد", en: "✓ Approve" }, req_reject: { ar: "✕ رفض", en: "✕ Reject" },
  req_print_doc: { ar: "🖨️ طباعة المستند", en: "🖨️ Print Document" },
  req_cancel_mgr: { ar: "إلغاء الطلب (المدير العام)", en: "Cancel Request (Manager)" },
  req_appoint: { ar: "تحديد موعد التوقيع ورفع النسخة الموقّعة", en: "Set signing appointment & upload signed copy" },
  req_appoint_date: { ar: "موعد المراجعة", en: "Appointment" }, req_location: { ar: "المكان", en: "Location" },
  req_set_appoint: { ar: "تحديد الموعد وإشعار العامل", en: "Set appointment & notify employee" },
  req_upload_signed: { ar: "رفع الطلب الموقّع (بعد توقيع العامل)", en: "Upload signed request" },
  req_upload_exit: { ar: "رفع إذن مغادرة البلاد", en: "Upload exit permit" },
  req_mark_received: { ar: "تسجيل استلام العامل", en: "Mark as received" },
  req_data: { ar: "البيانات", en: "Data" }, req_no_approvals: { ar: "لم تبدأ الموافقات بعد", en: "No approvals yet" },

  // الفروع / الهيكل / الأرشيف
  branch_name: { ar: "الفرع", en: "Branch" }, supervisor: { ar: "مسؤول الفرع", en: "Branch Supervisor" },
  view_branch_emps: { ar: "عرض موظفي الفرع", en: "View branch employees" },
  view_all_emps: { ar: "عرض كل الموظفين (كل الفروع)", en: "View all employees" },
  present_today: { ar: "حضور اليوم", en: "Present Today" }, on_leave_now: { ar: "في إجازة", en: "On Leave" },
  expiring_now: { ar: "إقامات تنتهي", en: "Expiring" },
  company_archive: { ar: "أرشيف الشركة", en: "Company Archive" }, branch_archive: { ar: "أرشيف الفروع", en: "Branch Archive" },
  official_docs: { ar: "أرشيف المستندات الرسمية", en: "Official Documents Archive" },
  file_number: { ar: "رقم ملف الشركة (القوى العاملة)", en: "Company File No. (Manpower)" },
  uploaded_v: { ar: "مرفوع", en: "Uploaded" }, not_uploaded: { ar: "غير مرفوع", en: "Not uploaded" },
  replace: { ar: "استبدال", en: "Replace" }, upload: { ar: "رفع", en: "Upload" },
  select_branch: { ar: "اختر الفرع", en: "Select Branch" },

  // الرواتب
  payroll_run: { ar: "تشغيل وحفظ", en: "Run & Save" }, payroll_preview: { ar: "معاينة", en: "Preview" },
  payroll_period: { ar: "الفترة", en: "Period" }, payroll_count: { ar: "عدد الموظفين", en: "Employees" },
  payroll_net_total: { ar: "إجمالي الصافي (د.ك)", en: "Total Net (KWD)" },
  payroll_gross: { ar: "الإجمالي", en: "Gross" }, payroll_ded: { ar: "الخصومات", en: "Deductions" },
  payroll_basic: { ar: "الأساسي", en: "Basic" }, payroll_present: { ar: "حضور", en: "Present" },
  payroll_absent: { ar: "غياب", en: "Absent" }, payroll_overtime: { ar: "الإضافي", en: "Overtime" },
  payroll_net: { ar: "الصافي", en: "Net" }, payroll_runs: { ar: "المسيّرات السابقة", en: "Previous Runs" },
  payroll_export: { ar: "تصدير Excel", en: "Export Excel" },

  // التدقيق
  audit_eyebrow: { ar: "الأمان", en: "Security" }, audit_title: { ar: "سجل التدقيق", en: "Audit Log" },
  audit_sub: { ar: "كل العمليات الحسّاسة مع المنفّذ والوقت وعنوان IP", en: "All sensitive operations with actor, time, IP" },
  audit_all: { ar: "كل العمليات", en: "All operations" },
  col_operation: { ar: "العملية", en: "Operation" }, col_entity: { ar: "الكيان", en: "Entity" },
  col_actor: { ar: "المنفّذ", en: "By" }, col_time: { ar: "الوقت", en: "Time" },

  // التقارير
  reports_sub: { ar: "تصدير البيانات إلى Excel أو CSV بترميز يدعم العربية", en: "Export data to Excel or CSV (Arabic-safe)" },
  rep_employees: { ar: "بيانات الموظفين", en: "Employees Data" },
  rep_employees_sub: { ar: "قائمة الموظفين (حسب الفرع المحدّد أو كل الفروع).", en: "Employee list (by branch or all)." },
  rep_attendance: { ar: "سجل الحضور الشهري", en: "Monthly Attendance" },
  rep_attendance_sub: { ar: "سجلات الحضور للشهر المحدد (حسب الفرع أو كل الفروع).", en: "Attendance records for the month." },
  rep_payroll_hint: { ar: "تصدير الرواتب يتم من صفحة مسيّر الرواتب.", en: "Payroll export is on the Payroll page." },

  // المندوب
  pro_eyebrow: { ar: "المعاملات الحكومية", en: "Government Transactions" },
  pro_sub: { ar: "الإقامات وأذونات العمل والتراخيص — متابعة الانتهاء والتجديد", en: "Residencies, work permits & licenses — tracking and renewal" },
  pro_tab_permits: { ar: "الإقامات وأذونات العمل", en: "Residencies & Work Permits" },
  pro_tab_licenses: { ar: "التراخيص", en: "Licenses" }, pro_tab_gov: { ar: "الجهات الحكومية", en: "Government Entities" },
  pro_renew: { ar: "تجديد", en: "Renew" }, pro_notes: { ar: "ملاحظات", en: "Notes" },
  pro_new_expiry: { ar: "تاريخ الانتهاء الجديد", en: "New Expiry Date" },
  pro_new_number: { ar: "الرقم الجديد (اختياري)", en: "New Number (optional)" },
  pro_save_renew: { ar: "حفظ التجديد", en: "Save Renewal" }, pro_add_note: { ar: "أضف ملاحظة...", en: "Add a note..." },
  pro_authority: { ar: "الجهة", en: "Authority" }, pro_workers: { ar: "العمالة", en: "Workforce" },

  // الصيغ
  templates_sub: { ar: "اختر صيغة ثم الموظف لتُعبّأ تلقائيًا وتُطبع", en: "Pick a template and an employee to auto-fill and print" },
  tpl_new: { ar: "+ صيغة جديدة", en: "+ New Template" }, tpl_fill_print: { ar: "تعبئة وطباعة", en: "Fill & Print" },
  tpl_category: { ar: "التصنيف", en: "Category" }, tpl_scope: { ar: "النطاق", en: "Scope" },
  tpl_global: { ar: "عامة", en: "Global" }, tpl_company: { ar: "الشركة", en: "Company" },
  tpl_select_emp: { ar: "اختر الموظف", en: "Select Employee" }, tpl_extra: { ar: "حقول إضافية مطلوبة", en: "Required extra fields" },
  tpl_preview_print: { ar: "معاينة وطباعة", en: "Preview & Print" },

  // الشركات
  company_new: { ar: "+ شركة جديدة", en: "+ New Company" }, company_reg: { ar: "السجل التجاري", en: "Commercial Reg" },
  company_enable: { ar: "تفعيل", en: "Enable" }, company_disable: { ar: "تعطيل", en: "Disable" },
  company_archive_action: { ar: "أرشفة", en: "Archive" },

  // المستخدمون
  user_new: { ar: "+ مستخدم جديد", en: "+ New User" }, user_role: { ar: "الدور", en: "Role" },
  user_perms: { ar: "الصلاحيات", en: "Permissions" }, user_reset_pw: { ar: "كلمة المرور", en: "Password" },
  user_impersonate: { ar: "انتحال", en: "Impersonate" }, user_matrix: { ar: "مصفوفة الأذونات الدقيقة", en: "Permission Matrix" },
  user_save_matrix: { ar: "حفظ المصفوفة", en: "Save Matrix" }, user_reset_role: { ar: "إعادة لصلاحيات الدور", en: "Reset to role defaults" },
  user_scope: { ar: "نطاق البيانات (تقييد بفرع):", en: "Data scope (restrict to branch):" },
  user_all_branches: { ar: "كل فروع الشركة", en: "All company branches" }, user_page: { ar: "الصفحة", en: "Page" },

  // ملف الموظف
  emp_status: { ar: "الحالة", en: "Status" }, emp_personal: { ar: "البيانات الشخصية", en: "Personal" },
  emp_hr_log: { ar: "سجل الموارد البشرية (إنذارات · جزاءات · مكافآت · ترقيات)", en: "HR Log (warnings · penalties · bonuses · promotions)" },
  emp_timeline: { ar: "الخط الزمني للموظف", en: "Employee Timeline" },
  emp_documents: { ar: "المستندات (أحدث نسخة)", en: "Documents (latest version)" },
  emp_permits: { ar: "الإقامات وأذونات العمل", en: "Residencies & Work Permits" },
  emp_recent_att: { ar: "آخر سجلات الحضور", en: "Recent Attendance" },
  emp_terminate: { ar: "إنهاء الخدمة وحساب المكافأة", en: "End of Service & Settlement" },
  emp_leave_bal: { ar: "رصيد الإجازات (حساب تلقائي حسب مدة الخدمة)", en: "Leave Balance (auto by service)" },
  leave_consumed: { ar: "الأيام المستهلَكة", en: "Days Used" }, leave_calc: { ar: "احسب الرصيد المتبقي", en: "Calculate Remaining" },
  leave_accrued: { ar: "المستحق", en: "Accrued" }, leave_remaining: { ar: "المتبقي", en: "Remaining" },

  // الحضور / المراجعة
  att_self: { ar: "الحضور والانصراف (خدمة ذاتية)", en: "Attendance (Self-service)" },
  att_review_title: { ar: "مراجعة حضور الموظفين", en: "Employee Attendance Review" },
  att_review_sub: { ar: "سجل يومي لكل موظف خلال الشهر", en: "Daily record per employee for the month" },
};

type I18nCtx = { lang: Lang; t: (k: string, vars?: Record<string, any>) => string; toggle: () => void };
const Ctx = createContext<I18nCtx>({ lang: "ar", t: (k) => k, toggle: () => {} });

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang] = useState<Lang>((localStorage.getItem("lang") as Lang) || "ar");
  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  }, [lang]);
  const t = (k: string, vars?: Record<string, any>) => {
    let s = dict[k]?.[lang] ?? k;
    if (vars) for (const [key, v] of Object.entries(vars)) s = s.replace(`{${key}}`, String(v));
    return s;
  };
  // تبديل اللغة يعيد تحميل الصفحة لضمان قلب الواجهة بالكامل (RTL/LTR + كل التسميات)
  const toggle = () => {
    localStorage.setItem("lang", lang === "ar" ? "en" : "ar");
    window.location.reload();
  };
  return <Ctx.Provider value={{ lang, t, toggle }}>{children}</Ctx.Provider>;
}

export const useI18n = () => useContext(Ctx);
