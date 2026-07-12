import { useEffect, useState } from "react";
import api from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import { taskAr, severityAr } from "../labels";
import { Skeleton, ErrorRetry, EmptyState } from "../components/States";

export default function Tasks() {
  const { t } = useI18n();
  const { can } = useAuth();
  const [tasks, setTasks] = useState<any[]>([]);
  const [state, setState] = useState<"loading" | "ok" | "error">("loading");
  const [status, setStatus] = useState("open");
  const [category, setCategory] = useState("");
  const [msg, setMsg] = useState("");
  const CATS = ["system", "government", "hr", "approvals"];

  const load = () => {
    setState("loading");
    api.get("/tasks/my", { params: { status, category: category || undefined } })
      .then((r) => { setTasks(r.data); setState("ok"); })
      .catch(() => setState("error"));
  };
  useEffect(() => { load(); }, [status, category]);

  const setTaskStatus = async (id: number, s: string) => {
    await api.post(`/tasks/${id}/status?status=${s}`);
    load();
    // يُحدّث عداد المهام في الشريط الجانبي فورًا بدل انتظار تغيير المسار (QA-P1-TASK-01)
    window.dispatchEvent(new Event("tasks:changed"));
  };
  const runScan = async () => {
    const r = await api.post("/tasks/run-scan");
    setMsg(t("scan_generated", { n: r.data.generated }));
    load();
    window.dispatchEvent(new Event("tasks:changed"));
  };

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="eyebrow">{t("tasks")}</div>
          <h2 style={{ margin: "2px 0 0" }}>{t("tasks")}</h2>
        </div>
        <div className="row">
          <select aria-label={t("tasks_all_categories")} value={category} onChange={(e) => setCategory(e.target.value)} style={{ width: 150 }}>
            <option value="">{t("tasks_all_categories")}</option>
            {CATS.map((c) => <option key={c} value={c}>{t(`cat_${c}`)}</option>)}
          </select>
          <select aria-label={t("status")} value={status} onChange={(e) => setStatus(e.target.value)} style={{ width: 150 }}>
            <option value="open">{t("tasks_open")}</option>
            <option value="done">{t("tasks_done")}</option>
            <option value="dismissed">{t("tasks_dismissed")}</option>
          </select>
          {can("manage_tasks") && <button onClick={runScan}>{t("tasks_run_scan")}</button>}
        </div>
      </div>
      {msg && <div className="ok">{msg}</div>}
      {state === "loading" ? <Skeleton rows={5} />
        : state === "error" ? <ErrorRetry onRetry={load} />
        : !tasks.length ? <EmptyState icon="tasks" />
        : <div className="table-wrap">
        <table>
          <thead><tr><th>{t("col_type")}</th><th>{t("col_title")}</th><th>{t("col_detail")}</th><th>{t("col_severity")}</th><th></th></tr></thead>
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
                      <button className="ghost sm" onClick={() => setTaskStatus(x.id, "done")}>{t("act_complete")}</button>
                      <button className="ghost sm" onClick={() => setTaskStatus(x.id, "dismissed")}>{t("act_dismiss")}</button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>}
    </div>
  );
}
