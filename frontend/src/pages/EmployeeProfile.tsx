import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import api from "../api";
import { useAuth } from "../auth";
import { attAr, statusAr } from "../labels";

export default function EmployeeProfile() {
  const { id } = useParams();
  const { can } = useAuth();
  const [p, setP] = useState<any>(null);
  const [docType, setDocType] = useState("passport");
  const [suggested, setSuggested] = useState<any>(null);
  const [msg, setMsg] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const [term, setTerm] = useState({ end_date: "", reason: "termination" });
  const [settlement, setSettlement] = useState<any>(null);
  const [consumed, setConsumed] = useState(0);
  const [leaveBal, setLeaveBal] = useState<any>(null);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [evForm, setEvForm] = useState({ kind: "warning", title: "", amount: "" });

  const EMP_STATUS = { active: "نشط", vacation: "في إجازة", suspended: "موقوف", resigned: "مستقيل", terminated: "منتهي الخدمة", retired: "متقاعد" };
  const EV_AR: Record<string, string> = { warning: "إنذار", penalty: "جزاء", bonus: "مكافأة", promotion: "ترقية", note: "ملاحظة" };

  const loadExtras = () => {
    api.get(`/employees/${id}/timeline`).then((r) => setTimeline(r.data.timeline)).catch(() => {});
    api.get(`/employees/${id}/events`).then((r) => setEvents(r.data)).catch(() => {});
  };
  useEffect(() => { loadExtras(); }, [id]);

  const calcLeave = async () => {
    const r = await api.post("/eos/leave-balance", null, { params: { employee_id: id, consumed_days: consumed } });
    setLeaveBal(r.data);
  };
  const changeStatus = async (status: string) => {
    await api.post(`/employees/${id}/status`, null, { params: { status } });
    setMsg("تم تغيير الحالة"); load();
  };
  const addEvent = async () => {
    if (!evForm.title) return;
    await api.post(`/employees/${id}/events`, null, { params: {
      kind: evForm.kind, title: evForm.title, amount: evForm.amount || undefined } });
    setEvForm({ kind: "warning", title: "", amount: "" }); loadExtras();
  };

  const REASONS: Record<string, string> = {
    termination: "فصل (غير تأديبي)", contract_expiry: "انتهاء العقد", resignation: "استقالة",
    death: "وفاة", disability: "عجز", misconduct: "فصل تأديبي",
  };

  const terminate = async () => {
    if (!term.end_date) return;
    if (!confirm("تأكيد إنهاء خدمة الموظف؟")) return;
    const r = await api.post(`/employees/${id}/terminate`, null, { params: term });
    setSettlement(r.data.settlement); setMsg("تم إنهاء الخدمة"); load();
  };

  const load = () => api.get(`/employees/${id}/profile`).then((r) => setP(r.data));
  useEffect(() => { load(); }, [id]);
  if (!p) return <div>…</div>;
  const e = p.employee;

  const ocrPreview = async (file: File) => {
    const fd = new FormData();
    fd.append("document_type_code", docType);
    fd.append("file", file);
    const r = await api.post("/documents/ocr-preview", fd);
    setSuggested(r.data.suggested);
  };

  const upload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("entity_type", "employee");
    fd.append("entity_id", String(id));
    fd.append("document_type_code", docType);
    fd.append("file", file);
    await api.post("/documents/upload", fd);
    setMsg("تم رفع المستند (أصبح الأحدث)"); setSuggested(null);
    if (fileRef.current) fileRef.current.value = "";
    load();
  };

  const downloadLatest = (type: string) =>
    window.open(`/api/documents/latest?entity_type=employee&entity_id=${id}&document_type_code=${type}`, "_blank");

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ margin: 0 }}>{e.name} <span className={`pill ${e.status === "active" ? "success" : "neutral"}`}>{(EMP_STATUS as any)[e.status] || statusAr(e.status)}</span></h2>
        {can("edit_employee") && (
          <div className="row">
            <span className="muted">الحالة:</span>
            <select value={e.status} onChange={(ev) => changeStatus(ev.target.value)} style={{ width: 160 }}>
              {Object.entries(EMP_STATUS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
        )}
      </div>
      {msg && <div className="ok">{msg}</div>}
      <div className="grid cards">
        <div className="card"><b>المسمى:</b> {e.job_title || "—"}<br /><b>الجنسية:</b> {e.nationality || "—"}<br />
          <b>الراتب:</b> {e.basic_salary} د.ك<br /><b>التعيين:</b> {e.hire_date || "—"}<br /><b>نوع العقد:</b> {e.contract_type}</div>
        <div className="card"><b>الجنس:</b> {e.gender === "male" ? "ذكر" : e.gender === "female" ? "أنثى" : "—"}<br />
          <b>الميلاد:</b> {e.date_of_birth || "—"}<br /><b>الحالة الاجتماعية:</b> {e.marital_status || "—"}<br />
          <b>البريد:</b> {e.email || "—"}</div>
        <div className="card"><b>رقم الجواز:</b> {e.passport_number || "—"}<br />
          <b>انتهاء الجواز:</b> {e.passport_expiry || "—"}<br /><b>التأمين الصحي:</b> {e.health_insurance || "—"}<br />
          <b>نمط الحضور:</b> {e.attendance_mode}</div>
      </div>

      <div className="card">
        <h3>الإقامات وأذونات العمل</h3>
        <table><thead><tr><th>النوع</th><th>الرقم</th><th>الانتهاء</th><th>الحالة</th></tr></thead>
          <tbody>{p.permits.map((x: any) => (
            <tr key={x.id}><td>{x.kind}</td><td>{x.number}</td><td>{x.expiry_date}</td>
              <td><span className="pill info">{statusAr(x.status)}</span></td></tr>
          ))}{!p.permits.length && <tr><td colSpan={4} className="muted">لا يوجد</td></tr>}</tbody></table>
      </div>

      <div className="card">
        <h3>المستندات (أحدث نسخة)</h3>
        <table><thead><tr><th>النوع</th><th>العنوان</th><th>النسخة</th><th>الانتهاء</th><th></th></tr></thead>
          <tbody>{p.documents.map((d: any) => (
            <tr key={d.id}><td>{d.type}</td><td>{d.title}</td><td>v{d.version}</td><td>{d.expiry_date}</td>
              <td><button className="ghost" onClick={() => downloadLatest(d.type)}>تنزيل الأحدث</button></td></tr>
          ))}{!p.documents.length && <tr><td colSpan={5} className="muted">لا يوجد</td></tr>}</tbody></table>

        {can("upload_documents") && (
          <div style={{ marginTop: 14, borderTop: "1px solid var(--border)", paddingTop: 14 }}>
            <h4>رفع مستند جديد (مع قراءة OCR مقترحة)</h4>
            <div className="row">
              <select value={docType} onChange={(e) => setDocType(e.target.value)} style={{ width: 200 }}>
                <option value="passport">جواز سفر (MRZ)</option>
                <option value="civil_id">بطاقة مدنية (باركود)</option>
                <option value="residency">إقامة</option>
                <option value="contract">عقد</option>
              </select>
              <input type="file" ref={fileRef}
                onChange={(e) => e.target.files && ocrPreview(e.target.files[0])} />
              <button onClick={upload}>رفع وحفظ</button>
            </div>
            {suggested && (
              <div className="card" style={{ background: "#f8fafc", marginTop: 10 }}>
                <b>بيانات مقترحة من OCR (راجعها قبل الحفظ):</b>
                <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(suggested, null, 2)}</pre>
              </div>
            )}
            {msg && <div className="ok">{msg}</div>}
          </div>
        )}
      </div>

      <div className="card">
        <h3>آخر سجلات الحضور</h3>
        <table><thead><tr><th>الدخول</th><th>الخروج</th><th>الحالة</th><th>سيلفي</th></tr></thead>
          <tbody>{p.attendance.map((a: any) => (
            <tr key={a.id}><td>{a.check_in_at && new Date(a.check_in_at).toLocaleString("ar")}</td>
              <td>{a.check_out_at && new Date(a.check_out_at).toLocaleString("ar")}</td>
              <td><span className={`pill ${a.status === "late" ? "warning" : "success"}`}>{attAr(a.status)}</span></td>
              <td>{a.selfie_in ? "✓" : "—"}</td></tr>
          ))}{!p.attendance.length && <tr><td colSpan={4} className="muted">لا يوجد</td></tr>}</tbody></table>
      </div>

      <div className="card">
        <h3>سجل الموارد البشرية (إنذارات · جزاءات · مكافآت · ترقيات)</h3>
        {can("edit_employee") && (
          <div className="row" style={{ marginBottom: 10 }}>
            <select value={evForm.kind} onChange={(e) => setEvForm({ ...evForm, kind: e.target.value })} style={{ width: 130 }}>
              {Object.entries(EV_AR).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <input placeholder="العنوان/السبب" value={evForm.title} onChange={(e) => setEvForm({ ...evForm, title: e.target.value })} style={{ flex: 1 }} />
            <input type="number" placeholder="مبلغ (اختياري)" value={evForm.amount} onChange={(e) => setEvForm({ ...evForm, amount: e.target.value })} style={{ width: 140 }} />
            <button onClick={addEvent}>إضافة</button>
          </div>
        )}
        <table>
          <thead><tr><th>النوع</th><th>العنوان</th><th>المبلغ</th><th>التاريخ</th></tr></thead>
          <tbody>{events.map((ev) => (
            <tr key={ev.id}>
              <td><span className={`pill ${ev.kind === "bonus" || ev.kind === "promotion" ? "success" : ev.kind === "note" ? "neutral" : "warning"}`}>{EV_AR[ev.kind]}</span></td>
              <td>{ev.title}</td><td>{ev.amount ? `${ev.amount} د.ك` : "—"}</td><td>{ev.date}</td>
            </tr>
          ))}{!events.length && <tr><td colSpan={4} className="muted">لا يوجد</td></tr>}</tbody>
        </table>
      </div>

      <div className="card">
        <h3>الخط الزمني للموظف</h3>
        <div className="steps">
          {timeline.map((it, i) => (
            <div className="step done" key={i}>
              <div className="rail"><div className="node">•</div><div className="connector" /></div>
              <div className="body">
                <div className="s-title">{it.text}</div>
                <div className="s-meta"><span>{new Date(it.at).toLocaleDateString("ar", { dateStyle: "medium" })}</span></div>
              </div>
            </div>
          ))}
          {!timeline.length && <div className="muted">لا أحداث بعد.</div>}
        </div>
      </div>

      {can("calculate_eos") && (
        <div className="card">
          <h3>رصيد الإجازات (حساب تلقائي حسب مدة الخدمة)</h3>
          <p className="muted">النظام يحسب الرصيد المستحق تلقائيًا — أدخل عدد الأيام المستهلكة فقط.</p>
          <div className="row">
            <div className="field" style={{ width: 200 }}><label>الأيام المستهلَكة</label>
              <input type="number" value={consumed} onChange={(ev) => setConsumed(+ev.target.value)} /></div>
            <div className="field" style={{ alignSelf: "flex-end" }}>
              <button onClick={calcLeave}>احسب الرصيد المتبقي</button></div>
          </div>
          {leaveBal && (
            <div className="grid stats">
              <div className="stat"><div className="num">{leaveBal.accrued_days}</div><div className="lbl">المستحق ({leaveBal.service_years} سنة خدمة)</div></div>
              <div className="stat"><div className="num">{leaveBal.consumed_days}</div><div className="lbl">المستهلَك</div></div>
              <div className="stat accent"><div className="num">{leaveBal.remaining_days}</div><div className="lbl">المتبقي</div></div>
            </div>
          )}
        </div>
      )}

      {can("terminate_employee") && e.status !== "terminated" && (
        <div className="card" style={{ borderTop: "3px solid var(--danger)" }}>
          <h3>إنهاء الخدمة وحساب المكافأة</h3>
          <div className="row">
            <div className="field" style={{ flex: 1 }}><label>تاريخ انتهاء الخدمة</label>
              <input type="date" value={term.end_date} onChange={(ev) => setTerm({ ...term, end_date: ev.target.value })} /></div>
            <div className="field" style={{ flex: 1 }}><label>السبب</label>
              <select value={term.reason} onChange={(ev) => setTerm({ ...term, reason: ev.target.value })}>
                {Object.entries(REASONS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select></div>
            <div className="field" style={{ alignSelf: "flex-end" }}>
              <button className="danger" onClick={terminate}>إنهاء الخدمة</button>
            </div>
          </div>
        </div>
      )}

      {settlement && (
        <div className="card">
          <h3>مكافأة نهاية الخدمة (تقديرية)</h3>
          <div className="grid stats">
            <div className="stat accent"><div className="num">{settlement.total_settlement}</div><div className="lbl">إجمالي التسوية (د.ك)</div></div>
            <div className="stat"><div className="num">{settlement.indemnity}</div><div className="lbl">المكافأة</div></div>
            <div className="stat"><div className="num">{settlement.leave_payout}</div><div className="lbl">بدل الإجازات</div></div>
          </div>
          <p className="muted">{settlement.service?.text} · {settlement.factor_note}</p>
          <p className="muted">{settlement.disclaimer}</p>
        </div>
      )}
    </div>
  );
}
