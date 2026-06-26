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

  return (
    <Ctx.Provider value={{ user, loading, login, logout, refreshUser, can, activeCompanyId, setActiveCompany }}>
      {children}
    </Ctx.Provider>
  );
}

export const useAuth = () => useContext(Ctx);
