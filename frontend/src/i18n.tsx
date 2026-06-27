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
