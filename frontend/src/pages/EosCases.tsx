import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import api, { errMsg } from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import { fmtKuwaitDateTime } from "../utils/datetime";
import { roleAr } from "../labels";

/**
 * P6-27 — شاشة حالات نهاية الخدمة.
 *
 * **قرار المالك**: حالة نهاية الخدمة هي المرجع في مسار الخروج. وكان
 * المرجع بلا شاشة إطلاًقا: ثمانية نقاط نهاية تسوق المعاملة من الفتح إلى
 * الحفظ، ولا واجهة تصل إليها. والمعروض الوحيد صفحة `/eos` — وهي
 * **حاسبة تقديرية** لا تلمس المعاملة.
 *
 * فمن أراد إنهاء خدمة لم يجد إلا المسودة على ملف الموظف، وهي المسار
 * الذي قرّر المالك ألّا يكون المرجع.
 *
 * **والصلاحيات تُقرأ من الخادم لا تُحسب هنا** (درس APP-01): الأدوار
 * المخوّلة لكل خطوة تأتي من `/eos/cases/stage-roles`. ومنطق صلاحيات
 * مكرَّر في مكانين ينحرف أحدهما عن الآخر — فيظهر زرّ يرفضه الخادم، أو
 * يُخفى إجراء يملكه صاحبه.
 */

type Case = {
  id: number; reference_no: string | null; status: string;
  stage_index: number; total_stages: number;
  employee_id: number; employee_name: string | null; employee_no: string | null;
  termination_date: string | null; termination_reason: string | null;
  notice_served: boolean | null; notice_served_date: string | null;
  settlement: any; is_final?: boolean; not_for_payment?: boolean; source_request_id: number | null;
  clearance_notes: string | null; acknowledgment_note: string | null;
  payment_reference: string | null; filing_location: string | null;
  document_status: string;
  initiated_at: string | null; calculated_at: string | null;
  approved_at: string | null; clearance_at: string | null;
  acknowledged_at: string | null; settled_at: string | null;
  printed_at: string | null; filed_at: string | null;
};

type Policy = {
  flow: string[]; roles: Record<string, string[]>;
  role_labels: Record<string, string>; reasons: Record<string, string>;
  you: string; you_label: string;
};


/** الخطوة التالية لكل حالة — من ترتيب المسار لا من قائمة مكتوبة ثانية. */
function nextStep(flow: string[], status: string): string | null {
  const i = flow.indexOf(status);
  return i >= 0 && i + 1 < flow.length ? flow[i + 1] : null;
}


const ACTION_PATH: Record<string, string> = {
  calculated: "calculate", approved: "approve", clearance: "clearance",
  acknowledged: "acknowledge", settled: "settle",
};

export default function EosCases() {
  const { t, lang } = useI18n();
  const { can, user } = useAuth();
  const stageLabel = (s: string) => (t(`eosc_st_${s}`) !== `eosc_st_${s}` ? t(`eosc_st_${s}`) : s);
  const actionLabel = (s: string) => (t(`eosc_act_${s}`) !== `eosc_act_${s}` ? t(`eosc_act_${s}`) : s);
  const reasonLabel = (r: string | null) =>
    !r ? "" : t(`rsn_${r}`) !== `rsn_${r}` ? t(`rsn_${r}`) : (policy?.reasons?.[r] || r);
  const [notice, setNotice] = useState({ served: "", date: "" });
  const [params, setParams] = useSearchParams();
  const [rows, setRows] = useState<Case[]>([]);
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [sel, setSel] = useState<Case | null>(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  // P6-27 — «تُفتح … أو مباشرة من هنا» كانت جملًة بلا باب: النقطة مبنيّة
  // (``POST /eos/cases``) ولا تناديها شاشة. وهذا الباب.
  const [opening, setOpening] = useState(false);
  const [employees, setEmployees] = useState<any[]>([]);
  const [form, setForm] = useState({ employee_id: "", termination_date: "", reason: "resignation",
                                     notice_served: "", notice_served_date: "" });

  const statusFilter = params.get("status") || "";

  const load = () =>
    api.get("/eos/cases", { params: statusFilter ? { status: statusFilter } : {} })
      .then((r) => setRows(r.data))
      .catch((e) => setErr(errMsg(e, t("eosc_err_load"))));

  useEffect(() => { load(); }, [statusFilter]);
  useEffect(() => {
    api.get("/eos/cases/stage-roles").then((r) => setPolicy(r.data)).catch(() => {});
  }, []);

  const startOpen = () => {
    setErr(""); setMsg(""); setOpening(true);
    if (!employees.length) {
      api.get("/employees").then((r) => setEmployees(r.data)).catch(() => setEmployees([]));
    }
  };

  const submitOpen = async () => {
    if (!form.employee_id || !form.termination_date) return;
    setErr(""); setMsg(""); setBusy(true);
    try {
      const q: Record<string, string> = {
        employee_id: form.employee_id, termination_date: form.termination_date,
        reason: form.reason,
      };
      if (form.reason === "termination" && form.notice_served) {
        q.notice_served = form.notice_served;
        if (form.notice_served === "true") q.notice_served_date = form.notice_served_date;
      }
      const r = await api.post("/eos/cases", null, { params: q });
      setMsg(t("eosc_opened"));
      setOpening(false);
      setForm({ employee_id: "", termination_date: "", reason: "resignation",
                notice_served: "", notice_served_date: "" });
      await load();
      await open(r.data.id);
    } catch (e: any) {
      setErr(errMsg(e, t("eosc_open_failed")));
    } finally { setBusy(false); }
  };

  const open = (id: number) =>
    api.get(`/eos/cases/${id}`).then((r) => {
      setSel(r.data); setNote("");
      setNotice({ served: r.data.notice_served === null ? "" : String(r.data.notice_served),
                  date: r.data.notice_served_date || "" });
    })
      .catch((e) => setErr(errMsg(e, t("eosc_err_open"))));

  /** هل يملك هذا المستخدم الخطوة التالية؟ — بقائمة الخادم لا بقائمة هنا. */
  const mayDo = (step: string) =>
    !!policy && (policy.you === "super_admin" ||
                 (policy.roles[step] || []).includes(policy.you));

  const act = async (step: string) => {
    if (!sel) return;
    setErr(""); setMsg(""); setBusy(true);
    // المعاملات التي يشترطها كل مسار — مقروءة من رسالة الخادم عند نقصها،
    // ومُرسَلة هنا صراحًة كي لا يُردّ الطلب 422 بعد ضغطة المستخدم.
    const q: Record<string, string> = {};
    if (step === "clearance") q.notes = note.trim();
    if (step === "acknowledged" && note.trim()) q.note = note.trim();
    if (step === "settled") q.payment_reference = note.trim();
    try {
      await api.post(`/eos/cases/${sel.id}/${ACTION_PATH[step]}`, null, { params: q });
      setMsg(t("eosc_step_done"));
      await load();
      await open(sel.id);
    } catch (e: any) {
      setErr(errMsg(e, t("eosc_err_step")));
    } finally { setBusy(false); }
  };

  // قرار المالك (2026-09-17) — «أُبلغ الإنذار؟» يُسجَّل قبل الحساب؛ والخادم
  // يرفض حساب فصلٍ غير تأديبي بلا جواب.
  const saveNotice = async () => {
    if (!sel || !notice.served) return;
    setErr(""); setMsg(""); setBusy(true);
    try {
      const q: Record<string, string> = { served: notice.served };
      if (notice.served === "true") q.served_date = notice.date;
      await api.post(`/eos/cases/${sel.id}/notice`, null, { params: q });
      setMsg(t("eosc_notice_saved"));
      await open(sel.id);
    } catch (e: any) {
      setErr(errMsg(e, t("eosc_err_notice")));
    } finally { setBusy(false); }
  };

  const money = (n: any) =>
    typeof n === "number" ? t("eosc_kwd", { n: n.toFixed(3) }) : "—";

  return (
    <div aria-labelledby="eosc-title">
      <div className="page-head">
        <div>
          <div className="eyebrow">{t("eosc_eyebrow")}</div>
          <h2 id="eosc-title">{t("eosc_title")}</h2>
          <div className="sub">{t("eosc_sub")}</div>
        </div>
        <div className="row" style={{ gap: 8 }}>
          {can("terminate_employee") && !opening && (
            <button onClick={startOpen}>{t("eosc_open_btn")}</button>
          )}
        <select value={statusFilter}
                onChange={(e) => setParams(e.target.value ? { status: e.target.value } : {})}
                aria-label={t("eosc_filter")}>
          <option value="">{t("eosc_all")}</option>
          {(policy?.flow || []).map((s) => (
            <option key={s} value={s}>{stageLabel(s)}</option>
          ))}
        </select>
        </div>
      </div>

      {opening && can("terminate_employee") && (
        <div className="card" style={{ borderInlineStart: "4px solid var(--brand)" }}>
          <h3 style={{ marginTop: 0 }}>{t("eosc_open_title")}</h3>
          <div className="sub" style={{ marginBottom: 8 }}>{t("eosc_open_hint")}</div>
          <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
            <div className="field" style={{ minWidth: 240 }}>
              <label htmlFor="eosc-emp">{t("eosc_open_emp")}</label>
              <select id="eosc-emp" value={form.employee_id}
                      onChange={(e) => setForm({ ...form, employee_id: e.target.value })}>
                <option value="">{t("eosc_choose")}</option>
                {employees.map((e: any) => (
                  <option key={e.id} value={e.id}>
                    {e.employee_no ? `[${e.employee_no}] ` : ""}{e.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="eosc-date">{t("eosc_open_date")}</label>
              <input id="eosc-date" type="date" value={form.termination_date}
                     onChange={(e) => setForm({ ...form, termination_date: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="eosc-reason">{t("eosc_open_reason")}</label>
              <select id="eosc-reason" value={form.reason}
                      onChange={(e) => setForm({ ...form, reason: e.target.value })}>
                {Object.keys(policy?.reasons || {}).map((k) => (
                  <option key={k} value={k}>{reasonLabel(k)}</option>
                ))}
              </select>
            </div>
            {/* قرار المالك (2026-09-17): الفصل غير التأديبي يُسأل عن الإنذار قبل الحساب. */}
            {form.reason === "termination" && (
              <div className="field">
                <label htmlFor="eosc-open-notice">{t("eosc_notice_q")}</label>
                <select id="eosc-open-notice" value={form.notice_served}
                        onChange={(e) => setForm({ ...form, notice_served: e.target.value })}>
                  <option value="">{t("eosc_choose")}</option>
                  <option value="true">{t("eosc_yes")}</option>
                  <option value="false">{t("eosc_no")}</option>
                </select>
              </div>
            )}
            {form.reason === "termination" && form.notice_served === "true" && (
              <div className="field">
                <label htmlFor="eosc-open-notice-date">{t("eosc_notice_date")}</label>
                <input id="eosc-open-notice-date" type="date" value={form.notice_served_date}
                       onChange={(e) => setForm({ ...form, notice_served_date: e.target.value })} />
              </div>
            )}
            <button disabled={busy || !form.employee_id || !form.termination_date}
                    onClick={submitOpen}>{t("eosc_open_save")}</button>
            <button className="ghost" onClick={() => setOpening(false)}>{t("eosc_open_cancel")}</button>
          </div>
        </div>
      )}

      {err && <div className="err" role="alert">{err}</div>}
      {msg && <div className="ok" role="status">{msg}</div>}

      <div className="card" style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th style={{ textAlign: "start", padding: 8 }}>{t("eosc_col_ref")}</th>
              <th style={{ textAlign: "start", padding: 8 }}>{t("eosc_col_emp")}</th>
              <th style={{ padding: 8 }}>{t("eosc_col_leave")}</th>
              <th style={{ padding: 8 }}>{t("eosc_col_stage")}</th>
              <th style={{ padding: 8 }}>{t("eosc_col_source")}</th>
              <th style={{ padding: 8 }} />
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.id} style={{ borderTop: "1px solid var(--border, #e2e8f0)" }}>
                <td style={{ padding: 8 }}>{c.reference_no || `#${c.id}`}</td>
                <td style={{ padding: 8 }}>
                  {c.employee_name}
                  {c.employee_no && <span className="muted"> · {c.employee_no}</span>}
                </td>
                <td style={{ padding: 8, textAlign: "center" }}>
                  {c.termination_date || "—"}
                </td>
                <td style={{ padding: 8, textAlign: "center" }}>
                  <span className={`pill ${c.status === "settled" ? "success" : "gold"}`}>
                    {stageLabel(c.status)}
                  </span>
                  <div className="muted" style={{ fontSize: 11 }}>
                    {c.stage_index + 1} / {c.total_stages}
                  </div>
                </td>
                <td style={{ padding: 8, textAlign: "center" }}>
                  {/* P6-27 — الرابط: من يقرأ المرجع يعرف من أين جاء. */}
                  {c.source_request_id
                    ? <a href={`/requests/${c.source_request_id}`}>
                        {t("eosc_request_n", { n: c.source_request_id })}
                      </a>
                    : <span className="muted">{t("eosc_direct")}</span>}
                </td>
                <td style={{ padding: 8, textAlign: "center" }}>
                  <button className="ghost" onClick={() => open(c.id)}>{t("eosc_details")}</button>
                </td>
              </tr>
            ))}
            {!rows.length && (
              <tr><td colSpan={6} style={{ padding: 16 }} className="muted">
                {t(statusFilter ? "eosc_none_status" : "eosc_none")}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {sel && (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h3 style={{ margin: 0 }}>
              {sel.reference_no || `#${sel.id}`} — {sel.employee_name}
            </h3>
            <div className="row" style={{ gap: 8 }}>
              {/* قرار المالك (2026-09-18): إلغاء الإقامة يُفتح من ملف نهاية الخدمة. */}
              {user?.can_submit_on_behalf && (
                <a className="btn ghost" title={t("eosc_cancel_residency_hint")}
                   href={`/requests?type=ADMRESCXL&new=1&employee=${sel.employee_id}`}>
                  {t("eosc_cancel_residency")}
                </a>
              )}
              <button className="ghost" onClick={() => setSel(null)}>{t("eosc_close")}</button>
            </div>
          </div>

          <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
            {/* التسمية من الخادم: قائمة ترجمة هنا تتقادم مع أول سبب يُضاف. */}
            {reasonLabel(sel.termination_reason)} · {t("eosc_leaving", { d: sel.termination_date })}
            {sel.source_request_id
              ? <> · {t("eosc_under")} <a href={`/requests/${sel.source_request_id}`}>
                  {t("eosc_request_n", { n: sel.source_request_id })}</a></>
              : <> · {t("eosc_direct")}</>}
          </div>

          {/* خطّ المراحل: ما تمّ ومتى — والفراغ يعني «لم يقع بعد» لا خطأ. */}
          <div style={{ marginTop: 14 }}>
            {(policy?.flow || []).map((s) => {
              const at = (sel as any)[`${s === "initiated" ? "initiated" : s}_at`]
                || (s === "clearance" ? sel.clearance_at : null);
              const done = (policy?.flow || []).indexOf(s) <= sel.stage_index;
              return (
                <div key={s} className="timeline-item"
                     style={{ opacity: done ? 1 : 0.45, paddingBottom: 10 }}>
                  <strong>{stageLabel(s)}</strong>
                  {at && <span className="muted"> · {fmtKuwaitDateTime(at, lang)}</span>}
                </div>
              );
            })}
          </div>

          {sel.termination_reason === "termination" && (
            <div style={{ marginTop: 14 }}>
              <h4 style={{ margin: "0 0 6px" }}>{t("eosc_notice_h")}</h4>
              {sel.status === "initiated" && can("terminate_employee") ? (
                <div className="row" style={{ gap: 8, alignItems: "flex-end", flexWrap: "wrap" }}>
                  <div className="field">
                    <label htmlFor="eosc-notice">{t("eosc_notice_q")}</label>
                    <select id="eosc-notice" value={notice.served}
                            onChange={(e) => setNotice({ ...notice, served: e.target.value })}>
                      <option value="">{t("eosc_choose")}</option>
                      <option value="true">{t("eosc_yes")}</option>
                      <option value="false">{t("eosc_no")}</option>
                    </select>
                  </div>
                  {notice.served === "true" && (
                    <div className="field">
                      <label htmlFor="eosc-notice-date">{t("eosc_notice_date")}</label>
                      <input id="eosc-notice-date" type="date" value={notice.date}
                             onChange={(e) => setNotice({ ...notice, date: e.target.value })} />
                    </div>
                  )}
                  <button className="ghost" disabled={busy || !notice.served
                            || (notice.served === "true" && !notice.date)}
                          onClick={saveNotice}>{t("eosc_save")}</button>
                </div>
              ) : (
                <div className="muted" style={{ fontSize: 12 }}>
                  {sel.notice_served === null ? t("eosc_notice_unset")
                    : sel.notice_served ? t("eosc_notice_on", { d: sel.notice_served_date })
                    : t("eosc_notice_not")}
                </div>
              )}
            </div>
          )}

          {sel.settlement && (
            <div style={{ marginTop: 14 }}>
              <h4 style={{ margin: "0 0 6px" }}>{t("eosc_settlement")}{" "}
                <span className={`pill ${sel.is_final ? "success" : "warn"}`} data-testid="eosc-final-pill">
                  {sel.is_final ? t("eosc_final") : t("eosc_preliminary")}
                </span>
              </h4>
              <div className="muted" style={{ fontSize: 12 }}>
                {t("eosc_indemnity")}: {money(sel.settlement?.indemnity)}
                {" · "}{t("eosc_leave_pay")}: {money(sel.settlement?.leave_payout)}
                {typeof sel.settlement?.notice_payout === "number" && (
                  <>{" · "}{t("eosc_notice_pay")}: {money(sel.settlement.notice_payout)}</>
                )}
              </div>
              <div className="muted" style={{ fontSize: 12 }}>
                {t("eosc_total")}: {money(sel.settlement?.total_settlement)}
              </div>
            </div>
          )}

          {sel.clearance_notes && (
            <div className="s-note" style={{ marginTop: 10 }}>
              {t("eosc_clearance")}: {sel.clearance_notes}
            </div>
          )}
          {sel.payment_reference && (
            <div className="s-note">{t("eosc_payref")}: {sel.payment_reference}</div>
          )}

          {/* الخطوة التالية — وحدها. ولا يُعرض ما لا يملكه هذا المستخدم. */}
          {(() => {
            const step = policy ? nextStep(policy.flow, sel.status) : null;
            if (!step) {
              return <div className="muted" style={{ marginTop: 14 }}>
                {t("eosc_finished")}
              </div>;
            }
            if (!mayDo(step)) {
              return <div className="muted" style={{ marginTop: 14 }}>
                {t("eosc_not_yours", {
                  step: actionLabel(step),
                  roles: (policy?.roles[step] || [])
                    .map((r) => roleAr(r))
                    .join(lang === "ar" ? "، " : ", ") || "—",
                })}
              </div>;
            }
            const needsNote = step === "clearance" || step === "settled";
            return (
              <div style={{ marginTop: 14, display: "grid", gap: 8, maxWidth: 460 }}>
                {needsNote && (
                  <input value={note} onChange={(e) => setNote(e.target.value)}
                         placeholder={step === "settled"
                           ? t("eosc_payref_ph")
                           : t("eosc_clear_ph")} />
                )}
                <div>
                  <button disabled={busy || (needsNote && !note.trim())}
                          onClick={() => act(step)}>
                    {actionLabel(step)}
                  </button>
                </div>
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}
