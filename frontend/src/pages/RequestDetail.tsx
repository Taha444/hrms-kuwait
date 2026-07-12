import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import api, { errMsg } from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import RequestSteps, { ProgressMini } from "../components/RequestSteps";
import { statusAr } from "../labels";

export default function RequestDetail() {
  const { id } = useParams();
  const { user, can } = useAuth();
  const { t } = useI18n();
  const [req, setReq] = useState<any>(null);
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [appt, setAppt] = useState({ scheduled_at: "", location: t("rd_company_hq") });

  const load = () => api.get(`/requests/${id}`).then((r) => setReq(r.data));
  useEffect(() => { load(); }, [id]);
  if (!req) return <div>…</div>;

  const act = async (fn: () => Promise<any>, ok: string) => {
    setErr(""); setMsg("");
    try { await fn(); setMsg(ok); load(); }
    catch (e: any) { setErr(errMsg(e, t("error"))); }
  };

  const decide = (decision: string) => {
    // الإرجاع للتصحيح يلزم توضيح السبب دائًما (QA-P2-WF-03)، خلافًا للاعتماد/الرفض
    if (decision === "returned" && !note.trim()) { setErr(t("rd_return_note_required")); return; }
    act(() => api.post(`/requests/${id}/decide`, { decision, note }), t("rd_decided"));
  };
  const cancel = () =>
    act(() => api.post(`/requests/${id}/cancel`, null, { params: { note } }), t("rd_cancelled"));
  const setAppointment = () => {
    // منع إرسال تاريخ فارغ للخادم (QA-P0-WF-02): "" لا يمكن تحويله لـ datetime فيرجع
    // 422 بمصفوفة أخطاء تحقق — تحقق واضح هنا بدل الاعتماد على معالجة الخطأ لاحقًا
    if (!appt.scheduled_at) { setErr(t("rd_appt_required")); return; }
    act(() => api.post(`/requests/${id}/appointment`, appt), t("rd_appt_set"));
  };
  const received = () => act(() => api.post(`/requests/${id}/received`), t("rd_received_done"));

  const uploadDoc = async (kind: string, file: File) => {
    const fd = new FormData();
    fd.append("kind", kind);
    fd.append("file", file);
    await act(() => api.post(`/requests/${id}/documents`, fd), t("rd_doc_uploaded"));
  };

  const downloadDoc = async (kind: string) => {
    setErr("");
    try {
      // window.open المباشر لا يرفق رمز الدخول، فيرجع 401 — نجلب الملف بالرمز ونعرضه كـ blob
      const res = await api.get(`/requests/${id}/document/${kind}`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data as Blob);
      window.open(url, "_blank");
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e: any) { setErr(errMsg(e, t("error"))); }
  };

  const markPrinted = (kind: string) =>
    act(() => api.post(`/requests/${id}/document/${kind}/mark-printed`), t("rd_marked_printed"));
  const markFiled = (kind: string) =>
    act(() => api.post(`/requests/${id}/document/${kind}/mark-filed`), t("rd_marked_filed"));

  const isManager = user?.role && ["company_manager", "company_owner", "super_admin"].includes(user.role);
  const genDoc = req.documents?.find((d: any) => d.kind === "generated_pdf");
  const printStatusLabel: Record<string, string> = {
    ready_to_print: t("rd_print_ready"), printed: t("rd_print_printed"), filed: t("rd_print_filed"),
  };

  return (
    <div>
      <h2>{t("rd_request")} #{req.id} — {req.type_name}</h2>
      <div className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div>
            <p><b>{t("rd_employee")}:</b> {req.employee_name}</p>
            <p><b>{t("rd_status")}:</b> <span className={`pill ${req.status}`}>{statusAr(req.status)}</span></p>
            {genDoc && (
              <p><b>{t("rd_print_status")}:</b>{" "}
                <span className={`pill ${genDoc.print_status}`}>
                  {printStatusLabel[genDoc.print_status] || genDoc.print_status}
                </span>
              </p>
            )}
            <p className="muted">{t("rd_data")}: {JSON.stringify(req.payload)}</p>
          </div>
          {genDoc && (
            <div className="row" style={{ flexWrap: "wrap" }}>
              <button onClick={() => downloadDoc("generated_pdf")}>{t("rd_print_doc")}</button>
              {isManager && genDoc.print_status === "ready_to_print" && (
                <button className="ghost" onClick={() => markPrinted("generated_pdf")}>{t("rd_mark_printed")}</button>
              )}
              {can("upload_documents") && genDoc.print_status === "printed" && (
                <button className="ghost" onClick={() => markFiled("generated_pdf")}>{t("rd_mark_filed")}</button>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 14 }}>
          <h3 style={{ margin: 0 }}>{t("rd_path")}</h3>
          <ProgressMini current={req.current_stage} total={req.total_stages} status={req.status} />
        </div>
        <RequestSteps stages={req.stages} status={req.status} />
      </div>

      {err && <div className="err">{err}</div>}
      {msg && <div className="ok">{msg}</div>}

      <div className="card">
        <h3>{t("rd_actions")}</h3>
        <div className="field"><label htmlFor="rd-note">{t("rd_note_optional")}</label>
          <input id="rd-note" value={note} onChange={(e) => setNote(e.target.value)} /></div>

        {req.status === "pending" && can("approve_request") && (
          <div className="row">
            <button onClick={() => decide("approved")}>{t("rd_approve")}</button>
            <button className="danger" onClick={() => decide("rejected")}>{t("rd_reject")}</button>
            {req.current_stage < 2 && (
              <button className="warn" onClick={() => decide("returned")}>{t("rd_return")}</button>
            )}
          </div>
        )}

        {req.status === "awaiting_signature" && can("approve_request") && (
          <div className="card" style={{ background: "#f8fafc" }}>
            <h4>{t("rd_sign_title")}</h4>
            <div className="row">
              <div className="field"><label htmlFor="rd-appt-when">{t("rd_review_appt")} *</label>
                <input id="rd-appt-when" type="datetime-local" required value={appt.scheduled_at}
                  onChange={(e) => setAppt({ ...appt, scheduled_at: e.target.value })} /></div>
              <div className="field"><label htmlFor="rd-appt-location">{t("rd_location")}</label>
                <input id="rd-appt-location" value={appt.location} onChange={(e) => setAppt({ ...appt, location: e.target.value })} /></div>
            </div>
            <button onClick={setAppointment}>{t("rd_set_appt")}</button>
            <div className="field" style={{ marginTop: 12 }}>
              <label htmlFor="rd-upload-signed">{t("rd_upload_signed")}</label>
              <input id="rd-upload-signed" type="file" onChange={(e) => e.target.files && uploadDoc("signed_scan", e.target.files[0])} />
            </div>
          </div>
        )}

        {req.status === "awaiting_delegate" && user?.role === "delegate" && (
          <div className="field">
            <label htmlFor="rd-upload-exit">{t("rd_upload_exit")}</label>
            <input id="rd-upload-exit" type="file" onChange={(e) => e.target.files && uploadDoc("exit_permit", e.target.files[0])} />
          </div>
        )}

        {req.status === "ready_for_pickup" && can("approve_request") && (
          <button onClick={received}>{t("rd_mark_received")}</button>
        )}

        {isManager && !["completed", "rejected", "cancelled", "returned"].includes(req.status) && (
          <div style={{ marginTop: 12 }}>
            <button className="warn" onClick={cancel}>{t("rd_cancel_mgr")}</button>
          </div>
        )}
      </div>
    </div>
  );
}
