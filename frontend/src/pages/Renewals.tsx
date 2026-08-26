import { useEffect, useRef, useState } from "react";
import { openAndPrint } from "../printDoc";
import api, { errMsg } from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import { fmtKuwaitDateTime } from "../utils/datetime";

// معاملات تجديد الإقامة (DEMO-001/002) — قائمة + تفاصيل بأفعال حسب الدور والحالة.
const ST_PILL: Record<string, string> = {
  rejected: "critical", completed: "success", new: "info",
  pending_manager: "warning", pending_hr: "warning", awaiting_signature: "warning",
  awaiting_civil_card: "warning", awaiting_contracts: "info", contracts_signed: "info",
  renewing: "info", with_delegate: "info", pending_hr_verify: "warning",
};

// R4 §7 — تسميات الحالات الجديدة (لتفادي التبعية على i18n)
const ST_LABEL: Record<string, string> = {
  new: "طلب جديد",
  pending_manager: "بانتظار موافقة المدير",
  pending_hr: "بانتظار HR",
  rejected: "مرفوض",
  with_delegate: "محوّل للمندوب",
  awaiting_contracts: "بانتظار العقود",
  awaiting_signature: "بانتظار توقيع الموظف",
  contracts_signed: "العقود موقّعة",
  renewing: "جاري التجديد",
  awaiting_civil_card: "بانتظار البطاقة المدنية",
  pending_hr_verify: "بانتظار تحقق HR",
  completed: "مكتملة",
};

export default function Renewals() {
  const { t, lang } = useI18n();
  const { user, can } = useAuth();
  const [items, setItems] = useState<any[]>([]);
  const [sel, setSel] = useState<any>(null);
  // RNW-21 — قصة المعاملة. تُجلب عند اختيارها لا مع القائمة: القائمة تُحدَّث
  // كل بضع ثوانٍ، وجلب قصة كل معاملة معها استعلام لا يقرؤه أحد.
  const [timeline, setTimeline] = useState<any[]>([]);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [reason, setReason] = useState("");
  const [notes, setNotes] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const isEmp = !!user?.employee_id;
  const isPro = can("manage_permits") || can("process_delegate_tasks");
  const isMgr = user?.role === "company_manager" || user?.role === "super_admin";
  const isHr = user?.role === "hr" || user?.role === "super_admin";

  // QA-05 — إقامات تستحق التجديد ولم يُفتح لها ملف. صفحة التجديدات تعرض
  // الملفات المبدوءة، ومركز العمليات يعرض الإقامات المقتربة من الانتهاء —
  // فرأى المستخدم "حالة حرجة" هناك وفراًغا هنا وقرأه عطًلا.
  const [duePermits, setDuePermits] = useState<any[]>([]);
  // RNW-01 — التنبيه المختار. البطاقات في «تستحق ولم يُفتح لها ملف» كانت
  // صفوف جدول بلا onClick، فالضغط لا يرسل طلًبا ولا يفتح شيًئا — تجاهل صامت.
  // اختياره منفصل عن اختيار المعاملة لأنهما نوعان مختلفان: الأول تنبيه محسوب
  // بلا سجل، والثاني معاملة لها رقم.
  const [selDue, setSelDue] = useState<any>(null);

  const load = () => {
    api.get("/renewals/due/permits").then((r) => setDuePermits(r.data)).catch(() => setDuePermits([]));
    return api.get("/renewals").then((r) => {
      setItems(r.data);
      if (sel) { const u = r.data.find((x: any) => x.id === sel.id); if (u) setSel(u); }
    }).catch((e) => setErr(errMsg(e, t("error"))));
  };

  // R9 §11 — تحقق من وجود قالب العقد الحكومي عند التحميل
  const [govContractTplExists, setGovContractTplExists] = useState<boolean | null>(null);
  useEffect(() => {
    api.get("/templates/exists", { params: { codes: "GOV-CONTRACT-RENEWAL" } })
      .then((r) => setGovContractTplExists(!!r.data["GOV-CONTRACT-RENEWAL"]))
      .catch(() => setGovContractTplExists(null));  // لا نُظهر التحذير عند فشل الاتصال
  }, []);
  useEffect(() => { load(); }, []);

  const act = async (fn: () => Promise<any>, ok?: string) => {
    setErr(""); setMsg("");
    try { await fn(); if (ok) setMsg(ok); await load(); }
    catch (e: any) { setErr(errMsg(e, t("error"))); }
  };

  // RNW-02 — تحويل التنبيه إلى معاملة. الفارق عن createMine أن هذا يمرّر
  // employee_id و permit_id صراحة: بدونهما يقع الخادم على user.employee_id
  // فيفتح ملًفا للمستخدم نفسه لا لصاحب البطاقة — وحساب بلا سجل موظف يُرفض
  // برسالة "لم يُحدَّد الموظف"، وهو ما كان يحدث فعًلا.
  const startCase = (d: any) => act(async () => {
    const fd = new FormData();
    fd.append("employee_id", String(d.employee_id));
    fd.append("permit_id", String(d.permit_id));
    if (reason) fd.append("reason", reason);
    if (notes) fd.append("notes", notes);
    const r = await api.post("/renewals", fd);
    setReason(""); setNotes("");
    setSelDue(null);      // التنبيه صار معاملة — ينتقل من مجموعة لأخرى
    setSel(r.data);
  }, t("rnw_case_started"));

  const createMine = () => act(async () => {
    const fd = new FormData();
    if (reason) fd.append("reason", reason);
    if (notes) fd.append("notes", notes);
    const r = await api.post("/renewals", fd);
    setReason(""); setNotes(""); setSel(r.data);
  }, t("rnw_created"));

  const decide = (decision: string) => act(async () => {
    if (decision === "rejected" && !rejectReason.trim()) { setErr(t("rnw_reject_reason")); throw new Error(); }
    const fd = new FormData();
    fd.append("decision", decision);
    if (rejectReason) fd.append("reject_reason", rejectReason);
    await api.post(`/renewals/${sel.id}/decide`, fd);
    setRejectReason("");
  });

  const uploadDoc = (docType: string) => {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("doc_type", docType); fd.append("file", file);
    act(async () => {
      await api.post(`/renewals/${sel.id}/upload`, fd);
      if (fileRef.current) fileRef.current.value = "";
    });
  };

  const setRenewing = () => act(() => api.post(`/renewals/${sel.id}/renewing`));

  // R8 §3 — توليد العقد الحكومي (يفتح نافذة جديدة بالـHTML للطباعة مباشرة)
  const generateGovContract = () => act(async () => {
    const r = await api.post(`/renewals/${sel.id}/gov-contract/generate`);
    if (!openAndPrint(r.data.html)) {
      setErr("مانع النوافذ المنبثقة منع فتح العقد — اسمح بالنوافذ لهذا الموقع ثم أعد المحاولة.");
    }
  }, "✓ تم توليد العقد الحكومي — اطبعه ووقّعه ثم ارفع النسخة الموقّعة");

  // R4 §7 — Finalize (PRO يعبّي بيانات المعاملة الحكومية)
  const [gov, setGov] = useState({
    gov_reference_no: "", fees_amount: "", fees_receipt_no: "",
    new_permit_number: "", new_expiry_date: "",
  });
  const finalize = () => {
    if (!gov.gov_reference_no.trim() || !gov.new_permit_number.trim() || !gov.new_expiry_date) {
      setErr("الرقم المرجعي + رقم الإقامة الجديد + تاريخ الانتهاء إلزامية"); return;
    }
    act(async () => {
      const fd = new FormData();
      Object.entries(gov).forEach(([k, v]) => fd.append(k, v));
      await api.post(`/renewals/${sel.id}/finalize`, fd);
      setGov({ gov_reference_no: "", fees_amount: "", fees_receipt_no: "",
               new_permit_number: "", new_expiry_date: "" });
    }, "✓ تم تسجيل بيانات المعاملة الحكومية");
  };

  // R4 §7 — HR verification (يقفل المعاملة بعد التحقق من التطابق)
  const [hrNote, setHrNote] = useState("");
  const hrVerify = () => act(async () => {
    const fd = new FormData();
    if (hrNote) fd.append("note", hrNote);
    await api.post(`/renewals/${sel.id}/hr-verify`, fd);
    setHrNote("");
  }, "✓ تم التحقق وإغلاق المعاملة");
  const download = async (dt: string) => {
    setErr("");
    try {
      // window.open المباشر لا يرفق رمز الدخول، فيرجع 401 — نجلب الملف بالرمز ونعرضه كـ blob
      const res = await api.get(`/renewals/${sel.id}/document/${dt}`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data as Blob);
      window.open(url, "_blank");
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e: any) { setErr(errMsg(e, t("error"))); }
  };
  const hasDoc = (dt: string) => sel?.documents?.some((d: any) => d.type === dt);

  // زر رفع بملف مخفي
  const UploadBtn = ({ docType, label }: { docType: string; label: string }) => (
    <label className="btn ghost sm" style={{ cursor: "pointer" }}>
      {label}
      <input type="file" ref={fileRef} style={{ display: "none" }}
        onChange={() => uploadDoc(docType)} />
    </label>
  );

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="eyebrow">{t("pro")}</div>
          <h2 style={{ margin: "2px 0 0" }}>{t("rnw_title")}</h2>
        </div>
      </div>
      {msg && <div className="ok">{msg}</div>}
      {err && <div className="err">{err}</div>}

      {/* الموظف: تقديم طلب تجديد */}
      {isEmp && !isPro && (
        <div className="card" style={{ borderTop: "3px solid var(--gold)" }}>
          <h3 style={{ marginTop: 0 }}>{t("rnw_new")}</h3>
          <p className="muted">{t("rnw_new_hint")}</p>
          <div className="field"><label htmlFor="rnw-reason">{t("rnw_reason")}</label>
            <input id="rnw-reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder={t("rnw_reason_ph")} /></div>
          <div className="field"><label htmlFor="rnw-notes">{t("rnw_notes")}</label>
            <input id="rnw-notes" value={notes} onChange={(e) => setNotes(e.target.value)} /></div>
          <button onClick={createMine}>{t("rnw_new")}</button>
        </div>
      )}

      <div className="md-layout" style={{ marginTop: 14 }}>
        <div className="md-list">
          <div className="md-rows">
            {items.map((it) => (
              <button key={it.id} className={`md-row ${sel?.id === it.id ? "active" : ""}`}
                onClick={() => {
                  setSelDue(null); setSel(it);
                  api.get(`/renewals/${it.id}/timeline`)
                     .then((r) => setTimeline(r.data.events || []))
                     .catch(() => setTimeline([]));
                }}>
                <span className="r-name">{it.employee_name} <span className={`pill ${ST_PILL[it.status] || "neutral"}`} style={{ marginInlineStart: 6 }}>{t(`rnw_st_${it.status}`)}</span></span>
                <span className="r-sub">{t(`rnw_type_${it.renewal_type}`)} · #{it.id}</span>
              </button>
            ))}
            {!items.length && <div className="empty" style={{ padding: 24 }}>{t("rnw_no_items")}</div>}
            {/* QA-05 — ما يستحق فتح ملف ولم يُفتح له: الجسر بين هذه الصفحة ومركز العمليات */}
            {duePermits.length > 0 && (
              <div className="card" style={{ marginTop: 12, borderTop: "3px solid var(--warning)" }}>
                <h4 style={{ marginTop: 0 }}>{t("rnw_due_no_case", { n: duePermits.length })}</h4>
                <div className="md-rows">
                  {duePermits.map((d: any) => (
                    <button key={d.permit_id}
                      className={`md-row ${selDue?.permit_id === d.permit_id ? "active" : ""}`}
                      onClick={() => { setSel(null); setSelDue(d); setErr(""); setMsg(""); }}>
                      <span className="r-name">
                        {d.employee_name || `#${d.employee_id}`}
                        <span className={`pill ${d.days_left < 0 ? "expired" : "warning"}`}
                              style={{ marginInlineStart: 6 }}>
                          {d.days_left < 0 ? t("rnw_expired") : t("rnw_days_remaining", { n: d.days_left })}
                        </span>
                      </span>
                      <span className="r-sub">
                        {d.number || "—"} · {d.expiry_date}
                        {d.branch_name ? ` · ${d.branch_name}` : ""}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="md-detail">
          {selDue ? (
            /* RNW-01 — لوحة التنبيه: بيانات كافية للقرار ثم إجراء واحد واضح.
               ليست معاملة بعد، فلا Timeline ولا مراحل — فقط ما يلزم للبدء. */
            <div className="card">
              <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ margin: 0 }}>{selDue.employee_name || `#${selDue.employee_id}`}</h3>
                <span className={`pill ${selDue.days_left < 0 ? "expired" : "warning"}`}>
                  {selDue.days_left < 0 ? t("rnw_expired")
                                        : t("rnw_days_remaining", { n: selDue.days_left })}
                </span>
              </div>
              <p className="muted" style={{ marginTop: 6 }}>{t("rnw_no_case_yet")}</p>

              <div style={{ display: "grid", gridTemplateColumns: "auto 1fr",
                           gap: "6px 12px", fontSize: 14, marginTop: 12 }}>
                <span><b>{t("rnw_f_employee_no")}:</b></span><span>{selDue.employee_no || "—"}</span>
                <span><b>{t("rnw_f_job")}:</b></span><span>{selDue.job_title || "—"}</span>
                <span><b>{t("rnw_f_company")}:</b></span><span>{selDue.company_name || "—"}</span>
                <span><b>{t("rnw_f_branch")}:</b></span><span>{selDue.branch_name || "—"}</span>
                <span><b>{t("rnw_f_permit_no")}:</b></span><code>{selDue.number || "—"}</code>
                <span><b>{t("rnw_f_expiry")}:</b></span><span>{selDue.expiry_date}</span>
              </div>

              {isPro ? (
                <>
                  {/* التجديد المبكر يلزمه سبب — الخادم يرفض بدونه، فنطلبه هنا
                      بدل أن يكتشف المستخدم الرفض بعد الضغط. */}
                  {selDue.days_left > 30 && (
                    <input style={{ marginTop: 12 }} value={reason}
                           onChange={(e) => setReason(e.target.value)}
                           placeholder={t("rnw_early_reason_ph")} />
                  )}
                  <button style={{ marginTop: 12 }} onClick={() => startCase(selDue)}>
                    {t("rnw_start_case")}
                  </button>
                </>
              ) : (
                /* لا تجاهل صامت: من لا يملك الصلاحية يُخبَر بالسبب ومن يفعلها */
                <div className="warn" style={{ marginTop: 12, fontSize: 13 }}>
                  {t("rnw_start_denied")}
                </div>
              )}
            </div>
          ) : !sel ? <div className="md-empty">{t("rnw_select")}</div> : (
            <div className="card">
              <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ margin: 0 }}>{sel.employee_name}</h3>
                <span className={`pill ${ST_PILL[sel.status] || "neutral"}`}>
                  {ST_LABEL[sel.status] || sel.status_label || sel.status}
                </span>
              </div>
              <p className="muted" style={{ marginTop: 6 }}>
                {t(`rnw_type_${sel.renewal_type}`)} · {t("rnw_days_left")}: {sel.days_left_at_request}
              </p>
              {sel.reason && <p><b>{t("rnw_reason")}:</b> {sel.reason}</p>}
              {sel.reject_reason && <p className="err"><b>{t("rnw_reject_reason")}:</b> {sel.reject_reason}</p>}

              {/* R4 §7 — عرض بيانات المعاملة الحكومية (لو مسجّلة) */}
              {sel.gov_reference_no && (
                <div style={{
                  background: "#e0ece8", padding: 10, borderRadius: 8,
                  fontSize: 13, marginTop: 10,
                }}>
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>📋 بيانات المعاملة الحكومية</div>
                  <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "4px 12px" }}>
                    <span><b>الرقم المرجعي:</b></span><code>{sel.gov_reference_no}</code>
                    <span><b>رقم الإقامة الجديد:</b></span><code>{sel.new_permit_number || "—"}</code>
                    <span><b>تاريخ الانتهاء الجديد:</b></span><span>{sel.new_expiry_date || "—"}</span>
                    <span><b>الرسوم:</b></span>
                    <span>{sel.fees_amount ?? "—"} د.ك · إيصال #{sel.fees_receipt_no || "—"}</span>
                    {sel.hr_verified_at && (
                      <>
                        <span><b>تحقق HR:</b></span>
                        <span style={{ color: "#065f46" }}>
                          ✓ {sel.hr_verification_note || "بدون ملاحظة"}
                        </span>
                      </>
                    )}
                  </div>
                </div>
              )}

              {/* RNW-21 — القصة: من التنبيه إلى المستند النهائي. تُقرأ من
                  سجل التدقيق، فكل حدث بفاعله الحقيقي ودوره ووقته. */}
              {timeline.length > 0 && (
                <details style={{ margin: "10px 0" }}>
                  <summary style={{ cursor: "pointer", fontWeight: 600 }}>
                    {t("rnw_timeline")} ({timeline.length})
                  </summary>
                  <div className="steps" style={{ marginTop: 8 }}>
                    {timeline.map((ev: any, i: number) => (
                      <div className="step done" key={i}>
                        <div className="rail">
                          <div className="node">•</div>
                          {i < timeline.length - 1 && <div className="connector" />}
                        </div>
                        <div>
                          <b>{ev.label}</b>
                          <div className="muted" style={{ fontSize: 12 }}>
                            {ev.actor || t("rnw_tl_system")}
                            {ev.actor_role ? ` · ${ev.actor_role}` : ""}
                            {ev.at ? ` · ${fmtKuwaitDateTime(ev.at, lang)}` : ""}
                          </div>
                          {ev.reference && (
                            <div className="muted" style={{ fontSize: 11 }}>{ev.reference}</div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </details>
              )}

              {/* المستندات */}
              <div style={{ margin: "10px 0" }}>
                <b>{t("rnw_docs")}:</b>
                {sel.documents?.length ? (
                  <div className="row" style={{ flexWrap: "wrap", marginTop: 6 }}>
                    {sel.documents.map((d: any) => (
                      <button key={d.type} className="ghost sm" onClick={() => download(d.type)}>
                        ⬇ {t(`rnw_doc_${d.type}`)} v{d.version}
                      </button>
                    ))}
                  </div>
                ) : <span className="muted"> —</span>}
              </div>

              {/* أفعال حسب الدور والحالة */}
              <div className="row" style={{ flexWrap: "wrap", gap: 8, borderTop: "1px solid var(--line)", paddingTop: 12 }}>
                {/* موافقات المبكر */}
                {isMgr && sel.status === "pending_manager" && (
                  <><button onClick={() => decide("approved")}>{t("rnw_approve")}</button>
                    <input aria-label={t("rnw_reject_reason")} placeholder={t("rnw_reject_reason")} value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} style={{ maxWidth: 220 }} />
                    <button className="danger" onClick={() => decide("rejected")}>{t("rnw_reject")}</button></>
                )}
                {isHr && sel.status === "pending_hr" && (
                  <><button onClick={() => decide("approved")}>{t("rnw_approve")}</button>
                    <input aria-label={t("rnw_reject_reason")} placeholder={t("rnw_reject_reason")} value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} style={{ maxWidth: 220 }} />
                    <button className="danger" onClick={() => decide("rejected")}>{t("rnw_reject")}</button></>
                )}
                {/* المندوب: العقود
                    R8 §3 — عقد الشركة اختياري في التجديد (الفارق عن التعيين). العقد الحكومي فقط الإلزامي. */}
                {isPro && sel.status === "awaiting_contracts" && (
                  <>
                    {govContractTplExists === false && (
                      <div className="err" style={{ width: "100%", fontSize: 12 }}>
                        ⚠ قالب <code>GOV-CONTRACT-RENEWAL</code> غير موجود — زر التوليد التلقائي معطّل.
                        على الإدارة إنشاؤه من صفحة <b>القوالب /templates</b> أولاً، أو قم بالرفع اليدوي.
                      </div>
                    )}
                    <button onClick={generateGovContract}
                            disabled={govContractTplExists === false}
                            style={{
                              background: govContractTplExists === false ? "#999" : "#0e5a54",
                              color: "white",
                              cursor: govContractTplExists === false ? "not-allowed" : "pointer",
                            }}>
                      🖨️ توليد العقد الحكومي (تلقائي)
                    </button>
                    {!hasDoc("renewal_contract_gov") && <UploadBtn docType="renewal_contract_gov" label={t("rnw_upload_contract_gov")} />}
                    <span className="muted" style={{ fontSize: 11 }}>
                      (عقد الشركة الداخلي اختياري — يُطلب فقط عند التعيين الأول)
                    </span>
                  </>
                )}
                {/* الموظف: النسخ الموقّعة — R9 §1: الحكومي فقط إلزامي */}
                {isEmp && sel.status === "awaiting_signature" && (
                  <>
                    {!hasDoc("renewal_signed_gov") && <UploadBtn docType="renewal_signed_gov" label={t("rnw_upload_signed_gov")} />}
                    {!hasDoc("renewal_signed_internal") && (
                      <>
                        <UploadBtn docType="renewal_signed_internal" label={t("rnw_upload_signed_internal")} />
                        <span className="muted" style={{ fontSize: 11 }}>(اختياري)</span>
                      </>
                    )}
                  </>
                )}
                {/* RNW-09 — النسخة الثالثة: بتوقيع الطرفين. نسخة الموظف ليست
                    النهائية، وهذه لا تمسحها — الثلاث تبقى قابلة للتنزيل. */}
                {isPro && ["contracts_signed", "renewing"].includes(sel.status)
                       && !hasDoc("renewal_contract_final") && (
                  <UploadBtn docType="renewal_contract_final" label={t("rnw_upload_final")} />
                )}
                {/* المندوب: بدء التجديد */}
                {isPro && sel.status === "contracts_signed" && (
                  <button onClick={setRenewing}>{t("rnw_set_renewing")}</button>
                )}
                {/* المندوب: إذن العمل */}
                {isPro && sel.status === "renewing" && (
                  <UploadBtn docType="work_permit" label={t("rnw_upload_permit")} />
                )}
                {/* الموظف: البطاقة المدنية */}
                {isEmp && sel.status === "awaiting_civil_card" && (
                  <UploadBtn docType="civil_id" label={t("rnw_upload_card")} />
                )}
              </div>

              {/* R4 §7 — PRO يعبّي بيانات المعاملة الحكومية (خلال renewing / awaiting_civil_card) */}
              {isPro && ["renewing", "contracts_signed", "with_delegate"].includes(sel.status) &&
                !sel.gov_reference_no && (
                <div style={{
                  background: "#fef3c7", border: "1px solid #fbbf24",
                  padding: 12, borderRadius: 8, marginTop: 12,
                }}>
                  <div style={{ fontWeight: 600, marginBottom: 6 }}>
                    📋 تسجيل بيانات المعاملة الحكومية (Finalize)
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                    <div className="field" style={{ margin: 0 }}>
                      <label>الرقم المرجعي الحكومي *</label>
                      <input value={gov.gov_reference_no}
                             onChange={(e) => setGov({ ...gov, gov_reference_no: e.target.value })}
                             placeholder="GOV-2026-000123" />
                    </div>
                    <div className="field" style={{ margin: 0 }}>
                      <label>رقم الإقامة الجديد *</label>
                      <input value={gov.new_permit_number}
                             onChange={(e) => setGov({ ...gov, new_permit_number: e.target.value })} />
                    </div>
                    <div className="field" style={{ margin: 0 }}>
                      <label>تاريخ انتهاء الإقامة الجديد *</label>
                      <input type="date" value={gov.new_expiry_date}
                             onChange={(e) => setGov({ ...gov, new_expiry_date: e.target.value })} />
                    </div>
                    <div className="field" style={{ margin: 0 }}>
                      <label>قيمة الرسوم (د.ك)</label>
                      <input type="number" step="0.001" value={gov.fees_amount}
                             onChange={(e) => setGov({ ...gov, fees_amount: e.target.value })} />
                    </div>
                    <div className="field" style={{ margin: 0, gridColumn: "1 / span 2" }}>
                      <label>رقم إيصال الرسوم</label>
                      <input value={gov.fees_receipt_no}
                             onChange={(e) => setGov({ ...gov, fees_receipt_no: e.target.value })} />
                    </div>
                  </div>
                  <button onClick={finalize} style={{ marginTop: 10 }}>
                    تسجيل وتحويل للتحقق
                  </button>
                </div>
              )}

              {/* R4 §7 — HR يتحقق ويقفل المعاملة */}
              {isHr && sel.status === "pending_hr_verify" && (
                <div style={{
                  background: "#d1fae5", border: "1px solid #10b981",
                  padding: 12, borderRadius: 8, marginTop: 12,
                }}>
                  <div style={{ fontWeight: 600, marginBottom: 6 }}>
                    ✅ تحقق HR وإغلاق المعاملة
                  </div>
                  <p style={{ fontSize: 12, color: "#065f46", margin: "0 0 8px" }}>
                    راجع بيانات المعاملة أعلاه وتطابقها مع الوثائق المرفوعة قبل الإغلاق.
                  </p>
                  <div className="field" style={{ margin: 0 }}>
                    <label>ملاحظة التحقق (اختياري)</label>
                    <input value={hrNote} onChange={(e) => setHrNote(e.target.value)}
                           placeholder="تم التحقق من الرقم المرجعي والتاريخ الجديد" />
                  </div>
                  <button onClick={hrVerify} style={{ marginTop: 8 }}>
                    تحقق وإغلاق
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
