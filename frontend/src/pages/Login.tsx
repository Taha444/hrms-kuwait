import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import { errMsg } from "../api";

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
      setErr(errMsg(e, t("login_failed")));
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="auth-wrap" role="main" aria-labelledby="login-title">
      <form className="auth-card" onSubmit={submit} aria-describedby={err ? "login-error" : undefined}>
        <div className="auth-brand">
          <div className="logo" aria-hidden="true">H<span>R</span></div>
          <h1 id="login-title">{t("app_name")}</h1>
          <span className="muted">{t("app_tagline")}</span>
        </div>
        <div className="field">
          <label htmlFor="login-civil-id">{t("civil_id")}</label>
          <input id="login-civil-id" value={civilId} onChange={(e) => setCivilId(e.target.value)} inputMode="numeric"
            placeholder="٠٠٠٠٠٠٠٠٠٠٠٠" autoFocus dir="ltr" style={{ textAlign: "center", letterSpacing: 2 }}
            autoComplete="username" required aria-required="true" />
        </div>
        <div className="field">
          <label htmlFor="login-password">{t("password")}</label>
          <input id="login-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
            dir="ltr" autoComplete="current-password" required aria-required="true" />
        </div>
        {err && <div className="err" id="login-error" role="alert" aria-live="assertive">{err}</div>}
        <button style={{ width: "100%", marginTop: 4 }} disabled={busy} aria-busy={busy}>
          {busy ? t("loading") : t("login")}
        </button>
        <p className="muted" style={{ marginTop: 16, textAlign: "center" }}>
          {t("demo_hint")} <code>000000000000</code> / <code>admin123</code>
        </p>
      </form>
    </main>
  );
}
