import { useEffect, useState } from "react";
import api, { errMsg } from "../api";
import { useI18n } from "../i18n";
import { statusAr, contractTypeAr } from "../labels";

// الخدمة الذاتية: ملف الموظف الشخصي — بياناته/عقده/مستنداته/إجازاته/إنذاراته + توقيعه الرقمي.
export default function MyProfile() {
  const { t, lang } = useI18n();
  const [p, setP] = useState<any>(null);
  const [err, setErr] = useState("");
  const [dlErr, setDlErr] = useState("");
  // SIG-01: حالة التوقيع
  const [sig, setSig] = useState<{ has_signature: boolean; updated_at: string | null } | null>(null);
  const [sigErr, setSigErr] = useState("");
  const [sigMsg, setSigMsg] = useState("");
  const [sigPreview, setSigPreview] = useState<string | null>(null);

  const loadSig = () => api.get("/me/signature").then((r) => {
    setSig(r.data);
    if (r.data.has_signature) {
      // نضيف timestamp cache-bust حتى يتحدث المعاينة بعد الرفع
      setSigPreview(`/api/me/signature/image?t=${Date.now()}`);
    } else {
      setSigPreview(null);
    }
  }).catch(() => setSig({ has_signature: false, updated_at: null }));

  useEffect(() => {
    api.get("/me/profile").then((r) => setP(r.data))
      .catch((e) => setErr(errMsg(e, t("error"))));
    loadSig();
  }, []);

  const uploadSig = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setSigErr(""); setSigMsg("");
    if (file.size > 500 * 1024) {
      setSigErr(t("sig_too_large"));
      e.target.value = "";
      return;
    }
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api.post("/me/signature", fd);
      setSigMsg(t("sig_uploaded"));
      loadSig();
    } catch (err: any) { setSigErr(errMsg(err, t("error"))); }
    e.target.value = "";
  };

  const deleteSig = async () => {
    if (!confirm(t("sig_confirm_delete"))) return;
    setSigErr(""); setSigMsg("");
    try {
      await api.delete("/me/signature");
      setSigMsg(t("sig_deleted"));
      loadSig();
    } catch (err: any) { setSigErr(errMsg(err, t("error"))); }
  };

  const download = async (type: string) => {
    // window.open المباشر لا يرفق رمز الدخول، فيرجع 401 (QA-P1-DOC-01)
    try {
      const res = await api.get(`/me/document/${encodeURIComponent(type)}`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data as Blob);
      window.open(url, "_blank");
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e: any) {
      setDlErr(errMsg(e, t("error")));
    }
  };

  if (err) return <div className="card empty">{err}</div>;
  if (!p) return <div className="empty">{t("loading")}</div>;
  const e = p.employee;
  const kwd = t("kwd_currency");

  return (
    <div aria-labelledby="profile-title">
      <div className="page-head">
        <div>
          <div className="eyebrow">{t("my_profile")}</div>
          <h2 id="profile-title" style={{ margin: "2px 0 0" }}>{e.name}</h2>
          <div className="sub" aria-label={`المسمى الوظيفي: ${e.job_title || "غير محدد"}`}>{e.job_title || "—"}</div>
        </div>
      </div>

      <div className="grid cards">
        <div className="card">
          <h3>{t("tab_personal")}</h3>
          <b>{t("fld_civil_id")}:</b> {e.civil_id || "—"}<br />
          <b>{t("epf_nationality")}:</b> {e.nationality || "—"}<br />
          <b>{t("epf_gender")}:</b> {e.gender === "male" ? t("gender_male") : e.gender === "female" ? t("gender_female") : "—"}<br />
          <b>{t("epf_dob")}:</b> {e.date_of_birth || "—"}<br />
          <b>{t("epf_email")}:</b> {e.email || "—"}<br />
          <b>{t("emp_phone")}:</b> {e.phone || "—"}
        </div>
        <div className="card">
          <h3>{t("my_contract")}</h3>
          <b>{t("epf_job")}:</b> {e.job_title || "—"}<br />
          <b>{t("epf_salary")}:</b> {e.basic_salary} {kwd}<br />
          <b>{t("epf_hire")}:</b> {e.hire_date || "—"}<br />
          <b>{t("epf_contract")}:</b> {contractTypeAr(e.contract_type)}<br />
          <b>{t("epf_passport")}:</b> {e.passport_number || "—"}
        </div>
      </div>

      <div className="card">
        <h3>{t("my_documents")}</h3>
        {dlErr && <div className="err">{dlErr}</div>}
        <table>
          <thead><tr><th>{t("epf_col_type")}</th><th>{t("col_title")}</th><th>{t("epf_col_version")}</th><th>{t("pro_col_expiry")}</th><th></th></tr></thead>
          <tbody>
            {p.documents.map((d: any) => (
              <tr key={d.id}><td>{d.type}</td><td>{d.title}</td><td>v{d.version}</td><td>{d.expiry_date || "—"}</td>
                <td><button className="ghost sm" onClick={() => download(d.type)}>{t("my_download")}</button></td></tr>
            ))}
            {!p.documents.length && <tr><td colSpan={5} className="muted">{t("att_no_records")}</td></tr>}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>{t("my_leaves")}</h3>
        <table>
          <thead><tr><th>{t("req_type")}</th><th>{t("req_from")}</th><th>{t("req_to")}</th><th>{t("req_days")}</th><th>{t("status")}</th></tr></thead>
          <tbody>
            {p.leaves.map((l: any) => (
              <tr key={l.id}><td>{l.type}</td><td>{l.start_date}</td><td>{l.end_date}</td><td>{l.days}</td>
                <td><span className="pill info">{statusAr(l.status)}</span></td></tr>
            ))}
            {!p.leaves.length && <tr><td colSpan={5} className="muted">{t("att_no_records")}</td></tr>}
          </tbody>
        </table>
      </div>

      {/* SIG-01: التوقيع الرقمي — الموظف يرفع صورة توقيعه فتُحقن في كل مستند رسمي مطبوع منسوب إليه */}
      <div className="card" style={{ borderTop: "3px solid var(--petrol-600)" }}>
        <h3>{t("sig_title")}</h3>
        <p className="muted" style={{ marginTop: 0 }}>{t("sig_hint")}</p>
        {sigErr && <div className="err">{sigErr}</div>}
        {sigMsg && <div className="ok">{sigMsg}</div>}
        <div className="row" style={{ alignItems: "center", gap: 24, flexWrap: "wrap" }}>
          {sigPreview ? (
            <div style={{ border: "1px solid var(--line)", padding: 12, background: "#fff",
                          minHeight: 80, minWidth: 200, borderRadius: 6 }}>
              <img src={sigPreview} alt={t("sig_preview")}
                   style={{ maxHeight: 80, maxWidth: 260, display: "block" }} />
            </div>
          ) : (
            <div className="muted" style={{ padding: 12 }}>{t("sig_none")}</div>
          )}
          <div>
            <label className="btn" style={{ cursor: "pointer" }}>
              {sig?.has_signature ? t("sig_replace") : t("sig_upload")}
              <input type="file" accept="image/png,image/jpeg" style={{ display: "none" }}
                     onChange={uploadSig} />
            </label>
            {sig?.has_signature && (
              <button className="ghost" style={{ marginInlineStart: 8 }} onClick={deleteSig}>
                {t("sig_delete")}
              </button>
            )}
            {sig?.updated_at && (
              <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>
                {t("sig_updated_at")}: {new Date(sig.updated_at).toLocaleString(lang)}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="card" style={{ borderTop: "3px solid var(--warning)" }}>
        <h3>{t("my_warnings")}</h3>
        {p.warnings.map((w: any) => (
          <div key={w.id} className="timeline-item">
            <span className="pill warning">{t("ev_warning")}</span> {w.title}
            {w.detail ? <div className="muted">{w.detail}</div> : null}
            <div className="muted">{new Date(w.date).toLocaleDateString(lang, { dateStyle: "medium" })}</div>
          </div>
        ))}
        {!p.warnings.length && <div className="muted">{t("my_no_warnings")}</div>}
      </div>
    </div>
  );
}
