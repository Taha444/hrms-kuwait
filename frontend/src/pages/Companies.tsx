import { useEffect, useState } from "react";
import api, { errMsg } from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import { statusAr } from "../labels";

export default function Companies() {
  const { t } = useI18n();
  // إنشاءُ الشركات وتعطيلُها للإدارة العليا، وتعديلُ بياناتها بـmanage_company
  // (قرار المالك 2026-09-11) — والشاشةُ كانت كلُّها للإدارة العليا وحدها.
  const { user, can } = useAuth();
  // قرار المالك (2026-09-18): صاحبُ الشركات يُنشئ ويعطّل كالإدارة العليا.
  const isAdmin = user?.role === "super_admin" || user?.role === "company_owner";
  const mayEdit = isAdmin || can("manage_company");
  const [list, setList] = useState<any[]>([]);
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState<any>({ name: "", eos_day_divisor: 26, eos_max_months: 18, alert_lead_days: 30, annual_leave_days: 30 });
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [editing, setEditing] = useState<any>(null);

  const load = () => api.get("/companies").then((r) => setList(r.data));
  useEffect(() => { load(); }, []);

  const create = async () => {
    setErr("");
    try { await api.post("/companies", form); setShowNew(false); load(); }
    catch (e: any) { setErr(errMsg(e, t("error"))); }
  };
  const openEdit = (c: any) => {
    setErr(""); setMsg("");
    setEditing({
      id: c.id, name: c.name || "", name_en: c.name_en || "",
      commercial_reg: c.commercial_reg || "", entity_type: c.entity_type || "",
      file_number: c.file_number || "",
      eos_day_divisor: c.eos_day_divisor ?? 26, eos_max_months: c.eos_max_months ?? 18,
      alert_lead_days: c.alert_lead_days ?? 30, annual_leave_days: c.annual_leave_days ?? 30,
    });
  };

  const saveEdit = async () => {
    setErr(""); setMsg("");
    const { id, ...body } = editing;
    try {
      await api.put(`/companies/${id}`, body);
      setEditing(null); setMsg(t("co_saved")); load();
    } catch (e: any) { setErr(errMsg(e, t("error"))); }
  };

  const setStatus = async (id: number, status: string) => {
    await api.post(`/companies/${id}/status?status=${status}`); load();
  };

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2>{t("companies")}</h2>
        {isAdmin && <button onClick={() => setShowNew((s) => !s)}>{t("company_new")}</button>}
      </div>
      {msg && <div className="ok">{msg}</div>}
      {editing && (
        <div className="card" style={{ borderInlineStart: "4px solid var(--brand)" }}>
          <h3 style={{ marginTop: 0 }}>{t("co_edit_title")}</h3>
          <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
            {([["name", t("col_name")], ["name_en", t("co_name_en")],
               ["commercial_reg", t("company_reg")], ["entity_type", t("co_entity_type")],
               ["file_number", t("co_file_number")]] as [string, string][]).map(([k, label]) => (
              <div className="field" key={k} style={{ flex: 1, minWidth: 180 }}>
                <label htmlFor={`co-e-${k}`}>{label}</label>
                <input id={`co-e-${k}`} value={editing[k]}
                       onChange={(e) => setEditing({ ...editing, [k]: e.target.value })} />
              </div>
            ))}
          </div>
          <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
            <div className="field" style={{ width: 170 }}>
              <label htmlFor="co-e-divisor">{t("co_eos_divisor")}</label>
              <select id="co-e-divisor" value={editing.eos_day_divisor}
                      onChange={(e) => setEditing({ ...editing, eos_day_divisor: +e.target.value })}>
                <option value={26}>26</option><option value={30}>30</option>
              </select>
            </div>
            {([["eos_max_months", t("co_eos_max")], ["alert_lead_days", t("co_alert_lead")],
               ["annual_leave_days", t("co_annual_leave")]] as [string, string][]).map(([k, label]) => (
              <div className="field" key={k} style={{ width: 170 }}>
                <label htmlFor={`co-e-${k}`}>{label}</label>
                <input id={`co-e-${k}`} type="number" min={0} value={editing[k]}
                       onChange={(e) => setEditing({ ...editing, [k]: +e.target.value })} />
              </div>
            ))}
          </div>
          <div className="sub">{t("co_money_hint")}</div>
          {err && <div className="err">{err}</div>}
          <div className="row" style={{ marginTop: 8 }}>
            <button onClick={saveEdit}>{t("save")}</button>
            <button className="ghost" onClick={() => setEditing(null)}>{t("cancel")}</button>
          </div>
        </div>
      )}
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
                {mayEdit && (
                  <button className="ghost sm" onClick={() => openEdit(c)}>{t("co_edit")}</button>
                )}
                {isAdmin && (<>
                <button className="ghost sm" onClick={() => setStatus(c.id, c.status === "active" ? "inactive" : "active")}>
                  {c.status === "active" ? t("company_disable") : t("company_enable")}</button>
                <button className="ghost sm" onClick={() => setStatus(c.id, "archived")}>{t("company_archive_action")}</button>
                </>)}
              </td></tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  );
}
