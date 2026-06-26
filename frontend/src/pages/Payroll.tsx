import { useEffect, useState } from "react";
import api, { downloadFile } from "../api";
import { useAuth } from "../auth";
import Icon from "../Icon";

function thisMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export default function Payroll() {
  const { can } = useAuth();
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
    } catch (e: any) { setErr(e.response?.data?.detail || "خطأ"); }
  };

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="eyebrow">الرواتب</div>
          <h2 style={{ margin: "2px 0 0" }}>مسيّر الرواتب</h2>
          <div className="sub">حساب الرواتب من الحضور والإضافي والخصومات</div>
        </div>
        <div className="row">
          <input type="month" value={period} onChange={(e) => setPeriod(e.target.value)} style={{ width: 160 }} />
          <button className="ghost" onClick={preview}>معاينة</button>
          {can("run_payroll") && <button onClick={run}>تشغيل وحفظ</button>}
        </div>
      </div>
      {msg && <div className="ok">{msg}</div>}
      {err && <div className="err">{err}</div>}

      {data && (
        <>
          <div className="grid stats">
            <div className="stat"><div className="num">{data.employees_count}</div><div className="lbl">عدد الموظفين</div></div>
            <div className="stat accent"><div className="num">{data.totals.net}</div><div className="lbl">إجمالي الصافي (د.ك)</div></div>
            <div className="stat"><div className="num">{data.totals.gross}</div><div className="lbl">الإجمالي</div></div>
            <div className="stat"><div className="num">{data.totals.deductions}</div><div className="lbl">الخصومات</div></div>
          </div>
          <div className="row" style={{ justifyContent: "flex-end", marginBottom: 10 }}>
            {runId && can("export_reports") && (
              <button className="ghost" onClick={() => downloadFile(`/reports/payroll/${runId}`, { fmt: "xlsx" }, "payroll.xlsx")}>
                <Icon name="doc" size={15} /> تصدير Excel
              </button>
            )}
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>الموظف</th><th>الأساسي</th><th>حضور</th><th>غياب</th><th>الإضافي</th><th>خصومات</th><th>الصافي</th></tr></thead>
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
        <h3>المسيّرات السابقة</h3>
        <table>
          <thead><tr><th>الفترة</th><th>الموظفون</th><th>الصافي</th><th>الحالة</th><th></th></tr></thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.id}>
                <td>{r.period}</td><td className="num">{r.employees_count}</td>
                <td className="num">{r.totals?.net}</td>
                <td><span className="pill success">{r.status}</span></td>
                <td>{can("export_reports") && <button className="ghost sm" onClick={() => downloadFile(`/reports/payroll/${r.id}`, { fmt: "xlsx" }, "payroll.xlsx")}>Excel</button>}</td>
              </tr>
            ))}
            {!runs.length && <tr><td colSpan={5} className="empty">لا توجد مسيّرات محفوظة</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
