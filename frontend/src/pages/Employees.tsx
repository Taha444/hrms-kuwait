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
    catch (e: any) { setErr(e.response?.data?.detail || t("error")); }
  };

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2>{t("employees")}</h2>
        {can("create_employee") && <button onClick={() => setShowNew((s) => !s)}>{t("emp_new_btn")}</button>}
      </div>
      <div className="row" style={{ marginBottom: 12 }}>
        <input placeholder={t("emp_search_ph")} value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && go(0)} style={{ maxWidth: 280 }} />
        <button className="ghost" onClick={() => go(0)}>{t("search")}</button>
        <select value={branch} onChange={(e) => onBranch(e.target.value)} style={{ maxWidth: 180 }}>
          <option value="">{t("all_branches")}</option>
          {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
        <select value={dept} onChange={(e) => { setDept(e.target.value); setPage(0); load(0, branch, e.target.value); }} style={{ maxWidth: 180 }}>
          <option value="">{t("all_departments")}</option>
          {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        {can("manage_departments") && (
          <button className="ghost" onClick={async () => {
            const name = prompt(t("add_department_prompt"));
            if (!name) return;
            await api.post("/departments", null, { params: { name, branch_id: branch || undefined } });
            api.get("/departments").then((r) => setDepartments(r.data));
          }}>{t("add_department")}</button>
        )}
      </div>

      {showNew && (
        <div className="card">
          <div className="row">
            <div className="field" style={{ flex: 2 }}><label>{t("fld_name")}</label>
              <input onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
            <div className="field" style={{ flex: 1 }}><label>{t("fld_civil_id")}</label>
              <input onChange={(e) => setForm({ ...form, civil_id: e.target.value })} /></div>
            <div className="field" style={{ flex: 1 }}><label>{t("fld_basic_salary")}</label>
              <input type="number" onChange={(e) => setForm({ ...form, basic_salary: +e.target.value })} /></div>
          </div>
          <div className="row">
            <div className="field" style={{ flex: 1 }}><label>{t("fld_job_title")}</label>
              <input onChange={(e) => setForm({ ...form, job_title: e.target.value })} /></div>
            <div className="field" style={{ flex: 1 }}><label>{t("fld_hire_date")}</label>
              <input type="date" onChange={(e) => setForm({ ...form, hire_date: e.target.value })} /></div>
            <div className="field" style={{ flex: 1 }}><label>{t("fld_att_mode")}</label>
              <select onChange={(e) => setForm({ ...form, attendance_mode: e.target.value })}>
                <option value="none">{t("att_none")}</option><option value="qr">QR</option>
                <option value="gps">GPS</option><option value="both">{t("att_both")}</option>
              </select></div>
          </div>
          <div className="row">
            <div className="field" style={{ flex: 1 }}><label>{t("fld_branch")}</label>
              <select onChange={(e) => setForm({ ...form, branch_id: e.target.value ? +e.target.value : null })}>
                <option value="">{t("opt_choose")}</option>
                {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
              </select></div>
            <div className="field" style={{ flex: 1 }}><label>{t("fld_department")}</label>
              <select onChange={(e) => setForm({ ...form, department_id: e.target.value ? +e.target.value : null })}>
                <option value="">{t("opt_choose")}</option>
                {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select></div>
          </div>
          <div className="row">
            <div className="field" style={{ flex: 1 }}><label>{t("fld_nationality")}</label>
              <input onChange={(e) => setForm({ ...form, nationality: e.target.value })} /></div>
            <div className="field" style={{ flex: 1 }}><label>{t("fld_gender")}</label>
              <select onChange={(e) => setForm({ ...form, gender: e.target.value || null })}>
                <option value="">{t("opt_choose")}</option><option value="male">{t("gender_male")}</option><option value="female">{t("gender_female")}</option>
              </select></div>
            <div className="field" style={{ flex: 1 }}><label>{t("fld_dob")}</label>
              <input type="date" onChange={(e) => setForm({ ...form, date_of_birth: e.target.value || null })} /></div>
            <div className="field" style={{ flex: 1 }}><label>{t("fld_passport")}</label>
              <input onChange={(e) => setForm({ ...form, passport_number: e.target.value })} /></div>
          </div>
          {err && <div className="err">{err}</div>}
          <button onClick={create}>{t("save")}</button>
        </div>
      )}

      <div className="card">
        <table>
          <thead><tr><th>{t("col_name")}</th><th>{t("col_job")}</th><th>{t("col_nationality")}</th><th>{t("col_salary")}</th><th>{t("col_attendance")}</th><th></th></tr></thead>
          <tbody>
            {emps.map((e) => (
              <tr key={e.id}>
                <td>{e.name}</td><td>{e.job_title}</td><td>{e.nationality}</td>
                <td>{e.basic_salary} {t("kwd_currency")}</td>
                <td><span className="pill info">{e.attendance_mode}</span></td>
                <td><Link to={`/employees/${e.id}`}>{t("col_profile")}</Link></td>
              </tr>
            ))}
            {!emps.length && <tr><td colSpan={6} className="empty">{t("no_data")}</td></tr>}
          </tbody>
        </table>
      </div>

      {total > PAGE && (
        <div className="row" style={{ justifyContent: "center", gap: 14 }}>
          <button className="ghost" disabled={page === 0} onClick={() => go(page - 1)}>{t("page_prev")}</button>
          <span className="muted">{t("page_of", { p: page + 1, n: Math.ceil(total / PAGE) })} {t("emp_count_suffix", { n: total })}</span>
          <button className="ghost" disabled={(page + 1) * PAGE >= total} onClick={() => go(page + 1)}>{t("page_next")}</button>
        </div>
      )}
    </div>
  );
}
