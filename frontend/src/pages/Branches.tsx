import { useEffect, useState } from "react";
import api from "../api";
import { useI18n } from "../i18n";

// إدارة الفروع + رابط شاشة عرض QR (توليد/تدوير المفتاح).
export default function Branches() {
  const { t } = useI18n();
  const [branches, setBranches] = useState<any[]>([]);
  const [links, setLinks] = useState<Record<number, string>>({});
  const [msg, setMsg] = useState("");

  const load = () => api.get("/branches").then((r) => setBranches(r.data));
  useEffect(() => { load(); }, []);

  const fullUrl = (path: string) => `${window.location.origin}${path}`;

  const loadLink = async (id: number) => {
    const r = await api.get(`/branches/${id}/kiosk-url`);
    if (r.data.kiosk_path) setLinks((l) => ({ ...l, [id]: fullUrl(r.data.kiosk_path) }));
  };
  useEffect(() => { branches.forEach((b) => loadLink(b.id)); }, [branches]);

  const rotate = async (id: number) => {
    const r = await api.post(`/branches/${id}/kiosk-key/rotate`);
    setLinks((l) => ({ ...l, [id]: fullUrl(r.data.kiosk_path) }));
    setMsg(t("br_rotated"));
  };
  const copy = (url: string) => { navigator.clipboard?.writeText(url); setMsg(t("br_copied")); };

  return (
    <div>
      <h2>{t("br_title")}</h2>
      {msg && <div className="ok">{msg}</div>}
      {branches.map((b) => (
        <div className="card" key={b.id}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <div><b>{b.name}</b> <span className="muted">· {t("geofence")} {b.geofence_radius_m}{t("meters")}</span></div>
            <div className="row">
              <button onClick={() => rotate(b.id)}>{t("br_rotate")}</button>
              {links[b.id] && <button className="ghost" onClick={() => window.open(links[b.id], "_blank")}>{t("br_open")}</button>}
            </div>
          </div>
          {links[b.id] && (
            <div className="row" style={{ marginTop: 10 }}>
              <input readOnly value={links[b.id]} onFocus={(e) => e.target.select()} />
              <button className="ghost" onClick={() => copy(links[b.id])}>{t("br_copy")}</button>
            </div>
          )}
          {!links[b.id] && <p className="muted">{t("br_no_key")}</p>}
        </div>
      ))}
      <div className="card muted">{t("br_hint")}</div>
    </div>
  );
}
