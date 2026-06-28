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
  branch_employees: { key: "kpi_branch_employees", icon: "employees", accent: true },
  branches: { key: "kpi_branches", icon: "branches" },
  expiring_permits: { key: "kpi_expiring_permits", icon: "attendance", accent: true },
  expired_residencies: { key: "kpi_expired_residencies", icon: "attendance", accent: true },
  residencies_expiring_30: { key: "kpi_residencies_30", icon: "attendance", accent: true },
  expiring_residencies: { key: "kpi_expiring_residencies", icon: "attendance", accent: true },
  expiring_work_permits: { key: "kpi_expiring_work_permits", icon: "doc" },
  expiring_licenses: { key: "kpi_expiring_licenses", icon: "doc", accent: true },
  open_transactions: { key: "kpi_open_transactions", icon: "doc" },
  gov_tasks: { key: "kpi_gov_tasks", icon: "tasks" },
  pending_requests: { key: "kpi_pending_requests", icon: "requests" },
  on_leave: { key: "kpi_on_leave", icon: "attendance" },
  notifications: { key: "kpi_notifications", icon: "tasks" },
  contracts: { key: "kpi_contracts", icon: "doc" },
  warnings: { key: "kpi_warnings", icon: "lock" },
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
          <Link to="/my-profile" className="card" style={{ textDecoration: "none" }}>
            <div className="stat-ico"><Icon name="employees" /></div>
            <div className="num" style={{ fontFamily: "var(--font-display)", fontSize: 22, color: "var(--petrol-700)" }}>{t("my_profile")}</div>
            <div className="lbl">{t("my_contract")} · {t("my_warnings")}</div>
          </Link>
        </div>
      </div>
    );
  }

  // ----- لوحة المالك: متابعة رقابية (اطلاع فقط) -----
  if (data.owner_view) {
    const perf = data.performance || {};
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
          <div className="stat"><div className="stat-ico"><Icon name="employees" size={20} /></div>
            <div className="num">{data.employees}</div><div className="lbl">{t("kpi_employees")}</div></div>
          <div className="stat"><div className="stat-ico"><Icon name="branches" size={20} /></div>
            <div className="num">{data.branches}</div><div className="lbl">{t("kpi_branches")}</div></div>
          <div className="stat accent"><div className="stat-ico"><Icon name="attendance" size={20} /></div>
            <div className="num">{data.residencies}</div><div className="lbl">{t("kpi_residencies")}</div>
            {data.residencies_expiring > 0 && <div className="muted" style={{ fontSize: 11 }}>{t("kpi_expiring_suffix", { n: data.residencies_expiring })}</div>}</div>
          <div className="stat accent"><div className="stat-ico"><Icon name="doc" size={20} /></div>
            <div className="num">{data.licenses}</div><div className="lbl">{t("kpi_licenses_active")}</div>
            {data.licenses_expiring > 0 && <div className="muted" style={{ fontSize: 11 }}>{t("kpi_expiring_suffix", { n: data.licenses_expiring })}</div>}</div>
          <div className="stat"><div className="stat-ico"><Icon name="tasks" size={20} /></div>
            <div className="num">{data.notifications}</div><div className="lbl">{t("kpi_notifications")}</div></div>
        </div>

        <div className="card">
          <h3>{t("perf_title")}</h3>
          <div className="grid stats">
            <div className="stat"><div className="num">{perf.attendance_rate ?? 0}%</div><div className="lbl">{t("perf_attendance")}</div></div>
            <div className="stat"><div className="num" style={{ color: "var(--success)" }}>{perf.valid_licenses_pct ?? 0}%</div><div className="lbl">{t("perf_valid_licenses")}</div></div>
            <div className="stat"><div className="num" style={{ color: "var(--danger)" }}>{perf.expired_licenses_pct ?? 0}%</div><div className="lbl">{t("perf_expired_licenses")}</div></div>
          </div>
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
