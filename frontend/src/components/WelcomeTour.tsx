import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import Icon from "../Icon";
import { roleAr } from "../labels";

/**
 * DEMO-5: Modal ترحيبي لأول دخول.
 *  - يظهر مرة واحدة لكل مستخدم (localStorage flag)
 *  - محتوى مخصّص حسب الدور: يعرض أهم 3 مهام + روابط سريعة
 *  - قابل للتجاهل، وله رابط "لا تُظهر مجددًا" + رابط لإعادة الفتح لاحقًا (?tour=1)
 */

type QuickAction = { label_ar: string; label_en: string; to: string; icon: string };

const ACTIONS_BY_ROLE: Record<string, QuickAction[]> = {
  super_admin: [
    { label_ar: "لوحة حالة النظام", label_en: "System Health", to: "/system-health", icon: "dashboard" },
    { label_ar: "إدارة الشركات", label_en: "Manage Companies", to: "/companies", icon: "companies" },
    { label_ar: "سجل التدقيق", label_en: "Audit Log", to: "/audit", icon: "lock" },
  ],
  company_owner: [
    { label_ar: "لوحة المؤشرات", label_en: "Dashboard", to: "/", icon: "dashboard" },
    { label_ar: "الهيكل التنظيمي", label_en: "Structure", to: "/structure", icon: "branches" },
    { label_ar: "التقارير", label_en: "Reports", to: "/reports", icon: "doc" },
  ],
  company_manager: [
    { label_ar: "عرض الموظفين", label_en: "Employees", to: "/employees", icon: "employees" },
    { label_ar: "مراجعة الطلبات", label_en: "Review Requests", to: "/tasks", icon: "tasks" },
    { label_ar: "الرواتب", label_en: "Payroll", to: "/payroll", icon: "eos" },
  ],
  hr: [
    { label_ar: "إضافة موظف جديد", label_en: "Add Employee", to: "/employees", icon: "employees" },
    { label_ar: "الطلبات المفتوحة", label_en: "Open Requests", to: "/tasks", icon: "tasks" },
    { label_ar: "تجديدات الإقامة", label_en: "Residency Renewals", to: "/renewals", icon: "attendance" },
  ],
  accountant: [
    { label_ar: "تشغيل الرواتب", label_en: "Run Payroll", to: "/payroll", icon: "eos" },
    { label_ar: "حساب مكافأة نهاية الخدمة", label_en: "EOS Calculator", to: "/eos", icon: "eos" },
    { label_ar: "التقارير المالية", label_en: "Financial Reports", to: "/reports", icon: "doc" },
  ],
  delegate: [
    { label_ar: "مهامي (تجديدات)", label_en: "My Tasks", to: "/tasks", icon: "tasks" },
    { label_ar: "مركز العمليات", label_en: "Operations", to: "/operations", icon: "scan" },
  ],
  branch_supervisor: [
    { label_ar: "موظفو الفرع", label_en: "Branch Employees", to: "/employees", icon: "employees" },
    { label_ar: "مراجعة الحضور", label_en: "Attendance Review", to: "/attendance-review", icon: "attendance" },
    { label_ar: "الطلبات", label_en: "Requests", to: "/requests", icon: "requests" },
  ],
  employee: [
    { label_ar: "بصمة حضور", label_en: "Punch In", to: "/attendance", icon: "attendance" },
    { label_ar: "تقديم طلب جديد", label_en: "New Request", to: "/requests", icon: "requests" },
    { label_ar: "ملفي الشخصي", label_en: "My Profile", to: "/my-profile", icon: "employees" },
  ],
  admin_employee: [
    { label_ar: "المهام", label_en: "Tasks", to: "/tasks", icon: "tasks" },
    { label_ar: "الطلبات", label_en: "Requests", to: "/requests", icon: "requests" },
  ],
};

const storageKey = (userId: number | undefined) => `hrms:tour:seen:${userId ?? "anon"}`;

export default function WelcomeTour() {
  const { user } = useAuth();
  const { lang } = useI18n();
  const isEn = lang === "en";
  const nav = useNavigate();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!user) return;
    // ?tour=1 → افتحها يدويًا (رابط "أعد جولة التعريف" في الفوتر)
    const forced = new URLSearchParams(window.location.search).get("tour") === "1";
    if (forced) { setOpen(true); return; }
    // تلقائيًا لأول دخول فقط
    const seen = localStorage.getItem(storageKey(user.id));
    if (!seen) setOpen(true);
  }, [user?.id]);

  const close = (remember = true) => {
    if (remember && user) localStorage.setItem(storageKey(user.id), "1");
    setOpen(false);
    // شيل ?tour=1 من الـURL لو موجود
    if (window.location.search.includes("tour=")) {
      window.history.replaceState({}, "", window.location.pathname);
    }
  };

  const goTo = (to: string) => { close(true); nav(to); };

  if (!open || !user) return null;
  const role = user.role || "employee";
  const actions = ACTIONS_BY_ROLE[role] || ACTIONS_BY_ROLE.employee;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="welcome-title"
      onClick={() => close(true)}
      style={{
        position: "fixed", inset: 0, background: "rgba(11,59,84,0.55)",
        display: "grid", placeItems: "center", zIndex: 1000, padding: 20,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "white", borderRadius: 16, padding: 28, maxWidth: 560,
          width: "100%", boxShadow: "0 20px 60px rgba(0,0,0,0.3)",
          maxHeight: "90vh", overflowY: "auto",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: 20 }}>
          <div style={{
            display: "inline-grid", placeItems: "center", width: 64, height: 64,
            borderRadius: "50%", background: "linear-gradient(145deg, #0e5a54, #082523)",
            color: "white", fontSize: 28, marginBottom: 12,
          }}>
            👋
          </div>
          <h2 id="welcome-title" style={{ margin: "0 0 6px", fontSize: 22 }}>
            {isEn ? `Welcome, ${user.full_name}!` : `أهلاً ${user.full_name}!`}
          </h2>
          <div style={{ color: "#6b7280", fontSize: 14 }}>
            {isEn ? "Your role: " : "دورك: "}<b>{isEn ? role : roleAr(role)}</b>
          </div>
        </div>

        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 13, color: "#374151", marginBottom: 10, fontWeight: 600 }}>
            {isEn ? "Quick actions for your role:" : "إجراءات سريعة تناسب دورك:"}
          </div>
          <div style={{ display: "grid", gap: 8 }}>
            {actions.map((a) => (
              <button
                key={a.to}
                onClick={() => goTo(a.to)}
                style={{
                  display: "flex", alignItems: "center", gap: 12, padding: "12px 16px",
                  background: "#f3f7f5", border: "1px solid #e5e7eb", borderRadius: 8,
                  cursor: "pointer", textAlign: "start", width: "100%",
                }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "#e0ece8"; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "#f3f7f5"; }}
              >
                <div style={{
                  display: "grid", placeItems: "center", width: 34, height: 34,
                  borderRadius: 8, background: "#0e5a54", color: "white",
                }}>
                  <Icon name={a.icon} size={16} />
                </div>
                <div style={{ flex: 1, fontWeight: 500, fontSize: 14 }}>
                  {isEn ? a.label_en : a.label_ar}
                </div>
                <Icon name="chevron" size={14} />
              </button>
            ))}
          </div>
        </div>

        <div style={{
          background: "#fef3c7", padding: 10, borderRadius: 8, fontSize: 12,
          color: "#78350f", marginBottom: 16,
        }}>
          <b>💡 {isEn ? "Tip:" : "نصيحة:"}</b>{" "}
          {isEn
            ? "Toggle language anytime from the top bar (🌐)."
            : "بدّل اللغة من الشريط العلوي في أي وقت (🌐)."}
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <button className="ghost sm" onClick={() => close(false)}
            style={{ fontSize: 12 }}>
            {isEn ? "Show again next login" : "أعد الظهور في المرة القادمة"}
          </button>
          <button onClick={() => close(true)}>
            {isEn ? "Got it, let's go!" : "فهمت، هيا نبدأ!"}
          </button>
        </div>
      </div>
    </div>
  );
}
