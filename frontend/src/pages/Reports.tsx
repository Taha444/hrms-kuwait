import { useEffect, useState } from "react";
import api, { downloadFile } from "../api";
import { useI18n } from "../i18n";
import Icon from "../Icon";

function thisMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export default function Reports() {
  const { t } = useI18n();
  const [month, setMonth] = useState(thisMonth());
  const [branches, setBranches] = useState<any[]>([]);
  const [branch, setBranch] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => { api.get("/branches").then((r) => setBranches(r.data)).catch(() => {}); }, []);
  const br = branch ? { branch_id: branch } : {};

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
    <div aria-labelledby="reports-title">
      <div className="page-head">
        <div>
          <div className="eyebrow">{t("reports")}</div>
          <h2 id="reports-title" style={{ margin: "2px 0 0" }}>{t("reports")}</h2>
          <div className="sub">{t("reports_sub")}</div>
        </div>
        <select aria-label={t("all_branches")} value={branch} onChange={(e) => setBranch(e.target.value)} style={{ maxWidth: 200 }}>
          <option value="">{t("all_branches")}</option>
          {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
      </div>

      <Card title={t("rep_employees")} desc={t("rep_employees_sub")}>
        <button disabled={busy === "emp_x"} onClick={() => dl("emp_x", "/reports/employees", { fmt: "xlsx", ...br }, "employees.xlsx")}>
          <Icon name="doc" size={15} /> Excel
        </button>
        <button className="ghost" disabled={busy === "emp_c"} onClick={() => dl("emp_c", "/reports/employees", { fmt: "csv", ...br }, "employees.csv")}>
          CSV
        </button>
      </Card>

      <Card title={t("rep_attendance")} desc={t("rep_attendance_sub")}>
        <input aria-label={t("rep_attendance")} type="month" value={month} onChange={(e) => setMonth(e.target.value)} style={{ width: 160 }} />
        <button disabled={busy === "att_x"} onClick={() => dl("att_x", "/reports/attendance", { month, fmt: "xlsx", ...br }, "attendance.xlsx")}>
          <Icon name="doc" size={15} /> Excel
        </button>
        <button className="ghost" disabled={busy === "att_c"} onClick={() => dl("att_c", "/reports/attendance", { month, fmt: "csv", ...br }, "attendance.csv")}>
          CSV
        </button>
      </Card>

      <div className="card muted">{t("rep_payroll_hint")}</div>
    </div>
  );
}
