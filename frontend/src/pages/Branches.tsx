import { useEffect, useState } from "react";
import api from "../api";

// إدارة الفروع + رابط شاشة عرض QR (توليد/تدوير المفتاح).
export default function Branches() {
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
    setMsg("تم توليد/تدوير مفتاح الشاشة — الرابط القديم لم يعد صالحًا.");
  };
  const copy = (url: string) => { navigator.clipboard?.writeText(url); setMsg("تم نسخ الرابط."); };

  return (
    <div>
      <h2>الفروع وشاشات عرض QR</h2>
      {msg && <div className="ok">{msg}</div>}
      {branches.map((b) => (
        <div className="card" key={b.id}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <div><b>{b.name}</b> <span className="muted">· نطاق {b.geofence_radius_m}م</span></div>
            <div className="row">
              <button onClick={() => rotate(b.id)}>توليد / تدوير مفتاح الشاشة</button>
              {links[b.id] && <button className="ghost" onClick={() => window.open(links[b.id], "_blank")}>فتح الشاشة</button>}
            </div>
          </div>
          {links[b.id] && (
            <div className="row" style={{ marginTop: 10 }}>
              <input readOnly value={links[b.id]} onFocus={(e) => e.target.select()} />
              <button className="ghost" onClick={() => copy(links[b.id])}>نسخ</button>
            </div>
          )}
          {!links[b.id] && <p className="muted">لم يُولّد مفتاح شاشة بعد لهذا الفرع.</p>}
        </div>
      ))}
      <div className="card muted">
        افتح رابط الشاشة على أي جهاز في الفرع بوضع ملء الشاشة. يتجدّد الرمز تلقائيًا
        ويبقى متزامنًا مع تطبيق الموظفين عبر الخادم — بلا أي تحديث يدوي.
      </div>
    </div>
  );
}
