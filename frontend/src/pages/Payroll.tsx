import { useEffect, useState } from "react";
import api, { downloadSensitiveReport } from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import { statusAr } from "../labels";
import Icon from "../Icon";

function thisMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export default function Payroll() {
  const { can } = useAuth();
  const { t } = useI18n();
  const [period, setPeriod] = useState(thisMonth());
  const [data, setData] = useState<any>(null);
  const [runId, setRunId] = useState<number | null>(null);
  const [runs, setRuns] = useState<any[]>([]);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const loadRuns = () => api.get("/payroll/runs").then((r) => setRuns(r.data)).catch(() => {});
  useEffect(() => { loadRuns(); }, []);

  const preview = async () => {
    setErr(""); setRunId(null);
    try { setData((await api.get("/payroll/preview", { params: { period } })).data); }
    catch (e: any) { setErr(e.response?.data?.detail || "خطأ"); }
  };
  const run = async () => {
    setErr("");
    try {
      const r = await api.post("/payroll/run", null, { params: { period } });
      setData(r.data); setRunId(r.data.run_id); setMsg("تم تشغيل المسيّر وحفظه");
      loadRuns();
    } catch (e: any) { setErr(e.response?.data?.detail || t("error")); }
  };

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="eyebrow">{t("payroll")}</div>
          <h2 style={{ margin: "2px 0 0" }}>{t("payroll")}</h2>
          <div className="sub">{t("rep_attendance_sub")}</div>
        </div>
        <div className="row">
          <input type="month" value={period} onChange={(e) => setPeriod(e.target.value)} style={{ width: 160 }} />
          <button className="ghost" onClick={preview}>{t("payroll_preview")}</button>
          {can("run_payroll") && <button onClick={run}>{t("payroll_run")}</button>}
        </div>
      </div>
      {msg && <div className="ok">{msg}</div>}
      {err && <div className="err">{err}</div>}

      {data && (
        <>
          <div className="grid stats">
            <div className="stat"><div className="num">{data.employees_count}</div><div className="lbl">{t("payroll_count")}</div></div>
            <div className="stat accent"><div className="num">{data.totals.net}</div><div className="lbl">{t("payroll_net_total")}</div></div>
            <div className="stat"><div className="num">{data.totals.gross}</div><div className="lbl">{t("payroll_gross")}</div></div>
            <div className="stat"><div className="num">{data.totals.deductions}</div><div className="lbl">{t("payroll_ded")}</div></div>
          </div>
          <div className="row" style={{ justifyContent: "flex-end", marginBottom: 10 }}>
            {runId && can("export_reports") && (
              <button className="ghost" onClick={() => downloadSensitiveReport(`/reports/payroll/${runId}`, { fmt: "xlsx" }, "payroll.xlsx", t("export_reason_prompt"))}>
                <Icon name="doc" size={15} /> {t("payroll_export")}
              </button>
            )}
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>{t("col_employee")}</th><th>{t("payroll_basic")}</th><th>{t("payroll_present")}</th><th>{t("payroll_absent")}</th><th>{t("payroll_overtime")}</th><th>{t("payroll_ded")}</th><th>{t("payroll_net")}</th></tr></thead>
              <tbody>
                {data.payslips.map((p: any) => (
                  <tr key={p.employee_id}>
                    <td><b>{p.name}</b><br /><span className="muted">{p.job_title}</span></td>
                    <td className="num">{p.basic_salary}</td>
                    <td className="num">{p.present_days}</td>
                    <td className="num">{p.absent_days}</td>
                    <td className="num">{p.overtime_pay}</td>
                    <td className="num">{p.total_deductions}</td>
                    <td className="num"><b style={{ color: "var(--petrol-700)" }}>{p.net}</b></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <div className="card">
        <h3>{t("payroll_runs")}</h3>
        <table>
          <thead><tr><th>{t("payroll_period")}</th><th>{t("payroll_count")}</th><th>{t("payroll_net")}</th><th>{t("status")}</th><th></th></tr></thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.id}>
                <td>{r.period}</td><td className="num">{r.employees_count}</td>
                <td className="num">{r.totals?.net}</td>
                <td><span className="pill success">{statusAr(r.status)}</span></td>
                <td>{can("export_reports") && <button className="ghost sm" onClick={() => downloadSensitiveReport(`/reports/payroll/${r.id}`, { fmt: "xlsx" }, "payroll.xlsx", t("export_reason_prompt"))}>Excel</button>}</td>
              </tr>
            ))}
            {!runs.length && <tr><td colSpan={5} className="empty">لا توجد مسيّرات محفوظة</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
