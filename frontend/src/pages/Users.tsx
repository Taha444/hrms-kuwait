import { useEffect, useState } from "react";
import api from "../api";
import { useAuth } from "../auth";
import { roleAr } from "../labels";

const USER_STATUS_AR: Record<string, string> = {
  active: "نشط", inactive: "غير نشط", suspended: "موقوف", locked: "مقفل",
};

export default function Users() {
  const { user: me, impersonate } = useAuth();
  const [users, setUsers] = useState<any[]>([]);
  const [catalog, setCatalog] = useState<any>({ permissions: {}, templates: {}, roles: [] });
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState<any>({ civil_id: "", full_name: "", role: "employee" });
  const [sel, setSel] = useState<any>(null);
  const [perms, setPerms] = useState<any>(null);
  const [mxCatalog, setMxCatalog] = useState<any>({ pages: [], actions_ar: {} });
  const [matrix, setMatrix] = useState<any>(null); // {matrix, custom_pages}
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const [branches, setBranches] = useState<any[]>([]);
  const load = () => api.get("/users").then((r) => setUsers(r.data));
  useEffect(() => {
    load();
    api.get("/users/catalog").then((r) => setCatalog(r.data));
    api.get("/users/permission-matrix").then((r) => setMxCatalog(r.data)).catch(() => {});
    api.get("/branches").then((r) => setBranches(r.data)).catch(() => {});
  }, []);
  const setScope = async (uid: number, branch_id: string) => {
    await api.post(`/users/${uid}/scope`, null, { params: { branch_id: branch_id || undefined } });
    load(); setMsg("تم ضبط نطاق البيانات");
  };

  const loadMatrix = (id: number) => api.get(`/users/${id}/matrix`).then((r) => setMatrix(r.data));
  const toggleCell = (page: string, action: string) => {
    setMatrix((m: any) => ({ ...m, matrix: { ...m.matrix, [page]: { ...m.matrix[page], [action]: !m.matrix[page][action] } } }));
  };
  const saveMatrix = async () => {
    const grants: Record<string, string[]> = {};
    for (const p of mxCatalog.pages) {
      grants[p.code] = p.actions.filter((a: string) => matrix.matrix[p.code]?.[a]);
    }
    await api.post(`/users/${sel.id}/matrix`, { grants });
    setMsg("تم حفظ مصفوفة الأذونات"); loadMatrix(sel.id);
  };
  const resetMatrix = async () => {
    await api.post(`/users/${sel.id}/matrix/reset`);
    setMsg("تمت إعادة الأذونات لصلاحيات الدور"); loadMatrix(sel.id);
  };

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
    loadMatrix(u.id);
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

      <div className="table-wrap">
        <table>
          <thead><tr><th>الرقم المدني</th><th>الاسم</th><th>الدور</th><th>الحالة</th><th></th></tr></thead>
          <tbody>{users.map((u) => (
            <tr key={u.id}><td className="num">{u.civil_id}</td><td>{u.full_name}</td>
              <td><span className="pill info">{roleAr(u.role)}</span></td>
              <td>
                <select value={u.status || "active"} onChange={async (e) => {
                  await api.post(`/users/${u.id}/status`, null, { params: { status: e.target.value } }); load();
                }} style={{ width: 110, padding: "4px 8px" }}>
                  {Object.entries(USER_STATUS_AR).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </td>
              <td className="row">
                <button className="ghost sm" onClick={() => openPerms(u)}>الصلاحيات</button>
                <button className="ghost sm" onClick={() => reset(u.id)}>كلمة المرور</button>
                {me?.role === "super_admin" && u.role !== "super_admin" && (
                  <button className="ghost sm" onClick={() => impersonate(u.id)}>انتحال</button>
                )}
              </td></tr>
          ))}</tbody>
        </table>
      </div>

      {sel && matrix && (
        <div className="card" style={{ borderTop: "3px solid var(--gold)" }}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h3 style={{ margin: 0 }}>مصفوفة الأذونات الدقيقة: {sel.full_name}</h3>
            <div className="row">
              <button onClick={saveMatrix}>حفظ المصفوفة</button>
              <button className="ghost" onClick={resetMatrix}>إعادة لصلاحيات الدور</button>
            </div>
          </div>
          <p className="muted">حدّد لكل صفحة الأفعال المسموحة. الصفحة التي تُعدّلها تتجاوز صلاحيات الدور لهذا المستخدم.</p>
          <div className="row" style={{ marginBottom: 10 }}>
            <span className="muted">نطاق البيانات (تقييد بفرع):</span>
            <select value={sel.scope_branch_id || ""} onChange={(e) => setScope(sel.id, e.target.value)} style={{ width: 220 }}>
              <option value="">كل فروع الشركة</option>
              {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          </div>
          <div className="att-wrap">
            <table className="att-matrix">
              <thead>
                <tr>
                  <th className="emp">الصفحة</th>
                  {["read", "add", "edit", "delete", "print", "export", "approve"].map((a) => (
                    <th key={a} className="day" style={{ minWidth: 64 }}>{mxCatalog.actions_ar[a] || a}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {mxCatalog.pages.map((p: any) => (
                  <tr key={p.code}>
                    <td className="emp">{p.label}
                      {matrix.custom_pages.includes(p.code) && <span className="pill gold" style={{ marginInlineStart: 6 }}>مخصّص</span>}
                    </td>
                    {["read", "add", "edit", "delete", "print", "export", "approve"].map((a) => (
                      <td key={a} className="cell">
                        {p.actions.includes(a) ? (
                          <input type="checkbox" checked={!!matrix.matrix[p.code]?.[a]}
                            onChange={() => toggleCell(p.code, a)} style={{ width: "auto" }} />
                        ) : <span className="muted">—</span>}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {sel && perms && (
        <div className="card">
          <h3>الصلاحيات التفصيلية (متقدّم): {sel.full_name} <span className="muted">({roleAr(perms.role)})</span></h3>
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
