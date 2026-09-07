import { useEffect, useState } from "react";
import api, { downloadSensitiveReport, errMsg } from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import { statusAr } from "../labels";
import Icon from "../Icon";

//: لون كل حالة من دورة المسيّر. المقفل وحده «نجاح» — وما قبله عمٌل باقٍ.
const RUN_PILL: Record<string, string> = {
  prepared: "warning", approved: "info", finalized: "info",
  locked: "success", adjustment_run: "neutral",
};

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

  // PR-UI — دورة المسيّر لم يكن لها مخرج من الشاشة: يُجهَّز ولا يُعتمَد ولا
  // يُقفَل ولا يُقفل نهائًيا. والخادم يفرض الدورة كاملة، فتبقى مسيّرات
  // العميل عند «مجهَّز» إلى الأبد — وهي عملية الشهر الأساسية عنده.
  //
  // والأعلام تأتي من الخادم ولا تُحسب هنا: شرط فصل السلطات مكتوب مرّة في
  // المنع، وزٌر يظهر ثم يفشل بـ403 أسوأ من زرّ غائب.
  const act = async (runId: number, path: string, params?: any) => {
    setErr(""); setMsg("");
    try {
      const r = await api.post(`/payroll/runs/${runId}/${path}`, null, { params });
      setMsg(`${t("payroll_state_now")} ${statusAr(r.data.status)}`);
      loadRuns();
    } catch (e: any) { setErr(errMsg(e, t("error"))); }
  };

  const askReason = (prompt: string): string | null => {
    const reason = window.prompt(prompt);
    return reason && reason.trim() ? reason.trim() : null;
  };

  // QA-24 — حقل الشهر يبدأ بقيمة، لكن المستخدم يستطيع مسحه. بلا هذا الفحص
  // يُرسَل period فارًغا فيعود خطأ خادم غامض بدل رسالة تقول ما ينقص.
  const requirePeriod = () => {
    if (!period) { setErr(t("payroll_pick_month")); return false; }
    return true;
  };

  const preview = async () => {
    setErr(""); setRunId(null);
    if (!requirePeriod()) return;
    try { setData((await api.get("/payroll/preview", { params: { period } })).data); }
    catch (e: any) { setErr(errMsg(e, t("error"))); }
  };
  const run = async () => {
    setErr("");
    if (!requirePeriod()) return;
    try {
      const r = await api.post("/payroll/run", null, { params: { period } });
      setData(r.data); setRunId(r.data.run_id); setMsg("تم تشغيل المسيّر وحفظه");
      loadRuns();
    } catch (e: any) { setErr(errMsg(e, t("error"))); }
  };

  return (
    <div aria-labelledby="payroll-title">
      <div className="page-head">
        <div>
          <div className="eyebrow">{t("payroll")}</div>
          <h2 id="payroll-title" style={{ margin: "2px 0 0" }}>{t("payroll")}</h2>
          <div className="sub">{t("rep_attendance_sub")}</div>
        </div>
        <div className="row">
          <input aria-label={t("payroll")} type="month" value={period} onChange={(e) => setPeriod(e.target.value)} style={{ width: 160 }} />
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
          <thead><tr><th>{t("payroll_period")}</th><th>{t("payroll_count")}</th><th>{t("payroll_net")}</th><th>{t("status")}</th><th>{t("payroll_trail")}</th><th></th></tr></thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.id}>
                <td>{r.period}</td><td className="num">{r.employees_count}</td>
                <td className="num">{r.totals?.net}</td>
                {/* PR-UI — لكل حالة لونها. كانت كلّها «نجاح»، فيستوي مسيٌّر
                    مجهَّز لم يعتمده أحد ومسيٌّر مقفل صُرف — واللون هو أول ما
                    يُقرأ من الجدول. */}
                <td><span className={`pill ${RUN_PILL[r.status] || "neutral"}`}>{statusAr(r.status)}</span></td>
                <td className="muted" style={{ fontSize: 11 }}>
                  {/* من جهّز ومن اعتمد: فصل السلطات لا يُثبَت بغير أسماء. */}
                  {r.prepared_by && <>{t("payroll_prepared_by")}: {r.prepared_by}<br /></>}
                  {r.approved_by && <>{t("payroll_approved_by")}: {r.approved_by}</>}
                  {r.adjustment_reason && <><br />{r.adjustment_reason}</>}
                </td>
                <td>
                  <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
                    {r.can_approve && <button className="sm" onClick={() => act(r.id, "approve")}>{t("payroll_approve")}</button>}
                    {r.can_finalize && <button className="sm" onClick={() => act(r.id, "finalize")}>{t("payroll_finalize")}</button>}
                    {r.can_lock && <button className="sm" onClick={() => act(r.id, "lock")}>{t("payroll_lock")}</button>}
                    {r.can_reopen && <button className="ghost sm" onClick={() => {
                      const reason = askReason(t("payroll_reopen_reason"));
                      if (reason) act(r.id, "reopen", { reason });
                    }}>{t("payroll_reopen")}</button>}
                    {r.can_adjust && <button className="ghost sm" onClick={() => {
                      const reason = askReason(t("payroll_adjust_reason"));
                      if (reason) act(r.id, "adjustment", { reason });
                    }}>{t("payroll_adjust")}</button>}
                    {can("export_reports") && <button className="ghost sm" onClick={() => downloadSensitiveReport(`/reports/payroll/${r.id}`, { fmt: "xlsx" }, "payroll.xlsx", t("export_reason_prompt"))}>Excel</button>}
                  </div>
                  {/* وصفٌّ بلا زرّ يقول لماذا — لا يُترَك المستخدم يخمّن. */}
                  {r.blocked_reason && <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>{r.blocked_reason}</div>}
                </td>
              </tr>
            ))}
            {!runs.length && <tr><td colSpan={6} className="empty">لا توجد مسيّرات محفوظة</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
