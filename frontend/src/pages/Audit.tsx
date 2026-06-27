import { useEffect, useState } from "react";
import api from "../api";
import { useI18n } from "../i18n";

export default function Audit() {
  const { t } = useI18n();
  const actionLabel = (a: string) => {
    const key = `audit_act_${a}`;
    const lbl = t(key);
    return lbl === key ? a : lbl;
  };
  const [rows, setRows] = useState<any[]>([]);
  const [action, setAction] = useState("");
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    api.get("/audit", { params: { limit: 200, action: action || undefined } })
      .then((r) => setRows(r.data)).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, [action]);

  const actions = Array.from(new Set(rows.map((r) => r.action)));

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="eyebrow">{t("audit_eyebrow")}</div>
          <h2 style={{ margin: "2px 0 0" }}>{t("audit_title")}</h2>
          <div className="sub">{t("audit_sub")}</div>
        </div>
        <select value={action} onChange={(e) => setAction(e.target.value)} style={{ width: 200 }}>
          <option value="">{t("audit_all")}</option>
          {actions.map((a) => <option key={a} value={a}>{actionLabel(a)}</option>)}
        </select>
      </div>

      <div className="table-wrap">
        <table>
          <thead><tr><th>{t("col_operation")}</th><th>{t("col_entity")}</th><th>{t("col_detail")}</th><th>{t("col_actor")}</th><th>IP</th><th>{t("col_time")}</th></tr></thead>
          <tbody>
            {loading ? <tr><td colSpan={6} className="empty">{t("loading")}</td></tr>
              : rows.map((r) => (
                <tr key={r.id}>
                  <td><span className="pill neutral">{actionLabel(r.action)}</span></td>
                  <td className="muted">{r.entity_type}{r.entity_id ? ` #${r.entity_id}` : ""}</td>
                  <td className="muted">{r.detail}</td>
                  <td>{r.by}</td>
                  <td className="muted">{r.ip}</td>
                  <td className="muted">{new Date(r.at).toLocaleString()}</td>
                </tr>
              ))}
            {!loading && !rows.length && <tr><td colSpan={6} className="empty">{t("no_data")}</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
