import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import { ProgressMini } from "../components/RequestSteps";
import { statusAr } from "../labels";

export default function Requests() {
  const { t } = useI18n();
  const { can } = useAuth();
  const [tab, setTab] = useState<"mine" | "inbox">("mine");
  const [mine, setMine] = useState<any[]>([]);
  const [inbox, setInbox] = useState<any[]>([]);
  const [types, setTypes] = useState<any[]>([]);
  const [showNew, setShowNew] = useState(false);
  const [typeCode, setTypeCode] = useState("");
  const [payload, setPayload] = useState<any>({});
  const [err, setErr] = useState("");

  const load = () => {
    api.get("/requests/mine").then((r) => setMine(r.data));
    if (can("approve_request")) api.get("/requests/inbox").then((r) => setInbox(r.data));
  };
  useEffect(() => {
    load();
    api.get("/requests/types").then((r) => { setTypes(r.data); setTypeCode(r.data[0]?.code || ""); });
  }, []);

  const submit = async () => {
    setErr("");
    try {
      await api.post("/requests", { request_type_code: typeCode, payload_json: payload });
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
          {err && <div className="err">{err}</div>}
          <button onClick={submit}>{t("submit")}</button>
        </div>
      )}

      <div className="row" style={{ marginBottom: 12 }}>
        <button className={tab === "mine" ? "" : "ghost"} onClick={() => setTab("mine")}>{t("my_requests")}</button>
        {can("approve_request") && (
          <button className={tab === "inbox" ? "" : "ghost"} onClick={() => setTab("inbox")}>
            {t("approval_inbox")} {inbox.length ? `(${inbox.length})` : ""}
          </button>
        )}
      </div>

      <div className="table-wrap">
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
            {!list.length && <tr><td colSpan={6} className="empty">{t("no_data")}</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
