import { useState } from "react";
import { downloadFile } from "../api";
import Icon from "../Icon";

function thisMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export default function Reports() {
  const [month, setMonth] = useState(thisMonth());
  const [busy, setBusy] = useState("");

  const dl = async (key: string, path: string, params: any, name: string) => {
    setBusy(key);
    try { await downloadFile(path, params, name); }
    finally { setBusy(""); }
  };

  const Card = ({ title, desc, children }: any) => (
    <div className="card">
      <h3 style={{ marginBottom: 4 }}>{title}</h3>
      <p className="muted" style={{ marginTop: 0 }}>{desc}</p>
      <div className="row">{children}</div>
    </div>
  );

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="eyebrow">التقارير</div>
          <h2 style={{ margin: "2px 0 0" }}>التقارير والتصدير</h2>
          <div className="sub">تصدير البيانات إلى Excel أو CSV بترميز يدعم العربية</div>
        </div>
      </div>

      <Card title="بيانات الموظفين" desc="قائمة كاملة بالموظفين في الشركة المختارة.">
        <button disabled={busy === "emp_x"} onClick={() => dl("emp_x", "/reports/employees", { fmt: "xlsx" }, "employees.xlsx")}>
          <Icon name="doc" size={15} /> Excel
        </button>
        <button className="ghost" disabled={busy === "emp_c"} onClick={() => dl("emp_c", "/reports/employees", { fmt: "csv" }, "employees.csv")}>
          CSV
        </button>
      </Card>

      <Card title="سجل الحضور الشهري" desc="كل سجلات الحضور للشهر المحدد.">
        <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} style={{ width: 160 }} />
        <button disabled={busy === "att_x"} onClick={() => dl("att_x", "/reports/attendance", { month, fmt: "xlsx" }, "attendance.xlsx")}>
          <Icon name="doc" size={15} /> Excel
        </button>
        <button className="ghost" disabled={busy === "att_c"} onClick={() => dl("att_c", "/reports/attendance", { month, fmt: "csv" }, "attendance.csv")}>
          CSV
        </button>
      </Card>

      <div className="card muted">
        تصدير الرواتب يتم من صفحة <b>مسيّر الرواتب</b> بجانب كل مسيّر محفوظ.
      </div>
    </div>
  );
}
