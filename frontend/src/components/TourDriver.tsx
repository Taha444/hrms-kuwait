import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useI18n } from "../i18n";
import Icon from "../Icon";

/**
 * R5 §3 — محرّك جولات تعليمية قائم على تسليط الضوء (Spotlight).
 *
 * الفكرة:
 *  - نضع طبقة سوداء شبه شفافة تغطي الشاشة كلها ما عدا نافذة صغيرة (spotlight)
 *    تُظهر العنصر المستهدف واضحًا
 *  - نضع tooltip بجوار العنصر (فوق/تحت حسب المساحة) بعنوان + وصف + Next/Back/Skip/Finish
 *  - الأهداف تُحدَّد عبر `data-tour="…"` على الـDOM (لا refs، عشان الجولة تعمل
 *    على أي صفحة بلا تعديل داخلي فيها)
 *  - لو الهدف غير موجود على الصفحة الحالية، ننتقل تلقائيًا للـpath المذكور في الخطوة
 *
 * RTL جاهز: نستخدم insetInlineStart/End بدلاً من left/right.
 */

export type TourStep = {
  /** CSS selector للـtarget (مثل: '[data-tour="sidebar-tasks"]') */
  target: string;
  /** لو الهدف على صفحة أخرى، ننتقل لها أولًا */
  page?: string;
  title: string;
  body: string;
  /** موقع الـtooltip بالنسبة للـtarget (auto = يحسبه) */
  placement?: "top" | "bottom" | "start" | "end" | "auto";
};

type Props = {
  steps: TourStep[];
  open: boolean;
  onComplete: () => void;   // Finish
  onSkip: (stepReached: number) => void;
};

const HIGHLIGHT_PAD = 8;

export default function TourDriver({ steps, open, onComplete, onSkip }: Props) {
  const { lang } = useI18n();
  const isEn = lang === "en";
  const nav = useNavigate();
  const [idx, setIdx] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const [waiting, setWaiting] = useState(false);
  const tooltipRef = useRef<HTMLDivElement>(null);

  const step = steps[idx];

  // إذا الخطوة تحتاج صفحة معيّنة، انتقل لها أولاً
  useEffect(() => {
    if (!open || !step?.page) return;
    if (window.location.pathname !== step.page) {
      nav(step.page);
      setWaiting(true);
    }
  }, [open, idx, step?.page]);

  // نبحث عن الهدف — نعيد المحاولة كل 100ms حتى نجده (max 3 ثوان)
  useLayoutEffect(() => {
    if (!open || !step) { setRect(null); return; }
    let attempts = 0;
    const findTarget = () => {
      const el = document.querySelector(step.target) as HTMLElement | null;
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        // ننتظر انتهاء الـscroll قبل قياس الـrect
        setTimeout(() => {
          const r = el.getBoundingClientRect();
          setRect(r);
          setWaiting(false);
        }, 250);
        return true;
      }
      return false;
    };
    if (findTarget()) return;
    const timer = setInterval(() => {
      attempts++;
      if (findTarget() || attempts > 30) {
        clearInterval(timer);
        if (attempts > 30) {
          // ما لقيناش الهدف — نعرض tooltip في وسط الشاشة
          setRect(null);
          setWaiting(false);
        }
      }
    }, 100);
    return () => clearInterval(timer);
  }, [open, idx, step?.target]);

  // ESC للتخطي
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => {
      if (e.key === "Escape") onSkip(idx);
      if (e.key === "ArrowRight") next();
      if (e.key === "ArrowLeft") back();
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, idx]);

  if (!open || !step) return null;

  const next = () => {
    if (idx < steps.length - 1) setIdx(idx + 1);
    else onComplete();
  };
  const back = () => { if (idx > 0) setIdx(idx - 1); };

  // نحسب موقع الـtooltip
  const TOOLTIP_W = 340;
  const TOOLTIP_H = 180;
  let tipStyle: React.CSSProperties = {
    position: "fixed",
    width: TOOLTIP_W,
    zIndex: 10001,
    background: "white",
    borderRadius: 12,
    boxShadow: "0 20px 60px rgba(0,0,0,0.4)",
    padding: 18,
  };
  if (rect) {
    // نحاول نضع Tooltip تحت العنصر، أو فوقه لو مافيش مساحة
    const spaceBelow = window.innerHeight - rect.bottom;
    const spaceAbove = rect.top;
    const showBelow = spaceBelow >= TOOLTIP_H + 20 || spaceBelow >= spaceAbove;
    const top = showBelow
      ? rect.bottom + 12
      : Math.max(20, rect.top - TOOLTIP_H - 12);
    // Center horizontally on the target when possible; clamp to viewport
    let left = rect.left + rect.width / 2 - TOOLTIP_W / 2;
    left = Math.max(20, Math.min(left, window.innerWidth - TOOLTIP_W - 20));
    tipStyle = { ...tipStyle, top, left };
  } else {
    // Center on screen if target not found
    tipStyle = {
      ...tipStyle,
      top: "50%", left: "50%",
      transform: "translate(-50%, -50%)",
    };
  }

  return (
    <>
      {/* Backdrop: 4 مستطيلات حول العنصر تُظلّل كل شيء عداه (spotlight cutout).
          لو ما فيش target: طبقة واحدة تغطي الشاشة كاملة. */}
      {rect ? (
        <>
          {/* top */}
          <div style={{
            position: "fixed", top: 0, left: 0, right: 0,
            height: Math.max(0, rect.top - HIGHLIGHT_PAD),
            background: "rgba(11,59,84,0.75)", zIndex: 10000,
          }} />
          {/* bottom */}
          <div style={{
            position: "fixed", top: rect.bottom + HIGHLIGHT_PAD, left: 0, right: 0, bottom: 0,
            background: "rgba(11,59,84,0.75)", zIndex: 10000,
          }} />
          {/* left */}
          <div style={{
            position: "fixed",
            top: Math.max(0, rect.top - HIGHLIGHT_PAD),
            left: 0, width: Math.max(0, rect.left - HIGHLIGHT_PAD),
            height: rect.height + HIGHLIGHT_PAD * 2,
            background: "rgba(11,59,84,0.75)", zIndex: 10000,
          }} />
          {/* right */}
          <div style={{
            position: "fixed",
            top: Math.max(0, rect.top - HIGHLIGHT_PAD),
            left: rect.right + HIGHLIGHT_PAD,
            right: 0,
            height: rect.height + HIGHLIGHT_PAD * 2,
            background: "rgba(11,59,84,0.75)", zIndex: 10000,
          }} />
          {/* Highlight ring around target */}
          <div style={{
            position: "fixed",
            top: rect.top - HIGHLIGHT_PAD, left: rect.left - HIGHLIGHT_PAD,
            width: rect.width + HIGHLIGHT_PAD * 2,
            height: rect.height + HIGHLIGHT_PAD * 2,
            borderRadius: 10,
            boxShadow: "0 0 0 3px #fbbf24, 0 0 20px rgba(251,191,36,0.6)",
            pointerEvents: "none", zIndex: 10001,
          }} />
        </>
      ) : (
        <div style={{
          position: "fixed", inset: 0, background: "rgba(11,59,84,0.75)", zIndex: 10000,
        }} />
      )}

      {/* Tooltip */}
      <div ref={tooltipRef} style={tipStyle} role="dialog" aria-modal="true"
           aria-labelledby="tour-title">
        <div style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          marginBottom: 8,
        }}>
          <div style={{
            fontSize: 11, background: "#e0ece8", color: "#0b3b38",
            padding: "2px 10px", borderRadius: 10, fontWeight: 600,
          }}>
            {isEn ? `Step ${idx + 1} of ${steps.length}` : `الخطوة ${idx + 1} من ${steps.length}`}
          </div>
          <button onClick={() => onSkip(idx)}
                  style={{ background: "none", border: "none", cursor: "pointer",
                           color: "#6b7280", padding: 4 }}
                  aria-label={isEn ? "Skip tour" : "تجاوز الجولة"}>
            <Icon name="x" size={16} />
          </button>
        </div>

        <h3 id="tour-title" style={{ margin: "0 0 6px", fontSize: 17, color: "#0e5a54" }}>
          {step.title}
        </h3>
        <p style={{ margin: "0 0 14px", fontSize: 13, color: "#4b5563", lineHeight: 1.6 }}>
          {waiting ? (isEn ? "Loading…" : "جارٍ التحميل…") : step.body}
        </p>

        {/* Progress dots */}
        <div style={{ display: "flex", gap: 4, marginBottom: 14 }}>
          {steps.map((_, i) => (
            <div key={i} style={{
              flex: 1, height: 3, borderRadius: 2,
              background: i <= idx ? "#0e5a54" : "#e5e7eb",
            }} />
          ))}
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", gap: 6 }}>
          <button onClick={() => onSkip(idx)}
                  className="ghost sm" style={{ fontSize: 12 }}>
            {isEn ? "Skip" : "تجاوز"}
          </button>
          <div style={{ display: "flex", gap: 6 }}>
            {idx > 0 && (
              <button onClick={back} className="ghost sm" style={{ fontSize: 12 }}>
                {isEn ? "Back" : "السابق"}
              </button>
            )}
            <button onClick={next} style={{ fontSize: 13, padding: "6px 16px" }}>
              {idx === steps.length - 1
                ? (isEn ? "Finish ✓" : "إنهاء ✓")
                : (isEn ? "Next →" : "التالي ←")}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
