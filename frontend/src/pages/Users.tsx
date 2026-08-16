import { useEffect, useState } from "react";
import api, { errMsg } from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import { roleAr } from "../labels";

const ACTIONS = ["read", "add", "edit", "delete", "print", "export", "approve"];

export default function Users() {
  const { user: me, impersonate } = useAuth();
  const { t } = useI18n();
  const USER_STATUS: Record<string, string> = {
    active: t("user_status_active"), inactive: t("user_status_inactive"),
    suspended: t("user_status_suspended"), locked: t("user_status_locked"),
  };
  const actionLabel = (a: string) => t(`act_${a}`);
  const [users, setUsers] = useState<any[]>([]);
  const [catalog, setCatalog] = useState<any>({ permissions: {}, templates: {}, roles: [] });
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState<any>({ civil_id: "", full_name: "", role: "employee" });
  const [sel, setSel] = useState<any>(null);
  const [perms, setPerms] = useState<any>(null);
  const [mxCatalog, setMxCatalog] = useState<any>({ pages: [], actions_ar: {} });
  const [matrix, setMatrix] = useState<any>(null); // {matrix, custom_pages}
  const [msg, setMsg] = useState("");
  // الكلمة المؤقّتة تُعرض في نافذة عند موضع الزر لا في شريط أعلى الصفحة:
  // الزر داخل صف في جدول طويل، والشريط يظهر خارج الشاشة فيبدو أن شيًئا
  // لم يحدث. ونافذة تُغلق بقصد تمنع بقاء كلمة مرور معروضة على شاشة مهجورة.
  const [pwInfo, setPwInfo] = useState<{ name: string; pw: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const [err, setErr] = useState("");

  const [branches, setBranches] = useState<any[]>([]);
  const load = () => api.get("/users").then((r) => setUsers(r.data));
  useEffect(() => {
    load();
    api.get("/users/catalog").then((r) => setCatalog(r.data));
    api.get("/users/permission-matrix").then((r) => setMxCatalog(r.data)).catch(() => {});
    api.get("/branches").then((r) => setBranches(r.data)).catch(() => {});
  }, []);
  // ضبط مستوى نطاق البيانات: company | branch | multi | self
  const setScope = async (uid: number, level: string, branchId?: string, branchIds?: number[]) => {
    await api.post(`/users/${uid}/scope`, null, {
      params: { level, branch_id: branchId || undefined, branch_ids: branchIds || undefined },
    });
    load();
    if (sel?.id === uid) setSel({ ...sel, scope_level: level, scope_branch_id: branchId ? +branchId : null });
    setMsg(t("user_scope_set"));
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
    setMsg(t("user_matrix_saved")); loadMatrix(sel.id);
  };
  const resetMatrix = async () => {
    await api.post(`/users/${sel.id}/matrix/reset`);
    setMsg(t("user_matrix_reset")); loadMatrix(sel.id);
  };

  const create = async () => {
    setErr("");
    try {
      const r = await api.post("/users", form);
      setShowNew(false); load();
      if (r.data?.temporary_password) {
        setCopied(false);
        setPwInfo({ name: r.data.full_name || form.civil_id, pw: r.data.temporary_password });
      }
    }
    catch (e: any) { setErr(errMsg(e, t("error"))); }
  };
  const toggle = async (id: number) => { await api.post(`/users/${id}/toggle`); load(); };
  const reset = async (id: number, name: string) => {
    setErr("");
    try {
      const r = await api.post("/auth/reset-password", { user_id: id });
      setCopied(false);
      setPwInfo({ name: r.data.full_name || name, pw: r.data.temporary_password });
    } catch (e: any) {
      // بلا هذا، فشل إعادة التعيين كان يمرّ بلا أي أثر على الشاشة
      setErr(errMsg(e, t("error")));
    }
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

  // R9 §14 — auto-link report state
  const [linkReport, setLinkReport] = useState<any | null>(null);
  const [linkBusy, setLinkBusy] = useState(false);
  const runAutoLink = async () => {
    setLinkBusy(true); setErr(""); setMsg("");
    try {
      const r = await api.post("/users/auto-link-employees");
      setLinkReport(r.data);
      const n = r.data.linked?.length || 0;
      setMsg(n > 0
        ? `تم ربط ${n} حساب بموظفاتهم`
        : "لا حسابات جديدة للربط — كل الحسابات مربوطة بالفعل");
      load();
    } catch (e: any) { setErr(errMsg(e, t("error"))); }
    finally { setLinkBusy(false); }
  };

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2>{t("users_title")}</h2>
        <div className="row" style={{ gap: 8 }}>
          <button onClick={runAutoLink} disabled={linkBusy} className="ghost"
                  title="يربط أي حساب بلا employee بموظف مطابق نفس الرقم المدني والشركة">
            🔗 ربط تلقائي بالموظفين
          </button>
          <button onClick={() => setShowNew((s) => !s)}>{t("user_new")}</button>
        </div>
      </div>
      {msg && <div className="ok">{msg}</div>}
      {linkReport && (
        <div className="card" style={{ borderInlineStart: "4px solid var(--brand)", marginBottom: 12 }}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h4 style={{ margin: 0 }}>تقرير الربط التلقائي</h4>
            <button className="ghost sm" onClick={() => setLinkReport(null)}>×</button>
          </div>
          <div style={{ fontSize: 13, marginTop: 8 }}>
            <div>✓ <b>{linkReport.linked?.length || 0}</b> ربط ناجح</div>
            {linkReport.no_employee?.length > 0 && (
              <div style={{ color: "#b45309" }}>
                ⚠ <b>{linkReport.no_employee.length}</b> حساب بدون موظف مطابق — يحتاج إنشاء Employee record:
                <ul style={{ marginTop: 4 }}>
                  {linkReport.no_employee.slice(0, 5).map((x: any) => (
                    <li key={x.user_id}>{x.role} — {x.name} ({x.civil_id})</li>
                  ))}
                  {linkReport.no_employee.length > 5 && <li>... و{linkReport.no_employee.length - 5} آخرين</li>}
                </ul>
              </div>
            )}
            {linkReport.conflicts?.length > 0 && (
              <div style={{ color: "var(--danger)" }}>
                ⚠ <b>{linkReport.conflicts.length}</b> تعارض (الموظف مربوط بحساب آخر)
              </div>
            )}
            <div className="muted" style={{ marginTop: 4 }}>
              فُحص إجمالاً: {linkReport.total_scanned} حساب unlinked
            </div>
          </div>
        </div>
      )}

      {showNew && (
        <div className="card">
          <div className="row">
            <div className="field" style={{ flex: 1 }}><label htmlFor="usr-civil-id">{t("user_civil_id")}</label>
              <input id="usr-civil-id" onChange={(e) => setForm({ ...form, civil_id: e.target.value })} /></div>
            <div className="field" style={{ flex: 1 }}><label htmlFor="usr-name">{t("user_name")}</label>
              <input id="usr-name" onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></div>
            <div className="field" style={{ flex: 1 }}><label htmlFor="usr-role">{t("user_role")}</label>
              <select id="usr-role" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                {(catalog.assignable_roles || catalog.roles).map((r: string) => <option key={r} value={r}>{roleAr(r)}</option>)}
              </select></div>
          </div>
          <p className="muted">{t("user_default_pw_hint")}</p>
          {err && <div className="err">{err}</div>}
          <button onClick={create}>{t("save")}</button>
        </div>
      )}

      <div className="table-wrap">
        <table>
          <thead><tr><th>{t("user_civil_id")}</th><th>{t("user_name")}</th><th>{t("user_role")}</th><th>{t("status")}</th><th></th></tr></thead>
          <tbody>{users.map((u) => (
            <tr key={u.id}><td className="num">{u.civil_id}</td><td>{u.full_name}</td>
              <td><span className="pill info">{roleAr(u.role)}</span></td>
              <td>
                <select aria-label={t("status")} value={u.status || "active"} onChange={async (e) => {
                  await api.post(`/users/${u.id}/status`, null, { params: { status: e.target.value } }); load();
                }} style={{ width: 110, padding: "4px 8px" }}>
                  {Object.entries(USER_STATUS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </td>
              <td className="row">
                <button className="ghost sm" onClick={() => openPerms(u)}>{t("user_perms")}</button>
                <button className="ghost sm" onClick={() => reset(u.id, u.full_name)}>{t("user_password")}</button>
                {me?.role === "super_admin" && u.role !== "super_admin" && (
                  <button className="ghost sm" onClick={() => impersonate(u.id)}>{t("user_impersonate")}</button>
                )}
              </td></tr>
          ))}</tbody>
        </table>
      </div>

      {sel && matrix && (
        <div className="card" style={{ borderTop: "3px solid var(--gold)" }}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h3 style={{ margin: 0 }}>{t("user_matrix_title")}: {sel.full_name}</h3>
            <div className="row">
              <button onClick={saveMatrix}>{t("user_save_matrix")}</button>
              <button className="ghost" onClick={resetMatrix}>{t("user_reset_role")}</button>
            </div>
          </div>
          <p className="muted">{t("user_matrix_hint")}</p>
          <div className="row" style={{ marginBottom: 10, flexWrap: "wrap" }}>
            <span className="muted">{t("user_data_scope")}</span>
            <select aria-label={t("user_data_scope")} value={sel.scope_level || "company"}
              onChange={(e) => {
                const lvl = e.target.value;
                // company/self لا يحتاجان فرعًا؛ branch يبدأ بأول فرع متاح
                if (lvl === "branch") setScope(sel.id, "branch", String(sel.scope_branch_id || branches[0]?.id || ""));
                else setScope(sel.id, lvl);
              }} style={{ width: 200 }}>
              <option value="company">{t("scope_company")}</option>
              <option value="branch">{t("scope_branch")}</option>
              <option value="multi">{t("scope_multi")}</option>
              <option value="self">{t("scope_self")}</option>
            </select>
            {sel.scope_level === "branch" && (
              <select aria-label={t("scope_branch")} value={sel.scope_branch_id || ""} onChange={(e) => setScope(sel.id, "branch", e.target.value)} style={{ width: 200 }}>
                <option value="" disabled>{t("opt_choose")}</option>
                {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
              </select>
            )}
            {sel.scope_level === "multi" && (
              <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
                {branches.map((b) => (
                  <label key={b.id} className="muted" style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    <input type="checkbox" style={{ width: "auto" }}
                      checked={(sel.scope_branch_ids || []).includes(b.id)}
                      onChange={(e) => {
                        const cur: number[] = sel.scope_branch_ids || [];
                        const next = e.target.checked ? [...cur, b.id] : cur.filter((x) => x !== b.id);
                        setSel({ ...sel, scope_branch_ids: next });
                        if (next.length) setScope(sel.id, "multi", undefined, next);
                      }} />
                    {b.name}
                  </label>
                ))}
              </div>
            )}
          </div>
          <div className="att-wrap">
            <table className="att-matrix">
              <thead>
                <tr>
                  <th className="emp">{t("user_page")}</th>
                  {ACTIONS.map((a) => (
                    <th key={a} className="day" style={{ minWidth: 64 }}>{actionLabel(a)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {mxCatalog.pages.map((p: any) => (
                  <tr key={p.code}>
                    <td className="emp">{p.label}
                      {matrix.custom_pages.includes(p.code) && <span className="pill gold" style={{ marginInlineStart: 6 }}>{t("user_custom")}</span>}
                    </td>
                    {ACTIONS.map((a) => (
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
          <h3>{t("user_adv_title")}: {sel.full_name} <span className="muted">({roleAr(perms.role)})</span></h3>
          <div className="row" style={{ marginBottom: 10 }}>
            <span className="muted">{t("user_apply_template")}</span>
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

      {pwInfo && (
        <div role="dialog" aria-modal="true"
             style={{ position: "fixed", inset: 0, background: "rgba(11,59,84,0.5)",
                     display: "grid", placeItems: "center", zIndex: 1500, padding: 20 }}>
          <div style={{ background: "white", borderRadius: 12, padding: 24,
                       maxWidth: 440, width: "100%" }}>
            <h3 style={{ marginTop: 0 }}>{t("pw_once_title")}</h3>
            <p className="muted" style={{ marginTop: 0 }}>
              {t("pw_once_for", { name: pwInfo.name })}
            </p>
            <div style={{ display: "flex", gap: 8, alignItems: "center", margin: "16px 0" }}>
              <code style={{ flex: 1, fontSize: 20, letterSpacing: 1, padding: "12px 14px",
                            background: "var(--bg, #f4f6f8)", borderRadius: 8,
                            direction: "ltr", textAlign: "center", userSelect: "all" }}>
                {pwInfo.pw}
              </code>
              <button className="ghost" onClick={() => {
                navigator.clipboard?.writeText(pwInfo.pw).then(() => setCopied(true),
                                                               () => setCopied(false));
              }}>{copied ? t("copied") : t("copy")}</button>
            </div>
            <div className="warn" style={{ fontSize: 13 }}>{t("pw_once_warning")}</div>
            <div className="row" style={{ justifyContent: "flex-end", marginTop: 16 }}>
              <button onClick={() => { setPwInfo(null); setCopied(false); }}>
                {t("pw_once_saved")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
