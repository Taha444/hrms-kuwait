import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";

export default function Login() {
  const { login } = useAuth();
  const { t } = useI18n();
  const nav = useNavigate();
  const [civilId, setCivilId] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      const u = await login(civilId.trim(), password);
      nav(u.must_change_password ? "/change-password" : (u.is_cross_company ? "/select-company" : "/"));
    } catch (e: any) {
      setErr(e.response?.data?.detail || "تعذّر تسجيل الدخول");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-wrap">
      <form className="auth-card" onSubmit={submit}>
        <div className="auth-brand">
          <div className="logo">H<span>R</span></div>
          <h1>نظام الموارد البشرية</h1>
          <span className="muted">الكويت · منصّة متعددة الشركات</span>
        </div>
        <div className="field">
          <label>{t("civil_id")}</label>
          <input value={civilId} onChange={(e) => setCivilId(e.target.value)} inputMode="numeric"
            placeholder="٠٠٠٠٠٠٠٠٠٠٠٠" autoFocus dir="ltr" style={{ textAlign: "center", letterSpacing: 2 }} />
        </div>
        <div className="field">
          <label>{t("password")}</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} dir="ltr" />
        </div>
        {err && <div className="err">{err}</div>}
        <button style={{ width: "100%", marginTop: 4 }} disabled={busy}>
          {busy ? t("loading") : t("login")}
        </button>
        <p className="muted" style={{ marginTop: 16, textAlign: "center" }}>
          تجريبي — إدارة عليا: <code>000000000000</code> / <code>admin123</code>
        </p>
      </form>
    </div>
  );
}
