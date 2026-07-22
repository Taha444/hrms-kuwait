import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { errMsg } from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import { ProgressMini } from "../components/RequestSteps";
import { Skeleton, ErrorRetry, EmptyState } from "../components/States";
import { statusAr } from "../labels";

export default function Requests() {
  const { t } = useI18n();
  const { can } = useAuth();
  const [tab, setTab] = useState<"mine" | "inbox">("mine");
  const [mine, setMine] = useState<any[]>([]);
  const [inbox, setInbox] = useState<any[]>([]);
  const [types, setTypes] = useState<any[]>([]);
  const [employees, setEmployees] = useState<any[]>([]);
  const [onBehalfOf, setOnBehalfOf] = useState<number | "">("");
  const [state, setState] = useState<"loading" | "ok" | "error">("loading");
  const [showNew, setShowNew] = useState(false);
  const [typeCode, setTypeCode] = useState("");
  const [payload, setPayload] = useState<any>({});
  const [err, setErr] = useState("");
  // من يملك view_employee (HR/مدير/مشرف/مندوب/محاسب) قد يقدّم طلًبا نيابًة عن موظف آخر —
  // كان النموذج يقدّم دائًما عن حساب المستخدم نفسه فقط (P1-01)
  const canActOnBehalf = can("view_employee");

  const load = () => {
    setState("loading");
    api.get("/requests/mine").then((r) => { setMine(r.data); setState("ok"); })
      .catch(() => setState("error"));
    if (can("approve_request") || can("process_delegate_tasks"))
      api.get("/requests/inbox").then((r) => setInbox(r.data)).catch(() => {});
  };
  useEffect(() => {
    load();
    api.get("/requests/types").then((r) => { setTypes(r.data); setTypeCode(r.data[0]?.code || ""); });
    if (canActOnBehalf) api.get("/employees").then((r) => setEmployees(r.data)).catch(() => {});
  }, []);

  // PILOT-P0-2: كل ما يتغير نوع الطلب نمسح الـpayload — كانت الحقول من نوع سابق
  // (مثل amount من "سلفة") تفضل في state، والاختبار على "leave" بيسقط لأن الحقول
  // المطلوبة start_date/end_date مش موجودة في state (رغم إن المستخدم يعتقد إنه أدخلها
  // في نوع مختلف قبل ما يبدّل النوع).
  useEffect(() => { setPayload({}); setErr(""); }, [typeCode]);

  // حقول إلزامية لكل نوع بنموذج مخصّص — يطابق REQUIRED_PAYLOAD_FIELDS في requests.py
  // (QA-P0-WF-01: منع تقديم طلب فارغ برسالة واضحة قرب الحقول قبل وصوله للخادم أصًلا)
  const REQUIRED_FIELDS: Record<string, [string, string][]> = {
    leave: [["start_date", t("req_from")], ["end_date", t("req_to")]],
    salary_certificate: [["addressed_to", t("req_addressed")], ["purpose", t("req_purpose")]],
    exit_permission: [["date", t("req_date")], ["reason", t("req_reason")]],
    advance: [["amount", t("req_amount")]],
    loan: [["amount", t("req_amount")], ["months", t("req_months")]],
    REQADV: [["subtype", t("req_subtype")], ["amount", t("req_amount")]],
    REQBANK: [["bank_name", t("req_bank_name")], ["iban", t("req_iban")]],
    REQEXP: [["amount", t("req_amount")], ["description", t("req_description")]],
    REQWARN: [["warning_ref", t("req_warning_ref")], ["response", t("req_response")]],
  };

  const submit = async () => {
    setErr("");
    const clean = Object.fromEntries(
      Object.entries(payload).filter(([, v]) => v !== "" && v !== undefined && v !== null)
    );
    const required = REQUIRED_FIELDS[typeCode];
    const missing = required
      ? required.filter(([k]) => clean[k] === undefined || clean[k] === "").map(([, label]) => label)
      : Object.keys(clean).length === 0 ? [t("req_details")] : [];
    if (missing.length) {
      setErr(`${t("req_missing_fields")}: ${missing.join("، ")}`);
      return;
    }
    try {
      const body: any = { request_type_code: typeCode, payload_json: clean };
      if (onBehalfOf) body.employee_id = onBehalfOf;
      await api.post("/requests", body);
      setShowNew(false); setPayload({}); load();
    } catch (e: any) { setErr(errMsg(e, t("error"))); }
  };

  const list = tab === "mine" ? mine : inbox;

  return (
    <div aria-labelledby="requests-title">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2 id="requests-title">{t("requests")}</h2>
        {can("submit_request") && (
          <button onClick={() => setShowNew((s) => !s)}
                 aria-expanded={showNew}
                 aria-controls="new-request-panel">
            + {t("new_request")}
          </button>
        )}
      </div>

      {showNew && (
        <div className="card" id="new-request-panel" role="region" aria-labelledby="new-request-title">
          <h3 id="new-request-title">{t("new_request")}</h3>
          <div className="field">
            <label htmlFor="req-type">{t("req_type")}</label>
            <select id="req-type" value={typeCode} onChange={(e) => setTypeCode(e.target.value)}>
              {types.map((x) => <option key={x.code} value={x.code}>{x.name}</option>)}
            </select>
          </div>
          {canActOnBehalf && (
            <div className="field">
              <label htmlFor="req-on-behalf">{t("req_on_behalf_of")}</label>
              <select id="req-on-behalf" value={onBehalfOf} onChange={(e) => setOnBehalfOf(e.target.value ? +e.target.value : "")}>
                <option value="">{t("req_myself")}</option>
                {employees.map((e) => <option key={e.id} value={e.id}>{e.name} — {e.job_title}</option>)}
              </select>
            </div>
          )}
          {typeCode === "leave" && (
            <>
              <div className="row">
                <div className="field" style={{ flex: 1 }}>
                  <label htmlFor="req-leave-from">{t("req_from")} *</label>
                  <input id="req-leave-from" type="date" required
                         value={payload.start_date || ""}
                         onChange={(e) => setPayload({ ...payload, start_date: e.target.value })} />
                </div>
                <div className="field" style={{ flex: 1 }}>
                  <label htmlFor="req-leave-to">{t("req_to")} *</label>
                  <input id="req-leave-to" type="date" required
                         value={payload.end_date || ""}
                         onChange={(e) => setPayload({ ...payload, end_date: e.target.value })} />
                </div>
                <div className="field" style={{ width: 100 }}>
                  <label htmlFor="req-leave-days">{t("req_days")}</label>
                  <input id="req-leave-days" type="number"
                         value={payload.days || ""}
                         onChange={(e) => setPayload({ ...payload, days: +e.target.value })} />
                </div>
              </div>
              <div className="field"><label htmlFor="req-leave-reason">{t("req_reason")}</label>
                <input id="req-leave-reason" onChange={(e) => setPayload({ ...payload, reason: e.target.value })} /></div>
            </>
          )}
          {typeCode === "salary_certificate" && (
            <>
              <div className="field"><label htmlFor="req-sc-addressed">{t("req_addressed")} *</label>
                <input id="req-sc-addressed" required onChange={(e) => setPayload({ ...payload, addressed_to: e.target.value })} /></div>
              <div className="field"><label htmlFor="req-sc-purpose">{t("req_purpose")} *</label>
                <input id="req-sc-purpose" required onChange={(e) => setPayload({ ...payload, purpose: e.target.value })} /></div>
            </>
          )}
          {typeCode === "exit_permission" && (
            <div className="row">
              <div className="field" style={{ flex: 1 }}><label htmlFor="req-exit-date">{t("req_date")} *</label>
                <input id="req-exit-date" type="date" required onChange={(e) => setPayload({ ...payload, date: e.target.value })} /></div>
              <div className="field" style={{ flex: 2 }}><label htmlFor="req-exit-reason">{t("req_reason")} *</label>
                <input id="req-exit-reason" required onChange={(e) => setPayload({ ...payload, reason: e.target.value })} /></div>
            </div>
          )}
          {(typeCode === "advance" || typeCode === "loan") && (
            <div className="row">
              <div className="field" style={{ flex: 1 }}><label htmlFor="req-adv-amount">{t("req_amount")} *</label>
                <input id="req-adv-amount" type="number" min={0} required onChange={(e) => setPayload({ ...payload, amount: +e.target.value })} /></div>
              {typeCode === "loan" && (
                <div className="field" style={{ width: 120 }}><label htmlFor="req-adv-months">{t("req_months")} *</label>
                  <input id="req-adv-months" type="number" min={1} required onChange={(e) => setPayload({ ...payload, months: +e.target.value })} /></div>
              )}
              <div className="field" style={{ flex: 2 }}><label htmlFor="req-adv-reason">{t("req_reason")}</label>
                <input id="req-adv-reason" onChange={(e) => setPayload({ ...payload, reason: e.target.value })} /></div>
            </div>
          )}
          {typeCode === "REQADV" && (
            <div className="row">
              <div className="field" style={{ width: 150 }}><label htmlFor="req-reqadv-subtype">{t("req_subtype")} *</label>
                <select id="req-reqadv-subtype" required onChange={(e) => setPayload({ ...payload, subtype: e.target.value })}>
                  <option value="advance">{t("req_subtype_advance")}</option>
                  <option value="loan">{t("req_subtype_loan")}</option>
                </select></div>
              <div className="field" style={{ flex: 1 }}><label htmlFor="req-reqadv-amount">{t("req_amount")} *</label>
                <input id="req-reqadv-amount" type="number" min={0} required onChange={(e) => setPayload({ ...payload, amount: +e.target.value })} /></div>
              <div className="field" style={{ width: 140 }}><label htmlFor="req-reqadv-installments">{t("req_installments")}</label>
                <input id="req-reqadv-installments" type="number" min={1} onChange={(e) => setPayload({ ...payload, installments: +e.target.value })} /></div>
              <div className="field" style={{ flex: 2 }}><label htmlFor="req-reqadv-reason">{t("req_reason")}</label>
                <input id="req-reqadv-reason" onChange={(e) => setPayload({ ...payload, reason: e.target.value })} /></div>
            </div>
          )}
          {typeCode === "REQBANK" && (
            <div className="row">
              <div className="field" style={{ flex: 1 }}><label htmlFor="req-bank-name">{t("req_bank_name")} *</label>
                <input id="req-bank-name" required onChange={(e) => setPayload({ ...payload, bank_name: e.target.value })} /></div>
              <div className="field" style={{ flex: 1 }}><label htmlFor="req-bank-iban">{t("req_iban")} *</label>
                <input id="req-bank-iban" required onChange={(e) => setPayload({ ...payload, iban: e.target.value })} /></div>
            </div>
          )}
          {typeCode === "REQEXP" && (
            <div className="row">
              <div className="field" style={{ flex: 1 }}><label htmlFor="req-exp-amount">{t("req_amount")} *</label>
                <input id="req-exp-amount" type="number" min={0} required onChange={(e) => setPayload({ ...payload, amount: +e.target.value })} /></div>
              <div className="field" style={{ flex: 1 }}><label htmlFor="req-exp-receipt">{t("req_receipt_ref")}</label>
                <input id="req-exp-receipt" onChange={(e) => setPayload({ ...payload, receipt_ref: e.target.value })} /></div>
              <div className="field" style={{ flex: 2 }}><label htmlFor="req-exp-description">{t("req_description")} *</label>
                <input id="req-exp-description" required onChange={(e) => setPayload({ ...payload, description: e.target.value })} /></div>
            </div>
          )}
          {typeCode === "REQWARN" && (
            <div className="row">
              <div className="field" style={{ flex: 1 }}><label htmlFor="req-warn-ref">{t("req_warning_ref")} *</label>
                <input id="req-warn-ref" required onChange={(e) => setPayload({ ...payload, warning_ref: e.target.value })} /></div>
              <div className="field" style={{ flex: 2 }}><label htmlFor="req-warn-response">{t("req_response")} *</label>
                <input id="req-warn-response" required onChange={(e) => setPayload({ ...payload, response: e.target.value })} /></div>
            </div>
          )}
          {!["leave", "salary_certificate", "exit_permission", "advance", "loan",
            "REQADV", "REQBANK", "REQEXP", "REQWARN"].includes(typeCode) && typeCode && (
            <>
              <div className="row">
                <div className="field" style={{ flex: 1 }}><label htmlFor="req-generic-date">{t("req_date")}</label>
                  <input id="req-generic-date" type="date" onChange={(e) => setPayload({ ...payload, date: e.target.value })} /></div>
                <div className="field" style={{ flex: 1 }}><label htmlFor="req-generic-amount">{t("req_amount")}</label>
                  <input id="req-generic-amount" type="number" min={0} onChange={(e) => setPayload({ ...payload, amount: e.target.value ? +e.target.value : undefined })} /></div>
              </div>
              <div className="field"><label htmlFor="req-generic-details">{t("req_details")} *</label>
                <textarea id="req-generic-details" rows={3} required onChange={(e) => setPayload({ ...payload, details: e.target.value })} /></div>
              <p className="muted">{t("req_details_hint")}</p>
            </>
          )}
          {err && <div className="err">{err}</div>}
          <button onClick={submit}>{t("submit")}</button>
        </div>
      )}

      <div className="row" style={{ marginBottom: 12 }}>
        <button className={tab === "mine" ? "" : "ghost"} onClick={() => setTab("mine")}>{t("my_requests")}</button>
        {(can("approve_request") || can("process_delegate_tasks")) && (
          <button className={tab === "inbox" ? "" : "ghost"} onClick={() => setTab("inbox")}>
            {t("approval_inbox")} {inbox.length ? `(${inbox.length})` : ""}
          </button>
        )}
      </div>

      {state === "loading" ? <Skeleton rows={4} />
        : state === "error" ? <ErrorRetry onRetry={load} />
        : !list.length ? <EmptyState icon="requests" />
        : <div className="table-wrap">
        <table>
          <thead><tr><th>#</th><th>{t("col_type")}</th><th>{t("col_employee")}</th><th>{t("status")}</th><th>{t("req_path")}</th><th></th></tr></thead>
          <tbody>
            {list.map((r) => (
              <tr key={r.id}>
                <td className="num">{r.id}</td>
                <td>{r.type_name}</td>
                <td>{r.employee_name}</td>
                <td><span className={`pill ${r.status}`}>{statusAr(r.status)}</span></td>
                <td><ProgressMini current={r.current_stage} total={r.total_stages} status={r.status} /></td>
                <td><Link to={`/requests/${r.id}`}>{t("view")} →</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>}
    </div>
  );
}
