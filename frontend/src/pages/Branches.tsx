import { useEffect, useState } from "react";
import api from "../api";
import { useI18n } from "../i18n";

// R3-A §5 — إدارة الفروع + مفتاح شاشة QR:
//   - المفتاح يُعرض masked (آخر 4 خانات) عند التحميل
//   - عند التدوير: modal يعرض المفتاح الكامل *مرة واحدة* مع تحذير
//   - رابط الشاشة الكامل يبقى قابلاً للنسخ (هو المسار المستخدم فعلًا)
type BranchLink = { masked: string | null; path: string | null };

export default function Branches() {
  const { t } = useI18n();
  const [branches, setBranches] = useState<any[]>([]);
  const [links, setLinks] = useState<Record<number, BranchLink>>({});
  const [msg, setMsg] = useState("");
  // Modal: المفتاح الجديد + التحذير — يظهر مرة واحدة بعد التدوير
  const [revealed, setRevealed] = useState<{
    branchName: string; key: string; url: string; warning: string;
  } | null>(null);

  const load = () => api.get("/branches").then((r) => setBranches(r.data));
  useEffect(() => { load(); }, []);

  const fullUrl = (path: string) => `${window.location.origin}${path}`;

  const loadLink = async (id: number) => {
    const r = await api.get(`/branches/${id}/kiosk-url`);
    setLinks((l) => ({
      ...l,
      [id]: {
        masked: r.data.kiosk_key_masked || null,
        path: r.data.kiosk_path ? fullUrl(r.data.kiosk_path) : null,
      },
    }));
  };
  useEffect(() => { branches.forEach((b) => loadLink(b.id)); }, [branches]);

  const rotate = async (branch: any) => {
    if (links[branch.id]?.masked && !confirm(
      "تدوير المفتاح سيُبطل الحالي فورًا. أي شاشة تستخدمه ستتوقف. متابعة؟"
    )) return;
    const r = await api.post(`/branches/${branch.id}/kiosk-key/rotate`);
    setLinks((l) => ({
      ...l,
      [branch.id]: {
        masked: r.data.kiosk_key_masked,
        path: fullUrl(r.data.kiosk_path),
      },
    }));
    setRevealed({
      branchName: branch.name,
      key: r.data.kiosk_key,
      url: fullUrl(r.data.kiosk_path),
      warning: r.data.warning,
    });
  };
  const copy = (text: string, label: string) => {
    navigator.clipboard?.writeText(text);
    setMsg(`✓ ${label} تم نسخه`);
  };

  // BR-EDIT — إنشاء الفرع وتعديله. **ولم تكن للفروع شاشٌة تُنشئ ولا
  // نقطٌة تُعدّل**: فرٌع بخطأ في اسمه يبقى به، وفرٌع بلا إحداثيات لا
  // يعمل فيه البصم بالموقع، وفرٌع بلا محافظة يوقف العقد الحكومي لكل
  // موظفيه — لأن المحافظة هي إدارة العمل المختصّة فيه.
  const EMPTY = {
    name: "", name_en: "", code: "", governorate: "", governorate_en: "",
    address: "", latitude: "", longitude: "", geofence_radius_m: "100",
  };
  const [form, setForm] = useState<any>(null);   // null = مغلق
  const [editing, setEditing] = useState<number | null>(null);
  const [err, setErr] = useState("");

  const openNew = () => { setForm({ ...EMPTY }); setEditing(null); setErr(""); };
  const openEdit = (b: any) => {
    setEditing(b.id); setErr("");
    setForm({
      name: b.name || "", name_en: b.name_en || "", code: b.code || "",
      governorate: b.governorate || "", governorate_en: b.governorate_en || "",
      address: b.address || "",
      latitude: b.latitude ?? "", longitude: b.longitude ?? "",
      geofence_radius_m: String(b.geofence_radius_m ?? 100),
    });
  };

  const save = async () => {
    setErr("");
    if (!form.name.trim()) { setErr(t("br_name_required")); return; }
    const body: any = {
      name: form.name.trim(),
      name_en: form.name_en.trim() || null,
      code: form.code.trim() || null,
      governorate: form.governorate.trim() || null,
      governorate_en: form.governorate_en.trim() || null,
      address: form.address.trim() || null,
    };
    // **الإحداثيات تُرسَل معًا أو لا تُرسَل**: نٌص فارغ يُقرأ صفًرا،
    // وصفٌر وصفٌر يضع الفرع في خليج غينيا فيمنع البصم عن كل موظفيه.
    if (form.latitude !== "" && form.longitude !== "") {
      body.latitude = Number(form.latitude);
      body.longitude = Number(form.longitude);
    }
    if (form.geofence_radius_m !== "") {
      body.geofence_radius_m = Number(form.geofence_radius_m);
    }
    try {
      if (editing) await api.put(`/branches/${editing}`, body);
      else await api.post("/branches", body);
      setForm(null); setEditing(null); setMsg(t("br_saved")); load();
    } catch (e: any) { setErr(e?.response?.data?.detail || t("error")); }
  };

  const FIELDS: [string, string, string?][] = [
    ["name", t("br_f_name")], ["name_en", t("br_f_name_en")],
    ["code", t("br_f_code"), t("br_f_code_hint")],
    ["governorate", t("br_f_gov"), t("br_f_gov_hint")],
    ["governorate_en", t("br_f_gov_en")],
    ["address", t("br_f_address")],
    ["latitude", t("br_f_lat"), t("br_f_geo_hint")], ["longitude", t("br_f_lng")],
    ["geofence_radius_m", t("geofence")],
  ];

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>{t("br_title")}</h2>
        <button onClick={openNew}>{t("br_new")}</button>
      </div>
      {msg && <div className="ok">{msg}</div>}

      {/* BR-EDIT — نموذج الفرع: إنشاًء وتعديًلا. */}
      {form && (
        <div className="card" style={{ borderInlineStart: "4px solid var(--brand)" }}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h3 style={{ margin: 0 }}>{editing ? t("br_edit") : t("br_new")}</h3>
            <button className="ghost sm" onClick={() => setForm(null)}>×</button>
          </div>
          {err && <div className="err">{err}</div>}
          <div className="grid cards" style={{ marginTop: 8 }}>
            {FIELDS.map(([key, label, hint]) => (
              <div className="field" key={key}>
                <label htmlFor={`br-${key}`}>{label}</label>
                <input id={`br-${key}`} value={form[key]}
                       inputMode={key === "latitude" || key === "longitude"
                                  || key === "geofence_radius_m" ? "decimal" : undefined}
                       onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
                {hint && <div className="muted" style={{ fontSize: 11 }}>{hint}</div>}
              </div>
            ))}
          </div>
          <div className="row" style={{ marginTop: 10 }}>
            <button onClick={save}>{t("save")}</button>
            <button className="ghost" onClick={() => setForm(null)}>{t("cancel")}</button>
          </div>
        </div>
      )}

      {branches.map((b) => {
        const link = links[b.id];
        return (
          <div className="card" key={b.id}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <div>
                <b>{b.name}</b>
                {b.code && <code style={{ marginInlineStart: 8, fontSize: 12 }}>{b.code}</code>}
                <span className="muted"> · {t("geofence")} {b.geofence_radius_m}{t("meters")}</span>
                {/* ما ينقص الفرع يُقال، فلا يُكتشَف حين يقف به عمل. */}
                {!b.governorate && (
                  <div style={{ fontSize: 12, color: "var(--danger)" }}>{t("br_no_gov")}</div>
                )}
                {(b.latitude == null || b.longitude == null) && (
                  <div style={{ fontSize: 12, color: "var(--warning)" }}>{t("br_no_geo")}</div>
                )}
              </div>
              <div className="row">
                <button className="ghost" onClick={() => openEdit(b)}>{t("br_edit")}</button>
                <button onClick={() => rotate(b)}>
                  {link?.masked ? "تدوير المفتاح" : t("br_rotate")}
                </button>
                {link?.path && (
                  <button className="ghost" onClick={() => window.open(link.path!, "_blank")}>
                    {t("br_open")}
                  </button>
                )}
              </div>
            </div>

            {link?.masked ? (
              <div style={{ marginTop: 10, fontSize: 13 }}>
                <span className="muted">مفتاح الشاشة: </span>
                <code style={{
                  background: "#f3f7f5", padding: "2px 8px", borderRadius: 4,
                  fontFamily: "monospace",
                }}>{link.masked}</code>
                <span className="muted" style={{ marginInlineStart: 8, fontSize: 11 }}>
                  (المفتاح الكامل يُعرض مرة واحدة عند التوليد فقط)
                </span>
              </div>
            ) : (
              <p className="muted">{t("br_no_key")}</p>
            )}

            {link?.path && (
              <div className="row" style={{ marginTop: 10 }}>
                <input aria-label={t("br_copy")} readOnly value={link.path}
                       onFocus={(e) => e.target.select()} />
                <button className="ghost" onClick={() => copy(link.path!, "رابط الشاشة")}>
                  {t("br_copy")}
                </button>
              </div>
            )}
          </div>
        );
      })}

      <div className="card muted">{t("br_hint")}</div>

      {/* Modal one-time reveal — R3-A §5 */}
      {revealed && (
        <div
          role="dialog" aria-modal="true"
          onClick={() => setRevealed(null)}
          style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)",
            display: "grid", placeItems: "center", zIndex: 1000, padding: 20,
          }}
        >
          <div onClick={(e) => e.stopPropagation()}
               style={{
                 background: "white", borderRadius: 12, padding: 24,
                 maxWidth: 560, width: "100%",
               }}>
            <h3 style={{ margin: "0 0 8px", color: "#065f46" }}>
              ✓ مفتاح جديد لـ{revealed.branchName}
            </h3>
            <div style={{
              background: "#fee2e2", border: "2px solid #ef4444", padding: 10,
              borderRadius: 6, fontSize: 13, color: "#7f1d1d", marginBottom: 12,
            }}>
              ⚠ <b>{revealed.warning}</b>
            </div>

            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4 }}>المفتاح الكامل:</div>
              <div className="row">
                <input readOnly value={revealed.key}
                       style={{ fontFamily: "monospace", fontSize: 12 }}
                       onFocus={(e) => e.target.select()} />
                <button onClick={() => copy(revealed.key, "المفتاح")}>نسخ</button>
              </div>
            </div>

            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4 }}>رابط الشاشة:</div>
              <div className="row">
                <input readOnly value={revealed.url}
                       onFocus={(e) => e.target.select()} />
                <button onClick={() => copy(revealed.url, "الرابط")}>نسخ</button>
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button onClick={() => window.open(revealed.url, "_blank")}>
                فتح الشاشة الآن
              </button>
              <button className="ghost" onClick={() => setRevealed(null)}>
                حفظت المفتاح، إغلاق
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
