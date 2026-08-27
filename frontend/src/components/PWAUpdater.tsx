import { useEffect, useState } from "react";
import { registerSW } from "virtual:pwa-register";

/**
 * R3-B §4 — يتحكم في تحديثات PWA Service Worker.
 *
 * السلوك:
 *  - يسجّل الـSW مع autoUpdate (vite-plugin-pwa)
 *  - لما deployment جديد ينزل، workbox (skipWaiting+clientsClaim) يفعّل
 *    الـSW الجديد فورًا، وهذا المكوّن يعرض توست صغير للمستخدم ويعيد التحميل
 *  - النتيجة: أي bug fix / feature يوصل لكل المستخدمين خلال ثوانٍ
 */
export default function PWAUpdater() {
  const [needsRefresh, setNeedsRefresh] = useState(false);

  useEffect(() => {
    const updateSW = registerSW({
      immediate: true,
      onNeedRefresh() {
        setNeedsRefresh(true);
      },
      onOfflineReady() {
        // النظام جاهز للعمل offline (المستخدم لا يحتاج إشعارًا)
      },
    });

    // لو المستخدم قبل الترقية — نطبقها ونعيد التحميل
    (window as any).__hrmsUpdateSW = () => updateSW(true);
  }, []);

  if (!needsRefresh) return null;

  return (
    <div style={{
      // bottom مرفوع فوق بصمة Operon (تقف عند 76px في نفس الزاوية المنطقية)
      position: "fixed", bottom: 84, insetInlineEnd: 26, zIndex: 999,
      background: "#0e5a54", color: "white", padding: "14px 18px",
      borderRadius: 10, boxShadow: "0 8px 24px rgba(0,0,0,0.25)",
      maxWidth: 340, fontSize: 14,
    }}>
      <div style={{ fontWeight: 600, marginBottom: 6 }}>
        🔄 نسخة جديدة متاحة
      </div>
      <div style={{ opacity: 0.9, marginBottom: 10, fontSize: 12 }}>
        اضغط للتحديث فورًا — البيانات المفتوحة ستُحفظ.
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <button
          onClick={() => (window as any).__hrmsUpdateSW?.()}
          style={{
            background: "white", color: "#0e5a54", border: "none",
            padding: "6px 14px", borderRadius: 6, cursor: "pointer",
            fontWeight: 600,
          }}
        >
          حدّث الآن
        </button>
        <button
          onClick={() => setNeedsRefresh(false)}
          style={{
            background: "transparent", color: "white",
            border: "1px solid rgba(255,255,255,0.3)",
            padding: "6px 14px", borderRadius: 6, cursor: "pointer",
          }}
        >
          لاحقًا
        </button>
      </div>
    </div>
  );
}
