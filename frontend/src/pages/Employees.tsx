import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import api from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import { fieldAr } from "../labels";
import EmployeeProfile from "./EmployeeProfile";
import EmployeeOnboarding from "./EmployeeOnboarding";

// تخطيط رئيسي-تفصيلي للموظفين: يسارًا قائمة وبحث، يمينًا تبويبات الملف أو نموذج إضافة (بلا نوافذ منبثقة).
export default function Employees() {
  const { t } = useI18n();
  const { can, user } = useAuth();
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
  const PAGE = 25;

  const load = (p = page, br = branch, dp = dept, query = q) => api.get("/employees", {
    params: { q: query || undefined, branch_id: br || undefined, department_id: dp || undefined, limit: PAGE, offset: p * PAGE },
  }).then((r) => { setEmps(r.data); setTotal(Number(r.headers["x-total-count"] || r.data.length)); });

  // SCR-Q — طابور تغييرات الحقول الحرجة. النقطة بُنيت ليجد المعتمِد ما
  // ينتظره **مجموًعا**: القائمة الوحيدة كانت داخل ملف الموظف، فمن يملك
  // القرار لا يجدها إلا بفتح الملفات واحًدا واحًدا. ثم بقيت النقطة بلا
  // طريق — فالبلاغ يقول إن هناك عمًلا ولا يقول أين هو.
  const [pendingChanges, setPendingChanges] = useState<any[]>([]);
  const isApprover = user?.role === "company_manager"
    || user?.role === "company_owner" || user?.role === "super_admin";
  const loadPending = () => {
    if (!isApprover) return;
    api.get("/employees/salary-change-requests/pending")
      .then((r) => setPendingChanges(r.data)).catch(() => setPendingChanges([]));
  };

  const decideChange = async (reqId: number, decision: "approved" | "rejected") => {
    let note: string | null = null;
    if (decision === "rejected") {
      note = window.prompt(t("scr_reject_reason"));
      if (!note || !note.trim()) return;
    }
    try {
      await api.post(`/employees/salary-change-requests/${reqId}/decide`, null,
                     { params: { decision, note: note?.trim() || undefined } });
      loadPending(); load();
    } catch (e: any) { alert(e?.response?.data?.detail || t("error")); }
  };

  useEffect(() => {
    api.get("/branches").then((r) => setBranches(r.data)).catch(() => {});
    api.get("/departments").then((r) => setDepartments(r.data)).catch(() => {});
    load(0);
    loadPending();
  }, []);

  const go = (p: number) => { setPage(p); load(p); };
  const onBranch = (b: string) => {
    setBranch(b); setPage(0);
    if (b) setParams({ branch: b }); else setParams({});
    load(0, b);
  };
  const select = (id: number) => { setMode("detail"); navigate(`/employees/${id}`); };
  const startNew = () => { setMode("new"); navigate("/employees"); };

  return (
    <div aria-labelledby="employees-title">
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 12 }}>
        <h2 id="employees-title" style={{ margin: 0 }}>{t("employees")}</h2>
        {can("create_employee") && <button onClick={startNew}>{t("emp_new_btn")}</button>}
      </div>

      {/* SCR-Q — ما ينتظر قرارك، مجموًعا. وبلا هذه الشاشة كان البلاغ يصل
          والمعتمِد يفتح الملفات واحًدا واحًدا بحًثا عمّا يخصّه. */}
      {isApprover && pendingChanges.length > 0 && (
        <div className="card" style={{ marginBottom: 12,
                                       borderInlineStart: "3px solid var(--warning)" }}>
          <h3 style={{ marginTop: 0 }}>{t("scr_title")} ({pendingChanges.length})</h3>
          <div className="sub" style={{ marginBottom: 8 }}>{t("scr_hint")}</div>
          <div className="table-wrap">
            <table>
              <thead><tr>
                <th>{t("col_employee")}</th><th>{t("scr_field")}</th>
                <th>{t("scr_change")}</th><th>{t("scr_by")}</th><th></th>
              </tr></thead>
              <tbody>
                {pendingChanges.map((c) => (
                  <tr key={c.id}>
                    <td><b>{c.employee_name}</b></td>
                    <td>{fieldAr(c.field_name)}</td>
                    <td dir="ltr" style={{ textAlign: "start" }}>
                      <span className="muted">{c.old_value || "—"}</span> → <b>{c.new_value}</b>
                      <div className="muted" style={{ fontSize: 11 }}>{c.effective_date}</div>
                    </td>
                    <td className="muted">{c.proposed_by_name}{c.reason && <div style={{ fontSize: 11 }}>{c.reason}</div>}</td>
                    <td>
                      <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
                        <button className="sm" onClick={() => decideChange(c.id, "approved")}>{t("scr_approve")}</button>
                        <button className="ghost sm" onClick={() => decideChange(c.id, "rejected")}>{t("scr_reject")}</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

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
                <span className="r-name">
                  {e.name}
                  {e.employee_no && (
                    <span style={{
                      marginInlineStart: 8, fontSize: 11, background: "#e0ece8",
                      color: "#0b3b38", padding: "1px 6px", borderRadius: 4,
                      fontFamily: "monospace", fontWeight: 500,
                    }}>{e.employee_no}</span>
                  )}
                </span>
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
            <EmployeeOnboarding
              branches={branches}
              departments={departments}
              onDone={async (emp) => {
                await load(0);
                select(emp.id);
              }}
              onCancel={() => setMode("detail")}
            />
          ) : (
            <EmployeeProfile id={selectedId ?? undefined} onChanged={() => load(page)} />
          )}
        </div>
      </div>
    </div>
  );
}
