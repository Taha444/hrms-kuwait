import { useEffect, useState } from "react";
import api from "../api";
import { useI18n } from "../i18n";

export default function Eos() {
  const { t } = useI18n();
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [form, setForm] = useState<any>({
    basic_salary: 500, hire_date: "2018-01-01", end_date: "2024-01-01",
    reason: "termination", contract_type: "indefinite", unused_leave_days: 0, day_divisor: 26,
  });
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState("");

  useEffect(() => { api.get("/eos/reasons").then((r) => setReasons(r.data)); }, []);

  const calc = async () => {
    setErr("");
    try { const r = await api.post("/eos/calculate", form); setRes(r.data); }
    catch (e: any) { setErr(e.response?.data?.detail || t("error")); }
  };

  return (
    <div>
      <h2>{t("eos_title")}</h2>
      <div className="card">
        <div className="row">
          <div className="field" style={{ flex: 1 }}><label>{t("eos_basic_salary")}</label>
            <input type="number" value={form.basic_salary}
              onChange={(e) => setForm({ ...form, basic_salary: +e.target.value })} /></div>
          <div className="field" style={{ flex: 1 }}><label>{t("eos_hire_date")}</label>
            <input type="date" value={form.hire_date}
              onChange={(e) => setForm({ ...form, hire_date: e.target.value })} /></div>
          <div className="field" style={{ flex: 1 }}><label>{t("eos_end_date")}</label>
            <input type="date" value={form.end_date}
              onChange={(e) => setForm({ ...form, end_date: e.target.value })} /></div>
        </div>
        <div className="row">
          <div className="field" style={{ flex: 1 }}><label>{t("eos_reason")}</label>
            <select value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })}>
              {Object.entries(reasons).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select></div>
          <div className="field" style={{ flex: 1 }}><label>{t("eos_contract_type")}</label>
            <select value={form.contract_type} onChange={(e) => setForm({ ...form, contract_type: e.target.value })}>
              <option value="indefinite">{t("eos_indefinite")}</option><option value="definite">{t("eos_definite")}</option>
            </select></div>
          <div className="field" style={{ flex: 1 }}><label>{t("eos_unused_leave")}</label>
            <input type="number" value={form.unused_leave_days}
              onChange={(e) => setForm({ ...form, unused_leave_days: +e.target.value })} /></div>
          <div className="field" style={{ width: 100 }}><label>{t("eos_divisor")}</label>
            <select value={form.day_divisor} onChange={(e) => setForm({ ...form, day_divisor: +e.target.value })}>
              <option value={26}>26</option><option value={30}>30</option></select></div>
        </div>
        {err && <div className="err">{err}</div>}
        <button onClick={calc}>{t("eos_calc")}</button>
      </div>

      {res && (
        <div className="card">
          <h3>{t("eos_result")}</h3>
          <div className="grid">
            <div className="stat card"><div className="num">{res.total_settlement}</div><div className="lbl">{t("eos_total")}</div></div>
            <div className="stat card"><div className="num">{res.indemnity}</div><div className="lbl">{t("eos_indemnity")}</div></div>
            <div className="stat card"><div className="num">{res.leave_payout}</div><div className="lbl">{t("eos_leave_payout")}</div></div>
            <div className="stat card"><div className="num">{res.daily_wage}</div><div className="lbl">{t("eos_daily_wage")}</div></div>
          </div>
          <p><b>{t("eos_service")}</b> {res.service.text} ({res.service.decimal_years} {t("eos_years")})</p>
          <p><b>{t("eos_factor")}</b> {(res.entitlement_factor * 100).toFixed(2)}% — {res.factor_note}</p>
          {res.cap_applied && <p className="err">{t("eos_cap")}</p>}
          <p className="muted">{res.disclaimer}</p>
        </div>
      )}
    </div>
  );
}
