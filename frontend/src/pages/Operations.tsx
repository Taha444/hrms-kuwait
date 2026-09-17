import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import Icon from "../Icon";

const U_PILL: Record<string, string> = { expired: "critical", critical: "critical", warning: "warning", ok: "success" };

export default function Operations() {
  const { t } = useI18n();
  const { can } = useAuth();
  // إنشاءُ ترخيص — النقطُة مبنيٌة والسعُة تُعَدّ عليه، ولا شاشَة تناديها.
  const [lic, setLic] = useState({ name: "", license_no: "", issuing_authority: "",
                                   allowed_workers: "" });
  const [licBusy, setLicBusy] = useState(false);
  const KIND: Record<string, string> = { residency: t("kind_residency"), work_permit: t("kind_work_permit") };
  const days = (d: number) => (d < 0 ? t("expired_since", { n: -d }) : `${d} ${t("days_unit")}`);
  const [branches, setBranches] = useState<any[]>([]);
  const [branch, setBranch] = useState("");
  const [data, setData] = useState<any>(null);
  const [licMsg, setLicMsg] = useState("");

  const load = (b = branch) => api.get("/operations", { params: { branch_id: b || undefined } }).then((r) => setData(r.data));

  const addLicense = async () => {
    if (!lic.name.trim()) return;
    setLicBusy(true); setLicMsg("");
    try {
      await api.post("/licenses", null, { params: {
        name: lic.name.trim(),
        license_no: lic.license_no.trim() || undefined,
        issuing_authority: lic.issuing_authority.trim() || undefined,
        allowed_workers: Number(lic.allowed_workers) || 0,
      } });
      setLic({ name: "", license_no: "", issuing_authority: "", allowed_workers: "" });
      setLicMsg(t("ops_lic_added"));
      load();
    } catch (e: any) {
      setLicMsg(e?.response?.data?.detail || t("error"));
    } finally { setLicBusy(false); }
  };
  useEffect(() => { api.get("/branches").then((r) => setBranches(r.data)).catch(() => {}); load(); }, []);
  if (!data) return <div className="empty">{t("loading")}</div>;

  const c = data.compliance;
  const Risk = ({ n, lbl, color }: any) => (
    <div className="stat" style={{ borderTop: `3px solid ${color}` }}>
      <div className="num" style={{ color }}>{n}</div><div className="lbl">{lbl}</div>
    </div>
  );

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="eyebrow">{t("ops_eyebrow")}</div>
          <h2 style={{ margin: "2px 0 0" }}>{t("operations")}</h2>
          <div className="sub">{t("ops_sub")}</div>
        </div>
        <select aria-label={t("all_branches")} value={branch} onChange={(e) => { setBranch(e.target.value); load(e.target.value); }} style={{ maxWidth: 200 }}>
          <option value="">{t("all_branches")}</option>
          {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
      </div>

      <div className="grid stats">
        <Risk n={c.expired} lbl={t("ops_expired")} color="var(--danger)" />
        <Risk n={c.critical} lbl={t("ops_critical")} color="var(--warning)" />
        <Risk n={c.warning} lbl={t("ops_warning")} color="var(--info)" />
        <Link to="/requests" className="stat" style={{ textDecoration: "none" }}>
          <div className="num">{data.pending_requests}</div><div className="lbl">{t("kpi_pending_requests")}</div>
        </Link>
        {/* BKL-06 — الرقم وقائمته في شاشة واحدة. كان ينقل إلى «مهامي»
            وهو يعدّ مهام الشركة كلها: 29 في البطاقة و12 في الوجهة، لأن
            المهام موزّعة على عدّة مندوبين. */}
        <a href="#gov-tasks" className="stat" style={{ textDecoration: "none" }}>
          <div className="num">{data.open_gov_tasks}</div><div className="lbl">{t("ops_gov_tasks")}</div>
        </a>
      </div>

      {/* BKL-06 — القائمة التي يعدّها الرقم أعلاه، بالنطاق نفسه */}
      <div className="card" id="gov-tasks">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h3 style={{ margin: 0 }}>{t("ops_gov_tasks")} ({data.open_gov_tasks})</h3>
        </div>
        {!(data.gov_tasks || []).length ? (
          <p className="muted">{t("ops_no_gov_tasks")}</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr>
                <th>{t("col_title")}</th><th>{t("ops_col_due")}</th>
                <th>{t("ops_col_severity")}</th>
              </tr></thead>
              <tbody>
                {(data.gov_tasks || []).map((k: any) => (
                  <tr key={k.id}>
                    <td>{k.title}{k.detail && <div className="muted" style={{ fontSize: 12 }}>{k.detail}</div>}</td>
                    <td>{k.due_date || "—"}</td>
                    <td>{k.severity || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h3 style={{ margin: 0 }}>{t("ops_permits_title")}</h3>
          <Link to="/pro"><button className="ghost sm">{t("ops_manage")}</button></Link>
        </div>
        <table style={{ marginTop: 10 }}>
          <thead><tr><th>{t("col_type")}</th><th>{t("col_employee")}</th><th>{t("col_number")}</th><th>{t("col_expiry")}</th><th>{t("col_remaining")}</th></tr></thead>
          <tbody>
            {data.permits.map((p: any) => (
              <tr key={p.id}>
                <td>{KIND[p.type] || p.type}</td><td>{p.employee}</td>
                <td className="muted">{p.number}</td><td>{p.expiry_date}</td>
                <td><span className={`pill ${U_PILL[p.urgency]}`}>{days(p.days_left)}</span></td>
              </tr>
            ))}
            {!data.permits.length && <tr><td colSpan={5} className="empty">{t("none_good")}</td></tr>}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>{t("ops_licenses_title")}</h3>
        <table>
          <thead><tr><th>{t("col_license")}</th><th>{t("col_number")}</th><th>{t("col_expiry")}</th><th>{t("col_remaining")}</th></tr></thead>
          <tbody>
            {data.licenses.map((l: any) => (
              <tr key={l.id}>
                <td><b>{l.name}</b></td><td className="muted">{l.license_no}</td>
                <td>{l.expiry_date}</td>
                <td><span className={`pill ${U_PILL[l.urgency]}`}>{days(l.days_left)}</span></td>
              </tr>
            ))}
            {!data.licenses.length && <tr><td colSpan={4} className="empty">{t("none_good")}</td></tr>}
          </tbody>
        </table>
        {/* ``POST /licenses`` كانت مبنيًّة بلا باب: لا شاشَة تُنشئ ترخيًصا،
            وسعُة العمالة تُعَدّ عليه. */}
        {can("manage_licenses") && (
          <div className="row" style={{ gap: 8, marginTop: 10, alignItems: "flex-end", flexWrap: "wrap" }}>
            <div className="field">
              <label htmlFor="ops-lic-name">{t("ops_lic_name")}</label>
              <input id="ops-lic-name" value={lic.name}
                     onChange={(e) => setLic({ ...lic, name: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="ops-lic-no">{t("ops_lic_no")}</label>
              <input id="ops-lic-no" value={lic.license_no}
                     onChange={(e) => setLic({ ...lic, license_no: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="ops-lic-auth">{t("ops_lic_authority")}</label>
              <input id="ops-lic-auth" value={lic.issuing_authority}
                     onChange={(e) => setLic({ ...lic, issuing_authority: e.target.value })} />
            </div>
            <div className="field" style={{ width: 140 }}>
              <label htmlFor="ops-lic-allowed">{t("ops_lic_allowed")}</label>
              <input id="ops-lic-allowed" type="number" min={0} value={lic.allowed_workers}
                     onChange={(e) => setLic({ ...lic, allowed_workers: e.target.value })} />
            </div>
            <button disabled={licBusy || !lic.name.trim()} onClick={addLicense}>{t("ops_lic_add")}</button>
            <div className="sub" style={{ width: "100%" }}>{t("ops_lic_hint")}</div>
            {licMsg && <div className="sub" style={{ width: "100%" }}>{licMsg}</div>}
          </div>
        )}
      </div>

      {/* قرار المالك (2026-09-17) — تنبيهٌ تفتيشي: العمل على غير ترخيص التسجيل. */}
      <div className="card">
        <h3>{t("ops_lic_mismatch_title")} ({(data.license_mismatch || []).length})</h3>
        <div className="sub" style={{ marginBottom: 8 }}>{t("ops_lic_mismatch_hint")}</div>
        <table>
          <thead><tr><th>{t("col_employee")}</th><th>{t("lic_registered")}</th><th>{t("lic_actual")}</th></tr></thead>
          <tbody>
            {(data.license_mismatch || []).map((m: any) => (
              <tr key={m.employee_id}>
                <td><a href={`/employees/${m.employee_id}`}><b>{m.name}</b></a></td>
                <td className="muted">{m.license_name || t("lic_none")}</td>
                <td><span className="pill warning">{m.actual_license_name}</span></td>
              </tr>
            ))}
            {!(data.license_mismatch || []).length && <tr><td colSpan={3} className="empty">{t("none_good")}</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
