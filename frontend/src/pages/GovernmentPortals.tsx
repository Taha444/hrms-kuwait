import { useEffect, useState } from "react";
import api, { errMsg } from "../api";
import { useI18n } from "../i18n";
import Icon from "../Icon";

/**
 * R8 §1 — الروابط الحكومية.
 *
 * - PRO + الإدارة: عرض الروابط مع أزرار فتح في tab جديدة
 * - super_admin + company_manager: إضافة/تعديل/إخفاء
 * - الروابط مجمّعة حسب الفئة (residency / civil_id / moci / ...)
 */

type Portal = {
  id: number;
  name_ar: string; name_en?: string;
  description_ar?: string; description_en?: string;
  url: string; category: string; icon?: string;
  sort_order: number; is_active: boolean;
};

type Group = { category: string; label: string; portals: Portal[] };

export default function GovernmentPortals() {
  const { t, lang } = useI18n();
  const isEn = lang === "en";
  const [data, setData] = useState<{ can_manage: boolean; groups: Group[];
                                     category_labels: Record<string, string> } | null>(null);
  const [err, setErr] = useState("");
  const [editing, setEditing] = useState<Partial<Portal> | null>(null);

  const load = () => api.get("/gov-portals").then((r) => setData(r.data))
    .catch((e) => setErr(errMsg(e, t("error"))));
  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!editing?.name_ar || !editing?.url) {
      setErr(isEn ? "Name & URL required" : "الاسم والرابط مطلوبان");
      return;
    }
    setErr("");
    try {
      const payload = {
        name_ar: editing.name_ar,
        name_en: editing.name_en || null,
        description_ar: editing.description_ar || null,
        description_en: editing.description_en || null,
        url: editing.url,
        category: editing.category || "other",
        icon: editing.icon || null,
        sort_order: editing.sort_order || 100,
        is_active: editing.is_active !== false,
      };
      if (editing.id) await api.put(`/gov-portals/${editing.id}`, payload);
      else await api.post("/gov-portals", payload);
      setEditing(null);
      load();
    } catch (e: any) { setErr(errMsg(e, t("error"))); }
  };

  const toggleActive = async (p: Portal) => {
    await api.put(`/gov-portals/${p.id}`, { ...p, is_active: !p.is_active });
    load();
  };

  const remove = async (p: Portal) => {
    if (!confirm(isEn ? `Delete "${p.name_ar}"?` : `حذف "${p.name_ar}" نهائيًا؟`)) return;
    try { await api.delete(`/gov-portals/${p.id}`); load(); }
    catch (e: any) { setErr(errMsg(e, t("error"))); }
  };

  if (!data) return <div className="card">{t("loading")}</div>;

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="eyebrow">{isEn ? "PRO Tools" : "أدوات المندوب"}</div>
          <h2 style={{ margin: "2px 0 0" }}>
            {isEn ? "Government Portals" : "الروابط الحكومية"}
          </h2>
          <div className="sub">
            {isEn ? "Quick access to government service portals used in PRO work."
                  : "وصول سريع للمواقع الحكومية المستخدمة في شغل المندوب."}
          </div>
        </div>
        {data.can_manage && (
          <button onClick={() => setEditing({ category: "other", is_active: true, sort_order: 100 })}>
            {isEn ? "+ Add portal" : "+ إضافة رابط"}
          </button>
        )}
      </div>

      {err && <div className="err">{err}</div>}

      {/* Form إضافة/تعديل */}
      {editing && (
        <div className="card" style={{ borderTop: "3px solid var(--gold)", marginBottom: 16 }}>
          <h3 style={{ marginTop: 0 }}>
            {editing.id ? (isEn ? "Edit portal" : "تعديل رابط")
                        : (isEn ? "New portal" : "رابط جديد")}
          </h3>
          <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
            <div className="field" style={{ flex: 1, minWidth: 200 }}>
              <label>{isEn ? "Name (Arabic) *" : "الاسم بالعربية *"}</label>
              <input value={editing.name_ar || ""}
                     onChange={(e) => setEditing({ ...editing, name_ar: e.target.value })} />
            </div>
            <div className="field" style={{ flex: 1, minWidth: 200 }}>
              <label>{isEn ? "Name (English)" : "الاسم بالإنجليزية"}</label>
              <input value={editing.name_en || ""}
                     onChange={(e) => setEditing({ ...editing, name_en: e.target.value })} />
            </div>
          </div>
          <div className="field">
            <label>{isEn ? "URL *" : "الرابط *"}</label>
            <input dir="ltr" value={editing.url || ""}
                   onChange={(e) => setEditing({ ...editing, url: e.target.value })}
                   placeholder="https://..." />
          </div>
          <div className="field">
            <label>{isEn ? "Description (Arabic)" : "وصف مختصر بالعربية"}</label>
            <input value={editing.description_ar || ""}
                   onChange={(e) => setEditing({ ...editing, description_ar: e.target.value })} />
          </div>
          <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
            <div className="field" style={{ minWidth: 180 }}>
              <label>{isEn ? "Category" : "الفئة"}</label>
              <select value={editing.category || "other"}
                      onChange={(e) => setEditing({ ...editing, category: e.target.value })}>
                {Object.entries(data.category_labels).map(([code, label]) => (
                  <option key={code} value={code}>{label}</option>
                ))}
              </select>
            </div>
            <div className="field" style={{ width: 120 }}>
              <label>{isEn ? "Icon (emoji)" : "أيقونة (emoji)"}</label>
              <input value={editing.icon || ""}
                     onChange={(e) => setEditing({ ...editing, icon: e.target.value })}
                     placeholder="🏛️" maxLength={4} />
            </div>
            <div className="field" style={{ width: 120 }}>
              <label>{isEn ? "Sort order" : "الترتيب"}</label>
              <input type="number" value={editing.sort_order || 100}
                     onChange={(e) => setEditing({ ...editing, sort_order: +e.target.value })} />
            </div>
            <div className="field" style={{ minWidth: 100 }}>
              <label>&nbsp;</label>
              <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
                <input type="checkbox" checked={editing.is_active !== false}
                       onChange={(e) => setEditing({ ...editing, is_active: e.target.checked })} />
                {isEn ? "Active" : "مفعّل"}
              </label>
            </div>
          </div>
          <div className="row" style={{ marginTop: 12 }}>
            <button onClick={save}>{isEn ? "Save" : "حفظ"}</button>
            <button className="ghost" onClick={() => setEditing(null)}>
              {isEn ? "Cancel" : "إلغاء"}
            </button>
          </div>
        </div>
      )}

      {/* الروابط مجمّعة حسب الفئة */}
      {data.groups.length === 0 && (
        <div className="card muted">
          {isEn ? "No portals defined yet."
                : "لا توجد روابط حكومية مضافة بعد."}
        </div>
      )}

      {data.groups.map((g) => (
        <div key={g.category} className="card" style={{ marginBottom: 12 }}>
          <h3 style={{ margin: "0 0 12px", color: "var(--petrol-700, #0b3b54)" }}>
            {g.label}
          </h3>
          <div style={{ display: "grid",
                        gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
                        gap: 10 }}>
            {g.portals.map((p) => (
              <div key={p.id} style={{
                border: "1px solid var(--line)", borderRadius: 8, padding: 12,
                background: p.is_active ? "white" : "#f5f5f5",
                opacity: p.is_active ? 1 : 0.6,
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                  {p.icon && <span style={{ fontSize: 20 }}>{p.icon}</span>}
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600 }}>
                      {isEn && p.name_en ? p.name_en : p.name_ar}
                    </div>
                    {p.description_ar && (
                      <div className="muted" style={{ fontSize: 12 }}>
                        {isEn && p.description_en ? p.description_en : p.description_ar}
                      </div>
                    )}
                  </div>
                </div>
                <div className="row" style={{ marginTop: 8, gap: 6 }}>
                  <a href={p.url} target="_blank" rel="noopener noreferrer"
                     className="btn" style={{ flex: 1, textAlign: "center",
                                             textDecoration: "none", padding: "6px 12px" }}>
                    {isEn ? "Open ↗" : "فتح ↗"}
                  </a>
                  {data.can_manage && (
                    <>
                      <button className="ghost sm" onClick={() => setEditing(p)}>
                        <Icon name="doc" size={14} />
                      </button>
                      <button className="ghost sm" onClick={() => toggleActive(p)}
                              title={p.is_active ? (isEn ? "Hide" : "إخفاء") : (isEn ? "Show" : "إظهار")}>
                        {p.is_active ? "👁️" : "🚫"}
                      </button>
                      <button className="ghost sm danger" onClick={() => remove(p)}
                              title={isEn ? "Delete" : "حذف"}>
                        <Icon name="x" size={14} />
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
