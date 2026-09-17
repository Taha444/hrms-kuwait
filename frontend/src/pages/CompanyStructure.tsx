import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { errMsg } from "../api";
import { useI18n } from "../i18n";
import { useAuth } from "../auth";
import Icon from "../Icon";

// هيكل الشركة: Company → Branches، كل فرع وحدة لها موظفوها وإحصائياتها.
export default function CompanyStructure() {
  const { t } = useI18n();
  const { can } = useAuth();
  const [data, setData] = useState<any>(null);
  const [stats, setStats] = useState<Record<number, any>>({});
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  // الأقساُم تُقرأ في شاشة الموظف ولا شاشَة تُنشئها — ``POST /departments``
  // مبنيٌّة بلا باب. وهذه هي، خلف صلاحيتها كما يفرضها الخادم.
  const [depts, setDepts] = useState<any[]>([]);
  const [dept, setDept] = useState({ name: "", branch_id: "" });
  const [busy, setBusy] = useState(false);
  const loadDepts = () => api.get("/departments").then((r) => setDepts(r.data))
    .catch(() => setDepts([]));
  const addDept = async () => {
    if (!dept.name.trim()) return;
    setBusy(true); setErr(""); setMsg("");
    try {
      const params: any = { name: dept.name.trim() };
      if (dept.branch_id) params.branch_id = Number(dept.branch_id);
      await api.post("/departments", null, { params });
      setDept({ name: "", branch_id: "" });
      setMsg(t("cs_dept_added"));
      loadDepts();
    } catch (e: any) { setErr(errMsg(e, t("error"))); }
    finally { setBusy(false); }
  };

  useEffect(() => { loadDepts(); }, []);

  useEffect(() => {
    api.get("/org/structure")
      .then((r) => {
        setData(r.data);
        r.data.branches.forEach((b: any) =>
          api.get(`/branches/${b.id}/stats`).then((s) =>
            setStats((prev) => ({ ...prev, [b.id]: s.data }))).catch(() => {}));
      })
      .catch((e) => setErr(errMsg(e, t("cs_load_failed"))));
  }, []);

  if (err) return <div className="card empty">{err}</div>;
  if (!data) return <div className="empty">{t("loading_dots")}</div>;

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
          <div className="eyebrow">{t("structure")}</div>
          <h2 style={{ margin: "2px 0 0" }}>{data.company.name}</h2>
          <div className="sub">{data.total_employees} · {data.branches.length} {t("branch_name")}</div>
        </div>
        <Link to="/employees"><button className="ghost">{t("view_all_emps")}</button></Link>
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
                <span className="pill neutral">{b.employee_count}</span>
              </div>
              {b.supervisors?.length > 0 ? (
                <div className="muted" style={{ fontSize: 12, margin: "6px 0" }}>
                  {t("supervisor")}: {b.supervisors.join(t("list_sep"))}
                </div>
              ) : (
                // BR-27 — الغياب يُعرَض كما يُعرَض الوجود. كان السطر يُخفى عند
                // الفراغ، فيستوي على الشاشة الفرعُ المُسنَد وغير المُسنَد —
                // ولا يُكتشف النقص إلا حين يقف طلب عند مرحلة بلا معتمِد.
                <div style={{ fontSize: 12, margin: "6px 0", color: "var(--danger)" }}>
                  {t("supervisor")}: {t("no_supervisor")}
                  {can("manage_users") && (
                    <> — <Link to="/users">{t("assign_supervisor")}</Link></>
                  )}
                </div>
              )}
              <div className="row" style={{ justifyContent: "space-around", margin: "12px 0", padding: "10px 0",
                borderTop: "1px solid var(--line)", borderBottom: "1px solid var(--line)" }}>
                <Mini val={s.present_today} lbl={t("present_today")} />
                <Mini val={s.on_leave} lbl={t("on_leave_now")} />
                {can("manage_permits") && <Mini val={s.expiring_permits} lbl={t("expiring_now")} />}
              </div>
              <div className="row">
                <Link to={`/employees?branch=${b.id}`}><button className="sm">{t("view_branch_emps")}</button></Link>
              </div>
            </div>
          );
        })}
        {!data.branches.length && <div className="card empty">{t("no_data")}</div>}
      </div>

      {/* الأقسام — تُعرض للجميع، وتُنشأ بصلاحية إدارتها. */}
      <div className="card" style={{ marginTop: 12 }}>
        <h3 style={{ marginTop: 0 }}>{t("cs_depts")} ({depts.length})</h3>
        {msg && <div className="ok">{msg}</div>}
        {depts.length === 0 ? (
          <div className="muted">{t("cs_dept_none")}</div>
        ) : (
          <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
            {depts.map((d: any) => (
              <span key={d.id} className="pill neutral">
                {d.name}
                <span className="muted" style={{ marginInlineStart: 6, fontSize: 11 }}>
                  {t("cs_dept_count", { n: d.employee_count })}
                </span>
              </span>
            ))}
          </div>
        )}
        {can("manage_departments") && (
          <div className="row" style={{ gap: 8, marginTop: 10, alignItems: "flex-end", flexWrap: "wrap" }}>
            <div className="field">
              <label htmlFor="cs-dept-name">{t("cs_dept_name")}</label>
              <input id="cs-dept-name" value={dept.name}
                     onChange={(e) => setDept({ ...dept, name: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="cs-dept-branch">{t("cs_dept_branch")}</label>
              <select id="cs-dept-branch" value={dept.branch_id}
                      onChange={(e) => setDept({ ...dept, branch_id: e.target.value })}>
                <option value="">{t("cs_dept_all")}</option>
                {data.branches.map((b: any) => (
                  <option key={b.id} value={b.id}>{b.name}</option>
                ))}
              </select>
            </div>
            <button disabled={busy || !dept.name.trim()} onClick={addDept}>{t("cs_dept_add")}</button>
          </div>
        )}
      </div>
    </div>
  );
}
