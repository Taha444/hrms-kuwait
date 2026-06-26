// تسميات عربية موحّدة للحالات والأدوار
export const STATUS_AR: Record<string, string> = {
  draft: "مسودة",
  pending: "بانتظار الاعتماد",
  approved: "معتمد",
  rejected: "مرفوض",
  cancelled: "ملغى",
  awaiting_signature: "بانتظار التوقيع",
  awaiting_delegate: "لدى المندوب",
  ready_for_pickup: "جاهز للاستلام",
  completed: "مكتمل",
};

export const ROLE_AR: Record<string, string> = {
  super_admin: "إدارة عليا", company_owner: "صاحب الشركات", company_manager: "مدير شركة",
  branch_supervisor: "مسؤول فرع", hr: "موارد بشرية", delegate: "مندوب", employee: "موظف",
};

export const statusAr = (s: string) => STATUS_AR[s] || s;
export const roleAr = (r: string) => ROLE_AR[r] || r;
