import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import Icon from "../Icon";

// هيكل الشركة: Company → Branches، كل فرع وحدة لها موظفوها وإحصائياتها.
export default function CompanyStructure() {
  const [data, setData] = useState<any>(null);
  const [stats, setStats] = useState<Record<number, any>>({});
  const [err, setErr] = useState("");

  useEffect(() => {
    api.get("/org/structure")
      .then((r) => {
        setData(r.data);
        r.data.branches.forEach((b: any) =>
          api.get(`/branches/${b.id}/stats`).then((s) =>
            setStats((prev) => ({ ...prev, [b.id]: s.data }))).catch(() => {}));
      })
      .catch((e) => setErr(e.response?.data?.detail || "تعذّر تحميل الهيكل (اختر شركة أولًا)"));
  }, []);

  if (err) return <div className="card empty">{err}</div>;
  if (!data) return <div className="empty">جارِ التحميل…</div>;

  const Mini = ({ icon, val, lbl }: any) => (
    <div style={{ textAlign: "center" }}>
      <div style={{ fontFamily: "var(--font-display)", fontSize: 22, fontWeight: 800, color: "var(--petrol-700)" }}>{val ?? "—"}</div>
      <div className="muted" style={{ fontSize: 11 }}>{lbl}</div>
    </div>
  );

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="eyebrow">الهيكل التنظيمي</div>
          <h2 style={{ margin: "2px 0 0" }}>{data.company.name}</h2>
          <div className="sub">{data.total_employees} موظف · {data.branches.length} فرع
            {data.unassigned_employees ? ` · ${data.unassigned_employees} بلا فرع` : ""}</div>
        </div>
        <Link to="/employees"><button className="ghost">عرض كل الموظفين (كل الفروع)</button></Link>
      </div>

      <div className="grid cards">
        {data.branches.map((b: any) => {
          const s = stats[b.id] || {};
          return (
            <div className="card" key={b.id} style={{ borderTop: "3px solid var(--petrol-600)" }}>
              <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
                <div>
                  <h3 style={{ margin: 0 }}><Icon name="branches" size={16} /> {b.name}</h3>
                  <div className="muted" style={{ fontSize: 12 }}>{b.address || "—"}</div>
                </div>
                <span className="pill neutral">{b.employee_count} موظف</span>
              </div>
              {b.supervisors?.length > 0 && (
                <div className="muted" style={{ fontSize: 12, margin: "6px 0" }}>
                  مسؤول الفرع: {b.supervisors.join("، ")}
                </div>
              )}
              <div className="row" style={{ justifyContent: "space-around", margin: "12px 0", padding: "10px 0",
                borderTop: "1px solid var(--line)", borderBottom: "1px solid var(--line)" }}>
                <Mini val={s.present_today} lbl="حضور اليوم" />
                <Mini val={s.on_leave} lbl="في إجازة" />
                <Mini val={s.expiring_permits} lbl="إقامات تنتهي" />
              </div>
              <div className="row">
                <Link to={`/employees?branch=${b.id}`}><button className="sm">عرض موظفي الفرع</button></Link>
                <Link to={`/branch-qr-screen?branch=${b.id}`} style={{ display: "none" }} />
              </div>
            </div>
          );
        })}
        {!data.branches.length && <div className="card empty">لا توجد فروع لهذه الشركة بعد.</div>}
      </div>
    </div>
  );
}
