import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import api, { downloadSensitiveReport, errMsg } from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import { attAr, statusAr, contractTypeAr } from "../labels";
import { fmtKuwaitDateTime, fmtKuwaitDate } from "../utils/datetime";

// ملف الموظف كحاوية تبويبات قابلة للتضمين داخل التخطيط الرئيسي-التفصيلي.
// يقبل id كخاصية (وضع مُضمَّن) أو يقرأه من المسار (صفحة مستقلة).
export default function EmployeeProfile({ id: idProp, onChanged }: { id?: number; onChanged?: () => void } = {}) {
  const params = useParams();
  const id = idProp ?? (params.id ? Number(params.id) : undefined);
  const { can } = useAuth();
  const { t, lang } = useI18n();
  const [tab, setTab] = useState("personal");
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
  const [history, setHistory] = useState<any[]>([]);  // R3-C — سجل التعديلات الحرجة
  const [evForm, setEvForm] = useState({ kind: "warning", title: "", amount: "" });
  const [actualEdit, setActualEdit] = useState(false);
  const [actualVal, setActualVal] = useState("");

  const EMP_STATUS: Record<string, string> = {
    active: t("empst_active"), vacation: t("empst_vacation"), suspended: t("empst_suspended"),
    resigned: t("empst_resigned"), terminated: t("empst_terminated"), retired: t("empst_retired"),
    // أرشفة (QA-P2-DATA-01): كانت غير متاحة من الواجهة رغم دعم الخادم لها — تتيح استبعاد
    // سجلات تجريبية/غير مرتبطة من التقارير والتصدير دون حذف فعلي للبيانات
    archived: t("empst_archived"),
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
    api.get(`/employees/${id}/change-history`).then((r) => setHistory(r.data)).catch(() => {});
  };
  const load = () => api.get(`/employees/${id}/profile`).then((r) => setP(r.data));
  useEffect(() => {
    if (!id) return;
    setTab("personal"); setSettlement(null); setLeaveBal(null); setMsg("");
    load(); loadExtras();
  }, [id]);

  const calcLeave = async () => {
    const r = await api.post("/eos/leave-balance", null, { params: { employee_id: id, consumed_days: consumed } });
    setLeaveBal(r.data);
  };
  const changeStatus = async (status: string) => {
    if (status === "archived" && !confirm(t("epf_archive_confirm"))) return;
    await api.post(`/employees/${id}/status`, null, { params: { status } });
    setMsg(t("epf_status_changed")); load(); onChanged?.();
  };
  const saveActualSalary = async () => {
    await api.post(`/employees/${id}/actual-salary`, null, { params: { amount: +actualVal || 0 } });
    setActualEdit(false); setMsg(t("actual_salary_saved")); load();
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
    // يُرسَل المستهلَك فقط؛ المتبقّي يُحسب آليًا في الخادم
    const r = await api.post(`/employees/${id}/terminate`, null, { params: { ...term, used_leave_days: consumed } });
    setSettlement(r.data.settlement); setMsg(t("epf_terminated_msg")); load(); onChanged?.();
  };

  const applyOcr = async () => {
    if (!suggested) return;
    // خريطة حقول OCR ← حقول ملف الموظف (بعد مراجعة المستخدم)
    const payload: any = {
      name: suggested.full_name || undefined,
      civil_id: suggested.civil_id || undefined,
      nationality: suggested.nationality || undefined,
      date_of_birth: suggested.date_of_birth || undefined,
      passport_number: suggested.passport_number || suggested.passport || undefined,
      passport_expiry: suggested.expiry_date || undefined,
    };
    const r = await api.post(`/employees/${id}/apply-ocr`, payload);
    setSuggested(null);
    setMsg(t("ocr_applied", { n: r.data.updated })); load();
  };
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
  const downloadLatest = async (type: string) => {
    // window.open المباشر لا يرفق رمز الدخول، فيرجع 401 (QA-P1-DOC-01) — نجلب الملف
    // بالرمز عبر api ونعرضه كـ blob، بنفس نمط RequestDetail.tsx
    try {
      const res = await api.get("/documents/latest", {
        params: { entity_type: "employee", entity_id: id, document_type_code: type },
        responseType: "blob",
      });
      const url = URL.createObjectURL(res.data as Blob);
      window.open(url, "_blank");
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e: any) {
      setMsg(errMsg(e, t("error")));
    }
  };

  if (!id) return <div className="md-empty">{t("emp_select_prompt")}</div>;
  if (!p) return <div className="empty">{t("loading")}</div>;
  const e = p.employee;

  // R2 §2 — تصفية التبويبات حسب دور العارض (view_scope من backend)
  const scope: string = p.view_scope || "full";
  const ALL_TABS: [string, string][] = [
    ["personal", t("tab_personal")], ["employment", t("tab_employment")],
    ["documents", t("tab_documents")], ["leave", t("tab_leave")],
    ["eos", t("tab_eos")], ["warnings", t("tab_warnings")],
    ["history", "سجل التعديلات"],  // R3-C — تبويب جديد لتاريخ التغييرات الحرجة
  ];
  const ALLOWED_BY_SCOPE: Record<string, Set<string>> = {
    // المحاسب: بيانات الرواتب فقط (employment + history للراتب) — لا هوية/مستندات/إجازات
    accountant: new Set(["employment", "history"]),
    // PRO: الجواز والوثائق الحكومية فقط
    pro: new Set(["documents"]),
    full: new Set(["personal", "employment", "documents", "leave", "eos", "warnings", "history"]),
  };
  const allowedTabs = ALLOWED_BY_SCOPE[scope] || ALLOWED_BY_SCOPE.full;
  const TABS = ALL_TABS.filter(([k]) => allowedTabs.has(k));
  // لو التبويب النشط ما يظهرش لهذا الدور — نلقائيًا نروح لأول تبويب مسموح
  if (tab && !allowedTabs.has(tab) && TABS[0]) {
    setTimeout(() => setTab(TABS[0][0]), 0);
  }

  return (
    <div className="md-detail">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
        <h2 style={{ margin: 0 }}>{e.name} <span className={`pill ${e.status === "active" ? "success" : "neutral"}`}>{EMP_STATUS[e.status] || statusAr(e.status)}</span></h2>
      </div>
      {msg && <div className="ok">{msg}</div>}

      {scope !== "full" && (
        <div style={{
          background: "#fef3c7", border: "1px solid #fbbf24", padding: 10,
          borderRadius: 8, marginBottom: 10, fontSize: 13,
        }}>
          <b>🔒 عرض محدود حسب دورك:</b>{" "}
          {scope === "accountant"
            ? "المحاسب يرى فقط بيانات الرواتب. الجواز والرقم المدني والمستندات الشخصية والإجازات والإنذارات مخفية بموجب سياسة فصل الواجبات."
            : "المندوب يرى فقط الوثائق الحكومية. الراتب والعقد والمسمى الوظيفي مخفية."}
        </div>
      )}
      <div className="tabs">
        {TABS.map(([key, label]) => (
          <button key={key} className={`tab ${tab === key ? "active" : ""}`} onClick={() => setTab(key)}>{label}</button>
        ))}
      </div>

      {/* ============ البيانات الشخصية ============ */}
      {tab === "personal" && (
        <div className="grid cards">
          <div className="card">
            {e.employee_no && (<><b>الرقم الوظيفي:</b> <code style={{ background: "#e0ece8", padding: "1px 6px", borderRadius: 4 }}>{e.employee_no}</code><br /></>)}
            <b>{t("fld_civil_id")}:</b> {e.civil_id || "—"}<br /><b>{t("epf_nationality")}:</b> {e.nationality || "—"}<br />
            <b>{t("epf_gender")}:</b> {genderLabel(e.gender)}<br /><b>{t("epf_dob")}:</b> {e.date_of_birth || "—"}<br />
            <b>{t("epf_marital")}:</b> {e.marital_status || "—"}</div>
          <div className="card"><b>{t("epf_email")}:</b> {e.email || "—"}<br /><b>{t("emp_phone")}:</b> {e.phone || "—"}<br />
            <b>{t("epf_passport")}:</b> {e.passport_number || "—"}<br /><b>{t("epf_passport_expiry")}:</b> {e.passport_expiry || "—"}<br />
            <b>{t("epf_health")}:</b> {e.health_insurance || "—"}</div>
        </div>
      )}

      {/* ============ التوظيف والعقد ============ */}
      {tab === "employment" && (
        <>
          <div className="grid cards">
            <div className="card"><b>{t("epf_job")}:</b> {e.job_title || "—"}<br />
              <b>{t("fld_official_salary")}:</b> {e.basic_salary} {kwd}<br />
              {p.can_view_actual_salary && (
                <><b>{t("fld_actual_salary")}:</b>{" "}
                  {!actualEdit
                    ? <>{p.actual_salary != null ? `${p.actual_salary} ${kwd}` : "—"}
                        {p.can_edit_actual_salary &&
                          <button className="ghost sm" style={{ marginInlineStart: 8 }}
                            onClick={() => { setActualEdit(true); setActualVal(String(p.actual_salary ?? "")); }}>
                            {t("edit")}</button>}</>
                    : <span className="row" style={{ display: "inline-flex", gap: 6 }}>
                        <input aria-label={t("fld_actual_salary")} type="number" min={0} value={actualVal} style={{ width: 110 }}
                          onChange={(ev) => setActualVal(ev.target.value)} />
                        <button className="sm" onClick={saveActualSalary}>{t("save")}</button>
                        <button className="ghost sm" onClick={() => setActualEdit(false)}>{t("cancel")}</button>
                      </span>}
                  <br /></>
              )}
              <b>{t("fld_actual_job")}:</b> {e.actual_job_title || "—"}<br />
              <b>{t("epf_hire")}:</b> {e.hire_date || "—"}<br /><b>{t("epf_contract")}:</b> {contractTypeAr(e.contract_type)}<br />
              <b>{t("fld_residency_expiry")}:</b>{" "}
              {p.permits?.find((x: any) => x.kind === "residency")?.expiry_date || "—"}<br />
              <b>{t("fld_work_place_official")}:</b> {p.official_branch_name || "—"}<br />
              <b>{t("fld_work_place_actual")}:</b> {p.actual_branch_name || "—"}<br />
              <b>{t("fld_work_hours_type")}:</b>{" "}
              {e.work_hours_type === "fixed" ? t("fld_hours_fixed")
                : e.work_hours_type === "unfixed" ? t("fld_hours_unfixed") : "—"}<br />
              {/* الرقمان يخصّان "محددة" فقط — إخفاؤهما مع "غير محددة" مقصود:
                  طبيعة العمل بلا ساعات ثابتة تجعل رقًما معلًنا بلا معنى */}
              {e.work_hours_type === "fixed" && (
                <>
                  <b>{t("fld_hours_official")}:</b> {e.official_work_hours ?? "—"}<br />
                  <b>{t("fld_hours_actual")}:</b> {e.actual_work_hours ?? "—"}<br />
                </>
              )}
              <b>{t("epf_att_mode")}:</b> {e.attendance_mode}
              {p.created_by_name && <><br /><span className="muted" style={{ fontSize: 12 }}>{t("emp_created_by")}: {p.created_by_name}</span></>}
            </div>
            <div className="card">
              {can("edit_employee") && (
                <div className="field" style={{ margin: 0 }}>
                  <label htmlFor="epf-status">{t("emp_status")}</label>
                  <select id="epf-status" value={e.status} onChange={(ev) => changeStatus(ev.target.value)}>
                    {Object.entries(EMP_STATUS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                </div>
              )}
            </div>
          </div>
          {/* الإقامات/أذونات العمل شأن حكومي → للمندوب فقط */}
          {can("manage_permits") && (
            <div className="card">
              <h3>{t("emp_permits")}</h3>
              <table><thead><tr><th>{t("epf_col_type")}</th><th>{t("pro_col_number")}</th><th>{t("pro_col_expiry")}</th><th>{t("status")}</th></tr></thead>
                <tbody>{p.permits.map((x: any) => (
                  <tr key={x.id}><td>{x.kind}</td><td>{x.number}</td><td>{x.expiry_date}</td>
                    <td><span className="pill info">{statusAr(x.status)}</span></td></tr>
                ))}{!p.permits.length && <tr><td colSpan={4} className="muted">{t("att_no_records")}</td></tr>}</tbody></table>
            </div>
          )}
          <div className="card">
            <h3>{t("emp_recent_att")}</h3>
            <table><thead><tr><th>{t("col_in")}</th><th>{t("col_out")}</th><th>{t("status")}</th><th>{t("epf_col_selfie")}</th></tr></thead>
              <tbody>{p.attendance.map((a: any) => (
                <tr key={a.id}><td>{fmtKuwaitDateTime(a.check_in_at, lang)}</td>
                  <td>{fmtKuwaitDateTime(a.check_out_at, lang)}</td>
                  <td><span className={`pill ${a.status === "late" ? "warning" : "success"}`}>{attAr(a.status)}</span></td>
                  <td>{a.selfie_in ? "✓" : "—"}</td></tr>
              ))}{!p.attendance.length && <tr><td colSpan={4} className="muted">{t("att_no_records")}</td></tr>}</tbody></table>
          </div>
        </>
      )}

      {/* ============ المستندات ============ */}
      {tab === "documents" && (
        <div className="card">
          <h3>{t("emp_documents")}</h3>
          <table><thead><tr><th>{t("epf_col_type")}</th><th>{t("col_title")}</th><th>{t("epf_col_version")}</th><th>{t("pro_col_expiry")}</th><th></th></tr></thead>
            <tbody>{p.documents.map((d: any) => (
              <tr key={d.id}><td>{d.type}</td><td>{d.title}</td><td>v{d.version}</td><td>{d.expiry_date}</td>
                <td><button className="ghost" onClick={() => downloadLatest(d.type)}>{t("epf_download_latest")}</button></td></tr>
            ))}{!p.documents.length && <tr><td colSpan={5} className="muted">{t("att_no_records")}</td></tr>}</tbody></table>

          {can("upload_documents") && (
            <div style={{ marginTop: 14, borderTop: "1px solid var(--line)", paddingTop: 14 }}>
              <h4>{t("epf_upload_title")}</h4>
              <div className="row">
                <select aria-label={t("epf_col_type")} value={docType} onChange={(e) => setDocType(e.target.value)} style={{ width: 200 }}>
                  <option value="passport">{t("epf_doc_passport")}</option>
                  <option value="civil_id">{t("epf_doc_civil")}</option>
                  <option value="residency">{t("epf_doc_residency")}</option>
                  <option value="contract">{t("epf_doc_contract")}</option>
                </select>
                <input aria-label={t("epf_upload_title")} type="file" ref={fileRef} onChange={(e) => e.target.files && ocrPreview(e.target.files[0])} />
                <button onClick={upload}>{t("epf_upload_save")}</button>
              </div>
              {suggested && (
                <div className="card" style={{ background: "#f8fafc", marginTop: 10 }}>
                  <b>{t("epf_ocr_suggested")}</b>
                  <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(suggested, null, 2)}</pre>
                  {can("edit_employee") && (
                    <button onClick={applyOcr}>{t("ocr_apply")}</button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ============ إدارة الإجازات ============ */}
      {tab === "leave" && (
        <>
        {/* الرصيد الفعلي المخزَّن وسجل حركاته — يختلف عن الحاسبة أدناه:
            هذا ما تبقّى فعًلا بعد الخصم التلقائي، وتلك تقدير استحقاق. */}
        <div className="card">
          <h3>{t("leave_current_balance")}</h3>
          <div className="grid stats">
            <div className="stat accent">
              <div className="num">{p.leave_balance ?? "—"}</div>
              <div className="lbl">{t("leave_days_available")}</div>
            </div>
          </div>
          <h4 style={{ marginTop: 18 }}>{t("leave_ledger_title")}</h4>
          <p className="muted" style={{ marginTop: 0 }}>{t("leave_ledger_hint")}</p>
          <table>
            <thead><tr>
              <th>{t("epf_col_type")}</th><th>{t("req_days")}</th>
              <th>{t("leave_before")}</th><th>{t("leave_after")}</th>
              <th>{t("col_title")}</th><th>{t("epf_col_date")}</th>
            </tr></thead>
            <tbody>
              {(p.leave_ledger || []).map((x: any) => (
                <tr key={x.id}>
                  <td><span className={`pill ${x.kind === "deduction" ? "warning" : "neutral"}`}>
                    {x.kind === "deduction" ? t("leave_deduction")
                      : x.kind === "grant" ? t("leave_grant") : t("leave_record")}
                  </span></td>
                  <td className="num">{x.kind === "deduction" ? `−${x.days}` : x.days}</td>
                  <td className="num">{x.balance_before}</td>
                  <td className="num">{x.balance_after}</td>
                  <td>{x.note || "—"}</td>
                  <td>{fmtKuwaitDate(x.created_at, lang)}</td>
                </tr>
              ))}
              {!(p.leave_ledger || []).length && (
                <tr><td colSpan={6} className="muted">{t("att_no_records")}</td></tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h3>{t("emp_leave_bal")}</h3>
          <p className="muted">{t("epf_leave_hint")}</p>
          <div className="row">
            <div className="field" style={{ width: 200 }}><label htmlFor="epf-leave-consumed">{t("leave_consumed")}</label>
              <input id="epf-leave-consumed" type="number" min={0} step={1} value={consumed} onChange={(ev) => setConsumed(+ev.target.value)} /></div>
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
          {leaveBal?.advance_note && <p className="err">⚠ {leaveBal.advance_note}</p>}
        </div>
        </>
      )}

      {/* ============ نهاية الخدمة ============ */}
      {tab === "eos" && (
        <>
          {can("terminate_employee") && e.status !== "terminated" && (
            <div className="card" style={{ borderTop: "3px solid var(--danger)" }}>
              <h3>{t("emp_terminate")}</h3>
              <p className="muted">{t("epf_leave_hint")}</p>
              <div className="row">
                <div className="field" style={{ flex: 1 }}><label htmlFor="epf-term-end">{t("epf_term_end_date")}</label>
                  <input id="epf-term-end" type="date" value={term.end_date} onChange={(ev) => setTerm({ ...term, end_date: ev.target.value })} /></div>
                <div className="field" style={{ flex: 1 }}><label htmlFor="epf-term-reason">{t("epf_reason")}</label>
                  <select id="epf-term-reason" value={term.reason} onChange={(ev) => setTerm({ ...term, reason: ev.target.value })}>
                    {Object.entries(REASONS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select></div>
                <div className="field" style={{ flex: 1 }}><label htmlFor="epf-term-used-leave">{t("eos_used_leave")}</label>
                  <input id="epf-term-used-leave" type="number" min={0} step={1} value={consumed} onChange={(ev) => setConsumed(+ev.target.value)} /></div>
                <div className="field" style={{ alignSelf: "flex-end" }}>
                  <button className="danger" onClick={terminate}>{t("epf_term_btn")}</button></div>
              </div>
            </div>
          )}
          {(() => {
            const s = settlement || p.saved_eos;
            if (!s) return e.status === "terminated" ? <div className="card muted">{t("empst_terminated")}</div> : null;
            return (
              <div className="card">
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <h3 style={{ margin: 0 }}>{settlement ? t("epf_settlement_title") : t("eos_saved_title")}</h3>
                  {can("calculate_eos") && (
                    <button className="ghost sm" onClick={() => downloadSensitiveReport(`/reports/eos/${id}`, { fmt: "xlsx" }, `eos_${id}.xlsx`, t("export_reason_prompt"))}>
                      {t("eos_export")}
                    </button>
                  )}
                </div>
                <div className="grid stats">
                  <div className="stat accent"><div className="num">{s.total_settlement}</div><div className="lbl">{t("epf_total_settlement")}</div></div>
                  <div className="stat"><div className="num">{s.indemnity}</div><div className="lbl">{t("epf_indemnity")}</div></div>
                  <div className="stat"><div className="num">{s.leave_payout}</div><div className="lbl">{t("epf_leave_payout")}</div></div>
                </div>
                {s.leave && (
                  <p className="muted">{t("eos_leave_detail", {
                    accrued: s.leave.accrued_days, used: s.leave.used_days, remaining: s.leave.remaining_days })}</p>
                )}
                {s.leave?.advance_note && <p className="err">⚠ {s.leave.advance_note}</p>}
                <p className="muted">{s.service?.text} · {s.factor_note}</p>
                <p className="muted">{s.disclaimer}</p>
              </div>
            );
          })()}
        </>
      )}

      {/* ============ الإنذارات والملاحظات ============ */}
      {tab === "warnings" && (
        <>
          <div className="card">
            <h3>{t("emp_hr_log")}</h3>
            {can("edit_employee") && (
              <div className="row" style={{ marginBottom: 10 }}>
                <select aria-label={t("epf_col_type")} value={evForm.kind} onChange={(e) => setEvForm({ ...evForm, kind: e.target.value })} style={{ width: 130 }}>
                  {Object.entries(EV_AR).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
                <input aria-label={t("epf_ev_title_ph")} placeholder={t("epf_ev_title_ph")} value={evForm.title} onChange={(e) => setEvForm({ ...evForm, title: e.target.value })} style={{ flex: 1 }} />
                <input aria-label={t("epf_ev_amount_ph")} type="number" placeholder={t("epf_ev_amount_ph")} value={evForm.amount} onChange={(e) => setEvForm({ ...evForm, amount: e.target.value })} style={{ width: 140 }} />
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
                    <div className="s-meta"><span>{fmtKuwaitDate(it.at, lang)}</span></div>
                  </div>
                </div>
              ))}
              {!timeline.length && <div className="muted">{t("epf_no_events")}</div>}
            </div>
          </div>
        </>
      )}

      {/* R3-C — سجل التعديلات الحرجة (راتب/تعيين/عقد/مسمى) */}
      {tab === "history" && (
        <div className="card">
          <h3>سجل التعديلات على البيانات الحرجة</h3>
          <p className="muted" style={{ fontSize: 12 }}>
            كل تعديل على الراتب أو تاريخ التعيين أو المسمى الوظيفي أو العقد يُسجَّل هنا
            بتاريخ التسجيل + تاريخ السريان + المُنفِّذ + السبب.
          </p>
          {!history.length ? (
            <div className="muted">لا يوجد سجل تعديلات بعد.</div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>الحقل</th>
                    <th>القيمة السابقة</th>
                    <th>القيمة الجديدة</th>
                    <th>تاريخ السريان</th>
                    <th>وقت التسجيل</th>
                    <th>المُنفِّذ</th>
                    <th>السبب</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((h) => (
                    <tr key={h.id}>
                      <td><span className="pill neutral">{h.field_name}</span></td>
                      <td className="muted"><code>{h.old_value ?? "—"}</code></td>
                      <td><code style={{ color: "#065f46", fontWeight: 600 }}>{h.new_value ?? "—"}</code></td>
                      <td>{h.effective_date}</td>
                      <td className="muted">{fmtKuwaitDateTime(h.changed_at, lang)}</td>
                      <td>{h.changed_by_name || `#${h.changed_by}` || "—"}</td>
                      <td className="muted">{h.reason || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
