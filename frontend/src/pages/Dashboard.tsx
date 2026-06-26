import { useEffect, useState } from "react";
import api from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import Icon from "../Icon";

export default function Dashboard() {
  const { t } = useI18n();
  const { user } = useAuth();
  const [data, setData] = useState<any>(null);

  useEffect(() => { api.get("/dashboard").then((r) => setData(r.data)); }, []);
  if (!data) return <div className="empty">{t("loading")}</div>;

  const Stat = ({ num, lbl, icon, accent }: any) =>
    num === null || num === undefined ? null : (
      <div className={`stat ${accent ? "accent" : ""}`}>
        <div className="stat-ico"><Icon name={icon} size={20} /></div>
        <div className="num">{num}</div>
        <div className="lbl">{lbl}</div>
      </div>
    );

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
        <Stat num={data.companies} lbl="عدد الشركات" icon="companies" accent />
        <Stat num={data.employees} lbl="الموظفون النشطون" icon="employees" />
        <Stat num={data.branches} lbl="الفروع" icon="branches" />
        <Stat num={data.expiring_permits} lbl="إقامات قرب الانتهاء" icon="attendance" accent />
        <Stat num={data.open_tasks} lbl="مهامي المفتوحة" icon="tasks" />
        <Stat num={data.pending_requests} lbl="طلبات بانتظار الاعتماد" icon="requests" />
        <Stat num={data.my_active_requests} lbl="طلباتي النشطة" icon="doc" />
      </div>
    </div>
  );
}
