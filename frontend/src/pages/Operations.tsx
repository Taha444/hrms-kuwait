import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import Icon from "../Icon";

// مركز العمليات والامتثال: كل ما يحتاج متابعة (إقامات/تراخيص قرب الانتهاء، طلبات، مهام).
const U_PILL: Record<string, string> = { expired: "critical", critical: "critical", warning: "warning", ok: "success" };
const KIND_AR: Record<string, string> = { residency: "إقامة", work_permit: "إذن عمل" };
const days = (d: number) => (d < 0 ? `منتهية منذ ${-d} يوم` : `${d} يوم`);

export default function Operations() {
  const [branches, setBranches] = useState<any[]>([]);
  const [branch, setBranch] = useState("");
  const [data, setData] = useState<any>(null);

  const load = (b = branch) => api.get("/operations", { params: { branch_id: b || undefined } }).then((r) => setData(r.data));
  useEffect(() => { api.get("/branches").then((r) => setBranches(r.data)).catch(() => {}); load(); }, []);
  if (!data) return <div className="empty">جارِ التحميل…</div>;

  const c = data.compliance;
  const Risk = ({ n, lbl, color }: any) => (
    <div className="stat" style={{ borderTop: `3px solid ${color}` }}>
      <div className="num" style={{ color }}>{n}</div><div className="lbl">{lbl}</div>
    </div>
  );

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="eyebrow">المتابعة والامتثال</div>
          <h2 style={{ margin: "2px 0 0" }}>مركز العمليات</h2>
          <div className="sub">كل ما يحتاج إجراءً في مكان واحد — إقامات وتراخيص وطلبات ومهام</div>
        </div>
        <select value={branch} onChange={(e) => { setBranch(e.target.value); load(e.target.value); }} style={{ maxWidth: 200 }}>
          <option value="">كل الفروع</option>
          {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
      </div>

      <div className="grid stats">
        <Risk n={c.expired} lbl="منتهية (مخالفة)" color="var(--danger)" />
        <Risk n={c.critical} lbl="حرجة (≤30 يوم)" color="var(--warning)" />
        <Risk n={c.warning} lbl="تحذير (≤90 يوم)" color="var(--info)" />
        <Link to="/requests" className="stat" style={{ textDecoration: "none" }}>
          <div className="num">{data.pending_requests}</div><div className="lbl">طلبات بانتظار الاعتماد</div>
        </Link>
        <Link to="/tasks" className="stat" style={{ textDecoration: "none" }}>
          <div className="num">{data.open_gov_tasks}</div><div className="lbl">مهام حكومية مفتوحة</div>
        </Link>
      </div>

      <div className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h3 style={{ margin: 0 }}>الإقامات وأذونات العمل القريبة من الانتهاء</h3>
          <Link to="/pro"><button className="ghost sm">إدارة المعاملات ←</button></Link>
        </div>
        <table style={{ marginTop: 10 }}>
          <thead><tr><th>النوع</th><th>الموظف</th><th>الرقم</th><th>الانتهاء</th><th>المتبقّي</th></tr></thead>
          <tbody>
            {data.permits.map((p: any) => (
              <tr key={p.id}>
                <td>{KIND_AR[p.type] || p.type}</td><td>{p.employee}</td>
                <td className="muted">{p.number}</td><td>{p.expiry_date}</td>
                <td><span className={`pill ${U_PILL[p.urgency]}`}>{days(p.days_left)}</span></td>
              </tr>
            ))}
            {!data.permits.length && <tr><td colSpan={5} className="empty">لا يوجد ✓</td></tr>}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>التراخيص القريبة من الانتهاء</h3>
        <table>
          <thead><tr><th>الترخيص</th><th>الرقم</th><th>الانتهاء</th><th>المتبقّي</th></tr></thead>
          <tbody>
            {data.licenses.map((l: any) => (
              <tr key={l.id}>
                <td><b>{l.name}</b></td><td className="muted">{l.license_no}</td>
                <td>{l.expiry_date}</td>
                <td><span className={`pill ${U_PILL[l.urgency]}`}>{days(l.days_left)}</span></td>
              </tr>
            ))}
            {!data.licenses.length && <tr><td colSpan={4} className="empty">لا يوجد ✓</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
