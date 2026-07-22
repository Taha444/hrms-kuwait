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
  const [totpCode, setTotpCode] = useState("");
  const [requires2fa, setRequires2fa] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      const u = await login(civilId.trim(), password, requires2fa ? totpCode.trim() : undefined);
      nav(u.must_change_password ? "/change-password" : (u.is_cross_company ? "/select-company" : "/"));
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      // V2.2 §9 — backend returns {requires_2fa: true} on first login attempt for TOTP-enabled users
      if (detail && typeof detail === "object" && detail.requires_2fa) {
        setRequires2fa(true);
        setErr(detail.message || "أدخل رمز التحقق الثنائي");
      } else {
        setErr(errMsg(e, t("login_failed")));
      }
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
        {requires2fa && (
          <div className="field">
            <label htmlFor="login-totp">رمز التحقق الثنائي (2FA)</label>
            <input id="login-totp" value={totpCode} onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              inputMode="numeric" pattern="[0-9]{6}" maxLength={6}
              placeholder="123456" autoFocus dir="ltr"
              style={{ textAlign: "center", letterSpacing: 6, fontSize: 20 }}
              autoComplete="one-time-code" required aria-required="true" />
            <span className="muted" style={{ fontSize: 12 }}>
              افتح تطبيق Authenticator وأدخل الرمز الظاهر (6 خانات)
            </span>
          </div>
        )}
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
