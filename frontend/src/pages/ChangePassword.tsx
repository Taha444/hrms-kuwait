import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { errMsg } from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";

export default function ChangePassword() {
  const { refreshUser, logout } = useAuth();
  const { t } = useI18n();
  const nav = useNavigate();
  const [oldP, setOldP] = useState("");
  const [newP, setNewP] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  // نفس سياسة الخادم (SEC-01): 8 أحرف على الأقل وحرف ورقم — تحقّق فوري بدل انتظار 422 (QA-P1-AUTH-01)
  const pwValid = newP.length >= 8 && /[A-Za-z؀-ۿ]/.test(newP) && /\d/.test(newP);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(""); setMsg("");
    if (!oldP || !pwValid) {
      setErr(t("pw_policy_error"));
      return;
    }
    try {
      await api.post("/auth/change-password", { old_password: oldP, new_password: newP });
      await refreshUser();
      setMsg(t("pw_changed"));
      setTimeout(() => nav("/"), 600);
    } catch (e: any) {
      setErr(errMsg(e, t("error")));
    }
  };

  return (
    <div className="auth-wrap">
      <form className="auth-card" onSubmit={submit}>
        <div className="auth-brand">
          <div className="logo">H<span>R</span></div>
          <h1 style={{ fontSize: 19 }}>{t("change_password")}</h1>
          <span className="muted">{t("pw_first_login")}</span>
        </div>
        <div className="field">
          <label htmlFor="cp-old">{t("pw_current")} *</label>
          <input id="cp-old" type="password" required value={oldP} onChange={(e) => setOldP(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="cp-new">{t("pw_new")} *</label>
          <input id="cp-new" type="password" required minLength={8}
            value={newP} onChange={(e) => setNewP(e.target.value)} />
          <p className="muted" style={{ fontSize: 12, margin: "4px 0 0" }}>{t("pw_policy_hint")}</p>
        </div>
        {err && <div className="err">{err}</div>}
        {msg && <div className="ok">{msg}</div>}
        <div className="row">
          <button>{t("save")}</button>
          <button type="button" className="ghost" onClick={logout}>{t("logout")}</button>
        </div>
      </form>
    </div>
  );
}
