import { useEffect, useState } from "react";
import api from "../api";
import { statusAr } from "../labels";

export default function Companies() {
  const [list, setList] = useState<any[]>([]);
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState<any>({ name: "", eos_day_divisor: 26, eos_max_months: 18, alert_lead_days: 30, annual_leave_days: 30 });
  const [err, setErr] = useState("");

  const load = () => api.get("/companies").then((r) => setList(r.data));
  useEffect(() => { load(); }, []);

  const create = async () => {
    setErr("");
    try { await api.post("/companies", form); setShowNew(false); load(); }
    catch (e: any) { setErr(e.response?.data?.detail || "خطأ"); }
  };
  const setStatus = async (id: number, status: string) => {
    await api.post(`/companies/${id}/status?status=${status}`); load();
  };

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2>الشركات</h2>
        <button onClick={() => setShowNew((s) => !s)}>+ شركة جديدة</button>
      </div>
      {showNew && (
        <div className="card">
          <div className="row">
            <div className="field" style={{ flex: 2 }}><label>الاسم</label>
              <input onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
            <div className="field" style={{ flex: 1 }}><label>السجل التجاري</label>
              <input onChange={(e) => setForm({ ...form, commercial_reg: e.target.value })} /></div>
            <div className="field" style={{ width: 120 }}><label>مقسوم EOS</label>
              <select value={form.eos_day_divisor} onChange={(e) => setForm({ ...form, eos_day_divisor: +e.target.value })}>
                <option value={26}>26</option><option value={30}>30</option></select></div>
          </div>
          {err && <div className="err">{err}</div>}
          <button onClick={create}>حفظ</button>
        </div>
      )}
      <div className="card">
        <table>
          <thead><tr><th>الاسم</th><th>السجل</th><th>مقسوم EOS</th><th>الحالة</th><th></th></tr></thead>
          <tbody>{list.map((c) => (
            <tr key={c.id}><td>{c.name}</td><td>{c.commercial_reg}</td><td>{c.eos_day_divisor}</td>
              <td><span className="pill info">{statusAr(c.status)}</span></td>
              <td className="row">
                <button className="ghost" onClick={() => setStatus(c.id, c.status === "active" ? "inactive" : "active")}>
                  {c.status === "active" ? "تعطيل" : "تفعيل"}</button>
                <button className="ghost" onClick={() => setStatus(c.id, "archived")}>أرشفة</button>
              </td></tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  );
}
