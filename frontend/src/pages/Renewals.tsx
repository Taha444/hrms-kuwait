import { useEffect, useRef, useState } from "react";
import api, { errMsg } from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";

// معاملات تجديد الإقامة (DEMO-001/002) — قائمة + تفاصيل بأفعال حسب الدور والحالة.
const ST_PILL: Record<string, string> = {
  rejected: "critical", completed: "success", new: "info",
  pending_manager: "warning", pending_hr: "warning", awaiting_signature: "warning",
  awaiting_civil_card: "warning", awaiting_contracts: "info", contracts_signed: "info",
  renewing: "info", with_delegate: "info",
};

export default function Renewals() {
  const { t, lang } = useI18n();
  const { user, can } = useAuth();
  const [items, setItems] = useState<any[]>([]);
  const [sel, setSel] = useState<any>(null);
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

  const load = () => api.get("/renewals").then((r) => {
    setItems(r.data);
    if (sel) { const u = r.data.find((x: any) => x.id === sel.id); if (u) setSel(u); }
  }).catch((e) => setErr(errMsg(e, t("error"))));
  useEffect(() => { load(); }, []);

  const act = async (fn: () => Promise<any>, ok?: string) => {
    setErr(""); setMsg("");
    try { await fn(); if (ok) setMsg(ok); await load(); }
    catch (e: any) { setErr(errMsg(e, t("error"))); }
  };

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
                onClick={() => setSel(it)}>
                <span className="r-name">{it.employee_name} <span className={`pill ${ST_PILL[it.status] || "neutral"}`} style={{ marginInlineStart: 6 }}>{t(`rnw_st_${it.status}`)}</span></span>
                <span className="r-sub">{t(`rnw_type_${it.renewal_type}`)} · #{it.id}</span>
              </button>
            ))}
            {!items.length && <div className="empty" style={{ padding: 24 }}>{t("rnw_no_items")}</div>}
          </div>
        </div>

        <div className="md-detail">
          {!sel ? <div className="md-empty">{t("rnw_select")}</div> : (
            <div className="card">
              <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ margin: 0 }}>{sel.employee_name}</h3>
                <span className={`pill ${ST_PILL[sel.status] || "neutral"}`}>{t(`rnw_st_${sel.status}`)}</span>
              </div>
              <p className="muted" style={{ marginTop: 6 }}>
                {t(`rnw_type_${sel.renewal_type}`)} · {t("rnw_days_left")}: {sel.days_left_at_request}
              </p>
              {sel.reason && <p><b>{t("rnw_reason")}:</b> {sel.reason}</p>}
              {sel.reject_reason && <p className="err"><b>{t("rnw_reject_reason")}:</b> {sel.reject_reason}</p>}

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
                {/* المندوب: العقود */}
                {isPro && sel.status === "awaiting_contracts" && (
                  <>{!hasDoc("renewal_contract_gov") && <UploadBtn docType="renewal_contract_gov" label={t("rnw_upload_contract_gov")} />}
                    {!hasDoc("renewal_contract_internal") && <UploadBtn docType="renewal_contract_internal" label={t("rnw_upload_contract_internal")} />}</>
                )}
                {/* الموظف: النسخ الموقّعة */}
                {isEmp && sel.status === "awaiting_signature" && (
                  <>{!hasDoc("renewal_signed_gov") && <UploadBtn docType="renewal_signed_gov" label={t("rnw_upload_signed_gov")} />}
                    {!hasDoc("renewal_signed_internal") && <UploadBtn docType="renewal_signed_internal" label={t("rnw_upload_signed_internal")} />}</>
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
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
