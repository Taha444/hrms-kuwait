// عميل الـ API: يضيف رمز الدخول تلقائيًا ويجدّده عند انتهائه
import axios from "axios";

const api = axios.create({ baseURL: "/api" });

export function setTokens(access: string | null, refresh?: string | null) {
  if (access) localStorage.setItem("access_token", access);
  else localStorage.removeItem("access_token");
  if (refresh !== undefined) {
    if (refresh) localStorage.setItem("refresh_token", refresh);
    else localStorage.removeItem("refresh_token");
  }
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  // حقن الشركة المختارة (للإدارة العليا/المالك) في طلبات العرض تلقائيًا
  const active = localStorage.getItem("active_company_id");
  const method = (config.method || "get").toLowerCase();
  if (active && active !== "all" && method === "get") {
    config.params = { company_id: Number(active), ...(config.params || {}) };
  }
  return config;
});

let refreshing = false;
api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry && !refreshing) {
      const refresh = localStorage.getItem("refresh_token");
      if (refresh) {
        original._retry = true;
        refreshing = true;
        try {
          const r = await axios.post("/api/auth/refresh", { refresh_token: refresh });
          setTokens(r.data.access_token, r.data.refresh_token);
          refreshing = false;
          original.headers.Authorization = `Bearer ${r.data.access_token}`;
          return api(original);
        } catch {
          refreshing = false;
          setTokens(null, null);
          window.location.href = "/login";
        }
      }
    }
    return Promise.reject(error);
  }
);

// تنزيل ملف (Excel/CSV) مع إرفاق رمز الدخول وفكّ اسم الملف من الترويسة
export async function downloadFile(path: string, params: any, fallbackName: string) {
  const res = await api.get(path, { params, responseType: "blob" });
  const cd = res.headers["content-disposition"] || "";
  const m = /filename="?([^"]+)"?/.exec(cd);
  const name = m ? decodeURIComponent(m[1]) : fallbackName;
  const url = URL.createObjectURL(res.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// تصدير تقرير حساس (رواتب/نهاية خدمة) — يتطلب سببًا صريحًا يُسجَّل في التدقيق (FIX-016)
export async function downloadSensitiveReport(path: string, params: any, fallbackName: string,
                                              promptText: string) {
  const reason = window.prompt(promptText);
  if (!reason || !reason.trim()) return;
  return downloadFile(path, { ...params, reason }, fallbackName);
}

export default api;
