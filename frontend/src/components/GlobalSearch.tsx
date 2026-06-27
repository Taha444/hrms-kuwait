import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";
import Icon from "../Icon";

// البحث الشامل من الشريط العلوي — يبحث في كل الكيانات ويُصنّف النتائج.
const CAT_AR: Record<string, string> = {
  employees: "الموظفون", companies: "الشركات", branches: "الفروع",
  licenses: "التراخيص", permits: "الإقامات",
};

export default function GlobalSearch() {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [res, setRes] = useState<any>(null);
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);
  const timer = useRef<any>(null);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const onChange = (v: string) => {
    setQ(v);
    clearTimeout(timer.current);
    if (v.trim().length < 2) { setRes(null); return; }
    timer.current = setTimeout(() => {
      api.get("/search", { params: { q: v } }).then((r) => { setRes(r.data); setOpen(true); }).catch(() => {});
    }, 250);
  };

  const goto = (link: string) => { setOpen(false); setQ(""); setRes(null); nav(link); };

  return (
    <div ref={boxRef} style={{ position: "relative", flex: 1, maxWidth: 420 }}>
      <div style={{ position: "relative" }}>
        <span style={{ position: "absolute", insetInlineStart: 12, top: 11, color: "var(--muted)" }}>
          <Icon name="scan" size={16} />
        </span>
        <input value={q} onChange={(e) => onChange(e.target.value)} onFocus={() => res && setOpen(true)}
          placeholder="بحث شامل: موظف · شركة · فرع · ترخيص · إقامة"
          style={{ paddingInlineStart: 36, background: "var(--surface-2)" }} />
      </div>
      {open && res && (
        <div style={{
          position: "absolute", top: "calc(100% + 6px)", insetInlineStart: 0, insetInlineEnd: 0,
          background: "#fff", border: "1px solid var(--line)", borderRadius: 12,
          boxShadow: "var(--shadow)", zIndex: 50, maxHeight: 420, overflowY: "auto", padding: 6,
        }}>
          {res.total === 0 && <div className="muted" style={{ padding: 14, textAlign: "center" }}>لا نتائج لـ «{res.query}»</div>}
          {Object.entries(res.results).map(([cat, items]: any) => items.length > 0 && (
            <div key={cat}>
              <div className="muted" style={{ fontSize: 11, fontWeight: 700, padding: "8px 10px 4px" }}>{CAT_AR[cat] || cat}</div>
              {items.map((it: any, i: number) => (
                <div key={i} onClick={() => goto(it.link)} style={{ padding: "8px 10px", borderRadius: 8, cursor: "pointer" }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-2)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
                  <div style={{ fontWeight: 600, fontSize: 13.5 }}>{it.label}</div>
                  {it.sub && <div className="muted" style={{ fontSize: 12 }}>{it.sub}</div>}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
