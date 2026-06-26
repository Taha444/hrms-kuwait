import { useEffect, useState } from "react";
import api from "../api";
import Icon from "../Icon";

// وحدة المندوب (PRO): متابعة الإقامات/أذونات العمل والتراخيص والجهات الحكومية + التجديد والملاحظات.
const URGENCY_PILL: Record<string, string> = {
  expired: "critical", critical: "critical", warning: "warning", ok: "success", none: "neutral",
};
const KIND_AR: Record<string, string> = { residency: "إقامة", work_permit: "إذن عمل" };

function daysText(d: number | null) {
  if (d === null || d === undefined) return "—";
  if (d < 0) return `منتهية منذ ${-d} يوم`;
  return `${d} يوم`;
}

export default function Pro() {
  const [tab, setTab] = useState<"permits" | "licenses" | "gov">("permits");
  const [permits, setPermits] = useState<any[]>([]);
  const [licenses, setLicenses] = useState<any[]>([]);
  const [gov, setGov] = useState<any>(null);
  const [renew, setRenew] = useState<any>(null); // {type:'permit'|'license', id, expiry, number, note}
  const [notesFor, setNotesFor] = useState<any>(null);
  const [notes, setNotes] = useState<any[]>([]);
  const [noteText, setNoteText] = useState("");
  const [msg, setMsg] = useState("");

  const loadPermits = () => api.get("/pro/permits").then((r) => setPermits(r.data));
  const loadLicenses = () => api.get("/licenses").then((r) => setLicenses(r.data));
  const loadGov = () => api.get("/pro/government").then((r) => setGov(r.data));
  useEffect(() => { loadPermits(); loadLicenses(); loadGov(); }, []);

  const submitRenew = async () => {
    const { type, id, expiry, number, note } = renew;
    const path = type === "permit" ? `/pro/permits/${id}/renew` : `/pro/licenses/${id}/renew`;
    await api.post(path, null, { params: { expiry_date: expiry, number: number || undefined, note: note || undefined } });
    setRenew(null); setMsg("تم التجديد بنجاح");
    type === "permit" ? loadPermits() : (loadLicenses(), loadGov());
  };

  const openNotes = async (entity_type: string, entity_id: number, label: string) => {
    setNotesFor({ entity_type, entity_id, label });
    const r = await api.get("/pro/notes", { params: { entity_type, entity_id } });
    setNotes(r.data);
  };
  const addNote = async () => {
    if (!noteText.trim()) return;
    await api.post("/pro/notes", null, { params: { ...notesFor, note: noteText } });
    setNoteText(""); openNotes(notesFor.entity_type, notesFor.entity_id, notesFor.label);
  };

  const Tab = ({ id, label }: any) => (
    <button className={tab === id ? "" : "ghost"} onClick={() => setTab(id)}>{label}</button>
  );

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="eyebrow">المعاملات الحكومية</div>
          <h2 style={{ margin: "2px 0 0" }}>معاملات المندوب</h2>
          <div className="sub">الإقامات وأذونات العمل والتراخيص — متابعة الانتهاء والتجديد</div>
        </div>
      </div>
      {msg && <div className="ok">{msg}</div>}

      <div className="row" style={{ marginBottom: 14 }}>
        <Tab id="permits" label="الإقامات وأذونات العمل" />
        <Tab id="licenses" label="التراخيص" />
        <Tab id="gov" label="الجهات الحكومية" />
      </div>

      {/* نموذج التجديد */}
      {renew && (
        <div className="card" style={{ borderTop: "3px solid var(--gold)" }}>
          <h3>تجديد {renew.type === "permit" ? "إقامة/إذن" : "ترخيص"}</h3>
          <div className="row">
            <div className="field" style={{ flex: 1 }}><label>تاريخ الانتهاء الجديد</label>
              <input type="date" value={renew.expiry} onChange={(e) => setRenew({ ...renew, expiry: e.target.value })} /></div>
            {renew.type === "permit" && (
              <div className="field" style={{ flex: 1 }}><label>الرقم الجديد (اختياري)</label>
                <input value={renew.number || ""} onChange={(e) => setRenew({ ...renew, number: e.target.value })} /></div>
            )}
            <div className="field" style={{ flex: 2 }}><label>ملاحظة (اختياري)</label>
              <input value={renew.note || ""} onChange={(e) => setRenew({ ...renew, note: e.target.value })} /></div>
          </div>
          <div className="row">
            <button onClick={submitRenew} disabled={!renew.expiry}>حفظ التجديد</button>
            <button className="ghost" onClick={() => setRenew(null)}>إلغاء</button>
          </div>
        </div>
      )}

      {/* لوحة الملاحظات */}
      {notesFor && (
        <div className="card" style={{ borderTop: "3px solid var(--petrol-600)" }}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h3 style={{ margin: 0 }}>ملاحظات: {notesFor.label}</h3>
            <button className="ghost sm" onClick={() => setNotesFor(null)}>إغلاق</button>
          </div>
          <div className="row" style={{ margin: "10px 0" }}>
            <input value={noteText} onChange={(e) => setNoteText(e.target.value)} placeholder="أضف ملاحظة..." />
            <button onClick={addNote}>إضافة</button>
          </div>
          {notes.map((n, i) => (
            <div key={i} className="timeline-item">
              <span className={`pill ${n.action === "renew" ? "success" : "neutral"}`}>{n.action === "renew" ? "تجديد" : "ملاحظة"}</span> {n.note}
              <div className="muted">{n.by} · {new Date(n.at).toLocaleString("ar")}</div>
            </div>
          ))}
          {!notes.length && <div className="muted">لا ملاحظات بعد.</div>}
        </div>
      )}

      {/* الإقامات وأذونات العمل */}
      {tab === "permits" && (
        <div className="table-wrap">
          <table>
            <thead><tr><th>النوع</th><th>الموظف</th><th>الرقم</th><th>الانتهاء</th><th>المتبقّي</th><th></th></tr></thead>
            <tbody>
              {permits.map((p) => (
                <tr key={p.id}>
                  <td>{KIND_AR[p.kind] || p.kind}</td>
                  <td>{p.employee_name}</td>
                  <td className="muted">{p.number}</td>
                  <td>{p.expiry_date}</td>
                  <td><span className={`pill ${URGENCY_PILL[p.urgency]}`}>{daysText(p.days_left)}</span></td>
                  <td className="row">
                    <button className="sm" onClick={() => setRenew({ type: "permit", id: p.id, expiry: "", number: p.number })}>تجديد</button>
                    <button className="ghost sm" onClick={() => openNotes("permit", p.id, `${KIND_AR[p.kind]} - ${p.employee_name}`)}>ملاحظات</button>
                  </td>
                </tr>
              ))}
              {!permits.length && <tr><td colSpan={6} className="empty">لا توجد إقامات/أذونات.</td></tr>}
            </tbody>
          </table>
        </div>
      )}

      {/* التراخيص */}
      {tab === "licenses" && (
        <div className="table-wrap">
          <table>
            <thead><tr><th>الترخيص</th><th>الرقم</th><th>الجهة</th><th>الانتهاء</th><th>العمالة</th><th></th></tr></thead>
            <tbody>
              {licenses.map((l) => (
                <tr key={l.id}>
                  <td><b>{l.name}</b></td><td className="muted">{l.license_no}</td>
                  <td>{l.issuing_authority}</td><td>{l.expiry_date}</td>
                  <td><span className={`pill ${l.over_capacity ? "critical" : "neutral"}`}>{l.actual_workers}/{l.allowed_workers}</span></td>
                  <td className="row">
                    <button className="sm" onClick={() => setRenew({ type: "license", id: l.id, expiry: "" })}>تجديد</button>
                    <button className="ghost sm" onClick={() => openNotes("license", l.id, l.name)}>ملاحظات</button>
                  </td>
                </tr>
              ))}
              {!licenses.length && <tr><td colSpan={6} className="empty">لا توجد تراخيص.</td></tr>}
            </tbody>
          </table>
        </div>
      )}

      {/* الجهات الحكومية */}
      {tab === "gov" && gov && (
        <div className="grid cards">
          {gov.entities.map((ent: any) => (
            <div className="card" key={ent.authority} style={{ borderTop: "3px solid var(--petrol-600)" }}>
              <h3 style={{ margin: "0 0 8px" }}><Icon name="building" size={16} /> {ent.authority}</h3>
              {ent.licenses.map((l: any) => (
                <div key={l.id} className="row" style={{ justifyContent: "space-between", padding: "6px 0", borderTop: "1px solid var(--line)" }}>
                  <span>{l.name}</span>
                  <span className={`pill ${URGENCY_PILL[l.urgency]}`}>{daysText(l.days_left)}</span>
                </div>
              ))}
            </div>
          ))}
          {!gov.entities.length && <div className="card empty">لا توجد تراخيص مسجّلة.</div>}
        </div>
      )}
    </div>
  );
}
