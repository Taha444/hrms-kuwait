import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import Icon from "../Icon";

// تعريف كل مؤشّر: مفتاح الترجمة + الأيقونة + هل هو مميّز
const META: Record<string, { key: string; icon: string; accent?: boolean }> = {
  companies: { key: "kpi_companies", icon: "companies", accent: true },
  employees: { key: "kpi_employees", icon: "employees" },
  branches: { key: "kpi_branches", icon: "branches" },
  expiring_permits: { key: "kpi_expiring_permits", icon: "attendance", accent: true },
  expiring_residencies: { key: "kpi_expiring_residencies", icon: "attendance", accent: true },
  expiring_work_permits: { key: "kpi_expiring_work_permits", icon: "doc" },
  expiring_licenses: { key: "kpi_expiring_licenses", icon: "doc", accent: true },
  pending_requests: { key: "kpi_pending_requests", icon: "requests" },
  on_leave: { key: "kpi_on_leave", icon: "attendance" },
  open_tasks: { key: "kpi_open_tasks", icon: "tasks" },
  my_open_tasks: { key: "kpi_my_tasks", icon: "tasks", accent: true },
  my_active_requests: { key: "kpi_my_requests", icon: "requests" },
};
const ORDER = Object.keys(META);

export default function Dashboard() {
  const { t } = useI18n();
  const { user } = useAuth();
  const [data, setData] = useState<any>(null);

  useEffect(() => { api.get("/dashboard").then((r) => setData(r.data)); }, []);
  if (!data) return <div className="empty">{t("loading")}</div>;

  if (data.personal_only) {
    return (
      <div>
        <div className="page-head">
          <div>
            <div className="eyebrow">{t("dash_welcome")}</div>
            <h2 style={{ margin: "2px 0 0" }}>{user?.full_name}</h2>
            <div className="sub">{t("emp_portal_sub")}</div>
          </div>
        </div>
        <div className="grid cards">
          <Link to="/tasks" className="card" style={{ textDecoration: "none" }}>
            <div className="stat-ico" style={{ background: "var(--gold-soft)", color: "#8a6d10" }}><Icon name="tasks" /></div>
            <div className="num" style={{ fontFamily: "var(--font-display)", fontSize: 30, color: "var(--petrol-700)" }}>{data.my_open_tasks}</div>
            <div className="lbl">{t("kpi_my_tasks")}</div>
          </Link>
          <Link to="/requests" className="card" style={{ textDecoration: "none" }}>
            <div className="stat-ico"><Icon name="requests" /></div>
            <div className="num" style={{ fontFamily: "var(--font-display)", fontSize: 30, color: "var(--petrol-700)" }}>{data.my_active_requests}</div>
            <div className="lbl">{t("kpi_my_requests")}</div>
          </Link>
          <Link to="/requests" className="card" style={{ textDecoration: "none" }}>
            <div className="stat-ico"><Icon name="doc" /></div>
            <div className="num" style={{ fontFamily: "var(--font-display)", fontSize: 22, color: "var(--petrol-700)" }}>{t("new_request")}</div>
            <div className="lbl">{t("new_request_sub")}</div>
          </Link>
        </div>
      </div>
    );
  }

  const keys = ORDER.filter((k) => data[k] !== null && data[k] !== undefined);
  return (
    <div>
      <div className="page-head">
        <div>
          <div className="eyebrow">{t("dash_eyebrow")}</div>
          <h2 style={{ margin: "2px 0 0" }}>{t("dash_welcome")}، {user?.full_name}</h2>
          <div className="sub">{t("dash_sub")}</div>
        </div>
      </div>
      <div className="grid stats">
        {keys.map((k) => (
          <div className={`stat ${META[k].accent ? "accent" : ""}`} key={k}>
            <div className="stat-ico"><Icon name={META[k].icon} size={20} /></div>
            <div className="num">{data[k]}</div>
            <div className="lbl">{t(META[k].key)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
