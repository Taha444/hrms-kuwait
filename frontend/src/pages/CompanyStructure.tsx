import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import { useI18n } from "../i18n";
import Icon from "../Icon";

// هيكل الشركة: Company → Branches، كل فرع وحدة لها موظفوها وإحصائياتها.
export default function CompanyStructure() {
  const { t } = useI18n();
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
              {b.supervisors?.length > 0 && (
                <div className="muted" style={{ fontSize: 12, margin: "6px 0" }}>
                  {t("supervisor")}: {b.supervisors.join("، ")}
                </div>
              )}
              <div className="row" style={{ justifyContent: "space-around", margin: "12px 0", padding: "10px 0",
                borderTop: "1px solid var(--line)", borderBottom: "1px solid var(--line)" }}>
                <Mini val={s.present_today} lbl={t("present_today")} />
                <Mini val={s.on_leave} lbl={t("on_leave_now")} />
                <Mini val={s.expiring_permits} lbl={t("expiring_now")} />
              </div>
              <div className="row">
                <Link to={`/employees?branch=${b.id}`}><button className="sm">{t("view_branch_emps")}</button></Link>
              </div>
            </div>
          );
        })}
        {!data.branches.length && <div className="card empty">{t("no_data")}</div>}
      </div>
    </div>
  );
}
