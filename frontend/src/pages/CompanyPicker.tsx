import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";
import { useAuth } from "../auth";
import Icon from "../Icon";

// شاشة اختيار الشركة — تظهر للإدارة العليا/المالك ليختاروا الشركة التي يعملون عليها.
export default function CompanyPicker() {
  const { user, setActiveCompany, logout } = useAuth();
  const nav = useNavigate();
  const [companies, setCompanies] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // نتجاهل الشركة المختارة سابقًا أثناء وجودنا في هذه الشاشة
    api.get("/companies", { params: { _all: 1 } })
      .then((r) => setCompanies(r.data))
      .finally(() => setLoading(false));
  }, []);

  const choose = (id: string | null) => {
    setActiveCompany(id);
    nav("/", { replace: true });
  };

  const mono = (name: string) => (name || "؟").trim().slice(0, 2);

  return (
    <div className="picker-wrap">
      <div className="picker-inner">
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 6 }}>
          <div className="row" style={{ gap: 12 }}>
            <div className="company-switch" style={{ cursor: "default" }}>
              <span className="mono">HR</span>
              <span>{user?.full_name}</span>
            </div>
          </div>
          <button className="ghost" onClick={logout}><Icon name="logout" size={16} /> خروج</button>
        </div>

        <div style={{ margin: "10px 0 26px" }}>
          <div className="eyebrow">مرحبًا</div>
          <h2 style={{ fontSize: 30, margin: "4px 0 4px" }}>اختر الشركة</h2>
          <p className="muted">حدّد الشركة التي تريد العمل عليها. يمكنك التبديل في أي وقت من الأعلى.</p>
        </div>

        {loading ? (
          <div className="empty">جارِ التحميل…</div>
        ) : (
          <div className="grid cards">
            <button className="company-card all" onClick={() => choose("all")}>
              <div className="mono"><Icon name="companies" size={24} /></div>
              <h3>كل الشركات</h3>
              <p className="muted">عرض مجمّع لكل الشركات والمؤشرات</p>
            </button>

            {companies.map((c) => (
              <button key={c.id} className="company-card" onClick={() => choose(String(c.id))}>
                <div className="mono">{mono(c.name)}</div>
                <h3>{c.name}</h3>
                <p className="muted">{c.name_en || c.entity_type || "—"}</p>
                <div style={{ marginTop: 10 }}>
                  <span className={`pill ${c.status}`}>{c.status}</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
