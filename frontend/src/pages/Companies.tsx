import { useEffect, useState } from "react";
import api, { errMsg } from "../api";
import { useI18n } from "../i18n";
import { statusAr } from "../labels";

export default function Companies() {
  const { t } = useI18n();
  const [list, setList] = useState<any[]>([]);
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState<any>({ name: "", eos_day_divisor: 26, eos_max_months: 18, alert_lead_days: 30, annual_leave_days: 30 });
  const [err, setErr] = useState("");

  const load = () => api.get("/companies").then((r) => setList(r.data));
  useEffect(() => { load(); }, []);

  const create = async () => {
    setErr("");
    try { await api.post("/companies", form); setShowNew(false); load(); }
    catch (e: any) { setErr(errMsg(e, t("error"))); }
  };
  const setStatus = async (id: number, status: string) => {
    await api.post(`/companies/${id}/status?status=${status}`); load();
  };

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2>{t("companies")}</h2>
        <button onClick={() => setShowNew((s) => !s)}>{t("company_new")}</button>
      </div>
      {showNew && (
        <div className="card">
          <div className="row">
            <div className="field" style={{ flex: 2 }}><label htmlFor="co-name">{t("col_name")}</label>
              <input id="co-name" onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
            <div className="field" style={{ flex: 1 }}><label htmlFor="co-reg">{t("company_reg")}</label>
              <input id="co-reg" onChange={(e) => setForm({ ...form, commercial_reg: e.target.value })} /></div>
            <div className="field" style={{ width: 120 }}><label htmlFor="co-eos-divisor">{t("eos")}</label>
              <select id="co-eos-divisor" value={form.eos_day_divisor} onChange={(e) => setForm({ ...form, eos_day_divisor: +e.target.value })}>
                <option value={26}>26</option><option value={30}>30</option></select></div>
          </div>
          {err && <div className="err">{err}</div>}
          <button onClick={create}>{t("save")}</button>
        </div>
      )}
      <div className="table-wrap">
        <table>
          <thead><tr><th>{t("col_name")}</th><th>{t("company_reg")}</th><th>{t("eos")}</th><th>{t("status")}</th><th></th></tr></thead>
          <tbody>{list.map((c) => (
            <tr key={c.id}><td>{c.name}</td><td>{c.commercial_reg}</td><td>{c.eos_day_divisor}</td>
              <td><span className="pill info">{statusAr(c.status)}</span></td>
              <td className="row">
                <button className="ghost sm" onClick={() => setStatus(c.id, c.status === "active" ? "inactive" : "active")}>
                  {c.status === "active" ? t("company_disable") : t("company_enable")}</button>
                <button className="ghost sm" onClick={() => setStatus(c.id, "archived")}>{t("company_archive_action")}</button>
              </td></tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  );
}
