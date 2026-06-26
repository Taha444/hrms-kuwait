import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import api from "../api";
import { useAuth } from "../auth";
import RequestSteps, { ProgressMini } from "../components/RequestSteps";
import { statusAr } from "../labels";

export default function RequestDetail() {
  const { id } = useParams();
  const { user, can } = useAuth();
  const [req, setReq] = useState<any>(null);
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [appt, setAppt] = useState({ scheduled_at: "", location: "مقر الشركة" });

  const load = () => api.get(`/requests/${id}`).then((r) => setReq(r.data));
  useEffect(() => { load(); }, [id]);
  if (!req) return <div>…</div>;

  const act = async (fn: () => Promise<any>, ok: string) => {
    setErr(""); setMsg("");
    try { await fn(); setMsg(ok); load(); }
    catch (e: any) { setErr(e.response?.data?.detail || "خطأ"); }
  };

  const decide = (decision: string) =>
    act(() => api.post(`/requests/${id}/decide`, { decision, note }), "تم تنفيذ القرار");
  const cancel = () =>
    act(() => api.post(`/requests/${id}/cancel`, null, { params: { note } }), "تم الإلغاء");
  const setAppointment = () =>
    act(() => api.post(`/requests/${id}/appointment`, appt), "تم تحديد الموعد");
  const received = () => act(() => api.post(`/requests/${id}/received`), "تم تسجيل الاستلام");

  const uploadDoc = async (kind: string, file: File) => {
    const fd = new FormData();
    fd.append("kind", kind);
    fd.append("file", file);
    await act(() => api.post(`/requests/${id}/documents`, fd), "تم رفع المستند");
  };

  const downloadDoc = (kind: string) => {
    window.open(`/api/requests/${id}/document/${kind}`, "_blank");
  };

  const isManager = user?.role && ["company_manager", "company_owner", "super_admin"].includes(user.role);

  return (
    <div>
      <h2>طلب #{req.id} — {req.type_name}</h2>
      <div className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div>
            <p><b>الموظف:</b> {req.employee_name}</p>
            <p><b>الحالة:</b> <span className={`pill ${req.status}`}>{statusAr(req.status)}</span></p>
            <p className="muted">البيانات: {JSON.stringify(req.payload)}</p>
          </div>
          {req.documents?.some((d: any) => d.kind === "generated_pdf") && (
            <button onClick={() => downloadDoc("generated_pdf")}>🖨️ طباعة المستند</button>
          )}
        </div>
      </div>

      <div className="card">
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 14 }}>
          <h3 style={{ margin: 0 }}>مسار الطلب</h3>
          <ProgressMini current={req.current_stage} total={req.total_stages} status={req.status} />
        </div>
        <RequestSteps stages={req.stages} status={req.status} />
      </div>

      {err && <div className="err">{err}</div>}
      {msg && <div className="ok">{msg}</div>}

      <div className="card">
        <h3>الإجراءات</h3>
        <div className="field"><label>ملاحظة (اختياري)</label>
          <input value={note} onChange={(e) => setNote(e.target.value)} /></div>

        {req.status === "pending" && can("approve_request") && (
          <div className="row">
            <button onClick={() => decide("approved")}>✓ اعتماد</button>
            <button className="danger" onClick={() => decide("rejected")}>✕ رفض</button>
          </div>
        )}

        {req.status === "awaiting_signature" && can("approve_request") && (
          <div className="card" style={{ background: "#f8fafc" }}>
            <h4>تحديد موعد التوقيع ورفع النسخة الموقّعة</h4>
            <div className="row">
              <div className="field"><label>موعد المراجعة</label>
                <input type="datetime-local" onChange={(e) => setAppt({ ...appt, scheduled_at: e.target.value })} /></div>
              <div className="field"><label>المكان</label>
                <input value={appt.location} onChange={(e) => setAppt({ ...appt, location: e.target.value })} /></div>
            </div>
            <button onClick={setAppointment}>تحديد الموعد وإشعار العامل</button>
            <div className="field" style={{ marginTop: 12 }}>
              <label>رفع الطلب الموقّع (بعد توقيع العامل)</label>
              <input type="file" onChange={(e) => e.target.files && uploadDoc("signed_scan", e.target.files[0])} />
            </div>
          </div>
        )}

        {req.status === "awaiting_delegate" && user?.role === "delegate" && (
          <div className="field">
            <label>رفع إذن مغادرة البلاد</label>
            <input type="file" onChange={(e) => e.target.files && uploadDoc("exit_permit", e.target.files[0])} />
          </div>
        )}

        {req.status === "ready_for_pickup" && can("approve_request") && (
          <button onClick={received}>تسجيل استلام العامل</button>
        )}

        {isManager && !["completed", "rejected", "cancelled"].includes(req.status) && (
          <div style={{ marginTop: 12 }}>
            <button className="warn" onClick={cancel}>إلغاء الطلب (المدير العام)</button>
          </div>
        )}
      </div>
    </div>
  );
}
