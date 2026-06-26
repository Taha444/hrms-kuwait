import { useEffect, useState } from "react";
import api from "../api";
import { roleAr } from "../labels";

export default function Users() {
  const [users, setUsers] = useState<any[]>([]);
  const [catalog, setCatalog] = useState<any>({ permissions: {}, templates: {}, roles: [] });
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState<any>({ civil_id: "", full_name: "", role: "employee" });
  const [sel, setSel] = useState<any>(null);
  const [perms, setPerms] = useState<any>(null);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const load = () => api.get("/users").then((r) => setUsers(r.data));
  useEffect(() => {
    load();
    api.get("/users/catalog").then((r) => setCatalog(r.data));
  }, []);

  const create = async () => {
    setErr("");
    try { await api.post("/users", form); setShowNew(false); load(); }
    catch (e: any) { setErr(e.response?.data?.detail || "خطأ"); }
  };
  const toggle = async (id: number) => { await api.post(`/users/${id}/toggle`); load(); };
  const reset = async (id: number) => {
    const r = await api.post("/auth/reset-password", { user_id: id });
    setMsg(`كلمة مرور مؤقتة: ${r.data.temporary_password}`);
  };
  const openPerms = async (u: any) => {
    setSel(u);
    const r = await api.get(`/users/${u.id}/permissions`);
    setPerms(r.data);
  };
  const togglePerm = async (code: string, has: boolean) => {
    if (has) await api.delete(`/users/${sel.id}/permissions/${code}`);
    else await api.post(`/users/${sel.id}/permissions`, { perm_codes: [code] });
    openPerms(sel);
  };
  const applyTemplate = async (tpl: string) => {
    await api.post(`/users/apply-template/${sel.id}/${tpl}`);
    openPerms(sel);
  };

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2>المستخدمون والصلاحيات</h2>
        <button onClick={() => setShowNew((s) => !s)}>+ مستخدم جديد</button>
      </div>
      {msg && <div className="ok">{msg}</div>}

      {showNew && (
        <div className="card">
          <div className="row">
            <div className="field" style={{ flex: 1 }}><label>الرقم المدني</label>
              <input onChange={(e) => setForm({ ...form, civil_id: e.target.value })} /></div>
            <div className="field" style={{ flex: 1 }}><label>الاسم</label>
              <input onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></div>
            <div className="field" style={{ flex: 1 }}><label>الدور</label>
              <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                {(catalog.assignable_roles || catalog.roles).map((r: string) => <option key={r} value={r}>{roleAr(r)}</option>)}
              </select></div>
          </div>
          <p className="muted">كلمة المرور الافتراضية تُطلب تغييرها عند أول دخول.</p>
          {err && <div className="err">{err}</div>}
          <button onClick={create}>حفظ</button>
        </div>
      )}

      <div className="card">
        <table>
          <thead><tr><th>الرقم المدني</th><th>الاسم</th><th>الدور</th><th>مفعّل</th><th></th></tr></thead>
          <tbody>{users.map((u) => (
            <tr key={u.id}><td>{u.civil_id}</td><td>{u.full_name}</td>
              <td><span className="pill info">{roleAr(u.role)}</span></td>
              <td>{u.is_active ? "✓" : "✕"}</td>
              <td className="row">
                <button className="ghost" onClick={() => openPerms(u)}>الصلاحيات</button>
                <button className="ghost" onClick={() => reset(u.id)}>إعادة تعيين</button>
                <button className="ghost" onClick={() => toggle(u.id)}>{u.is_active ? "تعطيل" : "تفعيل"}</button>
              </td></tr>
          ))}</tbody>
        </table>
      </div>

      {sel && perms && (
        <div className="card">
          <h3>صلاحيات: {sel.full_name} <span className="muted">({perms.role})</span></h3>
          <div className="row" style={{ marginBottom: 10 }}>
            <span className="muted">تطبيق قالب:</span>
            {Object.entries(catalog.templates).map(([k, v]: any) => (
              <button key={k} className="ghost" onClick={() => applyTemplate(k)}>{v.label}</button>
            ))}
          </div>
          <div className="grid">
            {Object.entries(catalog.permissions).map(([code, label]: any) => {
              const has = perms.effective.includes(code);
              return (
                <label key={code} className="card" style={{ margin: 0, cursor: "pointer" }}>
                  <input type="checkbox" checked={has} onChange={() => togglePerm(code, has)}
                    style={{ width: "auto", marginInlineEnd: 8 }} />
                  {label} <span className="muted">({code})</span>
                </label>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
