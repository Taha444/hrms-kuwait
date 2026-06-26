import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import Icon from "../Icon";

// تعريف كل مؤشّر: التسمية + الأيقونة + هل هو مميّز
const META: Record<string, { lbl: string; icon: string; accent?: boolean }> = {
  companies: { lbl: "عدد الشركات", icon: "companies", accent: true },
  employees: { lbl: "الموظفون النشطون", icon: "employees" },
  branches: { lbl: "الفروع", icon: "branches" },
  expiring_permits: { lbl: "إقامات/أذونات قرب الانتهاء", icon: "attendance", accent: true },
  expiring_residencies: { lbl: "إقامات قرب الانتهاء", icon: "attendance", accent: true },
  expiring_work_permits: { lbl: "أذونات عمل قرب الانتهاء", icon: "doc" },
  expiring_licenses: { lbl: "تراخيص قرب الانتهاء", icon: "doc", accent: true },
  pending_requests: { lbl: "طلبات بانتظار الاعتماد", icon: "requests" },
  on_leave: { lbl: "في إجازة اليوم", icon: "attendance" },
  open_tasks: { lbl: "مهامي المفتوحة", icon: "tasks" },
  my_open_tasks: { lbl: "مهامي", icon: "tasks", accent: true },
  my_active_requests: { lbl: "طلباتي النشطة", icon: "requests" },
};
const ORDER = Object.keys(META);

export default function Dashboard() {
  const { t } = useI18n();
  const { user } = useAuth();
  const [data, setData] = useState<any>(null);

  useEffect(() => { api.get("/dashboard").then((r) => setData(r.data)); }, []);
  if (!data) return <div className="empty">{t("loading")}</div>;

  // ----- العامل: عرض شخصي فقط (لا إحصائيات شركة) -----
  if (data.personal_only) {
    return (
      <div>
        <div className="page-head">
          <div>
            <div className="eyebrow">مرحبًا</div>
            <h2 style={{ margin: "2px 0 0" }}>{user?.full_name}</h2>
            <div className="sub">بوابتك الشخصية — مهامك وطلباتك وإشعاراتك</div>
          </div>
        </div>
        <div className="grid cards">
          <Link to="/tasks" className="card" style={{ textDecoration: "none" }}>
            <div className="stat-ico" style={{ background: "var(--gold-soft)", color: "#8a6d10" }}><Icon name="tasks" /></div>
            <div className="num" style={{ fontFamily: "var(--font-display)", fontSize: 30, color: "var(--petrol-700)" }}>{data.my_open_tasks}</div>
            <div className="lbl">مهامي وإشعاراتي</div>
          </Link>
          <Link to="/requests" className="card" style={{ textDecoration: "none" }}>
            <div className="stat-ico"><Icon name="requests" /></div>
            <div className="num" style={{ fontFamily: "var(--font-display)", fontSize: 30, color: "var(--petrol-700)" }}>{data.my_active_requests}</div>
            <div className="lbl">طلباتي النشطة</div>
          </Link>
          <Link to="/requests" className="card" style={{ textDecoration: "none" }}>
            <div className="stat-ico"><Icon name="doc" /></div>
            <div className="num" style={{ fontFamily: "var(--font-display)", fontSize: 22, color: "var(--petrol-700)" }}>تقديم طلب</div>
            <div className="lbl">إجازة · شهادة راتب</div>
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
          <div className="eyebrow">لوحة التحكم</div>
          <h2 style={{ margin: "2px 0 0" }}>مرحبًا، {user?.full_name}</h2>
          <div className="sub">نظرة سريعة على المؤشرات الخاصة بنطاقك</div>
        </div>
      </div>
      <div className="grid stats">
        {keys.map((k) => (
          <div className={`stat ${META[k].accent ? "accent" : ""}`} key={k}>
            <div className="stat-ico"><Icon name={META[k].icon} size={20} /></div>
            <div className="num">{data[k]}</div>
            <div className="lbl">{META[k].lbl}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
