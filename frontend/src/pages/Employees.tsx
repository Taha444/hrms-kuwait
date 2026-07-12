import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import api, { errMsg } from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import EmployeeProfile from "./EmployeeProfile";

// تخطيط رئيسي-تفصيلي للموظفين: يسارًا قائمة وبحث، يمينًا تبويبات الملف أو نموذج إضافة (بلا نوافذ منبثقة).
export default function Employees() {
  const { t } = useI18n();
  const { can } = useAuth();
  const navigate = useNavigate();
  const routeParams = useParams();
  const selectedId = routeParams.id ? Number(routeParams.id) : null;
  const [params, setParams] = useSearchParams();
  const [emps, setEmps] = useState<any[]>([]);
  const [branches, setBranches] = useState<any[]>([]);
  const [departments, setDepartments] = useState<any[]>([]);
  const [branch, setBranch] = useState<string>(params.get("branch") || "");
  const [dept, setDept] = useState<string>("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);
  const [mode, setMode] = useState<"detail" | "new">("detail");
  const [form, setForm] = useState<any>({ name: "", attendance_mode: "none", contract_type: "indefinite", basic_salary: 0 });
  const [err, setErr] = useState("");
  const PAGE = 25;

  const load = (p = page, br = branch, dp = dept, query = q) => api.get("/employees", {
    params: { q: query || undefined, branch_id: br || undefined, department_id: dp || undefined, limit: PAGE, offset: p * PAGE },
  }).then((r) => { setEmps(r.data); setTotal(Number(r.headers["x-total-count"] || r.data.length)); });

  useEffect(() => {
    api.get("/branches").then((r) => setBranches(r.data)).catch(() => {});
    api.get("/departments").then((r) => setDepartments(r.data)).catch(() => {});
    load(0);
  }, []);

  const go = (p: number) => { setPage(p); load(p); };
  const onBranch = (b: string) => {
    setBranch(b); setPage(0);
    if (b) setParams({ branch: b }); else setParams({});
    load(0, b);
  };
  const select = (id: number) => { setMode("detail"); navigate(`/employees/${id}`); };
  const startNew = () => { setMode("new"); setErr(""); navigate("/employees"); };

  const create = async () => {
    setErr("");
    // منع حفظ موظف بلا هوية/راتب (QA-P1-EMP-01)
    if (!form.name?.trim() || !form.civil_id?.trim() || !form.basic_salary || +form.basic_salary <= 0) {
      setErr(`${t("req_missing_fields")}: ${t("fld_name")}، ${t("fld_civil_id")}، ${t("fld_official_salary")}`);
      return;
    }
    const active = localStorage.getItem("active_company_id");
    const payload = active && active !== "all" ? { ...form, company_id: Number(active) } : form;
    try {
      const r = await api.post("/employees", payload);
      setForm({ name: "", attendance_mode: "none", contract_type: "indefinite", basic_salary: 0 });
      await load(0);
      select(r.data.id);  // افتح ملف الموظف الجديد مباشرةً
    } catch (e: any) { setErr(errMsg(e, t("error"))); }
  };

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>{t("employees")}</h2>
        {can("create_employee") && <button onClick={startNew}>{t("emp_new_btn")}</button>}
      </div>

      <div className="md-layout">
        {/* ============ القائمة (Master) ============ */}
        <div className="md-list">
          <div className="md-filters">
            <input aria-label={t("emp_search_ph")} placeholder={t("emp_search_ph")} value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && (setPage(0), load(0, branch, dept, q))} />
            <div className="row">
              <select aria-label={t("all_branches")} value={branch} onChange={(e) => onBranch(e.target.value)} style={{ flex: 1 }}>
                <option value="">{t("all_branches")}</option>
                {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
              </select>
              <select aria-label={t("all_departments")} value={dept} onChange={(e) => { setDept(e.target.value); setPage(0); load(0, branch, e.target.value); }} style={{ flex: 1 }}>
                <option value="">{t("all_departments")}</option>
                {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </div>
            <div className="muted" style={{ fontSize: 12 }}>{t("emp_search_results", { n: total })}</div>
          </div>
          <div className="md-rows">
            {emps.map((e) => (
              <button key={e.id} className={`md-row ${selectedId === e.id ? "active" : ""}`} onClick={() => select(e.id)}>
                <span className="r-name">{e.name}</span>
                <span className="r-sub">{e.job_title || "—"} · {e.nationality || "—"}</span>
              </button>
            ))}
            {!emps.length && <div className="md-row muted">{t("no_data")}</div>}
          </div>
          {total > PAGE && (
            <div className="row" style={{ justifyContent: "center", gap: 12, padding: 10 }}>
              <button className="ghost sm" disabled={page === 0} onClick={() => go(page - 1)}>{t("page_prev")}</button>
              <span className="muted" style={{ fontSize: 12 }}>{t("page_of", { p: page + 1, n: Math.ceil(total / PAGE) })}</span>
              <button className="ghost sm" disabled={(page + 1) * PAGE >= total} onClick={() => go(page + 1)}>{t("page_next")}</button>
            </div>
          )}
        </div>

        {/* ============ التفصيل (Detail) ============ */}
        <div className="md-detail">
          {mode === "new" ? (
            <div className="card">
              <h3>{t("emp_new_title")}</h3>
              <div className="row">
                <div className="field" style={{ flex: 2 }}><label htmlFor="emp-name">{t("fld_name")} *</label>
                  <input id="emp-name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
                <div className="field" style={{ flex: 1 }}><label htmlFor="emp-civil-id">{t("fld_civil_id")} *</label>
                  <input id="emp-civil-id" required value={form.civil_id || ""} onChange={(e) => setForm({ ...form, civil_id: e.target.value })} /></div>
                <div className="field" style={{ flex: 1 }}><label htmlFor="emp-basic-salary">{t("fld_official_salary")} *</label>
                  <input id="emp-basic-salary" type="number" required min={0.001} step="0.001" value={form.basic_salary || ""}
                    onChange={(e) => setForm({ ...form, basic_salary: e.target.value ? +e.target.value : 0 })} /></div>
              </div>
              <div className="row">
                <div className="field" style={{ flex: 1 }}><label htmlFor="emp-job-title">{t("fld_job_title")}</label>
                  <input id="emp-job-title" onChange={(e) => setForm({ ...form, job_title: e.target.value })} /></div>
                <div className="field" style={{ flex: 1 }}><label htmlFor="emp-hire-date">{t("fld_hire_date")}</label>
                  <input id="emp-hire-date" type="date" onChange={(e) => setForm({ ...form, hire_date: e.target.value })} /></div>
                <div className="field" style={{ flex: 1 }}><label htmlFor="emp-att-mode">{t("fld_att_mode")}</label>
                  <select id="emp-att-mode" onChange={(e) => setForm({ ...form, attendance_mode: e.target.value })}>
                    <option value="none">{t("att_none")}</option><option value="qr">QR</option>
                    <option value="gps">GPS</option><option value="both">{t("att_both")}</option>
                  </select></div>
              </div>
              <div className="row">
                <div className="field" style={{ flex: 1 }}><label htmlFor="emp-branch">{t("fld_official_branch")}</label>
                  <select id="emp-branch" onChange={(e) => setForm({ ...form, branch_id: e.target.value ? +e.target.value : null })}>
                    <option value="">{t("opt_choose")}</option>
                    {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                  </select></div>
                <div className="field" style={{ flex: 1 }}><label htmlFor="emp-actual-branch">{t("fld_actual_branch")}</label>
                  <select id="emp-actual-branch" onChange={(e) => setForm({ ...form, actual_branch_id: e.target.value ? +e.target.value : null })}>
                    <option value="">{t("opt_choose")}</option>
                    {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                  </select></div>
                <div className="field" style={{ flex: 1 }}><label htmlFor="emp-department">{t("fld_department")}</label>
                  <select id="emp-department" onChange={(e) => setForm({ ...form, department_id: e.target.value ? +e.target.value : null })}>
                    <option value="">{t("opt_choose")}</option>
                    {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
                  </select></div>
              </div>
              <div className="row">
                <div className="field" style={{ flex: 1 }}><label htmlFor="emp-nationality">{t("fld_nationality")}</label>
                  <input id="emp-nationality" onChange={(e) => setForm({ ...form, nationality: e.target.value })} /></div>
                <div className="field" style={{ flex: 1 }}><label htmlFor="emp-gender">{t("fld_gender")}</label>
                  <select id="emp-gender" onChange={(e) => setForm({ ...form, gender: e.target.value || null })}>
                    <option value="">{t("opt_choose")}</option><option value="male">{t("gender_male")}</option><option value="female">{t("gender_female")}</option>
                  </select></div>
                <div className="field" style={{ flex: 1 }}><label htmlFor="emp-dob">{t("fld_dob")}</label>
                  <input id="emp-dob" type="date" onChange={(e) => setForm({ ...form, date_of_birth: e.target.value || null })} /></div>
                <div className="field" style={{ flex: 1 }}><label htmlFor="emp-passport">{t("fld_passport")}</label>
                  <input id="emp-passport" onChange={(e) => setForm({ ...form, passport_number: e.target.value })} /></div>
              </div>
              {err && <div className="err">{err}</div>}
              <div className="row">
                <button onClick={create}>{t("save")}</button>
                <button className="ghost" onClick={() => setMode("detail")}>{t("cancel")}</button>
              </div>
            </div>
          ) : (
            <EmployeeProfile id={selectedId ?? undefined} onChanged={() => load(page)} />
          )}
        </div>
      </div>
    </div>
  );
}
