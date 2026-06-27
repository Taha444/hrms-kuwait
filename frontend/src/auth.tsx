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
  is_cross_company: boolean;
};

type AuthCtx = {
  user: User | null;
  loading: boolean;
  login: (civil_id: string, password: string) => Promise<User>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  can: (perm: string) => boolean;
  activeCompanyId: string | null; // رقم الشركة أو "all" أو null (لم يُختَر بعد)
  setActiveCompany: (id: string | null) => void;
  impersonatingName: string | null;
  impersonate: (userId: number, reason?: string) => Promise<void>;
  stopImpersonating: () => void;
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

  const login = async (civil_id: string, password: string) => {
    const r = await api.post("/auth/login", { civil_id, password });
    setTokens(r.data.access_token, r.data.refresh_token);
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
  const stopImpersonating = () => {
    const a = localStorage.getItem("imp_backup_access");
    const rf = localStorage.getItem("imp_backup_refresh");
    setTokens(a, rf || null);
    ["imp_backup_access", "imp_backup_refresh", "imp_name"].forEach((k) => localStorage.removeItem(k));
    window.location.href = "/users";
  };
  const impersonatingName = localStorage.getItem("imp_name");

  return (
    <Ctx.Provider value={{ user, loading, login, logout, refreshUser, can, activeCompanyId,
      setActiveCompany, impersonatingName, impersonate, stopImpersonating }}>
      {children}
    </Ctx.Provider>
  );
}

export const useAuth = () => useContext(Ctx);
