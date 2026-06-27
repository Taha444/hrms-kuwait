import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import api from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import { attAr, statusAr } from "../labels";

export default function EmployeeProfile() {
  const { id } = useParams();
  const { can } = useAuth();
  const { t, lang } = useI18n();
  const [p, setP] = useState<any>(null);
  const [docType, setDocType] = useState("passport");
  const [suggested, setSuggested] = useState<any>(null);
  const [msg, setMsg] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const [term, setTerm] = useState({ end_date: "", reason: "termination" });
  const [settlement, setSettlement] = useState<any>(null);
  const [consumed, setConsumed] = useState(0);
  const [leaveBal, setLeaveBal] = useState<any>(null);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [evForm, setEvForm] = useState({ kind: "warning", title: "", amount: "" });

  const EMP_STATUS: Record<string, string> = {
    active: t("empst_active"), vacation: t("empst_vacation"), suspended: t("empst_suspended"),
    resigned: t("empst_resigned"), terminated: t("empst_terminated"), retired: t("empst_retired"),
  };
  const EV_AR: Record<string, string> = {
    warning: t("ev_warning"), penalty: t("ev_penalty"), bonus: t("ev_bonus"),
    promotion: t("ev_promotion"), note: t("ev_note"),
  };
  const REASONS: Record<string, string> = {
    termination: t("rsn_termination"), contract_expiry: t("rsn_contract_expiry"), resignation: t("rsn_resignation"),
    death: t("rsn_death"), disability: t("rsn_disability"), misconduct: t("rsn_misconduct"),
  };
  const kwd = t("kwd_currency");
  const genderLabel = (g: string) => g === "male" ? t("gender_male") : g === "female" ? t("gender_female") : "—";

  const loadExtras = () => {
    api.get(`/employees/${id}/timeline`).then((r) => setTimeline(r.data.timeline)).catch(() => {});
    api.get(`/employees/${id}/events`).then((r) => setEvents(r.data)).catch(() => {});
  };
  useEffect(() => { loadExtras(); }, [id]);

  const calcLeave = async () => {
    const r = await api.post("/eos/leave-balance", null, { params: { employee_id: id, consumed_days: consumed } });
    setLeaveBal(r.data);
  };
  const changeStatus = async (status: string) => {
    await api.post(`/employees/${id}/status`, null, { params: { status } });
    setMsg(t("epf_status_changed")); load();
  };
  const addEvent = async () => {
    if (!evForm.title) return;
    await api.post(`/employees/${id}/events`, null, { params: {
      kind: evForm.kind, title: evForm.title, amount: evForm.amount || undefined } });
    setEvForm({ kind: "warning", title: "", amount: "" }); loadExtras();
  };

  const terminate = async () => {
    if (!term.end_date) return;
    if (!confirm(t("epf_term_confirm"))) return;
    const r = await api.post(`/employees/${id}/terminate`, null, { params: term });
    setSettlement(r.data.settlement); setMsg(t("epf_terminated_msg")); load();
  };

  const load = () => api.get(`/employees/${id}/profile`).then((r) => setP(r.data));
  useEffect(() => { load(); }, [id]);
  if (!p) return <div>…</div>;
  const e = p.employee;

  const ocrPreview = async (file: File) => {
    const fd = new FormData();
    fd.append("document_type_code", docType);
    fd.append("file", file);
    const r = await api.post("/documents/ocr-preview", fd);
    setSuggested(r.data.suggested);
  };

  const upload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("entity_type", "employee");
    fd.append("entity_id", String(id));
    fd.append("document_type_code", docType);
    fd.append("file", file);
    await api.post("/documents/upload", fd);
    setMsg(t("epf_doc_uploaded")); setSuggested(null);
    if (fileRef.current) fileRef.current.value = "";
    load();
  };

  const downloadLatest = (type: string) =>
    window.open(`/api/documents/latest?entity_type=employee&entity_id=${id}&document_type_code=${type}`, "_blank");

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ margin: 0 }}>{e.name} <span className={`pill ${e.status === "active" ? "success" : "neutral"}`}>{EMP_STATUS[e.status] || statusAr(e.status)}</span></h2>
        {can("edit_employee") && (
          <div className="row">
            <span className="muted">{t("emp_status")}:</span>
            <select value={e.status} onChange={(ev) => changeStatus(ev.target.value)} style={{ width: 160 }}>
              {Object.entries(EMP_STATUS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
        )}
      </div>
      {msg && <div className="ok">{msg}</div>}
      <div className="grid cards">
        <div className="card"><b>{t("epf_job")}:</b> {e.job_title || "—"}<br /><b>{t("epf_nationality")}:</b> {e.nationality || "—"}<br />
          <b>{t("epf_salary")}:</b> {e.basic_salary} {kwd}<br /><b>{t("epf_hire")}:</b> {e.hire_date || "—"}<br /><b>{t("epf_contract")}:</b> {e.contract_type}</div>
        <div className="card"><b>{t("epf_gender")}:</b> {genderLabel(e.gender)}<br />
          <b>{t("epf_dob")}:</b> {e.date_of_birth || "—"}<br /><b>{t("epf_marital")}:</b> {e.marital_status || "—"}<br />
          <b>{t("epf_email")}:</b> {e.email || "—"}</div>
        <div className="card"><b>{t("epf_passport")}:</b> {e.passport_number || "—"}<br />
          <b>{t("epf_passport_expiry")}:</b> {e.passport_expiry || "—"}<br /><b>{t("epf_health")}:</b> {e.health_insurance || "—"}<br />
          <b>{t("epf_att_mode")}:</b> {e.attendance_mode}</div>
      </div>

      <div className="card">
        <h3>{t("emp_permits")}</h3>
        <table><thead><tr><th>{t("epf_col_type")}</th><th>{t("pro_col_number")}</th><th>{t("pro_col_expiry")}</th><th>{t("status")}</th></tr></thead>
          <tbody>{p.permits.map((x: any) => (
            <tr key={x.id}><td>{x.kind}</td><td>{x.number}</td><td>{x.expiry_date}</td>
              <td><span className="pill info">{statusAr(x.status)}</span></td></tr>
          ))}{!p.permits.length && <tr><td colSpan={4} className="muted">{t("att_no_records")}</td></tr>}</tbody></table>
      </div>

      <div className="card">
        <h3>{t("emp_documents")}</h3>
        <table><thead><tr><th>{t("epf_col_type")}</th><th>{t("col_title")}</th><th>{t("epf_col_version")}</th><th>{t("pro_col_expiry")}</th><th></th></tr></thead>
          <tbody>{p.documents.map((d: any) => (
            <tr key={d.id}><td>{d.type}</td><td>{d.title}</td><td>v{d.version}</td><td>{d.expiry_date}</td>
              <td><button className="ghost" onClick={() => downloadLatest(d.type)}>{t("epf_download_latest")}</button></td></tr>
          ))}{!p.documents.length && <tr><td colSpan={5} className="muted">{t("att_no_records")}</td></tr>}</tbody></table>

        {can("upload_documents") && (
          <div style={{ marginTop: 14, borderTop: "1px solid var(--border)", paddingTop: 14 }}>
            <h4>{t("epf_upload_title")}</h4>
            <div className="row">
              <select value={docType} onChange={(e) => setDocType(e.target.value)} style={{ width: 200 }}>
                <option value="passport">{t("epf_doc_passport")}</option>
                <option value="civil_id">{t("epf_doc_civil")}</option>
                <option value="residency">{t("epf_doc_residency")}</option>
                <option value="contract">{t("epf_doc_contract")}</option>
              </select>
              <input type="file" ref={fileRef}
                onChange={(e) => e.target.files && ocrPreview(e.target.files[0])} />
              <button onClick={upload}>{t("epf_upload_save")}</button>
            </div>
            {suggested && (
              <div className="card" style={{ background: "#f8fafc", marginTop: 10 }}>
                <b>{t("epf_ocr_suggested")}</b>
                <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(suggested, null, 2)}</pre>
              </div>
            )}
            {msg && <div className="ok">{msg}</div>}
          </div>
        )}
      </div>

      <div className="card">
        <h3>{t("emp_recent_att")}</h3>
        <table><thead><tr><th>{t("col_in")}</th><th>{t("col_out")}</th><th>{t("status")}</th><th>{t("epf_col_selfie")}</th></tr></thead>
          <tbody>{p.attendance.map((a: any) => (
            <tr key={a.id}><td>{a.check_in_at && new Date(a.check_in_at).toLocaleString(lang)}</td>
              <td>{a.check_out_at && new Date(a.check_out_at).toLocaleString(lang)}</td>
              <td><span className={`pill ${a.status === "late" ? "warning" : "success"}`}>{attAr(a.status)}</span></td>
              <td>{a.selfie_in ? "✓" : "—"}</td></tr>
          ))}{!p.attendance.length && <tr><td colSpan={4} className="muted">{t("att_no_records")}</td></tr>}</tbody></table>
      </div>

      <div className="card">
        <h3>{t("emp_hr_log")}</h3>
        {can("edit_employee") && (
          <div className="row" style={{ marginBottom: 10 }}>
            <select value={evForm.kind} onChange={(e) => setEvForm({ ...evForm, kind: e.target.value })} style={{ width: 130 }}>
              {Object.entries(EV_AR).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <input placeholder={t("epf_ev_title_ph")} value={evForm.title} onChange={(e) => setEvForm({ ...evForm, title: e.target.value })} style={{ flex: 1 }} />
            <input type="number" placeholder={t("epf_ev_amount_ph")} value={evForm.amount} onChange={(e) => setEvForm({ ...evForm, amount: e.target.value })} style={{ width: 140 }} />
            <button onClick={addEvent}>{t("add")}</button>
          </div>
        )}
        <table>
          <thead><tr><th>{t("epf_col_type")}</th><th>{t("col_title")}</th><th>{t("epf_col_amount")}</th><th>{t("epf_col_date")}</th></tr></thead>
          <tbody>{events.map((ev) => (
            <tr key={ev.id}>
              <td><span className={`pill ${ev.kind === "bonus" || ev.kind === "promotion" ? "success" : ev.kind === "note" ? "neutral" : "warning"}`}>{EV_AR[ev.kind]}</span></td>
              <td>{ev.title}</td><td>{ev.amount ? `${ev.amount} ${kwd}` : "—"}</td><td>{ev.date}</td>
            </tr>
          ))}{!events.length && <tr><td colSpan={4} className="muted">{t("att_no_records")}</td></tr>}</tbody>
        </table>
      </div>

      <div className="card">
        <h3>{t("emp_timeline")}</h3>
        <div className="steps">
          {timeline.map((it, i) => (
            <div className="step done" key={i}>
              <div className="rail"><div className="node">•</div><div className="connector" /></div>
              <div className="body">
                <div className="s-title">{it.text}</div>
                <div className="s-meta"><span>{new Date(it.at).toLocaleDateString(lang, { dateStyle: "medium" })}</span></div>
              </div>
            </div>
          ))}
          {!timeline.length && <div className="muted">{t("epf_no_events")}</div>}
        </div>
      </div>

      {can("calculate_eos") && (
        <div className="card">
          <h3>{t("emp_leave_bal")}</h3>
          <p className="muted">{t("epf_leave_hint")}</p>
          <div className="row">
            <div className="field" style={{ width: 200 }}><label>{t("leave_consumed")}</label>
              <input type="number" value={consumed} onChange={(ev) => setConsumed(+ev.target.value)} /></div>
            <div className="field" style={{ alignSelf: "flex-end" }}>
              <button onClick={calcLeave}>{t("leave_calc")}</button></div>
          </div>
          {leaveBal && (
            <div className="grid stats">
              <div className="stat"><div className="num">{leaveBal.accrued_days}</div><div className="lbl">{t("epf_accrued_yrs", { y: leaveBal.service_years })}</div></div>
              <div className="stat"><div className="num">{leaveBal.consumed_days}</div><div className="lbl">{t("epf_used")}</div></div>
              <div className="stat accent"><div className="num">{leaveBal.remaining_days}</div><div className="lbl">{t("leave_remaining")}</div></div>
            </div>
          )}
        </div>
      )}

      {can("terminate_employee") && e.status !== "terminated" && (
        <div className="card" style={{ borderTop: "3px solid var(--danger)" }}>
          <h3>{t("emp_terminate")}</h3>
          <div className="row">
            <div className="field" style={{ flex: 1 }}><label>{t("epf_term_end_date")}</label>
              <input type="date" value={term.end_date} onChange={(ev) => setTerm({ ...term, end_date: ev.target.value })} /></div>
            <div className="field" style={{ flex: 1 }}><label>{t("epf_reason")}</label>
              <select value={term.reason} onChange={(ev) => setTerm({ ...term, reason: ev.target.value })}>
                {Object.entries(REASONS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select></div>
            <div className="field" style={{ alignSelf: "flex-end" }}>
              <button className="danger" onClick={terminate}>{t("epf_term_btn")}</button>
            </div>
          </div>
        </div>
      )}

      {settlement && (
        <div className="card">
          <h3>{t("epf_settlement_title")}</h3>
          <div className="grid stats">
            <div className="stat accent"><div className="num">{settlement.total_settlement}</div><div className="lbl">{t("epf_total_settlement")}</div></div>
            <div className="stat"><div className="num">{settlement.indemnity}</div><div className="lbl">{t("epf_indemnity")}</div></div>
            <div className="stat"><div className="num">{settlement.leave_payout}</div><div className="lbl">{t("epf_leave_payout")}</div></div>
          </div>
          <p className="muted">{settlement.service?.text} · {settlement.factor_note}</p>
          <p className="muted">{settlement.disclaimer}</p>
        </div>
      )}
    </div>
  );
}
