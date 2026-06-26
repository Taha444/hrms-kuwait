// نظام ترجمة بسيط (عربي افتراضي + إنجليزي) مع دعم RTL/LTR
import { createContext, useContext, useEffect, useState, ReactNode } from "react";

type Lang = "ar" | "en";

const dict: Record<string, { ar: string; en: string }> = {
  app_name: { ar: "نظام الموارد البشرية", en: "HRMS" },
  login: { ar: "تسجيل الدخول", en: "Login" },
  logout: { ar: "تسجيل الخروج", en: "Logout" },
  civil_id: { ar: "الرقم المدني", en: "Civil ID" },
  password: { ar: "كلمة المرور", en: "Password" },
  dashboard: { ar: "لوحة التحكم", en: "Dashboard" },
  employees: { ar: "الموظفون", en: "Employees" },
  tasks: { ar: "المهام", en: "Tasks" },
  requests: { ar: "الطلبات", en: "Requests" },
  my_requests: { ar: "طلباتي", en: "My Requests" },
  inbox: { ar: "بانتظار موافقتي", en: "Approval Inbox" },
  new_request: { ar: "طلب جديد", en: "New Request" },
  attendance: { ar: "الحضور", en: "Attendance" },
  branch_qr: { ar: "الفروع وشاشات QR", en: "Branches & Kiosk" },
  eos: { ar: "مكافأة نهاية الخدمة", en: "End of Service" },
  companies: { ar: "الشركات", en: "Companies" },
  users: { ar: "المستخدمون والصلاحيات", en: "Users & Permissions" },
  documents: { ar: "المستندات", en: "Documents" },
  change_password: { ar: "تغيير كلمة المرور", en: "Change Password" },
  approve: { ar: "اعتماد", en: "Approve" },
  reject: { ar: "رفض", en: "Reject" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  save: { ar: "حفظ", en: "Save" },
  submit: { ar: "إرسال", en: "Submit" },
  status: { ar: "الحالة", en: "Status" },
  loading: { ar: "جارِ التحميل…", en: "Loading…" },
  no_data: { ar: "لا توجد بيانات", en: "No data" },
  check_in: { ar: "تسجيل حضور", en: "Check In" },
  check_out: { ar: "تسجيل انصراف", en: "Check Out" },
};

type I18nCtx = { lang: Lang; t: (k: string) => string; toggle: () => void };
const Ctx = createContext<I18nCtx>({ lang: "ar", t: (k) => k, toggle: () => {} });

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>((localStorage.getItem("lang") as Lang) || "ar");
  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
    localStorage.setItem("lang", lang);
  }, [lang]);
  const t = (k: string) => dict[k]?.[lang] ?? k;
  const toggle = () => setLang((l) => (l === "ar" ? "en" : "ar"));
  return <Ctx.Provider value={{ lang, t, toggle }}>{children}</Ctx.Provider>;
}

export const useI18n = () => useContext(Ctx);
