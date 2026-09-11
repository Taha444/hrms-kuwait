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
  returned: { ar: "أُعيد للتصحيح", en: "Returned for Correction" },
  // PR-UI — حالات مسيّر الرواتب. كانت تُعرض بأكوادها الإنجليزية الخام
  // (``prepared`` · ``finalized``) لأن الخريطة لا تعرفها — والدالة تُعيد
  // المفتاح نفسه عند الغياب، فيبدو الكود تسميًة مقصودة.
  prepared: { ar: "مجهَّز — بانتظار الاعتماد", en: "Prepared — awaiting approval" },
  finalized: { ar: "مُعتمَد ومُقفَل — بانتظار القفل النهائي",
               en: "Finalized — awaiting lock" },
  adjustment_run: { ar: "مسيّر تسوية", en: "Adjustment run" },
  // ``apply_failed`` — طلٌب اكتملت موافقاته ولم يقع أثره على البيانات.
  // وهي أحوُج حالٍة إلى اسٍم يُفهَم، وكانت تُعرض «apply_failed» بالإنجليزية
  // في قائمة الطلبات وفي تفصيلها: الدالة تُعيد المفتاح عند الغياب فيبدو
  // الكود تسميًة مقصودة — العطُل نفسه الذي أُصلح لحالات المسيّر فوق.
  //
  // والنصُّ هو نصُّ الخادم بحرفه (``workflow.STATUS_MAP``)، فلا تُقرأ
  // الحالُة الواحدة باسمين.
  apply_failed: { ar: "فشل التطبيق — يحتاج إجراء",
                  en: "Apply failed — action needed" },
});

// SCR-Q — أسماء الحقول الحرجة. كانت خريطًة محلّية عربية داخل ملف الموظف،
// فلمّا لزمت شاشًة ثانية كان الخيار: نسخها (قاعدة في موضعين تنحرفان) أو
// نقلها إلى مصدرها. وهذا مكان التسميات كلّها، وثنائي اللغة كغيره.
export const fieldAr = M({
  basic_salary: { ar: "الراتب الأساسي", en: "Basic salary" },
  actual_salary: { ar: "الراتب الفعلي", en: "Actual salary" },
  hire_date: { ar: "تاريخ التعيين", en: "Hire date" },
  job_title: { ar: "المسمى الوظيفي", en: "Job title" },
  contract_type: { ar: "نوع العقد", en: "Contract type" },
});

export const roleAr = M({
  super_admin: { ar: "إدارة عليا", en: "Super Admin" }, company_owner: { ar: "صاحب الشركات", en: "Company Owner" },
  company_manager: { ar: "مدير شركة", en: "Manager" }, branch_supervisor: { ar: "مسؤول فرع", en: "Branch Supervisor" },
  hr: { ar: "موارد بشرية", en: "HR" }, delegate: { ar: "مندوب", en: "PRO" },
  accountant: { ar: "محاسب", en: "Accountant" },
  admin_employee: { ar: "موظف إداري", en: "Admin Employee" }, employee: { ar: "موظف", en: "Employee" },
});

export const attAr = M({
  present: { ar: "حاضر", en: "Present" }, late: { ar: "متأخر", en: "Late" },
  early_leave: { ar: "خروج مبكر", en: "Early Leave" }, absent: { ar: "غائب", en: "Absent" },
  leave: { ar: "إجازة", en: "Leave" }, off: { ar: "عطلة", en: "Off" }, future: { ar: "—", en: "—" },
  // QA-03 — "غير مسجَّل" حالة ثالثة مستقلة عن الغياب: لا سجل ≠ غياب
  unrecorded: { ar: "غير مسجَّل", en: "Unrecorded" },
  not_employed: { ar: "خارج مدة التوظيف", en: "Not employed" },
});

// QA-22 — أنماط الحضور (qr/gps/both/none) كانت تظهر خامًا: attAr أعلاه يغطي
// حالات الحضور (حاضر/متأخر) لا أنماطه، فكل استدعاء بنمط كان يُرجع الكود نفسه.
export const attModeAr = M({
  qr: { ar: "رمز QR", en: "QR code" },
  gps: { ar: "الموقع الجغرافي", en: "GPS" },
  both: { ar: "رمز QR والموقع", en: "QR + GPS" },
  none: { ar: "بدون حضور", en: "No attendance" },
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

// نوع العقد (QA-P2-LOC-01): كانت قيمة indefinite/definite الخام تظهر داخل شاشات عربية
export const contractTypeAr = M({
  indefinite: { ar: "غير محدد المدة", en: "Indefinite" },
  definite: { ar: "محدد المدة", en: "Definite" },
});

// QA-22 (sweep) — نوع الإقامة/الإذن كان يُعرض خاًما ("residency") في ملف
// الموظف وشاشة التعيين. القيم تأتي من Permit.kind في الخادم.
export const permitKindAr = M({
  residency: { ar: "إقامة", en: "Residency" },
  work_permit: { ar: "إذن عمل", en: "Work permit" },
  visa: { ar: "تأشيرة", en: "Visa" },
});

export const urgencyAr = M({
  expired: { ar: "منتهية", en: "Expired" }, critical: { ar: "حرجة", en: "Critical" },
  warning: { ar: "تحذير", en: "Warning" }, ok: { ar: "سليمة", en: "OK" }, none: { ar: "—", en: "—" },
});
