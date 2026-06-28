import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "./auth";
import { useI18n } from "./i18n";
import api from "./api";
import Icon from "./Icon";
import GlobalSearch from "./components/GlobalSearch";

import Login from "./pages/Login";
import ChangePassword from "./pages/ChangePassword";
import CompanyPicker from "./pages/CompanyPicker";
import Dashboard from "./pages/Dashboard";
import Employees from "./pages/Employees";
import MyProfile from "./pages/MyProfile";
import CompanyStructure from "./pages/CompanyStructure";
import Archive from "./pages/Archive";
import Tasks from "./pages/Tasks";
import Requests from "./pages/Requests";
import RequestDetail from "./pages/RequestDetail";
import Attendance from "./pages/Attendance";
import AttendanceReview from "./pages/AttendanceReview";
import Pro from "./pages/Pro";
import Operations from "./pages/Operations";
import Branches from "./pages/Branches";
import Kiosk from "./pages/Kiosk";
import Eos from "./pages/Eos";
import Templates from "./pages/Templates";
import Payroll from "./pages/Payroll";
import Reports from "./pages/Reports";
import Audit from "./pages/Audit";
import Companies from "./pages/Companies";
import Users from "./pages/Users";
import { roleAr } from "./labels";

// لوجو/شعار مميّز لكل دور (أيقونة + لون)
const ROLE_THEME: Record<string, { icon: string; c1: string; c2: string }> = {
  super_admin: { icon: "key", c1: "#c9a227", c2: "#8a6d10" },
  company_owner: { icon: "building", c1: "#0e5a54", c2: "#082523" },
  company_manager: { icon: "dashboard", c1: "#0f766e", c2: "#0b3b38" },
  hr: { icon: "employees", c1: "#0e7490", c2: "#0b3b54" },
  delegate: { icon: "doc", c1: "#15857b", c2: "#0b3b38" },
  accountant: { icon: "eos", c1: "#7c5e10", c2: "#3d2e08" },
  branch_supervisor: { icon: "branches", c1: "#15803d", c2: "#0b3b1f" },
  admin_employee: { icon: "users", c1: "#5c706a", c2: "#384542" },
  employee: { icon: "requests", c1: "#0f766e", c2: "#0b3b38" },
};
const roleTheme = (r?: string) => ROLE_THEME[r || ""] || ROLE_THEME.employee;

function Sidebar({ open }: { open: boolean }) {
  const { user, can } = useAuth();
  const { t } = useI18n();
  const loc = useLocation();
  const [taskCount, setTaskCount] = useState(0);

  useEffect(() => {
    api.get("/tasks/count").then((r) => setTaskCount(r.data.open)).catch(() => {});
  }, [loc.pathname]);

  const Item = ({ to, icon, label, badge }: any) => (
    <NavLink to={to} end={to === "/"} className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
      <Icon name={icon} className="ico" />
      <span>{label}</span>
      {badge ? <span className="badge">{badge}</span> : null}
    </NavLink>
  );

  const isEmployee = !!user?.employee_id; // فقط من له ملف موظف يبصم حضورًا
  const isOwner = user?.role === "company_owner"; // مالك: واجهة رقابية مقيّدة (اطلاع فقط)
  const isCrossCompany = ["super_admin", "company_owner"].includes(user?.role || "");
  const canReview = ["super_admin", "company_manager"].includes(user?.role || "");
  // مركز العمليات والأرشيف يعرضان معاملات حكومية/تراخيص — للـ PRO/الإدارة العليا فقط
  const canOperations = can("manage_permits") || can("manage_licenses") || user?.role === "super_admin";
  const canArchive = can("manage_licenses") || can("manage_company") || user?.role === "super_admin";

  // واجهة المالك: لوحة + متابعة الفروع + التقارير + الإشعارات فقط — لا شيء غير ذلك
  if (isOwner) {
    return (
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div className="brand">
          <div className="logo">H<span>R</span></div>
          <b>نظام الموارد البشرية</b>
        </div>
        <div className="nav-group">
          <div className="nav-label">{t("main_section")}</div>
          <Item to="/" icon="dashboard" label={t("dashboard")} />
          <Item to="/structure" icon="branches" label={t("structure")} />
          <Item to="/reports" icon="doc" label={t("reports")} />
          <Item to="/tasks" icon="tasks" label={t("tasks")} badge={taskCount} />
        </div>
        <div className="sb-foot">
          <Item to="/change-password" icon="key" label={t("change_password")} />
        </div>
      </aside>
    );
  }

  return (
    <aside className={`sidebar ${open ? "open" : ""}`}>
      <div className="brand">
        <div className="logo">H<span>R</span></div>
        <b>نظام الموارد البشرية</b>
      </div>

      <div className="nav-group">
        <div className="nav-label">{t("main_section")}</div>
        <Item to="/" icon="dashboard" label={t("dashboard")} />
        <Item to="/tasks" icon="tasks" label={t("tasks")} badge={taskCount} />
        <Item to="/requests" icon="requests" label={t("requests")} />
        {canOperations && <Item to="/operations" icon="scan" label={t("operations")} />}
      </div>

      <div className="nav-group">
        <div className="nav-label">{t("resources_section")}</div>
        {/* خدمة ذاتية: ملف الموظف الشخصي (لمن له ملف موظف بلا صلاحية عرض عامة) */}
        {isEmployee && !can("view_employee") && <Item to="/my-profile" icon="employees" label={t("my_profile")} />}
        {can("view_employee") && <Item to="/employees" icon="employees" label={t("employees")} />}
        {/* الهيكل يعرض كل الفروع → للإدارة فقط (مسؤول الفرع مقيّد بفرعه) */}
        {(canReview || isCrossCompany || can("manage_branches")) &&
          <Item to="/structure" icon="branches" label={t("structure")} />}
        {canArchive && <Item to="/archive" icon="doc" label={t("archive")} />}
        {isEmployee && can("record_attendance") && <Item to="/attendance" icon="attendance" label={t("attendance")} />}
        {canReview && <Item to="/attendance-review" icon="attendance" label={t("attendance_review")} />}
        {can("manage_permits") && <Item to="/pro" icon="doc" label={t("pro")} />}
        {can("manage_branches") && <Item to="/branches" icon="branches" label={t("branch_qr")} />}
        {can("manage_templates") && <Item to="/templates" icon="doc" label={t("templates_nav")} />}
        {can("view_payroll") && <Item to="/payroll" icon="eos" label={t("payroll")} />}
        {can("calculate_eos") && <Item to="/eos" icon="eos" label={t("eos")} />}
        {can("export_reports") && <Item to="/reports" icon="doc" label={t("reports")} />}
      </div>

      {(user?.role === "super_admin" || can("manage_users") || can("view_audit")) && (
        <div className="nav-group">
          <div className="nav-label">{t("admin_section")}</div>
          {user?.role === "super_admin" && <Item to="/companies" icon="companies" label={t("companies")} />}
          {can("manage_users") && <Item to="/users" icon="users" label={t("users")} />}
          {can("view_audit") && <Item to="/audit" icon="lock" label={t("audit")} />}
        </div>
      )}

      <div className="sb-foot">
        <Item to="/change-password" icon="key" label={t("change_password")} />
      </div>
    </aside>
  );
}

function Topbar() {
  const { user, logout, activeCompanyId, setActiveCompany } = useAuth();
  const { t, lang, toggle } = useI18n();
  const nav = useNavigate();
  const [companyName, setCompanyName] = useState<string>("");

  useEffect(() => {
    if (!user?.is_cross_company) return;
    if (activeCompanyId === "all") { setCompanyName(t("all_companies")); return; }
    api.get("/companies", { params: { _r: 1 } }).then((r) => {
      const c = r.data.find((x: any) => String(x.id) === activeCompanyId);
      setCompanyName(c?.name || t("pick_company"));
    }).catch(() => {});
  }, [activeCompanyId, user]);

  const th = roleTheme(user?.role);

  return (
    <div className="topbar">
      {user?.is_cross_company && (
        <div className="company-switch" onClick={() => { setActiveCompany(null); nav("/select-company"); }}
             title={t("pick_company")}>
          <Icon name="building" size={16} />
          <span>{companyName || t("pick_company")}</span>
          <Icon name="chevron" size={15} className="chev" />
        </div>
      )}
      <GlobalSearch />
      <div className="spacer" />
      <button className="icon-btn" onClick={() => nav("/tasks")} title={t("tasks")}>
        <Icon name="bell" size={18} />
      </button>
      <button className="icon-btn" onClick={toggle} title={t("language")}>
        <Icon name="globe" size={18} /><span style={{ fontSize: 11, fontWeight: 700, marginInlineStart: 2 }}>{lang === "ar" ? "EN" : "ع"}</span>
      </button>
      <div className="user-chip">
        <div className="avatar" style={{ background: `linear-gradient(145deg, ${th.c1}, ${th.c2})` }} title={roleAr(user?.role || "")}>
          <Icon name={th.icon} size={18} />
        </div>
        <div className="meta">
          <b>{user?.full_name}</b>
          <small>{roleAr(user?.role || "")}</small>
        </div>
      </div>
      <button className="icon-btn" onClick={logout} title={t("logout")}><Icon name="logout" size={18} /></button>
    </div>
  );
}

function ImpersonationBanner() {
  const { impersonatingName, stopImpersonating } = useAuth();
  if (!impersonatingName) return null;
  return (
    <div style={{ background: "#8a6d10", color: "#fff", padding: "8px 24px", display: "flex",
      alignItems: "center", gap: 12, fontSize: 13.5 }}>
      <Icon name="users" size={16} />
      <span>أنت تتصفّح كـ <b>{impersonatingName}</b> (انتحال هوية)</span>
      <button className="ghost" style={{ marginInlineStart: "auto", padding: "4px 12px" }}
        onClick={stopImpersonating}>إنهاء الانتحال</button>
    </div>
  );
}

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="app">
      <Sidebar open={false} />
      <div className="main">
        <ImpersonationBanner />
        <Topbar />
        <div className="content">{children}</div>
      </div>
    </div>
  );
}

function Protected({ children }: { children: React.ReactNode }) {
  const { user, loading, activeCompanyId } = useAuth();
  const { t } = useI18n();
  if (loading) return <div className="auth-wrap" style={{ color: "#fff" }}>{t("loading")}</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.must_change_password) return <Navigate to="/change-password" replace />;
  // الإدارة العليا/المالك يجب أن يختاروا شركة أولًا
  if (user.is_cross_company && !activeCompanyId) return <Navigate to="/select-company" replace />;
  return <Layout>{children}</Layout>;
}

export default function App() {
  const { user, loading } = useAuth();
  if (loading) return <div className="auth-wrap" style={{ color: "#fff" }}>…</div>;
  return (
    <Routes>
      <Route path="/kiosk/qr/:branchId" element={<Kiosk />} />
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
      <Route path="/change-password" element={user ? <ChangePassword /> : <Navigate to="/login" replace />} />
      <Route path="/select-company" element={
        !user ? <Navigate to="/login" replace />
        : user.is_cross_company ? <CompanyPicker /> : <Navigate to="/" replace />
      } />
      <Route path="/" element={<Protected><Dashboard /></Protected>} />
      <Route path="/tasks" element={<Protected><Tasks /></Protected>} />
      <Route path="/requests" element={<Protected><Requests /></Protected>} />
      <Route path="/requests/:id" element={<Protected><RequestDetail /></Protected>} />
      <Route path="/employees" element={<Protected><Employees /></Protected>} />
      <Route path="/employees/:id" element={<Protected><Employees /></Protected>} />
      <Route path="/my-profile" element={<Protected><MyProfile /></Protected>} />
      <Route path="/structure" element={<Protected><CompanyStructure /></Protected>} />
      <Route path="/archive" element={<Protected><Archive /></Protected>} />
      <Route path="/attendance" element={<Protected><Attendance /></Protected>} />
      <Route path="/attendance-review" element={<Protected><AttendanceReview /></Protected>} />
      <Route path="/pro" element={<Protected><Pro /></Protected>} />
      <Route path="/operations" element={<Protected><Operations /></Protected>} />
      <Route path="/branches" element={<Protected><Branches /></Protected>} />
      <Route path="/eos" element={<Protected><Eos /></Protected>} />
      <Route path="/templates" element={<Protected><Templates /></Protected>} />
      <Route path="/payroll" element={<Protected><Payroll /></Protected>} />
      <Route path="/reports" element={<Protected><Reports /></Protected>} />
      <Route path="/audit" element={<Protected><Audit /></Protected>} />
      <Route path="/companies" element={<Protected><Companies /></Protected>} />
      <Route path="/users" element={<Protected><Users /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
