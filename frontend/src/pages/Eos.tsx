import { useEffect, useState } from "react";
import api from "../api";

export default function Eos() {
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [form, setForm] = useState<any>({
    basic_salary: 500, hire_date: "2018-01-01", end_date: "2024-01-01",
    reason: "termination", contract_type: "indefinite", unused_leave_days: 0, day_divisor: 26,
  });
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState("");

  useEffect(() => { api.get("/eos/reasons").then((r) => setReasons(r.data)); }, []);

  const calc = async () => {
    setErr("");
    try { const r = await api.post("/eos/calculate", form); setRes(r.data); }
    catch (e: any) { setErr(e.response?.data?.detail || "خطأ"); }
  };

  return (
    <div>
      <h2>مكافأة نهاية الخدمة (قانون العمل الكويتي 6/2010)</h2>
      <div className="card">
        <div className="row">
          <div className="field" style={{ flex: 1 }}><label>الراتب الأساسي (د.ك)</label>
            <input type="number" value={form.basic_salary}
              onChange={(e) => setForm({ ...form, basic_salary: +e.target.value })} /></div>
          <div className="field" style={{ flex: 1 }}><label>تاريخ التعيين</label>
            <input type="date" value={form.hire_date}
              onChange={(e) => setForm({ ...form, hire_date: e.target.value })} /></div>
          <div className="field" style={{ flex: 1 }}><label>تاريخ الانتهاء</label>
            <input type="date" value={form.end_date}
              onChange={(e) => setForm({ ...form, end_date: e.target.value })} /></div>
        </div>
        <div className="row">
          <div className="field" style={{ flex: 1 }}><label>سبب الانتهاء</label>
            <select value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })}>
              {Object.entries(reasons).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select></div>
          <div className="field" style={{ flex: 1 }}><label>نوع العقد</label>
            <select value={form.contract_type} onChange={(e) => setForm({ ...form, contract_type: e.target.value })}>
              <option value="indefinite">غير محدد المدة</option><option value="definite">محدد المدة</option>
            </select></div>
          <div className="field" style={{ flex: 1 }}><label>رصيد إجازات غير مستخدم</label>
            <input type="number" value={form.unused_leave_days}
              onChange={(e) => setForm({ ...form, unused_leave_days: +e.target.value })} /></div>
          <div className="field" style={{ width: 100 }}><label>المقسوم</label>
            <select value={form.day_divisor} onChange={(e) => setForm({ ...form, day_divisor: +e.target.value })}>
              <option value={26}>26</option><option value={30}>30</option></select></div>
        </div>
        {err && <div className="err">{err}</div>}
        <button onClick={calc}>احسب</button>
      </div>

      {res && (
        <div className="card">
          <h3>النتيجة التفصيلية</h3>
          <div className="grid">
            <div className="stat card"><div className="num">{res.total_settlement}</div><div className="lbl">إجمالي التسوية (د.ك)</div></div>
            <div className="stat card"><div className="num">{res.indemnity}</div><div className="lbl">المكافأة</div></div>
            <div className="stat card"><div className="num">{res.leave_payout}</div><div className="lbl">بدل الإجازات</div></div>
            <div className="stat card"><div className="num">{res.daily_wage}</div><div className="lbl">أجر اليوم</div></div>
          </div>
          <p><b>مدة الخدمة:</b> {res.service.text} ({res.service.decimal_years} سنة)</p>
          <p><b>نسبة الاستحقاق:</b> {(res.entitlement_factor * 100).toFixed(2)}% — {res.factor_note}</p>
          {res.cap_applied && <p className="err">⚠ طُبّق الحد الأقصى (18 شهرًا).</p>}
          <p className="muted">{res.disclaimer}</p>
        </div>
      )}
    </div>
  );
}
