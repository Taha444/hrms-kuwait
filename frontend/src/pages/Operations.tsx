import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import { useI18n } from "../i18n";
import Icon from "../Icon";

const U_PILL: Record<string, string> = { expired: "critical", critical: "critical", warning: "warning", ok: "success" };

export default function Operations() {
  const { t } = useI18n();
  const KIND: Record<string, string> = { residency: t("kind_residency"), work_permit: t("kind_work_permit") };
  const days = (d: number) => (d < 0 ? t("expired_since", { n: -d }) : `${d} ${t("days_unit")}`);
  const [branches, setBranches] = useState<any[]>([]);
  const [branch, setBranch] = useState("");
  const [data, setData] = useState<any>(null);

  const load = (b = branch) => api.get("/operations", { params: { branch_id: b || undefined } }).then((r) => setData(r.data));
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
        <select value={branch} onChange={(e) => { setBranch(e.target.value); load(e.target.value); }} style={{ maxWidth: 200 }}>
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
        <Link to="/tasks" className="stat" style={{ textDecoration: "none" }}>
          <div className="num">{data.open_gov_tasks}</div><div className="lbl">{t("ops_gov_tasks")}</div>
        </Link>
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
      </div>
    </div>
  );
}
