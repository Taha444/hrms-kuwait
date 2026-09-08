import { useEffect, useState } from "react";
import api, { errMsg } from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import { attAr } from "../labels";

// مراجعة الحضور الشهري (للسوبر أدمن/المالك/مدير الشركة): مصفوفة موظف × يوم.
const WD_AR = ["ح", "ن", "ث", "ر", "خ", "ج", "س"]; // الأحد..السبت
const WD_EN = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];
const MARK: Record<string, string> = { present: "✓", late: "!", absent: "✗", leave: "L", off: "", future: "" };

function thisMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export default function AttendanceReview() {
  const { t, lang } = useI18n();
  const { can } = useAuth();
  const [month, setMonth] = useState(thisMonth());
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  // ATT-07 — حالة إقفال الشهر: المسيّر يُمنع على فترة مفتوحة، وكانت
  // رسالته تحيل إلى «مراجعة الحضور» ولا شيء هنا يُغلق. بوابة بلا مخرج.
  const [close, setClose] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const loadClose = () =>
    api.get("/attendance/close-status", { params: { period: month } })
      .then((r) => setClose(r.data))
      .catch(() => setClose(null));

  // ATT-POL — موظف نشط بنمط ``none`` بلا إعفاء موثَّق يوقف إقفال المسيّر،
  // وكانت رسالة الرفض تسمّي **مساًرا خاًما** لا شاشة له. وهذه هي الشاشة:
  // نفس المكان الذي يُراجَع فيه الحضور ويُقفَل شهره.
  const [gaps, setGaps] = useState<any[]>([]);
  const loadGaps = () => api.get("/employees/attendance-policy/pending")
    .then((r) => setGaps(r.data)).catch(() => setGaps([]));

  const load = () => {
    setLoading(true);
    setMsg(""); setErr("");
    api.get("/attendance/review", { params: { month } })
      .then((r) => setData(r.data))
      .finally(() => setLoading(false));
    loadClose();
    loadGaps();
  };
  useEffect(() => { load(); }, [month]);

  const act = async (fn: () => Promise<any>, done: string) => {
    setBusy(true); setMsg(""); setErr("");
    try { await fn(); setMsg(done); await loadClose(); }
    catch (e: any) { setErr(errMsg(e, t("error"))); }
    finally { setBusy(false); }
  };

  // الإقفال إقرار على رقم، لا زرّ شكلي: العدد يُعرض في السؤال نفسه.
  const closeMonth = () => {
    const n = close?.unrecorded_days ?? 0;
    if (!window.confirm(t("att_close_confirm").replace("{n}", String(n))
                                             .replace("{m}", month))) return;
    act(() => api.post("/attendance/close-month", null,
                       { params: { period: month } }), t("att_close_done"));
  };

  // والسياسة تُثبَّت من هنا: نمٌط فعليّ، أو إعفاٌء **بسبب مكتوب** — فالإعفاء
  // بلا سبب هو الحال نفسها التي جاء المنع من أجلها.
  const setPolicy = (empId: number, mode: string) => {
    let params: any = { mode };
    if (mode === "none") {
      const reason = window.prompt(t("att_pol_exempt_reason"));
      if (!reason || !reason.trim()) return;
      params = { mode, exempt: true, exempt_reason: reason.trim() };
    }
    act(() => api.post(`/employees/${empId}/attendance-policy`, null, { params })
          .then(loadGaps), t("att_pol_done"));
  };

  const reopenMonth = () => {
    // السبب إلزامي على الخادم — فيُطلَب هنا بدل أن يُردّ الطلب بخطأ.
    const reason = window.prompt(t("att_reopen_reason"));
    if (!reason || !reason.trim()) return;
    act(() => api.post("/attendance/reopen-month", null,
                       { params: { period: month, reason: reason.trim() } }),
        t("att_reopen_done"));
  };

  const WD = lang === "ar" ? WD_AR : WD_EN;
  const dayMeta = (iso: string) => {
    const d = new Date(iso + "T00:00:00");
    const code = WD[d.getDay()];
    const weekend = d.getDay() === 5 || d.getDay() === 6; // الجمعة/السبت
    return { num: d.getDate(), code, weekend };
  };

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="eyebrow">{t("attendance")}</div>
          <h2 style={{ margin: "2px 0 0" }}>{t("att_review_title")}</h2>
          <div className="sub">{t("att_review_sub")}</div>
        </div>
        <div className="row">
          <input aria-label={t("att_review_title")} type="month" value={month} onChange={(e) => setMonth(e.target.value)} style={{ width: 170 }} />
          <button className="ghost" onClick={load}>{t("refresh")}</button>
        </div>
      </div>

      {msg && <div className="ok">{msg}</div>}
      {err && <div className="err">{err}</div>}

      {/* ATT-POL — موظفون نشطون بلا سياسة حضور موثَّقة. يوقفون إقفال
          المسيّر في الوضع الصارم، وكانت رسالة المنع تحيل إلى **مسار
          خام** لا شاشة له — أمٌر بفعل بلا باب. وهذا الباب. */}
      {gaps.length > 0 && (
        <div className="card" style={{ marginBottom: 12,
                                       borderInlineStart: "3px solid var(--warning)" }}>
          <h3 style={{ marginTop: 0 }}>{t("att_pol_title")} ({gaps.length})</h3>
          <div className="sub" style={{ marginBottom: 8 }}>{t("att_pol_hint")}</div>
          <div className="table-wrap">
            <table>
              <thead><tr>
                <th>{t("col_employee")}</th><th>{t("fld_hire_date")}</th><th></th>
              </tr></thead>
              <tbody>
                {gaps.map((g) => (
                  <tr key={g.id}>
                    <td><b>{g.name}</b>{g.employee_no && <><br /><span className="muted">{g.employee_no}</span></>}</td>
                    <td className="muted">{g.hire_date || "—"}</td>
                    <td>
                      <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
                        <button className="sm" disabled={busy} onClick={() => setPolicy(g.id, "qr")}>{t("att_pol_qr")}</button>
                        <button className="sm" disabled={busy} onClick={() => setPolicy(g.id, "gps")}>{t("att_pol_gps")}</button>
                        <button className="sm" disabled={busy} onClick={() => setPolicy(g.id, "both")}>{t("att_pol_both")}</button>
                        <button className="ghost sm" disabled={busy} onClick={() => setPolicy(g.id, "none")}>{t("att_pol_exempt")}</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ATT-07 / DLV-01 — حالة الشهر والمخرج منها.
          الرواتب لا تُشغَّل على فترة مفتوحة، وهذا هو الموضع الذي تحيل
          إليه رسالة المنع. وعدد الأيام بلا سجل معروض لأن الإقفال إقرار
          عليه: من أقرّ ومتى وعلى كم يوم — جواب مكتوب بعد شهور. */}
      {close && (
        <div className="card" style={{ marginBottom: 12 }}>
          <div className="row" style={{ justifyContent: "space-between",
                                        flexWrap: "wrap", gap: 8 }}>
            <div>
              <span className={`pill ${close.closed ? "completed" : "pending"}`}>
                {close.closed ? t("att_period_closed") : t("att_period_open")}
              </span>
              <span style={{ marginInlineStart: 10, fontSize: 13 }}>
                {t("att_unrecorded_days")}: <b>{close.unrecorded_days ?? 0}</b>
              </span>
              {/* التاريخ في سطره: بجوار العدد كان الرقمان يلتصقان بصرًيا
                  في الاتجاه العربي فيُقرآن رقًما واحًدا («360» ثم سنة). */}
              {close.closed_at && (
                <div className="sub" style={{ marginTop: 4 }}>
                  {t("att_closed_at")}: {close.closed_at.slice(0, 16).replace("T", " ")}
                </div>
              )}
              {close.status === "reopened" && close.reopen_reason && (
                <div className="sub" style={{ marginTop: 4 }}>
                  {t("att_reopen_reason_label")}: {close.reopen_reason}
                </div>
              )}
            </div>
            {can("manage_attendance") && (
              <div className="row">
                {close.closed
                  ? <button className="ghost" disabled={busy} onClick={reopenMonth}>
                      {t("att_reopen_month")}
                    </button>
                  : <button disabled={busy} onClick={closeMonth}>
                      {t("att_close_month")}
                    </button>}
              </div>
            )}
          </div>
          {!close.closed && (
            <div className="sub" style={{ marginTop: 6 }}>{t("att_close_hint")}</div>
          )}
        </div>
      )}

      <div className="att-legend">
        <span className="lg"><span className="sw" style={{ background: "var(--success-bg)" }} /> {t("att_legend_present")}</span>
        <span className="lg"><span className="sw" style={{ background: "var(--warning-bg)" }} /> {t("att_legend_late")}</span>
        <span className="lg"><span className="sw" style={{ background: "var(--danger-bg)" }} /> {t("att_legend_absent")}</span>
        <span className="lg"><span className="sw" style={{ background: "var(--info-bg)" }} /> {t("att_legend_leave")}</span>
        <span className="lg"><span className="sw" style={{ background: "#f1f4f3" }} /> {t("att_legend_off")}</span>
      </div>

      {loading ? <div className="empty">{t("loading")}</div>
        : !data?.employees?.length ? <div className="card empty">{t("att_no_tracked")}</div>
        : (
          <div className="att-wrap">
            <table className="att-matrix">
              <thead>
                <tr>
                  <th className="emp">{t("col_employee")} ({data.total_employees})</th>
                  {data.days.map((iso: string) => {
                    const m = dayMeta(iso);
                    return <th key={iso} className={`day ${m.weekend ? "we" : ""}`}>{m.num}<small>{m.code}</small></th>;
                  })}
                  <th className="day" style={{ minWidth: 44 }}>{t("att_legend_present")}</th>
                  <th className="day" style={{ minWidth: 44 }}>{t("att_legend_absent")}</th>
                  <th className="day" style={{ minWidth: 44 }}>{t("att_legend_leave")}</th>
                </tr>
              </thead>
              <tbody>
                {data.employees.map((e: any) => (
                  <tr key={e.employee_id}>
                    <td className="emp" title={e.job_title || ""}>
                      {e.name}
                      {e.exempt && (
                        <span title={e.exempt_reason || "معفى"} style={{
                          marginInlineStart: 6, fontSize: 10, background: "#e0ece8",
                          color: "#0b3b38", padding: "1px 6px", borderRadius: 4,
                          fontWeight: 600,
                        }}>معفى</span>
                      )}
                    </td>
                    {e.exempt ? (
                      <td className="cell muted" colSpan={data.days.length + 3}
                          style={{ textAlign: "center", fontSize: 12, color: "#6b7280" }}>
                        {e.exempt_reason || "معفى من الحضور — لا تسجيل يومي"}
                      </td>
                    ) : (
                      <>
                        {data.days.map((iso: string) => {
                          const st = e.cells[iso] || "off";
                          return (
                            <td key={iso} className="cell">
                              <span className={`att-dot ${st}`} title={`${iso} · ${attAr(st)}`}>{MARK[st]}</span>
                            </td>
                          );
                        })}
                        <td className="sum" style={{ color: "var(--success)" }}>{e.summary.present + e.summary.late}</td>
                        <td className="sum" style={{ color: "var(--danger)" }}>{e.summary.absent}</td>
                        <td className="sum" style={{ color: "var(--info)" }}>{e.summary.leave}</td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
    </div>
  );
}
