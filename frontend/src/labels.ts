// تسميات ثنائية اللغة لكل الأكواد — تتبع اللغة المختارة تلقائيًا (لا خلط)
export const getLang = (): "ar" | "en" => (localStorage.getItem("lang") as "ar" | "en") || "ar";

type Pair = { ar: string; en: string };
const M = (m: Record<string, Pair>) => (k: string) => {
  const p = m[k];
  return p ? p[getLang()] : k;
};

export const statusAr = M({
  draft: { ar: "مسودة", en: "Draft" }, pending: { ar: "بانتظار الاعتماد", en: "Pending" },
  approved: { ar: "معتمد", en: "Approved" }, rejected: { ar: "مرفوض", en: "Rejected" },
  cancelled: { ar: "ملغى", en: "Cancelled" }, awaiting_signature: { ar: "بانتظار التوقيع", en: "Awaiting Signature" },
  awaiting_delegate: { ar: "لدى المندوب", en: "With Delegate" }, ready_for_pickup: { ar: "جاهز للاستلام", en: "Ready for Pickup" },
  completed: { ar: "مكتمل", en: "Completed" }, active: { ar: "نشط", en: "Active" },
  inactive: { ar: "متوقف", en: "Inactive" }, archived: { ar: "مؤرشف", en: "Archived" },
  terminated: { ar: "منتهي الخدمة", en: "Terminated" }, open: { ar: "مفتوحة", en: "Open" },
  in_progress: { ar: "قيد التنفيذ", en: "In Progress" }, done: { ar: "منجزة", en: "Done" },
  dismissed: { ar: "متجاهَلة", en: "Dismissed" }, suspended: { ar: "موقوف", en: "Suspended" },
  locked: { ar: "مقفل", en: "Locked" }, resigned: { ar: "مستقيل", en: "Resigned" },
  retired: { ar: "متقاعد", en: "Retired" }, vacation: { ar: "في إجازة", en: "On Vacation" },
});

export const roleAr = M({
  super_admin: { ar: "إدارة عليا", en: "Super Admin" }, company_owner: { ar: "صاحب الشركات", en: "Company Owner" },
  company_manager: { ar: "مدير شركة", en: "Manager" }, branch_supervisor: { ar: "مسؤول فرع", en: "Branch Supervisor" },
  hr: { ar: "موارد بشرية", en: "HR" }, delegate: { ar: "مندوب", en: "PRO" },
  admin_employee: { ar: "موظف إداري", en: "Admin Employee" }, employee: { ar: "موظف", en: "Employee" },
});

export const attAr = M({
  present: { ar: "حاضر", en: "Present" }, late: { ar: "متأخر", en: "Late" },
  early_leave: { ar: "خروج مبكر", en: "Early Leave" }, absent: { ar: "غائب", en: "Absent" },
  leave: { ar: "إجازة", en: "Leave" }, off: { ar: "عطلة", en: "Off" }, future: { ar: "—", en: "—" },
});

export const taskAr = M({
  renew_residency: { ar: "تجديد إقامة", en: "Renew Residency" }, renew_work_permit: { ar: "تجديد إذن عمل", en: "Renew Work Permit" },
  renew_passport: { ar: "تجديد جواز", en: "Renew Passport" }, transfer_info: { ar: "نقل معلومات", en: "Transfer Info" },
  doc_expiring: { ar: "مستند قارب الانتهاء", en: "Document Expiring" }, license_expiring: { ar: "ترخيص قارب الانتهاء", en: "License Expiring" },
  capacity_exceeded: { ar: "تجاوز سعة الترخيص", en: "Capacity Exceeded" }, request_stage: { ar: "مرحلة طلب", en: "Request Stage" },
  request_update: { ar: "تحديث طلب", en: "Request Update" }, exit_permit: { ar: "إذن مغادرة", en: "Exit Permit" },
  pickup_ready: { ar: "جاهز للاستلام", en: "Ready for Pickup" }, appointment: { ar: "موعد", en: "Appointment" },
});

export const severityAr = M({
  info: { ar: "معلومة", en: "Info" }, warning: { ar: "تحذير", en: "Warning" }, critical: { ar: "حرج", en: "Critical" },
});

export const urgencyAr = M({
  expired: { ar: "منتهية", en: "Expired" }, critical: { ar: "حرجة", en: "Critical" },
  warning: { ar: "تحذير", en: "Warning" }, ok: { ar: "سليمة", en: "OK" }, none: { ar: "—", en: "—" },
});
