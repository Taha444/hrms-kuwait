import { useEffect, useState } from "react";
import api from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import { taskAr, severityAr } from "../labels";

export default function Tasks() {
  const { t } = useI18n();
  const { can } = useAuth();
  const [tasks, setTasks] = useState<any[]>([]);
  const [status, setStatus] = useState("open");
  const [category, setCategory] = useState("");
  const [msg, setMsg] = useState("");
  const CAT_AR: Record<string, string> = {
    system: "النظام", government: "حكومية", hr: "موارد بشرية", approvals: "موافقات",
  };

  const load = () => api.get("/tasks/my", { params: { status, category: category || undefined } }).then((r) => setTasks(r.data));
  useEffect(() => { load(); }, [status, category]);

  const setTaskStatus = async (id: number, s: string) => {
    await api.post(`/tasks/${id}/status?status=${s}`);
    load();
  };
  const runScan = async () => {
    const r = await api.post("/tasks/run-scan");
    setMsg(`تم توليد ${r.data.generated} مهمة`);
    load();
  };

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2>{t("tasks")}</h2>
        <div className="row">
          <select value={category} onChange={(e) => setCategory(e.target.value)} style={{ width: 150 }}>
            <option value="">كل التصنيفات</option>
            {Object.entries(CAT_AR).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <select value={status} onChange={(e) => setStatus(e.target.value)} style={{ width: 160 }}>
            <option value="open">المفتوحة</option>
            <option value="done">المنجزة</option>
            <option value="dismissed">المتجاهَلة</option>
          </select>
          {can("manage_tasks") && <button onClick={runScan}>تشغيل المسح اليومي</button>}
        </div>
      </div>
      {msg && <div className="ok">{msg}</div>}
      <div className="card">
        <table>
          <thead><tr><th>النوع</th><th>العنوان</th><th>التفاصيل</th><th>الأهمية</th><th></th></tr></thead>
          <tbody>
            {tasks.map((x) => (
              <tr key={x.id}>
                <td><span className="pill info">{taskAr(x.type)}</span></td>
                <td>{x.title}</td>
                <td className="muted">{x.detail}</td>
                <td><span className={`pill ${x.severity}`}>{severityAr(x.severity)}</span></td>
                <td>
                  {status === "open" && (
                    <div className="row">
                      <button className="ghost" onClick={() => setTaskStatus(x.id, "done")}>إنجاز</button>
                      <button className="ghost" onClick={() => setTaskStatus(x.id, "dismissed")}>تجاهل</button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {!tasks.length && <tr><td colSpan={5} className="muted">{t("no_data")}</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
