import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { errMsg } from "../api";
import { useI18n } from "../i18n";
import { contractTypeAr } from "../labels";
import { fmtKuwaitDateTime, fmtKuwaitDate } from "../utils/datetime";

// الخدمة الذاتية: ملف الموظف الشخصي — بياناته/عقده/مستنداته/إجازاته/إنذاراته + توقيعه الرقمي.
export default function MyProfile() {
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  const [p, setP] = useState<any>(null);
  const [err, setErr] = useState("");
  const [dlErr, setDlErr] = useState("");
  // SIG-01: حالة التوقيع
  const [sig, setSig] = useState<{ has_signature: boolean; updated_at: string | null } | null>(null);
  const [sigErr, setSigErr] = useState("");
  const [sigMsg, setSigMsg] = useState("");
  const [sigPreview, setSigPreview] = useState<string | null>(null);
  // QA-25 — حالة الصورة منفصلة عن حقيقة "هل يوجد توقيع؟". كان الصندوق يقرأ
  // الصورة بينما "آخر تحديث" وزر الاستبدال يقرآن has_signature، فإذا فشل
  // تحميل الصورة ظهر "لم يتم رفع توقيع بعد" فوق تاريخ آخر تحديث — تناقض
  // مصدره مصدران لحقيقة واحدة لا خطأ في أيهما.
  const [sigImg, setSigImg] = useState<"idle" | "loading" | "error">("idle");

  // المعاينة تُجلب كـblob عبر axios ثم تُحوَّل لـobject URL. وضع المسار مباشرة
  // في <img src> لا يعمل: المتصفح لا يرفق ترويسة Authorization مع طلب الصورة،
  // فيرجع 401 وتظهر صورة مكسورة — نفس سبب عطل الصورة الشخصية.
  const loadSig = () => api.get("/me/signature").then(async (r) => {
    setSig(r.data);
    setSigPreview((prev) => { if (prev) URL.revokeObjectURL(prev); return null; });
    if (r.data.has_signature) {
      setSigImg("loading");
      try {
        const img = await api.get("/me/signature/image", { responseType: "blob" });
        setSigPreview(URL.createObjectURL(img.data as Blob));
        setSigImg("idle");
      } catch { setSigPreview(null); setSigImg("error"); }
    } else {
      setSigImg("idle");
    }
  }).catch(() => { setSig({ has_signature: false, updated_at: null }); setSigImg("idle"); });

  // نحرّر آخر object URL عند مغادرة الصفحة حتى لا تتسرّب الذاكرة
  useEffect(() => () => { if (sigPreview) URL.revokeObjectURL(sigPreview); }, [sigPreview]);

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

  const download = async (type: string) => {
    setDlErr("");
    // window.open المباشر لا يرفق رمز الدخول فيرجع 401 (QA-P1-DOC-01)، لذلك
    // نجلب الملف عبر axios. لكن window.open بعد await يقع خارج سياق ضغطة
    // المستخدم فيحجبه مانع النوافذ المنبثقة في المحاولات التالية — وهو ما جعل
    // التنزيل يبدو متاًحا "مرة واحدة فقط". رابط تنزيل مؤقت لا يخضع لذلك الحجب.
    try {
      const res = await api.get(`/me/document/${encodeURIComponent(type)}`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data as Blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${type}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
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
          {e.employee_no && (
            <div style={{
              display: "inline-block", marginTop: 6, background: "#e0ece8",
              color: "#0b3b38", padding: "3px 10px", borderRadius: 6,
              fontFamily: "monospace", fontWeight: 600, fontSize: 13,
            }} aria-label={`الرقم الوظيفي: ${e.employee_no}`}>
              {e.employee_no}
            </div>
          )}
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
              <tr key={d.id}><td>{d.type_label || d.type}</td><td>{d.title}</td><td>v{d.version}</td><td>{d.expiry_date || "—"}</td>
                <td><button className="ghost sm" onClick={() => download(d.type)}>{t("my_download")}</button></td></tr>
            ))}
            {!p.documents.length && <tr><td colSpan={5} className="muted">{t("att_no_records")}</td></tr>}
          </tbody>
        </table>
      </div>

      {/* قائمة "إجازاتي" أُزيلت من الخدمة الذاتية بطلب العميل: الموظف يتابع
          إجازاته من صفحة الطلبات نفسها، وعرضها هنا كان يكرر المعلومة في مكانين. */}

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
          ) : sig?.has_signature ? (
            /* QA-25 — يوجد توقيع لكن صورته لم تُحمَّل: حالة ثالثة صريحة، لا "لا يوجد توقيع" */
            <div className="muted" style={{ padding: 12 }}>
              {sigImg === "error" ? t("sig_preview_failed") : t("loading")}
            </div>
          ) : (
            <div className="muted" style={{ padding: 12 }}>{t("sig_none")}</div>
          )}
          <div>
            {/* أول رفع يتم هنا مباشرة. أما الاستبدال فيمر بطلب رسمي: التوقيع
                دليل يُحتجّ به على المستندات، فتغييره يحتاج سببًا مسجَّلًا
                واعتماد HR. كان زر الاستبدال يرفع الملف مباشرة بلا سبب فيرفضه
                الخادم بـ400 «سبب استبدال التوقيع إلزامي» — وهو الخطأ المُبلَّغ. */}
            {sig?.has_signature ? (
              <button onClick={() => navigate("/requests?type=REQSIG&new=1")}>
                {t("sig_replace")}
              </button>
            ) : (
              <label className="btn" style={{ cursor: "pointer" }}>
                {t("sig_upload")}
                <input type="file" accept="image/png,image/jpeg" style={{ display: "none" }}
                       onChange={uploadSig} />
              </label>
            )}
            {/* زر حذف التوقيع أُزيل: التوقيع مرجع للمستندات الموقَّعة سابًقا،
                وحذفه من الموظف مباشرة يترك تلك المستندات بلا سند. */}
            {sig?.updated_at && (
              <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>
                {t("sig_updated_at")}: {fmtKuwaitDateTime(sig.updated_at, lang)}
              </div>
            )}
          </div>
        </div>
      </div>

      {p.may_receive_warning !== false && (
      <div className="card" style={{ borderTop: "3px solid var(--warning)" }}>
        <h3>{t("my_warnings")}</h3>
        {p.warnings.map((w: any) => (
          <div key={w.id} className="timeline-item">
            <span className="pill warning">{t("ev_warning")}</span> {w.title}
            {w.detail ? <div className="muted">{w.detail}</div> : null}
            <div className="muted">{fmtKuwaitDate(w.date, lang)}</div>
          </div>
        ))}
        {!p.warnings.length && <div className="muted">{t("my_no_warnings")}</div>}
      </div>
      )}
    </div>
  );
}
