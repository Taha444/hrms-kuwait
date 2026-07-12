import { useEffect, useRef, useState } from "react";
import api, { errMsg } from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import Icon from "../Icon";

// وحدة الصيغ والنماذج: تسجيل صيغة بمتغيّرات {{...}}، تعبئتها تلقائيًا ببيانات الموظف، وطباعتها.
const NEW_TEMPLATE = `<h2>عنوان الصيغة</h2>
<p>التاريخ: {{date_today}}</p>
<p>السيد/ة <b>{{employee_name}}</b> — الرقم المدني {{civil_id}} — وظيفة {{job_title}}.</p>
<p>اكتب نص الصيغة هنا...</p>
<br><br><p>التوقيع: ............................</p>`;

export default function Templates() {
  const { user } = useAuth();
  const { t } = useI18n();
  const isAdmin = user?.role === "super_admin";
  const [templates, setTemplates] = useState<any[]>([]);
  const [placeholders, setPlaceholders] = useState<Record<string, string>>({});
  const [employees, setEmployees] = useState<any[]>([]);
  const [editing, setEditing] = useState<any>(null); // {id?, name, category, body_html}
  const [filling, setFilling] = useState<any>(null); // template being filled
  const [empId, setEmpId] = useState<number | "">("");
  const [extra, setExtra] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const bodyRef = useRef<HTMLTextAreaElement>(null);

  const load = () => api.get("/templates").then((r) => setTemplates(r.data));
  useEffect(() => {
    load();
    api.get("/templates/placeholders").then((r) => setPlaceholders(r.data));
    api.get("/employees").then((r) => { setEmployees(r.data); if (r.data[0]) setEmpId(r.data[0].id); });
  }, []);

  const insertToken = (key: string) => {
    const ta = bodyRef.current;
    if (!ta || !editing) return;
    const s = ta.selectionStart, e = ta.selectionEnd;
    const token = `{{${key}}}`;
    const next = editing.body_html.slice(0, s) + token + editing.body_html.slice(e);
    setEditing({ ...editing, body_html: next });
    setTimeout(() => { ta.focus(); ta.selectionStart = ta.selectionEnd = s + token.length; }, 0);
  };

  const saveTemplate = async () => {
    setErr("");
    try {
      if (editing.id) await api.put(`/templates/${editing.id}`, editing);
      else await api.post("/templates", editing);
      setEditing(null); setMsg(t("tpl_saved")); load();
    } catch (e: any) { setErr(errMsg(e, t("error"))); }
  };

  const remove = async (id: number) => {
    if (!confirm(t("tpl_confirm_delete"))) return;
    await api.delete(`/templates/${id}`); load();
  };

  const openFill = async (tpl: any) => {
    const full = (await api.get(`/templates/${tpl.id}`)).data;
    const customKeys = (full.placeholders || []).filter((k: string) => !placeholders[k]);
    const init: Record<string, string> = {};
    customKeys.forEach((k: string) => (init[k] = ""));
    setExtra(init);
    setFilling({ ...full, customKeys });
  };

  const renderPrint = async () => {
    setErr("");
    try {
      const r = await api.post(`/templates/${filling.id}/render`, { employee_id: empId, extra, save: true });
      const w = window.open("", "_blank");
      if (w) { w.document.write(r.data.html); w.document.close(); w.focus(); }
      setMsg(t("tpl_rendered"));
    } catch (e: any) { setErr(errMsg(e, t("error"))); }
  };

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="eyebrow">{t("tpl_eyebrow")}</div>
          <h2 style={{ margin: "2px 0 0" }}>{t("templates_title")}</h2>
          <div className="sub">{t("templates_sub")}{isAdmin ? t("templates_sub_admin") : ""}</div>
        </div>
        {isAdmin && (
          <button onClick={() => setEditing({ name: "", category: t("tpl_default_category"), body_html: NEW_TEMPLATE })}>
            {t("tpl_new")}
          </button>
        )}
      </div>

      {msg && <div className="ok">{msg}</div>}
      {err && <div className="err">{err}</div>}

      {/* محرّر الصيغة */}
      {editing && (
        <div className="card">
          <h3>{editing.id ? t("tpl_edit") : t("tpl_new_title")}</h3>
          <div className="row">
            <div className="field" style={{ flex: 2 }}><label htmlFor="tpl-name">{t("tpl_name")}</label>
              <input id="tpl-name" value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} /></div>
            <div className="field" style={{ flex: 1 }}><label htmlFor="tpl-category">{t("tpl_category")}</label>
              <input id="tpl-category" value={editing.category} onChange={(e) => setEditing({ ...editing, category: e.target.value })} /></div>
          </div>
          <label>{t("tpl_auto_vars")}</label>
          <div className="row" style={{ marginBottom: 10 }}>
            {Object.entries(placeholders).map(([k, v]) => (
              <button key={k} type="button" className="ghost sm" onClick={() => insertToken(k)} title={`{{${k}}}`}>
                {v}
              </button>
            ))}
          </div>
          <div className="field">
            <label htmlFor="tpl-body">{t("tpl_body_label")}</label>
            <textarea id="tpl-body" ref={bodyRef} rows={12} value={editing.body_html}
              onChange={(e) => setEditing({ ...editing, body_html: e.target.value })}
              style={{ fontFamily: "monospace", lineHeight: 1.7 }} />
          </div>
          <p className="muted">{t("tpl_custom_hint")} <code>{"{{addressed_to}}"}</code></p>
          <div className="row">
            <button onClick={saveTemplate}>{t("save")}</button>
            <button className="ghost" onClick={() => setEditing(null)}>{t("cancel")}</button>
          </div>
        </div>
      )}

      {/* لوحة التعبئة والطباعة */}
      {filling && (
        <div className="card" style={{ borderTop: "3px solid var(--gold)" }}>
          <h3>{t("tpl_fill_print")}: {filling.name}</h3>
          <div className="field" style={{ maxWidth: 360 }}>
            <label htmlFor="tpl-emp">{t("tpl_select_emp")}</label>
            <select id="tpl-emp" value={empId} onChange={(e) => setEmpId(+e.target.value)}>
              {employees.map((e) => <option key={e.id} value={e.id}>{e.name} — {e.job_title}</option>)}
            </select>
          </div>
          {filling.customKeys?.length > 0 && (
            <>
              <label>{t("tpl_extra")}</label>
              <div className="row">
                {filling.customKeys.map((k: string) => (
                  <div className="field" key={k} style={{ flex: 1, minWidth: 200 }}>
                    <label htmlFor={`tpl-extra-${k}`}>{k}</label>
                    <input id={`tpl-extra-${k}`} value={extra[k] || ""} onChange={(e) => setExtra({ ...extra, [k]: e.target.value })} />
                  </div>
                ))}
              </div>
            </>
          )}
          <div className="row">
            <button onClick={renderPrint}><Icon name="doc" size={16} /> {t("tpl_preview_print")}</button>
            <button className="ghost" onClick={() => setFilling(null)}>{t("close")}</button>
          </div>
        </div>
      )}

      {/* قائمة الصيغ */}
      <div className="table-wrap">
        <table>
          <thead><tr><th>{t("tpl_col_name")}</th><th>{t("tpl_category")}</th><th>{t("tpl_col_vars")}</th><th>{t("tpl_scope")}</th><th></th></tr></thead>
          <tbody>
            {templates.map((tpl) => (
              <tr key={tpl.id}>
                <td><b>{tpl.name}</b></td>
                <td><span className="pill neutral">{tpl.category}</span></td>
                <td className="muted">{t("tpl_vars_count", { n: tpl.placeholders?.length || 0 })}</td>
                <td>{tpl.is_global ? <span className="pill gold">{t("tpl_global")}</span> : <span className="pill info">{t("tpl_company")}</span>}</td>
                <td className="row">
                  <button className="sm" onClick={() => openFill(tpl)}>{t("tpl_fill_print")}</button>
                  {isAdmin && <button className="ghost sm" onClick={() => api.get(`/templates/${tpl.id}`).then((r) => setEditing(r.data))}>{t("edit")}</button>}
                  {isAdmin && <button className="ghost sm" onClick={() => remove(tpl.id)}>{t("delete")}</button>}
                </td>
              </tr>
            ))}
            {!templates.length && <tr><td colSpan={5} className="empty">{t("tpl_none")}</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
