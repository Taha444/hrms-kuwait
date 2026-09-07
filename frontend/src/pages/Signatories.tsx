import { useEffect, useState } from "react";
import api, { errMsg } from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";

/**
 * SEC2-15 — سجل المخوّلين بالتوقيع.
 *
 * **لماذا شاشة**: السجل كان يُقرأ عند توليد كل مستند رسمي
 * (`workflow.generate_document` → `resolve_authorized_signatory`) ولا
 * سبيل إلى الكتابة فيه إلا بالواجهة البرمجية. فكل شركة تبقى على المسار
 * الاحتياطي: توقيع **آخر معتمِد** على الورقة، وبلا عنوان وظيفي أصًلا.
 *
 * **والفخّ الصامت معروض لا مخفيّ**: مخوّل بلا صورة توقيع محفوظة يسقط إلى
 * الاحتياط بلا خطأ. فيقرأ المالك سجًلا مكتمًلا والمستندات تخرج بتوقيع
 * غيره. لذلك `has_signature` من الخادم — بنفس شرط التوليد — ولافتة
 * صريحة عند نقصه.
 */

type Sig = {
  id: number; user_id: number; user_name: string | null;
  title_ar: string; title_en: string | null;
  scope_type: string; scope_value: string | null;
  effective_from: string | null; effective_to: string | null;
  is_active: boolean; has_signature: boolean;
};

const EMPTY = {
  user_id: 0, title_ar: "", title_en: "",
  scope_type: "any", scope_value: "",
  effective_from: "", effective_to: "", notes: "",
};

export default function Signatories() {
  const { t, lang } = useI18n();
  const { can, user } = useAuth();
  const manage = can("manage_users");
  // SIG-REPL — اعتماد استبدال التوقيع مقتصر على الموارد البشرية في الخادم.
  const isHr = user?.role === "hr" || user?.role === "super_admin";

  const [rows, setRows] = useState<Sig[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [showInactive, setShowInactive] = useState(false);
  const [form, setForm] = useState<any>(EMPTY);
  const [editing, setEditing] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const load = () => {
    api.get("/signatories", { params: { include_inactive: showInactive } })
      .then((r) => setRows(r.data)).catch((e) => setErr(errMsg(e, t("error"))));
  };
  useEffect(() => { load(); }, [showInactive]);
  useEffect(() => {
    if (!manage) return;
    api.get("/users").then((r) => setUsers(r.data.filter((u: any) => u.is_active)))
      .catch(() => {});
  }, [manage]);

  // SIG-REPL — استبدال التوقيع ينشئ **مهمة حرجة** للموارد البشرية تقول
  // «راجِع الاستبدال واعتمده»، ولم تكن في النظام شاشة تعتمده. فالمهمة
  // تأمر بفعل لا سبيل إليه، والتوقيع القديم يبقى نشًطا بلا قرار.
  const [pending, setPending] = useState<any[]>([]);
  const [pendingImg, setPendingImg] = useState<Record<number, string>>({});
  const loadPending = () => {
    if (!isHr) return;
    api.get("/signatures/pending").then((r) => setPending(r.data)).catch(() => {});
  };
  useEffect(() => { loadPending(); }, [isHr]);

  const reset = () => { setForm(EMPTY); setEditing(null); };

  const submit = async () => {
    setErr(""); setMsg("");
    if (!form.user_id) { setErr(t("sig_pick_user")); return; }
    if (!form.title_ar.trim()) { setErr(t("sig_title_required")); return; }
    // الخادم يشترطها مع نطاق مخصَّص — تُطلَب هنا بدل أن يُردّ الطلب بخطأ.
    if (form.scope_type !== "any" && !form.scope_value.trim()) {
      setErr(t("sig_scope_value_required")); return;
    }
    const body = {
      user_id: Number(form.user_id),
      title_ar: form.title_ar.trim(),
      title_en: form.title_en.trim() || null,
      scope_type: form.scope_type,
      scope_value: form.scope_type === "any" ? null : form.scope_value.trim(),
      effective_from: form.effective_from || null,
      effective_to: form.effective_to || null,
      notes: form.notes.trim() || null,
    };
    setBusy(true);
    try {
      if (editing) await api.put(`/signatories/${editing}`, body);
      else await api.post("/signatories", body);
      setMsg(editing ? t("sig_updated") : t("sig_added"));
      reset(); load();
    } catch (e: any) { setErr(errMsg(e, t("error"))); }
    finally { setBusy(false); }
  };

  const edit = (s: Sig) => {
    setEditing(s.id);
    setForm({
      user_id: s.user_id, title_ar: s.title_ar, title_en: s.title_en || "",
      scope_type: s.scope_type, scope_value: s.scope_value || "",
      effective_from: s.effective_from || "", effective_to: s.effective_to || "",
      notes: "",
    });
  };

  const deactivate = async (s: Sig) => {
    if (!window.confirm(t("sig_deactivate_confirm").replace("{n}", s.title_ar))) return;
    setBusy(true); setErr(""); setMsg("");
    try {
      await api.delete(`/signatories/${s.id}`);
      setMsg(t("sig_deactivated")); load();
    } catch (e: any) { setErr(errMsg(e, t("error"))); }
    finally { setBusy(false); }
  };

  const scopeLabel = (s: Sig) =>
    s.scope_type === "any" ? t("sig_scope_any")
      : `${t(`sig_scope_${s.scope_type}`)}: ${s.scope_value}`;

  const showPending = async (uid: number) => {
    if (pendingImg[uid]) { setPendingImg({ ...pendingImg, [uid]: "" }); return; }
    try {
      const r = await api.get(`/signatures/pending/${uid}/image`, { responseType: "blob" });
      setPendingImg({ ...pendingImg, [uid]: URL.createObjectURL(r.data) });
    } catch (e: any) { setErr(errMsg(e, t("error"))); }
  };

  const decidePending = async (uid: number, action: "approve" | "reject") => {
    setErr(""); setMsg("");
    let params: any = undefined;
    if (action === "reject") {
      const reason = window.prompt(t("sig_reject_reason"));
      if (!reason || !reason.trim()) return;
      params = { reason: reason.trim() };
    }
    try {
      await api.post(`/signatures/pending/${uid}/${action}`, null, { params });
      setMsg(t(action === "approve" ? "sig_pending_approved" : "sig_pending_rejected"));
      loadPending();
    } catch (e: any) { setErr(errMsg(e, t("error"))); }
  };

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="eyebrow">{t("sig_eyebrow")}</div>
          <h2 style={{ margin: "2px 0 0" }}>{t("sig_reg_title")}</h2>
          <div className="sub">{t("sig_sub")}</div>
        </div>
        <div className="row">
          {/* لا ``row`` داخل ``row``: الأولى تُكدّس المربّع فوق نصّه */}
          <label style={{ display: "inline-flex", alignItems: "center",
                          gap: 6, fontSize: 13, whiteSpace: "nowrap" }}>
            <input type="checkbox" checked={showInactive}
                   onChange={(e) => setShowInactive(e.target.checked)} />
            {t("sig_show_inactive")}
          </label>
          <button className="ghost" onClick={load}>{t("refresh")}</button>
        </div>
      </div>

      {msg && <div className="ok">{msg}</div>}
      {err && <div className="err">{err}</div>}

      {/* SIG-REPL — طابور الاستبدالات: المهمة الحرجة تُرسَل إلى الموارد
          البشرية وتقول «اعتمِد»، وكان الاعتماد بلا شاشة. */}
      {isHr && pending.length > 0 && (
        <div className="card" style={{ borderInlineStart: "3px solid var(--warning)" }}>
          <h3 style={{ marginTop: 0 }}>{t("sig_pending_title")} ({pending.length})</h3>
          <div className="sub" style={{ marginBottom: 8 }}>{t("sig_pending_hint")}</div>
          <div className="table-wrap">
            <table>
              <thead><tr>
                <th>{t("col_employee")}</th><th>{t("sig_pending_reason")}</th>
                <th>{t("sig_pending_at")}</th><th></th>
              </tr></thead>
              <tbody>
                {pending.map((p) => (
                  <tr key={p.user_id}>
                    <td><b>{p.full_name}</b><br /><span className="muted">{p.civil_id}</span></td>
                    <td>
                      {p.reason || "—"}
                      {pendingImg[p.user_id] && (
                        <div style={{ marginTop: 6 }}>
                          <img src={pendingImg[p.user_id]} alt={t("sig_pending_view")}
                               style={{ maxHeight: 80, background: "#fff",
                                        border: "1px solid var(--line)", padding: 4 }} />
                        </div>
                      )}
                    </td>
                    <td className="muted">{p.uploaded_at?.slice(0, 16).replace("T", " ")}</td>
                    <td>
                      <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
                        {/* القرار على صورة تُرى لا على اسم يُقرأ. والصورة
                            تُجلَب بالرمز: رابٌط مباشر يعود 401 صامًتا. */}
                        <button className="ghost sm" onClick={() => showPending(p.user_id)}>
                          {t("sig_pending_view")}
                        </button>
                        <button className="sm" onClick={() => decidePending(p.user_id, "approve")}>
                          {t("sig_pending_approve")}
                        </button>
                        <button className="ghost sm" onClick={() => decidePending(p.user_id, "reject")}>
                          {t("sig_pending_reject")}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ما يحدث بلا سجل — مكتوب لا مفترَض */}
      {rows.filter((s) => s.is_active).length === 0 && (
        <div className="card" style={{ borderInlineStart: "3px solid var(--gold)" }}>
          <b>{t("sig_none_title")}</b>
          <div className="sub" style={{ marginTop: 4 }}>{t("sig_none_hint")}</div>
        </div>
      )}

      <div className="card">
        <table className="table">
          <thead>
            <tr>
              <th>{t("sig_signer")}</th>
              <th>{t("sig_job_title")}</th>
              <th>{t("sig_scope")}</th>
              <th>{t("sig_period")}</th>
              <th>{t("status")}</th>
              {manage && <th />}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr><td colSpan={manage ? 6 : 5} className="muted">{t("no_data")}</td></tr>
            )}
            {rows.map((s) => (
              <tr key={s.id} style={{ opacity: s.is_active ? 1 : 0.55 }}>
                <td>
                  {s.user_name || `#${s.user_id}`}
                  {/* الفخّ الصامت: بلا صورة توقيع يسقط إلى الاحتياط */}
                  {s.is_active && !s.has_signature && (
                    <span className="pill warn" style={{ marginInlineStart: 6 }}
                          title={t("sig_no_image_hint")}>
                      {t("sig_no_image")}
                    </span>
                  )}
                </td>
                <td>{lang === "en" && s.title_en ? s.title_en : s.title_ar}</td>
                <td>{scopeLabel(s)}</td>
                <td className="sub">
                  {s.effective_from || "—"} → {s.effective_to || "—"}
                </td>
                <td>
                  <span className={`pill ${s.is_active ? "completed" : "neutral"}`}>
                    {s.is_active ? t("sig_active") : t("sig_inactive")}
                  </span>
                </td>
                {manage && (
                  <td>
                    <div className="row">
                      <button className="ghost sm" onClick={() => edit(s)}>{t("edit")}</button>
                      {s.is_active && (
                        <button className="ghost sm" disabled={busy}
                                style={{ color: "var(--danger)" }}
                                onClick={() => deactivate(s)}>{t("sig_deactivate")}</button>
                      )}
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {manage && (
        <div className="card">
          <h3>{editing ? t("sig_edit_title") : t("sig_add_title")}</h3>
          <div className="row">
            <div className="field">
              <label htmlFor="sig-user">{t("sig_signer")} *</label>
              <select id="sig-user" value={form.user_id} disabled={!!editing}
                      onChange={(e) => setForm({ ...form, user_id: e.target.value })}>
                <option value={0}>—</option>
                {users.map((u) => (
                  <option key={u.id} value={u.id}>{u.full_name || u.civil_id}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="sig-title-ar">{t("sig_job_title")} *</label>
              <input id="sig-title-ar" value={form.title_ar}
                     onChange={(e) => setForm({ ...form, title_ar: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="sig-title-en">{t("sig_job_title_en")}</label>
              <input id="sig-title-en" value={form.title_en}
                     onChange={(e) => setForm({ ...form, title_en: e.target.value })} />
            </div>
          </div>

          <div className="row">
            <div className="field">
              <label htmlFor="sig-scope">{t("sig_scope")}</label>
              <select id="sig-scope" value={form.scope_type}
                      onChange={(e) => setForm({ ...form, scope_type: e.target.value })}>
                <option value="any">{t("sig_scope_any")}</option>
                <option value="code">{t("sig_scope_code")}</option>
                <option value="prefix">{t("sig_scope_prefix")}</option>
                <option value="category">{t("sig_scope_category")}</option>
              </select>
            </div>
            {form.scope_type !== "any" && (
              <div className="field">
                <label htmlFor="sig-scope-value">{t("sig_scope_value")} *</label>
                <input id="sig-scope-value" value={form.scope_value}
                       placeholder={form.scope_type === "prefix" ? "HRMS-PR-" : "HRMS-PR-017"}
                       onChange={(e) => setForm({ ...form, scope_value: e.target.value })} />
              </div>
            )}
            <div className="field">
              <label htmlFor="sig-from">{t("sig_from")}</label>
              <input id="sig-from" type="date" value={form.effective_from}
                     onChange={(e) => setForm({ ...form, effective_from: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="sig-to">{t("sig_to")}</label>
              <input id="sig-to" type="date" value={form.effective_to}
                     onChange={(e) => setForm({ ...form, effective_to: e.target.value })} />
            </div>
          </div>

          <div className="sub" style={{ marginBottom: 8 }}>{t("sig_scope_hint")}</div>

          <div className="row">
            <button disabled={busy} onClick={submit}>
              {editing ? t("save") : t("sig_add")}
            </button>
            {editing && <button className="ghost" onClick={reset}>{t("cancel")}</button>}
          </div>
        </div>
      )}
    </div>
  );
}
