import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import api from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";

export default function Employees() {
  const { t } = useI18n();
  const { can } = useAuth();
  const [params, setParams] = useSearchParams();
  const [emps, setEmps] = useState<any[]>([]);
  const [branches, setBranches] = useState<any[]>([]);
  const [departments, setDepartments] = useState<any[]>([]);
  const [branch, setBranch] = useState<string>(params.get("branch") || "");
  const [dept, setDept] = useState<string>("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState<any>({ name: "", attendance_mode: "none", contract_type: "indefinite", basic_salary: 0 });
  const [err, setErr] = useState("");
  const PAGE = 25;

  const load = (p = page, br = branch, dp = dept) => api.get("/employees", {
    params: { q: q || undefined, branch_id: br || undefined, department_id: dp || undefined, limit: PAGE, offset: p * PAGE },
  }).then((r) => { setEmps(r.data); setTotal(Number(r.headers["x-total-count"] || r.data.length)); });

  useEffect(() => {
    api.get("/branches").then((r) => setBranches(r.data)).catch(() => {});
    api.get("/departments").then((r) => setDepartments(r.data)).catch(() => {});
  }, []);
  useEffect(() => { load(0); setPage(0); }, []);
  const go = (p: number) => { setPage(p); load(p); };
  const onBranch = (b: string) => {
    setBranch(b); setPage(0);
    if (b) setParams({ branch: b }); else setParams({});
    load(0, b);
  };

  const create = async () => {
    setErr("");
    // الإدارة العليا/المالك: أرفق الشركة المختارة حاليًا
    const active = localStorage.getItem("active_company_id");
    const payload = active && active !== "all" ? { ...form, company_id: Number(active) } : form;
    try { await api.post("/employees", payload); setShowNew(false); load(); }
    catch (e: any) { setErr(e.response?.data?.detail || "خطأ"); }
  };

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2>{t("employees")}</h2>
        {can("create_employee") && <button onClick={() => setShowNew((s) => !s)}>+ موظف جديد</button>}
      </div>
      <div className="row" style={{ marginBottom: 12 }}>
        <input placeholder="بحث: الاسم / الرقم المدني / رقم الموظف / رقم الإقامة" value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && go(0)} style={{ maxWidth: 280 }} />
        <button className="ghost" onClick={() => go(0)}>بحث</button>
        <select value={branch} onChange={(e) => onBranch(e.target.value)} style={{ maxWidth: 180 }}>
          <option value="">كل الفروع</option>
          {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
        <select value={dept} onChange={(e) => { setDept(e.target.value); setPage(0); load(0, branch, e.target.value); }} style={{ maxWidth: 180 }}>
          <option value="">كل الإدارات</option>
          {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        {can("manage_departments") && (
          <button className="ghost" onClick={async () => {
            const name = prompt("اسم الإدارة/القسم الجديد:");
            if (!name) return;
            await api.post("/departments", null, { params: { name, branch_id: branch || undefined } });
            api.get("/departments").then((r) => setDepartments(r.data));
          }}>+ إدارة</button>
        )}
      </div>

      {showNew && (
        <div className="card">
          <div className="row">
            <div className="field" style={{ flex: 2 }}><label>الاسم</label>
              <input onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
            <div className="field" style={{ flex: 1 }}><label>الرقم المدني</label>
              <input onChange={(e) => setForm({ ...form, civil_id: e.target.value })} /></div>
            <div className="field" style={{ flex: 1 }}><label>الراتب الأساسي</label>
              <input type="number" onChange={(e) => setForm({ ...form, basic_salary: +e.target.value })} /></div>
          </div>
          <div className="row">
            <div className="field" style={{ flex: 1 }}><label>المسمى الوظيفي</label>
              <input onChange={(e) => setForm({ ...form, job_title: e.target.value })} /></div>
            <div className="field" style={{ flex: 1 }}><label>تاريخ التعيين</label>
              <input type="date" onChange={(e) => setForm({ ...form, hire_date: e.target.value })} /></div>
            <div className="field" style={{ flex: 1 }}><label>نمط الحضور</label>
              <select onChange={(e) => setForm({ ...form, attendance_mode: e.target.value })}>
                <option value="none">بدون</option><option value="qr">QR</option>
                <option value="gps">GPS</option><option value="both">كلاهما</option>
              </select></div>
          </div>
          <div className="row">
            <div className="field" style={{ flex: 1 }}><label>الفرع</label>
              <select onChange={(e) => setForm({ ...form, branch_id: e.target.value ? +e.target.value : null })}>
                <option value="">— اختر —</option>
                {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
              </select></div>
            <div className="field" style={{ flex: 1 }}><label>الإدارة/القسم</label>
              <select onChange={(e) => setForm({ ...form, department_id: e.target.value ? +e.target.value : null })}>
                <option value="">— اختر —</option>
                {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select></div>
          </div>
          <div className="row">
            <div className="field" style={{ flex: 1 }}><label>الجنسية</label>
              <input onChange={(e) => setForm({ ...form, nationality: e.target.value })} /></div>
            <div className="field" style={{ flex: 1 }}><label>الجنس</label>
              <select onChange={(e) => setForm({ ...form, gender: e.target.value || null })}>
                <option value="">— اختر —</option><option value="male">ذكر</option><option value="female">أنثى</option>
              </select></div>
            <div className="field" style={{ flex: 1 }}><label>تاريخ الميلاد</label>
              <input type="date" onChange={(e) => setForm({ ...form, date_of_birth: e.target.value || null })} /></div>
            <div className="field" style={{ flex: 1 }}><label>رقم الجواز</label>
              <input onChange={(e) => setForm({ ...form, passport_number: e.target.value })} /></div>
          </div>
          {err && <div className="err">{err}</div>}
          <button onClick={create}>{t("save")}</button>
        </div>
      )}

      <div className="card">
        <table>
          <thead><tr><th>الاسم</th><th>المسمى</th><th>الجنسية</th><th>الراتب</th><th>الحضور</th><th></th></tr></thead>
          <tbody>
            {emps.map((e) => (
              <tr key={e.id}>
                <td>{e.name}</td><td>{e.job_title}</td><td>{e.nationality}</td>
                <td>{e.basic_salary} د.ك</td>
                <td><span className="pill info">{e.attendance_mode}</span></td>
                <td><Link to={`/employees/${e.id}`}>الملف</Link></td>
              </tr>
            ))}
            {!emps.length && <tr><td colSpan={6} className="empty">{t("no_data")}</td></tr>}
          </tbody>
        </table>
      </div>

      {total > PAGE && (
        <div className="row" style={{ justifyContent: "center", gap: 14 }}>
          <button className="ghost" disabled={page === 0} onClick={() => go(page - 1)}>السابق</button>
          <span className="muted">صفحة {page + 1} من {Math.ceil(total / PAGE)} · {total} موظف</span>
          <button className="ghost" disabled={(page + 1) * PAGE >= total} onClick={() => go(page + 1)}>التالي</button>
        </div>
      )}
    </div>
  );
}
