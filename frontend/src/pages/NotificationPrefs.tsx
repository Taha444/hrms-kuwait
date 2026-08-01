import { useEffect, useState } from "react";
import api, { errMsg } from "../api";
import { useI18n } from "../i18n";

// V2.2 §20 — تفضيلات إشعارات المستخدم (فئة × قناة)
type Pref = { category: string; channel: string; enabled: boolean };

const CHANNELS = ["in_app", "whatsapp", "sms", "email"];
const CHANNEL_LABEL_AR: Record<string, string> = {
  in_app: "داخل النظام", whatsapp: "واتساب", sms: "SMS", email: "بريد",
};
const CHANNEL_LABEL_EN: Record<string, string> = {
  in_app: "In-app", whatsapp: "WhatsApp", sms: "SMS", email: "Email",
};

export default function NotificationPrefs() {
  const { lang } = useI18n();
  const isEn = lang === "en";
  const [rows, setRows] = useState<Pref[]>([]);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => api.get("/notifications/preferences")
    .then(r => setRows(r.data))
    .catch(e => setErr(errMsg(e, isEn ? "Failed to load preferences" : "فشل تحميل التفضيلات")));

  useEffect(() => { load(); }, []);

  const categories = Array.from(new Set(rows.map(r => r.category)));

  const toggle = (category: string, channel: string) => {
    setRows(rs => rs.map(r =>
      (r.category === category && r.channel === channel) ? { ...r, enabled: !r.enabled } : r
    ));
  };

  const save = async () => {
    setErr(""); setMsg(""); setBusy(true);
    try {
      await api.put("/notifications/preferences", rows);
      setMsg(isEn ? "Saved successfully" : "تم الحفظ بنجاح");
    } catch (e: any) { setErr(errMsg(e, isEn ? "Save failed" : "فشل الحفظ")); }
    finally { setBusy(false); }
  };

  return (
    <div aria-labelledby="np-title">
      <div className="page-head">
        <div>
          <div className="eyebrow">{isEn ? "Settings" : "الإعدادات"}</div>
          <h2 id="np-title">{isEn ? "Notification Preferences" : "تفضيلات الإشعارات"}</h2>
          <div className="sub">
            {isEn
              ? "Choose which channels each category of notification uses"
              : "اختر القنوات المستخدمة لكل فئة إشعارات"}
          </div>
        </div>
        <button onClick={save} disabled={busy} aria-busy={busy}>
          {busy ? (isEn ? "Saving..." : "جارٍ الحفظ...") : (isEn ? "Save" : "حفظ")}
        </button>
      </div>

      {msg && <div className="ok" role="status" aria-live="polite">{msg}</div>}
      {err && <div className="err" role="alert" aria-live="assertive">{err}</div>}

      {categories.length === 0 ? (
        <div className="card"><p>{isEn ? "Loading..." : "جارٍ التحميل..."}</p></div>
      ) : (
        <div className="card" style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={{ textAlign: isEn ? "left" : "right", padding: 8 }}>
                  {isEn ? "Category" : "الفئة"}
                </th>
                {CHANNELS.map(ch => (
                  <th key={ch} style={{ padding: 8, minWidth: 90 }}>
                    {isEn ? CHANNEL_LABEL_EN[ch] : CHANNEL_LABEL_AR[ch]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {categories.map(cat => (
                <tr key={cat} style={{ borderTop: "1px solid var(--border, #e2e8f0)" }}>
                  <td style={{ padding: 8 }}>{cat}</td>
                  {CHANNELS.map(ch => {
                    const row = rows.find(r => r.category === cat && r.channel === ch);
                    return (
                      <td key={ch} style={{ padding: 8, textAlign: "center" }}>
                        <input
                          type="checkbox"
                          checked={row?.enabled ?? true}
                          onChange={() => toggle(cat, ch)}
                          aria-label={`${cat} — ${isEn ? CHANNEL_LABEL_EN[ch] : CHANNEL_LABEL_AR[ch]}`}
                        />
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
