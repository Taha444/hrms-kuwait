import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";
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

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(""); setMsg("");
    try {
      await api.post("/auth/change-password", { old_password: oldP, new_password: newP });
      await refreshUser();
      setMsg("تم التغيير بنجاح");
      setTimeout(() => nav("/"), 600);
    } catch (e: any) {
      setErr(e.response?.data?.detail || "خطأ");
    }
  };

  return (
    <div className="auth-wrap">
      <form className="auth-card" onSubmit={submit}>
        <div className="auth-brand">
          <div className="logo">H<span>R</span></div>
          <h1 style={{ fontSize: 19 }}>{t("change_password")}</h1>
          <span className="muted">يلزم تعيين كلمة مرور جديدة لأول دخول</span>
        </div>
        <div className="field">
          <label>كلمة المرور الحالية</label>
          <input type="password" value={oldP} onChange={(e) => setOldP(e.target.value)} />
        </div>
        <div className="field">
          <label>كلمة المرور الجديدة</label>
          <input type="password" value={newP} onChange={(e) => setNewP(e.target.value)} />
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
