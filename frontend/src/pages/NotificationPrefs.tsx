import { useEffect, useState } from "react";
import api, { errMsg } from "../api";
import { enablePush, permissionState } from "../push";
import { fmtKuwaitDateTime } from "../utils/datetime";
import { useI18n } from "../i18n";

// V2.2 §20 — تفضيلات إشعارات المستخدم (فئة × قناة)
type Pref = {
  category: string; channel: string; enabled: boolean;
  available?: boolean; unavailable_reason?: string | null;
};
type Channel = { channel: string; label: string; available: boolean; reason: string | null };

// P10-33 — القنوات من الخادم لا من مصفوفة هنا.
//
// كانت القائمة مكتوبة ثلاث مرّات (النموذج، الراوتر، وهذه المصفوفة)،
// والمفتاح يُعرض للأربع بلا شرط وافتراضه مُفعَّل — فيرى المستخدم واتساب
// والبريد يعملان ولا يصله شيء. والبريد لا صنف قناة له إطلاًقا.
const CHANNEL_LABEL_EN: Record<string, string> = {
  in_app: "In-app", whatsapp: "WhatsApp", sms: "SMS", email: "Email",
};

export default function NotificationPrefs() {
  const { lang } = useI18n();
  const isEn = lang === "en";
  const [rows, setRows] = useState<Pref[]>([]);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [devices, setDevices] = useState<any[]>([]);
  const [pushBusy, setPushBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => api.get("/notifications/preferences")
    .then(r => setRows(r.data))
    .catch(e => setErr(errMsg(e, isEn ? "Failed to load preferences" : "فشل تحميل التفضيلات")));

  const loadChannels = () => api.get("/notifications/channels")
    .then(r => setChannels(r.data)).catch(() => setChannels([]));

  const loadDevices = () => api.get("/notifications/devices")
    .then(r => setDevices(r.data)).catch(() => setDevices([]));

  useEffect(() => { load(); loadChannels(); loadDevices(); }, []);

  // P-FCM — الإذن يُطلب **بضغطة صريحة** لا عند فتح الصفحة: متصفّح يسأل
  // قبل أن يفهم المستخدم لماذا يُرفض غالًبا، والرفض في Chrome دائم ولا
  // يُعاد سؤاله.
  const askPush = async () => {
    setErr(""); setMsg(""); setPushBusy(true);
    const why = await enablePush();
    setPushBusy(false);
    if (why) { setErr(why); return; }
    setMsg(isEn ? "Device registered" : "سُجّل هذا الجهاز");
    loadDevices();
  };

  const dropDevice = async (id: number) => {
    setErr(""); setMsg("");
    try {
      await api.delete(`/notifications/devices/${id}`);
      setMsg(isEn ? "Device removed" : "أُلغي الجهاز");
      loadDevices();
    } catch (e: any) { setErr(errMsg(e, isEn ? "Failed" : "تعذّر الإلغاء")); }
  };

  const categories = Array.from(new Set(rows.map(r => r.category)));

  const toggle = (category: string, channel: string) => {
    // قناة لا تُسلِّم لا تُبدَّل: الحفظ عليها يَعِد بما لا يقع.
    if (!channels.find(c => c.channel === channel)?.available) return;
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

      {/* P-FCM — الأجهزة المسجَّلة. الإشعار الفوري يصل **جهاًزا** لا
          مستخدًما: الهاتف والحاسب لكلٍّ رمزه، فيُعرضان ليعرف صاحبهما
          أيّهما يُلغي. */}
      <div className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ marginTop: 0 }}>
          {isEn ? "Push notifications" : "الإشعارات الفورية"}
        </h3>
        <div className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
          {isEn
            ? "Get notified on your phone or browser even when HRMS is closed."
            : "تصلك التنبيهات على هاتفك أو متصفّحك حتى والنظام مغلق. "
              + "ولا تحمل بيانات حسّاسة — التفاصيل بعد تسجيل الدخول."}
        </div>

        {permissionState() === "unsupported" ? (
          <div className="muted">
            {isEn ? "This browser does not support push."
                  : "هذا المتصفّح لا يدعم الإشعارات الفورية"}
          </div>
        ) : (
          <button onClick={askPush} disabled={pushBusy}>
            {pushBusy
              ? (isEn ? "Registering..." : "جارٍ التسجيل...")
              : (isEn ? "Enable on this device" : "فعّل على هذا الجهاز")}
          </button>
        )}

        {devices.length > 0 && (
          <table style={{ width: "100%", borderCollapse: "collapse",
                          marginTop: 12 }}>
            <thead><tr>
              <th style={{ textAlign: "right", padding: 6 }}>
                {isEn ? "Device" : "الجهاز"}</th>
              <th style={{ padding: 6 }}>{isEn ? "Platform" : "المنصّة"}</th>
              <th style={{ padding: 6 }}>{isEn ? "Last seen" : "آخر وصول"}</th>
              <th style={{ padding: 6 }} />
            </tr></thead>
            <tbody>
              {devices.map((d) => (
                <tr key={d.id} style={{ borderTop: "1px solid var(--border, #e2e8f0)" }}>
                  <td style={{ padding: 6, fontSize: 12 }}>{d.label || "—"}</td>
                  <td style={{ padding: 6, textAlign: "center" }}>{d.platform}</td>
                  <td style={{ padding: 6, textAlign: "center", fontSize: 12 }}>
                    {d.last_seen_at
                      ? fmtKuwaitDateTime(d.last_seen_at, lang) : "—"}
                  </td>
                  <td style={{ padding: 6, textAlign: "center" }}>
                    <button className="ghost" onClick={() => dropDevice(d.id)}>
                      {isEn ? "Remove" : "إلغاء"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

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
                {channels.map(c => (
                  <th key={c.channel} style={{ padding: 8, minWidth: 90 }}
                      title={c.reason || undefined}>
                    {isEn ? (CHANNEL_LABEL_EN[c.channel] || c.label) : c.label}
                    {!c.available && (
                      <div className="muted" style={{ fontSize: 11, fontWeight: 400 }}>
                        {isEn ? "not available" : "غير مُفعَّلة"}
                      </div>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {categories.map(cat => (
                <tr key={cat} style={{ borderTop: "1px solid var(--border, #e2e8f0)" }}>
                  <td style={{ padding: 8 }}>{cat}</td>
                  {channels.map(c => {
                    const row = rows.find(r => r.category === cat && r.channel === c.channel);
                    const label = isEn ? (CHANNEL_LABEL_EN[c.channel] || c.label) : c.label;
                    return (
                      <td key={c.channel} style={{ padding: 8, textAlign: "center" }}
                          title={c.reason || undefined}>
                        <input
                          type="checkbox"
                          checked={(row?.enabled ?? false) && c.available}
                          disabled={!c.available}
                          onChange={() => toggle(cat, c.channel)}
                          aria-label={`${cat} — ${label}`}
                          aria-describedby={c.available ? undefined : `np-why-${c.channel}`}
                        />
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          {channels.some(c => !c.available) && (
            <div style={{ marginTop: 12 }}>
              {channels.filter(c => !c.available).map(c => (
                <div key={c.channel} className="muted" id={`np-why-${c.channel}`}
                     style={{ fontSize: 12 }}>
                  {(isEn ? (CHANNEL_LABEL_EN[c.channel] || c.label) : c.label)}: {c.reason}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
