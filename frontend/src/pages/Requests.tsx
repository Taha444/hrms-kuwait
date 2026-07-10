import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
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

  const submit = async () => {
    setErr("");
    try {
      const clean = Object.fromEntries(
        Object.entries(payload).filter(([, v]) => v !== "" && v !== undefined && v !== null)
      );
      const body: any = { request_type_code: typeCode, payload_json: clean };
      if (onBehalfOf) body.employee_id = onBehalfOf;
      await api.post("/requests", body);
      setShowNew(false); setPayload({}); load();
    } catch (e: any) { setErr(e.response?.data?.detail || t("error")); }
  };

  const list = tab === "mine" ? mine : inbox;

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2>{t("requests")}</h2>
        {can("submit_request") && <button onClick={() => setShowNew((s) => !s)}>+ {t("new_request")}</button>}
      </div>

      {showNew && (
        <div className="card">
          <h3>{t("new_request")}</h3>
          <div className="field">
            <label>{t("req_type")}</label>
            <select value={typeCode} onChange={(e) => setTypeCode(e.target.value)}>
              {types.map((x) => <option key={x.code} value={x.code}>{x.name}</option>)}
            </select>
          </div>
          {canActOnBehalf && (
            <div className="field">
              <label>{t("req_on_behalf_of")}</label>
              <select value={onBehalfOf} onChange={(e) => setOnBehalfOf(e.target.value ? +e.target.value : "")}>
                <option value="">{t("req_myself")}</option>
                {employees.map((e) => <option key={e.id} value={e.id}>{e.name} — {e.job_title}</option>)}
              </select>
            </div>
          )}
          {typeCode === "leave" && (
            <>
              <div className="row">
                <div className="field" style={{ flex: 1 }}>
                  <label>{t("req_from")}</label>
                  <input type="date" onChange={(e) => setPayload({ ...payload, start_date: e.target.value })} />
                </div>
                <div className="field" style={{ flex: 1 }}>
                  <label>{t("req_to")}</label>
                  <input type="date" onChange={(e) => setPayload({ ...payload, end_date: e.target.value })} />
                </div>
                <div className="field" style={{ width: 100 }}>
                  <label>{t("req_days")}</label>
                  <input type="number" onChange={(e) => setPayload({ ...payload, days: +e.target.value })} />
                </div>
              </div>
              <div className="field"><label>{t("req_reason")}</label>
                <input onChange={(e) => setPayload({ ...payload, reason: e.target.value })} /></div>
            </>
          )}
          {typeCode === "salary_certificate" && (
            <>
              <div className="field"><label>{t("req_addressed")}</label>
                <input onChange={(e) => setPayload({ ...payload, addressed_to: e.target.value })} /></div>
              <div className="field"><label>{t("req_purpose")}</label>
                <input onChange={(e) => setPayload({ ...payload, purpose: e.target.value })} /></div>
            </>
          )}
          {typeCode === "exit_permission" && (
            <div className="row">
              <div className="field" style={{ flex: 1 }}><label>{t("req_date")}</label>
                <input type="date" onChange={(e) => setPayload({ ...payload, date: e.target.value })} /></div>
              <div className="field" style={{ flex: 2 }}><label>{t("req_reason")}</label>
                <input onChange={(e) => setPayload({ ...payload, reason: e.target.value })} /></div>
            </div>
          )}
          {(typeCode === "advance" || typeCode === "loan") && (
            <div className="row">
              <div className="field" style={{ flex: 1 }}><label>{t("req_amount")}</label>
                <input type="number" min={0} onChange={(e) => setPayload({ ...payload, amount: +e.target.value })} /></div>
              {typeCode === "loan" && (
                <div className="field" style={{ width: 120 }}><label>{t("req_months")}</label>
                  <input type="number" min={1} onChange={(e) => setPayload({ ...payload, months: +e.target.value })} /></div>
              )}
              <div className="field" style={{ flex: 2 }}><label>{t("req_reason")}</label>
                <input onChange={(e) => setPayload({ ...payload, reason: e.target.value })} /></div>
            </div>
          )}
          {typeCode === "REQADV" && (
            <div className="row">
              <div className="field" style={{ width: 150 }}><label>{t("req_subtype")}</label>
                <select onChange={(e) => setPayload({ ...payload, subtype: e.target.value })}>
                  <option value="advance">{t("req_subtype_advance")}</option>
                  <option value="loan">{t("req_subtype_loan")}</option>
                </select></div>
              <div className="field" style={{ flex: 1 }}><label>{t("req_amount")}</label>
                <input type="number" min={0} onChange={(e) => setPayload({ ...payload, amount: +e.target.value })} /></div>
              <div className="field" style={{ width: 140 }}><label>{t("req_installments")}</label>
                <input type="number" min={1} onChange={(e) => setPayload({ ...payload, installments: +e.target.value })} /></div>
              <div className="field" style={{ flex: 2 }}><label>{t("req_reason")}</label>
                <input onChange={(e) => setPayload({ ...payload, reason: e.target.value })} /></div>
            </div>
          )}
          {typeCode === "REQBANK" && (
            <div className="row">
              <div className="field" style={{ flex: 1 }}><label>{t("req_bank_name")}</label>
                <input onChange={(e) => setPayload({ ...payload, bank_name: e.target.value })} /></div>
              <div className="field" style={{ flex: 1 }}><label>{t("req_iban")}</label>
                <input onChange={(e) => setPayload({ ...payload, iban: e.target.value })} /></div>
            </div>
          )}
          {typeCode === "REQEXP" && (
            <div className="row">
              <div className="field" style={{ flex: 1 }}><label>{t("req_amount")}</label>
                <input type="number" min={0} onChange={(e) => setPayload({ ...payload, amount: +e.target.value })} /></div>
              <div className="field" style={{ flex: 1 }}><label>{t("req_receipt_ref")}</label>
                <input onChange={(e) => setPayload({ ...payload, receipt_ref: e.target.value })} /></div>
              <div className="field" style={{ flex: 2 }}><label>{t("req_description")}</label>
                <input onChange={(e) => setPayload({ ...payload, description: e.target.value })} /></div>
            </div>
          )}
          {typeCode === "REQWARN" && (
            <div className="row">
              <div className="field" style={{ flex: 1 }}><label>{t("req_warning_ref")}</label>
                <input onChange={(e) => setPayload({ ...payload, warning_ref: e.target.value })} /></div>
              <div className="field" style={{ flex: 2 }}><label>{t("req_response")}</label>
                <input onChange={(e) => setPayload({ ...payload, response: e.target.value })} /></div>
            </div>
          )}
          {!["leave", "salary_certificate", "exit_permission", "advance", "loan",
            "REQADV", "REQBANK", "REQEXP", "REQWARN"].includes(typeCode) && typeCode && (
            <>
              <div className="row">
                <div className="field" style={{ flex: 1 }}><label>{t("req_date")}</label>
                  <input type="date" onChange={(e) => setPayload({ ...payload, date: e.target.value })} /></div>
                <div className="field" style={{ flex: 1 }}><label>{t("req_amount")}</label>
                  <input type="number" min={0} onChange={(e) => setPayload({ ...payload, amount: e.target.value ? +e.target.value : undefined })} /></div>
              </div>
              <div className="field"><label>{t("req_details")}</label>
                <textarea rows={3} onChange={(e) => setPayload({ ...payload, details: e.target.value })} /></div>
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
