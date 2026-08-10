import type { TourStep } from "./TourDriver";

/**
 * R5 §3 — نصوص الجولات التعليمية لكل دور.
 *
 * كل دور له مصفوفة 5–7 خطوات (بالحد الأدنى للطول). النصوص ثنائية اللغة (ar/en).
 * الأهداف تُحدَّد بـdata-tour attributes على الـsidebar/topbar/cards الرئيسية.
 *
 * tour_key = "role:{role}:v1" — لو غيّرنا الخطوات لاحقًا، نرفع الرقم (v2) عشان
 * تظهر الجولة من جديد للمستخدمين اللي أكملوا القديمة.
 */

export const TOUR_VERSION = "v1";

export function tourKeyForRole(role: string): string {
  return `role:${role}:${TOUR_VERSION}`;
}

type Bilingual = { ar: string; en: string };
type StepDef = {
  target: string;
  page?: string;
  placement?: TourStep["placement"];
  title: Bilingual;
  body: Bilingual;
};

// أدوار مماثلة تستخدم نفس مصفوفة الخطوات
const EMPLOYEE_STEPS: StepDef[] = [
  {
    target: '[data-tour="dashboard-header"]',
    page: "/",
    title: { ar: "لوحة المؤشرات", en: "Dashboard" },
    body: {
      ar: "هنا تبدأ يومك — تُظهر لك ملخّصًا لطلباتك، مهامك، وتذكيرات هامة.",
      en: "Your daily starting point — a summary of your requests, tasks, and reminders.",
    },
  },
  {
    target: '[data-tour="nav-my-profile"]',
    title: { ar: "ملفي الشخصي", en: "My Profile" },
    body: {
      ar: "بياناتك الشخصية وحسابك ورقمك الوظيفي. تستطيع تحديث توقيعك من هنا.",
      en: "Your personal info, employee ID, and signature. Update from here.",
    },
  },
  {
    target: '[data-tour="nav-attendance"]',
    title: { ar: "بصمة الحضور", en: "My Attendance" },
    body: {
      ar: "لتسجيل الحضور والانصراف بمسح QR الفرع أو التسجيل اليدوي المسموح به.",
      en: "Punch in/out by scanning the branch QR — the fastest way to log attendance.",
    },
  },
  {
    target: '[data-tour="nav-requests"]',
    title: { ar: "طلباتي", en: "My Requests" },
    body: {
      ar: "قدّم طلبات جديدة (إجازة، شهادة راتب، تعديل بيانات…) وتابع حالتها هنا.",
      en: "Submit new requests (leave, salary certificate, data update…) and track them.",
    },
  },
  {
    target: '[data-tour="nav-tasks"]',
    title: { ar: "مهامي والإشعارات", en: "Tasks & Notifications" },
    body: {
      ar: "الشارة الحمراء تعني وجود مهمة بانتظارك — ردّ سريع تُقفل التذكرة.",
      en: "The red badge means a task awaits you — a quick reply closes the ticket.",
    },
  },
  {
    target: '[data-tour="topbar-lang"]',
    title: { ar: "تبديل اللغة", en: "Language Toggle" },
    body: {
      ar: "بدّل بين العربية والإنجليزية في أي لحظة — كل شيء ينعكس فورًا.",
      en: "Switch Arabic ↔ English anytime — everything mirrors instantly.",
    },
  },
];

const SUPERVISOR_STEPS: StepDef[] = [
  {
    target: '[data-tour="dashboard-header"]',
    page: "/",
    title: { ar: "لوحة الفرع", en: "Branch Dashboard" },
    body: {
      ar: "ترى إحصاءات موظفي فروعك المعيّنة فقط — لا تظهر بيانات فروع أخرى.",
      en: "Stats for your assigned branches only — other branches are hidden.",
    },
  },
  {
    target: '[data-tour="nav-employees"]',
    title: { ar: "موظفو الفرع", en: "Branch Employees" },
    body: {
      ar: "قائمة موظفيك — انقر على أي موظف لعرض ملفه (بلا صلاحية تعديل مباشر).",
      en: "Your team roster — click any employee to view their file (read-only).",
    },
  },
  {
    target: '[data-tour="nav-attendance-review"]',
    title: { ar: "مراجعة الحضور", en: "Attendance Review" },
    body: {
      ar: "راجع بصمات الحضور، اعتمد التصحيحات، وارفع تنبيهات على الغياب المتكرر.",
      en: "Review punches, approve corrections, and flag repeated absences.",
    },
  },
  {
    target: '[data-tour="nav-tasks"]',
    title: { ar: "الاعتمادات المطلوبة", en: "Pending Approvals" },
    body: {
      ar: "أنت المُعتمِد الأول لطلبات موظفي فرعك — الشارة تعني طلب بانتظارك.",
      en: "You are the first approver for your team's requests — badge = pending.",
    },
  },
  {
    target: '[data-tour="nav-reports"]',
    title: { ar: "تقارير الفرع", en: "Branch Reports" },
    body: {
      ar: "صدّر تقارير الحضور والإجازات لفروعك — Excel أو PDF.",
      en: "Export attendance and leave reports for your branches — Excel or PDF.",
    },
  },
];

const HR_STEPS: StepDef[] = [
  {
    target: '[data-tour="nav-employees"]',
    page: "/",
    title: { ar: "إدارة الموظفين", en: "Employees" },
    body: {
      ar: "أضف موظفًا جديدًا، ارفع صورة بطاقته المدنية، وسيقرأها OCR تلقائيًا.",
      en: "Add a new employee, scan their civil ID — OCR auto-fills the fields.",
    },
  },
  {
    target: '[data-tour="nav-users"]',
    title: { ar: "ربط الحسابات", en: "User Linking" },
    body: {
      ar: "بعد إنشاء الموظف، اربطه بحساب دخول — يتولّد اسم مستخدم وكلمة سر تلقائيًا.",
      en: "After creating an employee, link them to a login account — auto credentials.",
    },
  },
  {
    target: '[data-tour="nav-attendance-review"]',
    title: { ar: "مراجعة حضور كل الشركة", en: "Company-wide Attendance" },
    body: {
      ar: "ترى حضور كل موظفي شركتك — أول خطوة قبل قفل الشهر وتشغيل الرواتب.",
      en: "See all company punches — first step before month close and payroll.",
    },
  },
  {
    target: '[data-tour="nav-tasks"]',
    title: { ar: "الاعتمادات والطلبات", en: "Approvals & Requests" },
    body: {
      ar: "أنت مرحلة أساسية في معظم الطلبات (إنذارات، إنهاء خدمة، توقيعات…).",
      en: "You are a mandatory stage in most flows (warnings, EOS, signatures…).",
    },
  },
  {
    target: '[data-tour="nav-renewals"]',
    title: { ar: "تجديدات الإقامة", en: "Residency Renewals" },
    body: {
      ar: "التحقق النهائي من بيانات المعاملة الحكومية قبل إغلاقها.",
      en: "Final verification of government transaction data before closing.",
    },
  },
  {
    target: '[data-tour="nav-templates"]',
    title: { ar: "الصيغ والقوالب", en: "Templates" },
    body: {
      ar: "توليد شهادات ومستندات رسمية — «معاينة» ثم «توليد» لإصدار مستند برقم مرجعي.",
      en: "Generate official certificates — Preview then Generate to issue with ref#.",
    },
  },
  {
    target: '[data-tour="nav-reports"]',
    title: { ar: "تقارير HR", en: "HR Reports" },
    body: {
      ar: "صدّر تقارير الموظفين، الإجازات، والإنذارات — كل تصدير يُسجَّل في التدقيق.",
      en: "Export employees, leaves, warnings — every export is audit-logged.",
    },
  },
];

const MANAGER_STEPS: StepDef[] = [
  {
    target: '[data-tour="dashboard-header"]',
    page: "/",
    title: { ar: "لوحة الشركة", en: "Company Dashboard" },
    body: {
      ar: "ترى إحصاءات شركتك كاملة عبر كل الفروع والإدارات.",
      en: "Full company stats across all branches and departments.",
    },
  },
  {
    target: '[data-tour="nav-tasks"]',
    title: { ar: "اعتمادات الشركة", en: "Company Approvals" },
    body: {
      ar: "أنت مرحلة اعتماد لطلبات مالية وإدارية كبيرة (سلف، ترقيات، إنهاء خدمة).",
      en: "You approve major requests (advances, promotions, terminations).",
    },
  },
  {
    target: '[data-tour="nav-attendance-review"]',
    title: { ar: "مراجعة الحضور", en: "Attendance Review" },
    body: {
      ar: "راجع بصمات موظفي شركتك بالكامل — تقدر تصدّرها لأي فترة.",
      en: "Review all employee punches — exportable for any period.",
    },
  },
  {
    target: '[data-tour="nav-users"]',
    title: { ar: "المستخدمون والصلاحيات", en: "Users & Permissions" },
    body: {
      ar: "أنشئ مستخدمين، أسند أدوار، وامنح صلاحيات دقيقة عبر مصفوفة (صفحة×فعل).",
      en: "Create users, assign roles, and grant fine-grained page×action permissions.",
    },
  },
  {
    target: '[data-tour="nav-reports"]',
    title: { ar: "التقارير التنفيذية", en: "Executive Reports" },
    body: {
      ar: "تقارير الرواتب، الحضور، الأداء، والإحصاءات المالية — كلها Excel/PDF.",
      en: "Payroll, attendance, performance, and financial reports — Excel/PDF.",
    },
  },
  {
    target: '[data-tour="nav-branches"]',
    title: { ar: "الفروع والـKiosk", en: "Branches & Kiosk" },
    body: {
      ar: "أدر الفروع، والمواقع الجغرافية، وشاشات QR للحضور — مع تدوير آمن للمفاتيح.",
      en: "Manage branches, geofences, and attendance QR displays — with secure key rotation.",
    },
  },
];

const ACCOUNTANT_STEPS: StepDef[] = [
  {
    target: '[data-tour="nav-payroll"]',
    page: "/",
    title: { ar: "مركز الرواتب", en: "Payroll Center" },
    body: {
      ar: "من هنا تُشغّل الرواتب. اختر الشركة والفترة قبل البدء.",
      en: "Where payroll runs originate. Pick company + period first.",
    },
  },
  {
    target: '[data-tour="nav-attendance-review"]',
    title: { ar: "الحضور المُقفَل", en: "Closed Attendance" },
    body: {
      ar: "لا تشغيل رواتب قبل قفل حضور الشهر — هذا يحمي من احتساب أيام غير مؤكدة.",
      en: "No payroll runs until attendance is closed — prevents unverified day counts.",
    },
  },
  {
    target: '[data-tour="nav-payroll"]',
    title: { ar: "معاينة الرواتب", en: "Payroll Preview" },
    body: {
      ar: "«معاينة» تحسب بلا التزام. راجع الأرقام قبل التجهيز الرسمي (Prepared).",
      en: "Preview calculates without commit. Verify before Prepared state.",
    },
  },
  {
    target: '[data-tour="nav-payroll"]',
    title: { ar: "دورة حياة الرواتب", en: "Payroll Lifecycle" },
    body: {
      ar: "prepared → approved → finalized → locked. أنت المُجَهِّز، والاعتماد لمستخدم آخر.",
      en: "prepared → approved → finalized → locked. You prepare; another user approves.",
    },
  },
  {
    target: '[data-tour="nav-payroll"]',
    title: { ar: "التسويات بعد القفل", en: "Post-Lock Adjustments" },
    body: {
      ar: "بعد القفل، أي تعديل يستلزم Adjustment Run صريح مع سبب مسجَّل.",
      en: "After lock, any change requires an explicit Adjustment Run with reason.",
    },
  },
  {
    target: '[data-tour="nav-reports"]',
    title: { ar: "التقارير المالية", en: "Financial Reports" },
    body: {
      ar: "قسائم رواتب، مستحقات، خصومات — كل تصدير يُسجَّل مع سبب التصدير.",
      en: "Payslips, dues, deductions — every export logged with a reason.",
    },
  },
];

const PRO_STEPS: StepDef[] = [
  {
    target: '[data-tour="dashboard-header"]',
    page: "/",
    title: { ar: "مركز عمليات المندوب", en: "PRO Operations" },
    body: {
      ar: "لوحتك تُظهر تنبيهات الإقامات المقاربة على الانتهاء وتراخيص الشركة.",
      en: "Your dashboard highlights expiring residencies and company licenses.",
    },
  },
  {
    target: '[data-tour="nav-operations"]',
    title: { ar: "مركز العمليات", en: "Operations Center" },
    body: {
      ar: "التنبيهات هنا قابلة للتنفيذ — كل تنبيه له زر «ابدأ التجديد».",
      en: "Alerts here are actionable — each one has a 'Start Renewal' button.",
    },
  },
  {
    target: '[data-tour="nav-renewals"]',
    title: { ar: "دورة التجديد", en: "Renewal Lifecycle" },
    body: {
      ar: "بعد تلقّي المستندات، سجّل الرقم المرجعي الحكومي + الرسوم + الإقامة الجديدة.",
      en: "After documents, record gov reference no + fees + new permit details.",
    },
  },
  {
    target: '[data-tour="nav-archive"]',
    title: { ar: "أرشيف التراخيص", en: "License Archive" },
    body: {
      ar: "كل التراخيص الحكومية للشركة — تنبيهات تلقائية قبل 90 يومًا من الانتهاء.",
      en: "All company government licenses — auto-alerts 90 days before expiry.",
    },
  },
  {
    target: '[data-tour="nav-tasks"]',
    title: { ar: "مهامك", en: "Your Tasks" },
    body: {
      ar: "المهام المُسنَدة تلقائيًا لك — كل معاملة تجديد تفتح مهمة مرتبطة بها.",
      en: "Tasks auto-assigned to you — each renewal opens a linked task.",
    },
  },
];

// P1-#20 — جولة صاحب الشركة (portfolio + oversight only, no operational actions)
const OWNER_STEPS: StepDef[] = [
  {
    target: '[data-tour="dashboard-header"]',
    page: "/",
    title: { ar: "لوحة المالك — Portfolio", en: "Owner Portfolio" },
    body: {
      ar: "نظرة رقابية على كل شركاتك. الأرقام مجمَّعة عبر الشركات — يمكن التصفية بشركة معينة.",
      en: "Read-only overview across all your companies. Aggregated by default — filter to one company anytime.",
    },
  },
  {
    target: '[data-tour="nav-employees"]',
    title: { ar: "الموظفون", en: "Employees" },
    body: {
      ar: "عرض كامل لموظفي الشركات. لا صلاحية إضافة/تعديل (رقابي فقط).",
      en: "Full read view of employees across companies. No add/edit — oversight only.",
    },
  },
  {
    target: '[data-tour="nav-reports"]',
    title: { ar: "التقارير", en: "Reports" },
    body: {
      ar: "تقارير مجمّعة قابلة للتصدير. كل تصدير حسّاس يطلب سبب صريح للـaudit.",
      en: "Aggregated reports, exportable. Every sensitive export requires an explicit reason for audit.",
    },
  },
  {
    target: '[data-tour="nav-payroll"]',
    title: { ar: "الرواتب — قراءة فقط", en: "Payroll — Read-Only" },
    body: {
      ar: "المالك يشوف المسيّرات والإجماليات، بس مافيش صلاحية تشغيل/اعتماد. المحاسب/HR هم المسؤولون.",
      en: "You see runs and totals, but cannot prepare or approve. Accountant/HR handle operations.",
    },
  },
  {
    target: '[data-tour="nav-audit"]',
    title: { ar: "سجل التدقيق", en: "Audit Log" },
    body: {
      ar: "كل عملية حسّاسة مسجَّلة: من فعل ماذا، متى، ومن أي جهاز. Correlation ID يربط الأحداث المتعلقة.",
      en: "Every sensitive action logged: who did what, when, from where. Correlation IDs link related events.",
    },
  },
  {
    target: '[data-tour="nav-tasks"]',
    title: { ar: "المهام", en: "Tasks" },
    body: {
      ar: "شارة المهام تظهر المتأخرات والتصعيدات — لن تُسند لك مهام تشغيلية بحكم الدور الرقابي.",
      en: "Task badge shows overdue and escalations — no operational tasks are assigned to your oversight role.",
    },
  },
];

// خريطة الأدوار → مصفوفة الخطوات
const ROLE_TOURS: Record<string, StepDef[]> = {
  employee: EMPLOYEE_STEPS,
  branch_supervisor: SUPERVISOR_STEPS,
  hr: HR_STEPS,
  company_manager: MANAGER_STEPS,
  accountant: ACCOUNTANT_STEPS,
  delegate: PRO_STEPS,
  admin_employee: EMPLOYEE_STEPS,
  // P1-#20 — owner يحصل على portfolio tour مركّز على العرض والحوكمة
  company_owner: OWNER_STEPS,
  // super_admin يشوف كل شيء بحكم الدور — لا يحتاج جولة موجّهة
};

/** يحوّل نصوص الجولة للغة الحالية، ويُرجع مصفوفة TourStep جاهزة للـTourDriver. */
export function getTourForRole(role: string, lang: "ar" | "en"): TourStep[] {
  const steps = ROLE_TOURS[role];
  if (!steps) return [];
  return steps.map((s) => ({
    target: s.target,
    page: s.page,
    placement: s.placement,
    title: s.title[lang],
    body: s.body[lang],
  }));
}
