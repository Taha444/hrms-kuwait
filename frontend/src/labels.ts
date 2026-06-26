// تسميات عربية موحّدة لكل الأكواد/الحالات — لتوحيد لغة الواجهة (لا خلط بالإنجليزية)

export const STATUS_AR: Record<string, string> = {
  draft: "مسودة", pending: "بانتظار الاعتماد", approved: "معتمد", rejected: "مرفوض",
  cancelled: "ملغى", awaiting_signature: "بانتظار التوقيع", awaiting_delegate: "لدى المندوب",
  ready_for_pickup: "جاهز للاستلام", completed: "مكتمل",
  active: "نشط", inactive: "متوقف", archived: "مؤرشف", terminated: "منتهي الخدمة",
  open: "مفتوحة", in_progress: "قيد التنفيذ", done: "منجزة", dismissed: "متجاهَلة",
  scheduled: "مجدول", missed: "فائت", finalized: "نهائي",
};

export const ROLE_AR: Record<string, string> = {
  super_admin: "إدارة عليا", company_owner: "صاحب الشركات", company_manager: "مدير شركة",
  branch_supervisor: "مسؤول فرع", hr: "موارد بشرية", delegate: "مندوب", employee: "موظف",
};

// حالات الحضور
export const ATT_AR: Record<string, string> = {
  present: "حاضر", late: "متأخر", early_leave: "خروج مبكر", absent: "غائب",
  leave: "إجازة", off: "عطلة", future: "—",
};

// أنواع المهام/الإشعارات
export const TASK_AR: Record<string, string> = {
  renew_residency: "تجديد إقامة", renew_work_permit: "تجديد إذن عمل",
  renew_passport: "تجديد جواز", transfer_info: "نقل معلومات", doc_expiring: "مستند قارب الانتهاء",
  license_expiring: "ترخيص قارب الانتهاء", capacity_exceeded: "تجاوز سعة الترخيص",
  request_stage: "مرحلة طلب", request_update: "تحديث طلب", exit_permit: "إذن مغادرة",
  pickup_ready: "جاهز للاستلام", appointment: "موعد",
};

export const SEVERITY_AR: Record<string, string> = {
  info: "معلومة", warning: "تحذير", critical: "حرج",
};

export const URGENCY_AR: Record<string, string> = {
  expired: "منتهية", critical: "حرجة", warning: "تحذير", ok: "سليمة", none: "—",
};

const pick = (m: Record<string, string>, k: string) => m[k] || k;
export const statusAr = (s: string) => pick(STATUS_AR, s);
export const roleAr = (r: string) => pick(ROLE_AR, r);
export const attAr = (s: string) => pick(ATT_AR, s);
export const taskAr = (t: string) => pick(TASK_AR, t);
export const severityAr = (s: string) => pick(SEVERITY_AR, s);
export const urgencyAr = (u: string) => pick(URGENCY_AR, u);
