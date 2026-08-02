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

  return (
    <div>
      <h2>{t("br_title")}</h2>
      {msg && <div className="ok">{msg}</div>}

      {branches.map((b) => {
        const link = links[b.id];
        return (
          <div className="card" key={b.id}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <div>
                <b>{b.name}</b>
                <span className="muted"> · {t("geofence")} {b.geofence_radius_m}{t("meters")}</span>
              </div>
              <div className="row">
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
