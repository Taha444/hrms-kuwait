import { useEffect, useState } from "react";
import api from "../api";
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
  const [month, setMonth] = useState(thisMonth());
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const load = () => {
    setLoading(true);
    api.get("/attendance/review", { params: { month } })
      .then((r) => setData(r.data))
      .finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, [month]);

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
                    <td className="emp" title={e.job_title || ""}>{e.name}</td>
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
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
    </div>
  );
}
