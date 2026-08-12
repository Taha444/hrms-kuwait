// سياق المصادقة: يحفظ المستخدم الحالي وصلاحياته ويوفّر تسجيل الدخول/الخروج
import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import api, { setTokens } from "./api";

export type User = {
  id: number;
  full_name: string | null;
  role: string;
  company_id: number | null;
  permissions: string[];
  must_change_password: boolean;
  employee_id: number | null;
  is_cross_company: boolean;         // موسّع: super_admin/owner/متعدد الشركات
  needs_company_selection?: boolean; // ضيّق: فقط المستخدمين الفعليين متعددي الشركات
  can_submit_on_behalf?: boolean;    // تقديم طلب باسم موظف آخر (HR فقط) — يقرره الخادم
  // R9 §17 — صورة البروفايل
  has_avatar?: boolean;
  avatar_updated_at?: string | null;
};

type AuthCtx = {
  user: User | null;
  loading: boolean;
  login: (civil_id: string, password: string, totp_code?: string) => Promise<User>;
  selectCompany: (companyId: number) => Promise<User>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  can: (perm: string) => boolean;
  activeCompanyId: string | null; // رقم الشركة أو "all" أو null (لم يُختَر بعد)
  setActiveCompany: (id: string | null) => void;
  impersonatingName: string | null;
  impersonate: (userId: number, reason?: string) => Promise<void>;
  stopImpersonating: () => Promise<void>;
};

const Ctx = createContext<AuthCtx>({} as AuthCtx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeCompanyId, setActiveCompanyId] = useState<string | null>(
    localStorage.getItem("active_company_id")
  );

  const setActiveCompany = (id: string | null) => {
    if (id) localStorage.setItem("active_company_id", id);
    else localStorage.removeItem("active_company_id");
    setActiveCompanyId(id);
  };

  const refreshUser = async () => {
    try {
      const r = await api.get("/auth/me");
      setUser(r.data);
    } catch {
      setUser(null);
    }
  };

  useEffect(() => {
    (async () => {
      if (localStorage.getItem("access_token")) await refreshUser();
      setLoading(false);
    })();
  }, []);

  const login = async (civil_id: string, password: string, totp_code?: string) => {
    const body: Record<string, string> = { civil_id, password };
    if (totp_code) body.totp_code = totp_code;
    const r = await api.post("/auth/login", body);
    setTokens(r.data.access_token, r.data.refresh_token);
    // R9 §16 — مستخدم متعدد الشركات: نحفظ قائمة شركاته للـpicker
    if (r.data.is_cross_company && r.data.companies) {
      localStorage.setItem("cross_company_options", JSON.stringify(r.data.companies));
      localStorage.removeItem("active_company_id");
      // نرد user بدون data كامل — الـpicker هيوجهنا لـselect-company
      return {
        is_cross_company: true,
        needs_company_selection: true,  // Login.tsx يقرأها لتوجيه /select-company
        companies: r.data.companies,
      } as any;
    }
    localStorage.removeItem("cross_company_options");
    await refreshUser();
    const me = await api.get("/auth/me");
    setUser(me.data);
    return me.data as User;
  };

  // R9 §16 — استدعاء endpoint select-company بعد اختيار شركة من الـpicker
  const selectCompany = async (companyId: number) => {
    const r = await api.post(`/auth/select-company?company_id=${companyId}`);
    setTokens(r.data.access_token, r.data.refresh_token);
    localStorage.removeItem("cross_company_options");
    setActiveCompany(String(companyId));
    await refreshUser();
    const me = await api.get("/auth/me");
    setUser(me.data);
    return me.data as User;
  };

  const logout = () => {
    setTokens(null, null);
    localStorage.removeItem("active_company_id");
    setUser(null);
    window.location.href = "/login";
  };

  const can = (perm: string) =>
    !!user && (user.role === "super_admin" || user.permissions.includes(perm));

  const impersonate = async (userId: number, reason?: string) => {
    const r = await api.post(`/users/${userId}/impersonate`, null, { params: { reason } });
    localStorage.setItem("imp_backup_access", localStorage.getItem("access_token") || "");
    localStorage.setItem("imp_backup_refresh", localStorage.getItem("refresh_token") || "");
    localStorage.setItem("imp_name", r.data.impersonated.full_name || "مستخدم");
    setTokens(r.data.access_token, r.data.refresh_token);
    localStorage.removeItem("active_company_id");
    window.location.href = "/";
  };
  const stopImpersonating = async () => {
    // يسجّل impersonate_end بمعرفة المُنتحِل الفعلي (P1-04) قبل استعادة رمز الإدارة العليا —
    // بعد الاستعادة لا يعود الرمز الحالي يحمل claim الانتحال فيصبح استدعاؤه بلا معنى.
    try { await api.post("/users/impersonate-end"); } catch { /* لا نمنع الخروج لو فشل التسجيل */ }
    const a = localStorage.getItem("imp_backup_access");
    const rf = localStorage.getItem("imp_backup_refresh");
    setTokens(a, rf || null);
    ["imp_backup_access", "imp_backup_refresh", "imp_name"].forEach((k) => localStorage.removeItem(k));
    window.location.href = "/users";
  };
  const impersonatingName = localStorage.getItem("imp_name");

  return (
    <Ctx.Provider value={{ user, loading, login, selectCompany, logout, refreshUser, can,
      activeCompanyId, setActiveCompany, impersonatingName, impersonate, stopImpersonating }}>
      {children}
    </Ctx.Provider>
  );
}

export const useAuth = () => useContext(Ctx);
