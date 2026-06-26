import { useEffect, useRef, useState } from "react";
import api from "../api";
import { useAuth } from "../auth";
import Icon from "../Icon";

// وحدة الصيغ والنماذج: تسجيل صيغة بمتغيّرات {{...}}، تعبئتها تلقائيًا ببيانات الموظف، وطباعتها.
const NEW_TEMPLATE = `<h2>عنوان الصيغة</h2>
<p>التاريخ: {{date_today}}</p>
<p>السيد/ة <b>{{employee_name}}</b> — الرقم المدني {{civil_id}} — وظيفة {{job_title}}.</p>
<p>اكتب نص الصيغة هنا...</p>
<br><br><p>التوقيع: ............................</p>`;

export default function Templates() {
  const { user } = useAuth();
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
      setEditing(null); setMsg("تم حفظ الصيغة"); load();
    } catch (e: any) { setErr(e.response?.data?.detail || "خطأ"); }
  };

  const remove = async (id: number) => {
    if (!confirm("حذف هذه الصيغة؟")) return;
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
      setMsg("تم توليد المستند وحفظه في ملف الموظف");
    } catch (e: any) { setErr(e.response?.data?.detail || "خطأ"); }
  };

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="eyebrow">المستندات</div>
          <h2 style={{ margin: "2px 0 0" }}>الصيغ والنماذج</h2>
          <div className="sub">اختر صيغة ثم الموظف لتُعبّأ تلقائيًا وتُطبع{isAdmin ? " · أو أنشئ صيغة جديدة" : ""}</div>
        </div>
        {isAdmin && (
          <button onClick={() => setEditing({ name: "", category: "عام", body_html: NEW_TEMPLATE })}>
            + صيغة جديدة
          </button>
        )}
      </div>

      {msg && <div className="ok">{msg}</div>}
      {err && <div className="err">{err}</div>}

      {/* محرّر الصيغة */}
      {editing && (
        <div className="card">
          <h3>{editing.id ? "تعديل صيغة" : "صيغة جديدة"}</h3>
          <div className="row">
            <div className="field" style={{ flex: 2 }}><label>اسم الصيغة</label>
              <input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} /></div>
            <div className="field" style={{ flex: 1 }}><label>التصنيف</label>
              <input value={editing.category} onChange={(e) => setEditing({ ...editing, category: e.target.value })} /></div>
          </div>
          <label>المتغيّرات التلقائية — اضغط لإدراجها في النص</label>
          <div className="row" style={{ marginBottom: 10 }}>
            {Object.entries(placeholders).map(([k, v]) => (
              <button key={k} type="button" className="ghost sm" onClick={() => insertToken(k)} title={`{{${k}}}`}>
                {v}
              </button>
            ))}
          </div>
          <div className="field">
            <label>نص الصيغة (HTML) — استخدم {"{{متغيّر}}"} للحقول</label>
            <textarea ref={bodyRef} rows={12} value={editing.body_html}
              onChange={(e) => setEditing({ ...editing, body_html: e.target.value })}
              style={{ fontFamily: "monospace", lineHeight: 1.7 }} />
          </div>
          <p className="muted">يمكنك إضافة متغيّرات مخصّصة مثل <code>{"{{addressed_to}}"}</code> وسيُطلب إدخالها عند التعبئة.</p>
          <div className="row">
            <button onClick={saveTemplate}>حفظ</button>
            <button className="ghost" onClick={() => setEditing(null)}>إلغاء</button>
          </div>
        </div>
      )}

      {/* لوحة التعبئة والطباعة */}
      {filling && (
        <div className="card" style={{ borderTop: "3px solid var(--gold)" }}>
          <h3>تعبئة وطباعة: {filling.name}</h3>
          <div className="field" style={{ maxWidth: 360 }}>
            <label>اختر الموظف</label>
            <select value={empId} onChange={(e) => setEmpId(+e.target.value)}>
              {employees.map((e) => <option key={e.id} value={e.id}>{e.name} — {e.job_title}</option>)}
            </select>
          </div>
          {filling.customKeys?.length > 0 && (
            <>
              <label>حقول إضافية مطلوبة</label>
              <div className="row">
                {filling.customKeys.map((k: string) => (
                  <div className="field" key={k} style={{ flex: 1, minWidth: 200 }}>
                    <label>{k}</label>
                    <input value={extra[k] || ""} onChange={(e) => setExtra({ ...extra, [k]: e.target.value })} />
                  </div>
                ))}
              </div>
            </>
          )}
          <div className="row">
            <button onClick={renderPrint}><Icon name="doc" size={16} /> معاينة وطباعة</button>
            <button className="ghost" onClick={() => setFilling(null)}>إغلاق</button>
          </div>
        </div>
      )}

      {/* قائمة الصيغ */}
      <div className="table-wrap">
        <table>
          <thead><tr><th>الصيغة</th><th>التصنيف</th><th>المتغيّرات</th><th>النطاق</th><th></th></tr></thead>
          <tbody>
            {templates.map((t) => (
              <tr key={t.id}>
                <td><b>{t.name}</b></td>
                <td><span className="pill neutral">{t.category}</span></td>
                <td className="muted">{t.placeholders?.length || 0} متغيّر</td>
                <td>{t.is_global ? <span className="pill gold">عامة</span> : <span className="pill info">الشركة</span>}</td>
                <td className="row">
                  <button className="sm" onClick={() => openFill(t)}>تعبئة وطباعة</button>
                  {isAdmin && <button className="ghost sm" onClick={() => api.get(`/templates/${t.id}`).then((r) => setEditing(r.data))}>تعديل</button>}
                  {isAdmin && <button className="ghost sm" onClick={() => remove(t.id)}>حذف</button>}
                </td>
              </tr>
            ))}
            {!templates.length && <tr><td colSpan={5} className="empty">لا توجد صيغ بعد — أنشئ واحدة.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
