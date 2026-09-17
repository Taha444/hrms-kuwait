import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { errMsg } from "../api";
import { useAuth } from "../auth";
import Icon from "../Icon";
import { useI18n } from "../i18n";
import { roleAr } from "../labels";

// R9 §16 — شاشة اختيار الشركة لمستخدم متعدد الشركات (مثل مندوب يخدم شركتين).
// تختلف عن CompanyPicker (اللي للـsuper_admin بيختار من كل الشركات):
// هنا نقرأ فقط شركات المستخدم من /auth/my-companies، وننادي /auth/select-company
// اللي بيرد access_token جديد بـactive_company_id claim.
export default function SelectCompany() {
  const { user, selectCompany, logout } = useAuth();
  const { t } = useI18n();
  const nav = useNavigate();
  const [companies, setCompanies] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<number | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    // نحاول أولًا من localStorage (تم حفظها من login response)
    const cached = localStorage.getItem("cross_company_options");
    if (cached) {
      try {
        setCompanies(JSON.parse(cached));
        setLoading(false);
        return;
      } catch { /* fallthrough للـAPI */ }
    }
    api.get("/auth/my-companies")
      .then((r) => setCompanies(r.data.companies || []))
      .catch((e) => setErr(errMsg(e, t("sc_load_failed"))))
      .finally(() => setLoading(false));
  }, []);

  const choose = async (companyId: number) => {
    setBusy(companyId); setErr("");
    try {
      await selectCompany(companyId);
      nav("/", { replace: true });
    } catch (e: any) {
      setErr(errMsg(e, t("sc_choose_failed")));
    } finally {
      setBusy(null);
    }
  };

  const mono = (name: string) => (name || "?").trim().slice(0, 2);

  return (
    <div className="picker-wrap">
      <div className="picker-inner">
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 6 }}>
          <div className="row" style={{ gap: 12 }}>
            <div className="company-switch" style={{ cursor: "default" }}>
              <span className="mono">HR</span>
              <span>{user?.full_name || t("sc_multi_user")}</span>
            </div>
          </div>
          <button className="ghost" onClick={logout}>
            <Icon name="logout" size={16} /> {t("sc_logout")}
          </button>
        </div>

        <div style={{ margin: "10px 0 26px" }}>
          <div className="eyebrow">{t("sc_hello")}</div>
          <h2 style={{ fontSize: 30, margin: "4px 0 4px" }}>{t("sc_title")}</h2>
          <p className="muted">
            {t("sc_count", { n: companies.length })}
          </p>
        </div>

        {err && <div className="err" style={{ marginBottom: 12 }}>{err}</div>}

        {loading ? (
          <div className="empty">{t("sc_loading")}</div>
        ) : companies.length === 0 ? (
          <div className="empty">
            {t("sc_none")}
          </div>
        ) : (
          <div className="grid cards">
            {companies.map((c) => (
              <button key={c.id} className="company-card"
                      onClick={() => choose(c.id)}
                      disabled={busy !== null}
                      style={{
                        cursor: busy === c.id ? "wait" : "pointer",
                        opacity: busy !== null && busy !== c.id ? 0.5 : 1,
                      }}>
                <div className="mono">{mono(c.name)}</div>
                <h3>{c.name}</h3>
                <p className="muted">{c.name_en || "—"}</p>
                <div style={{ marginTop: 10 }}>
                  <span className="pill info">{roleAr(c.role || "delegate")}</span>
                </div>
                {busy === c.id && (
                  <p className="muted" style={{ fontSize: 12, marginTop: 6 }}>
                    {t("sc_choosing")}
                  </p>
                )}
              </button>
            ))}
          </div>
        )}

        <p className="muted" style={{ marginTop: 20, fontSize: 12, textAlign: "center" }}>
          {t("sc_tip")}
        </p>
      </div>
    </div>
  );
}
