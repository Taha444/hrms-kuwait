import { useEffect, useState } from "react";
import api, { errMsg } from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";

/**
 * الورديات — تعريف أوقات الدوام التي يُقاس عليها الحضور.
 *
 * **لماذا شاشة**: الوردية تُقرأ عند كل بصمة (`_compute_in_status`) وفي
 * المسيّر، ولا سبيل إلى تعريفها إلا بالواجهة البرمجية. فكل شركة تبقى
 * على وردية البذرة أو بلا وردية أصًلا.
 *
 * **وما يترتّب على غيابها ليس نقص ميزة بل خطأ صامت**: من لا وردية له
 * يُوسَم «حاضر» دائًما — لا تأخير ولا انصراف مبكّر مهما كان وقت بصمته.
 * فالشاشة تعرض عدد من عليها كلّ وردية، وتقول ما يجري لمن بلا وردية.
 */

type Shift = {
  id: number; name: string; start_time: string; end_time: string;
  work_days: string; grace_minutes: number; employee_count: number;
};

//: 0 = الأحد — كما يخزّنها الخادم (`work_days` نصٌّ بفواصل).
const DAYS = ["الأحد", "الإثنين", "الثلاثاء", "الأربعاء", "الخميس",
              "الجمعة", "السبت"];

const EMPTY = {
  name: "", start_time: "08:00", end_time: "17:00",
  work_days: ["0", "1", "2", "3", "4"], grace_minutes: 15,
};

export default function Shifts() {
  const { t } = useI18n();
  const { can } = useAuth();
  const manage = can("manage_attendance");

  const [rows, setRows] = useState<Shift[]>([]);
  const [form, setForm] = useState<any>(EMPTY);
  const [editing, setEditing] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const load = () => {
    api.get("/shifts").then((r) => setRows(r.data))
      .catch((e) => setErr(errMsg(e, t("error"))));
  };
  useEffect(() => { load(); }, []);

  const reset = () => { setForm(EMPTY); setEditing(null); };

  const toggleDay = (d: string) =>
    setForm({
      ...form,
      work_days: form.work_days.includes(d)
        ? form.work_days.filter((x: string) => x !== d)
        : [...form.work_days, d].sort(),
    });

  const submit = async () => {
    setErr(""); setMsg("");
    if (!form.name.trim()) { setErr(t("sh_name_required")); return; }
    if (!form.work_days.length) { setErr(t("sh_days_required")); return; }
    // وقت نهاية قبل بدايته يجعل مدّة الوردية سالبة في المسيّر.
    if (form.end_time <= form.start_time) { setErr(t("sh_bad_times")); return; }
    const body = {
      name: form.name.trim(),
      start_time: `${form.start_time}:00`,
      end_time: `${form.end_time}:00`,
      work_days: form.work_days.join(","),
      grace_minutes: Number(form.grace_minutes) || 0,
    };
    setBusy(true);
    try {
      if (editing) await api.put(`/shifts/${editing}`, body);
      else await api.post("/shifts", body);
      setMsg(editing ? t("sh_updated") : t("sh_added"));
      reset(); load();
    } catch (e: any) { setErr(errMsg(e, t("error"))); }
    finally { setBusy(false); }
  };

  const edit = (s: Shift) => {
    setEditing(s.id);
    setForm({
      name: s.name,
      start_time: s.start_time.slice(0, 5),
      end_time: s.end_time.slice(0, 5),
      work_days: (s.work_days || "").split(",").filter(Boolean),
      grace_minutes: s.grace_minutes,
    });
  };

  const dayNames = (csv: string) =>
    (csv || "").split(",").filter(Boolean)
      .map((d) => DAYS[Number(d)] ?? d).join("، ");

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="eyebrow">{t("attendance")}</div>
          <h2 style={{ margin: "2px 0 0" }}>{t("sh_title")}</h2>
          <div className="sub">{t("sh_sub")}</div>
        </div>
        <button className="ghost" onClick={load}>{t("refresh")}</button>
      </div>

      {msg && <div className="ok">{msg}</div>}
      {err && <div className="err">{err}</div>}

      {/* ما يجري بلا وردية — مكتوب لا مفترَض */}
      <div className="card" style={{ borderInlineStart: "3px solid var(--gold)" }}>
        <div className="sub">{t("sh_no_shift_note")}</div>
      </div>

      <div className="card">
        <table className="table">
          <thead>
            <tr>
              <th>{t("sh_name")}</th>
              <th>{t("sh_hours")}</th>
              <th>{t("sh_days")}</th>
              <th>{t("sh_grace")}</th>
              <th>{t("sh_assigned")}</th>
              {manage && <th />}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr><td colSpan={manage ? 6 : 5} className="muted">{t("sh_none")}</td></tr>
            )}
            {rows.map((s) => (
              <tr key={s.id}>
                <td>{s.name}</td>
                <td className="sub">{s.start_time.slice(0, 5)} → {s.end_time.slice(0, 5)}</td>
                <td className="sub">{dayNames(s.work_days)}</td>
                <td className="sub">{s.grace_minutes} {t("sh_minute")}</td>
                <td>
                  {/* صفر يعني أن الوردية معرَّفة ولا أثر لها */}
                  <span className={`pill ${s.employee_count ? "completed" : "warn"}`}>
                    {s.employee_count}
                  </span>
                  {!s.employee_count && (
                    <div className="sub">{t("sh_unused")}</div>
                  )}
                </td>
                {manage && (
                  <td>
                    <button className="ghost sm" onClick={() => edit(s)}>{t("edit")}</button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {manage && (
        <div className="card">
          <h3>{editing ? t("sh_edit_title") : t("sh_add_title")}</h3>
          {editing && (
            <div className="sub" style={{ marginBottom: 8 }}>{t("sh_edit_warning")}</div>
          )}
          <div className="row">
            <div className="field">
              <label htmlFor="sh-name">{t("sh_name")} *</label>
              <input id="sh-name" value={form.name}
                     onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="sh-start">{t("sh_start")} *</label>
              <input id="sh-start" type="time" value={form.start_time}
                     onChange={(e) => setForm({ ...form, start_time: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="sh-end">{t("sh_end")} *</label>
              <input id="sh-end" type="time" value={form.end_time}
                     onChange={(e) => setForm({ ...form, end_time: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="sh-grace">{t("sh_grace")}</label>
              <input id="sh-grace" type="number" min={0} value={form.grace_minutes}
                     onChange={(e) => setForm({ ...form, grace_minutes: e.target.value })} />
            </div>
          </div>

          <div className="field">
            <label>{t("sh_days")} *</label>
            <div className="row" style={{ flexWrap: "wrap", gap: 10 }}>
              {DAYS.map((name, i) => (
                <label key={i} style={{ display: "inline-flex", alignItems: "center",
                                        gap: 5, fontSize: 13, whiteSpace: "nowrap" }}>
                  <input type="checkbox" checked={form.work_days.includes(String(i))}
                         onChange={() => toggleDay(String(i))} />
                  {name}
                </label>
              ))}
            </div>
          </div>

          <div className="sub" style={{ marginBottom: 8 }}>{t("sh_grace_hint")}</div>

          <div className="row">
            <button disabled={busy} onClick={submit}>
              {editing ? t("save") : t("sh_add")}
            </button>
            {editing && <button className="ghost" onClick={reset}>{t("cancel")}</button>}
          </div>
        </div>
      )}
    </div>
  );
}
