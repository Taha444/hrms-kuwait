import { useEffect, useState } from "react";
import api from "../api";

// مراجعة الحضور الشهري (للسوبر أدمن/المالك/مدير الشركة): مصفوفة موظف × يوم.
const WD = ["ح", "ن", "ث", "ر", "خ", "ج", "س"]; // الأحد..السبت
const STATUS_AR: Record<string, string> = {
  present: "حاضر", late: "متأخر", absent: "غائب", leave: "إجازة", off: "عطلة", future: "—",
};
const MARK: Record<string, string> = { present: "✓", late: "!", absent: "✗", leave: "إ", off: "", future: "" };

function thisMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export default function AttendanceReview() {
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

  const dayMeta = (iso: string) => {
    const d = new Date(iso + "T00:00:00");
    // getDay(): الأحد=0 .. السبت=6 — يطابق ترتيب WD
    const code = WD[d.getDay()];
    const weekend = d.getDay() === 5 || d.getDay() === 6; // الجمعة/السبت
    return { num: d.getDate(), code, weekend };
  };

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="eyebrow">الحضور والانصراف</div>
          <h2 style={{ margin: "2px 0 0" }}>مراجعة حضور الموظفين</h2>
          <div className="sub">سجل يومي لكل موظف خلال الشهر — حاضر / متأخر / غائب / إجازة</div>
        </div>
        <div className="row">
          <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} style={{ width: 170 }} />
          <button className="ghost" onClick={load}>تحديث</button>
        </div>
      </div>

      <div className="att-legend">
        <span className="lg"><span className="sw" style={{ background: "var(--success-bg)" }} /> حاضر</span>
        <span className="lg"><span className="sw" style={{ background: "var(--warning-bg)" }} /> متأخر</span>
        <span className="lg"><span className="sw" style={{ background: "var(--danger-bg)" }} /> غائب</span>
        <span className="lg"><span className="sw" style={{ background: "var(--info-bg)" }} /> إجازة</span>
        <span className="lg"><span className="sw" style={{ background: "#f1f4f3" }} /> عطلة</span>
      </div>

      {loading ? <div className="empty">جارِ التحميل…</div>
        : !data?.employees?.length ? <div className="card empty">لا يوجد موظفون مفعّل لهم الحضور في هذه الشركة.</div>
        : (
          <div className="att-wrap">
            <table className="att-matrix">
              <thead>
                <tr>
                  <th className="emp">الموظف ({data.total_employees})</th>
                  {data.days.map((iso: string) => {
                    const m = dayMeta(iso);
                    return <th key={iso} className={`day ${m.weekend ? "we" : ""}`}>{m.num}<small>{m.code}</small></th>;
                  })}
                  <th className="day" style={{ minWidth: 44 }}>حاضر</th>
                  <th className="day" style={{ minWidth: 44 }}>غياب</th>
                  <th className="day" style={{ minWidth: 44 }}>إجازة</th>
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
                          <span className={`att-dot ${st}`} title={`${iso} · ${STATUS_AR[st]}`}>{MARK[st]}</span>
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
