import { useEffect, useState } from "react";
import api, { errMsg } from "../api";
import { useI18n } from "../i18n";

// P0-#9 — إعادة تصميم: مافيش demo defaults. الحساب يبدأ بـEmployee selection.
// Salary/Hire Date من الـEmployee record (read-only). المستخدم يدخل فقط:
// end_date, reason, used_leave_days.
export default function Eos() {
  const { t } = useI18n();
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [employees, setEmployees] = useState<any[]>([]);
  const [empId, setEmpId] = useState<number | "">("");
  const [selectedEmp, setSelectedEmp] = useState<any>(null);
  const [form, setForm] = useState<any>({
    end_date: "", reason: "termination", used_leave_days: 0,
  });
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  // تسمية السبب من القاموس، وما لا مقابل له يُعرض بتسمية الخادم.
  const reasonLabel = (k: string) => (t(`rsn_${k}`) !== `rsn_${k}` ? t(`rsn_${k}`) : reasons[k] || k);

  useEffect(() => {
    api.get("/eos/reasons").then((r) => setReasons(r.data));
    api.get("/employees").then((r) => setEmployees(r.data));
  }, []);

  useEffect(() => {
    if (!empId) { setSelectedEmp(null); return; }
    const emp = employees.find((e) => e.id === empId);
    setSelectedEmp(emp || null);
    setRes(null);  // امسح النتيجة القديمة عند تغيير الموظف
  }, [empId, employees]);

  const calc = async () => {
    if (!empId || !selectedEmp) {
      setErr(t("eosx_pick_first"));
      return;
    }
    if (!selectedEmp.basic_salary || !selectedEmp.hire_date) {
      setErr(t("eosx_incomplete", { name: selectedEmp.name }));
      return;
    }
    if (!form.end_date) {
      setErr(t("eosx_end_required"));
      return;
    }
    setErr(""); setBusy(true);
    try {
      const r = await api.post("/eos/for-employee", {
        employee_id: empId,
        end_date: form.end_date,
        reason: form.reason,
        used_leave_days: form.used_leave_days,
      });
      setRes(r.data);
    } catch (e: any) {
      setErr(errMsg(e, t("error")));
    } finally { setBusy(false); }
  };

  const unset = <span style={{ color: "var(--danger)" }}>{t("eosx_unset")}</span>;

  return (
    <div>
      <h2>{t("eos_title")}</h2>
      <div className="card">
        {/* اختيار الموظف — إلزامي */}
        <div className="field">
          <label htmlFor="eos-emp">{t("eosx_pick")}</label>
          <select id="eos-emp" value={empId}
                  onChange={(e) => setEmpId(e.target.value ? +e.target.value : "")}>
            <option value="">{t("eosx_choose")}</option>
            {employees.map((e) => (
              <option key={e.id} value={e.id}>
                {e.employee_no ? `[${e.employee_no}] ` : ""}{e.name} — {e.job_title || "—"}
              </option>
            ))}
          </select>
        </div>

        {/* بيانات الموظف — read-only من الـrecord */}
        {selectedEmp && (
          <div className="card" style={{ background: "#f0f6fa", padding: 12, marginBottom: 12 }}>
            <b>{t("eosx_record_of", { name: selectedEmp.name })}</b>
            <div className="row" style={{ marginTop: 8, gap: 20, fontSize: 14 }}>
              <div><b>{t("eosx_basic")}</b> {selectedEmp.basic_salary
                ? t("eosx_kwd", { n: selectedEmp.basic_salary }) : unset}</div>
              <div><b>{t("eosx_hire")}</b> {selectedEmp.hire_date || unset}</div>
              <div><b>{t("eosx_contract")}</b> {t(selectedEmp.contract_type === "indefinite"
                ? "eosx_indefinite" : "eosx_definite")}</div>
            </div>
          </div>
        )}

        {/* الحقول اللي المستخدم يدخلها */}
        <div className="row">
          <div className="field" style={{ flex: 1 }}>
            <label htmlFor="eos-end">{t("eosx_end")}</label>
            <input id="eos-end" type="date" value={form.end_date}
                   onChange={(e) => setForm({ ...form, end_date: e.target.value })} required />
          </div>
          <div className="field" style={{ flex: 1 }}>
            <label htmlFor="eos-reason">{t("eosx_reason")}</label>
            <select id="eos-reason" value={form.reason}
                    onChange={(e) => setForm({ ...form, reason: e.target.value })}>
              {Object.keys(reasons).map((k) => <option key={k} value={k}>{reasonLabel(k)}</option>)}
            </select>
          </div>
          <div className="field" style={{ flex: 1 }}>
            <label htmlFor="eos-used-leave">{t("eosx_used_leave")}</label>
            <input id="eos-used-leave" type="number" min={0} step={1} value={form.used_leave_days}
                   onChange={(e) => setForm({ ...form, used_leave_days: +e.target.value })} />
          </div>
        </div>
        {/* قرار المالك (2026-09-17): بدل الإنذار يُحسب في المعاملة بجواب «أُبلغ الإنذار؟» —
            وهذه الحسبة المبدئية بلا ذلك الجواب، فلا تحمله. */}
        {form.reason === "termination" && <div className="sub">{t("eosx_notice_hint")}</div>}

        {err && <div className="err">{err}</div>}
        <button onClick={calc} disabled={busy || !empId}
                style={{ opacity: (!empId ? 0.5 : 1) }}>
          {busy ? t("eosx_calculating") : t("eosx_calc")}
        </button>
      </div>

      {res && (
        <div className="card">
          <h3>{t("eosx_result", { name: res.employee?.name ?? "" })}</h3>
          <div className="grid">
            <div className="stat card"><div className="num">{res.total_settlement}</div><div className="lbl">{t("eosx_total")}</div></div>
            <div className="stat card"><div className="num">{res.indemnity}</div><div className="lbl">{t("eosx_indemnity")}</div></div>
            <div className="stat card"><div className="num">{res.leave_payout}</div><div className="lbl">{t("eosx_leave_payout")}</div></div>
            <div className="stat card"><div className="num">{res.daily_wage}</div><div className="lbl">{t("eosx_daily")}</div></div>
          </div>
          <p><b>{t("eosx_service")}</b> {res.service.text} ({t("eosx_years", { n: res.service.decimal_years })})</p>
          {res.leave && (
            <p><b>{t("eosx_leave")}</b> {t("eosx_leave_line", {
              accrued: res.leave.accrued_days, used: res.leave.used_days, remaining: res.leave.remaining_days })}</p>
          )}
          {res.leave?.advance_note && <p className="err">⚠ {res.leave.advance_note}</p>}
          <p><b>{t("eosx_factor")}</b> {(res.entitlement_factor * 100).toFixed(2)}% — {res.factor_note}</p>
          {res.cap_applied && <p className="err">{t("eos_cap")}</p>}
          <p className="muted">{res.disclaimer}</p>
        </div>
      )}
    </div>
  );
}
