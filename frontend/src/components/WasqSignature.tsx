/**
 * بصمة WASQ — محل بصمة Operon القديمة (كانت تُحمَّل من سكربت خارجي في
 * index.html بمعرّف #operon-signature). نفس الموضع، نفس السلوك، هوية جديدة.
 *
 * الموضع محسوب لا عشوائي (نفس منطق البصمة القديمة):
 * - inset-inline-end يعني اليسار في العربية واليمين في الإنجليزية، أي نهاية
 *   اتجاه القراءة وبعيًدا عن الشريط الجانبي في الحالتين.
 * - 26px هو padding المحتوى نفسه (styles.css)، فتقف البصمة على نفس شبكة
 *   البطاقات لا على رقم مخترع.
 * - هادئة حتى تُقصَد: نصف شفافية تكتمل عند المرور، فتُرى ولا تنافس محتوى
 *   الصفحة على الانتباه. تُخفى عند الطباعة (المستندات الرسمية تُطبع من
 *   المتصفح، لا داعي لبصمة بانٍ عليها).
 * - z-index أقل من أي نافذة حوار أو جولة تعليمية (999) فلا تعترض شيًئا فوقها.
 * - الخلفية شبه المعتمة (WASQ Brand Mark Kit، نفس تصميم wasq-built-by-badge.svg)
 *   تجعلها مقروءة فوق أي خلفية بالموقع — الصفحات الداكنة (تسجيل الدخول) أو
 *   الفاتحة (لوحة التحكم) — بلا حاجة لاكتشاف تلقائي للثيم.
 */
export default function WasqSignature() {
  return (
    <>
      <style>{`
        #wasq-signature {
          position: fixed;
          z-index: 900;
          inset-inline-end: 26px;
          bottom: 26px;
          opacity: .55;
          transition: opacity .25s ease;
        }
        #wasq-signature:hover { opacity: 1; }
        @media (max-width: 900px) {
          #wasq-signature {
            inset-inline-end: 18px;
            bottom: 18px;
          }
        }
        @media print { #wasq-signature { display: none !important; } }
      `}</style>
      <div id="wasq-signature">
        <a
          href="https://wasq-4d58f.web.app"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Built by WASQ"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 10,
            padding: "6px 14px 6px 10px",
            borderRadius: 999,
            background: "rgba(6,7,16,0.9)",
            border: "1px solid rgba(79,110,247,0.35)",
            backdropFilter: "blur(8px)",
            WebkitBackdropFilter: "blur(8px)",
            textDecoration: "none",
          }}
        >
          <svg viewBox="0 0 18 18" width="16" height="16" fill="none" aria-hidden="true">
            <polygon
              points="9,1 16.5,5 16.5,13 9,17 1.5,13 1.5,5"
              stroke="#4F6EF7" strokeWidth="0.9" fill="rgba(79,110,247,0.1)"
            />
            <polygon
              points="9,4.5 13,6.8 13,11.2 9,13.5 5,11.2 5,6.8"
              fill="#4F6EF7" fillOpacity="0.7"
            />
          </svg>
          <span style={{ display: "flex", flexDirection: "column", lineHeight: 1.15 }}>
            <span style={{
              fontFamily: "'JetBrains Mono', monospace", fontSize: 8.5,
              letterSpacing: "0.08em", color: "rgba(232,234,246,0.55)",
            }}>
              BUILT BY
            </span>
            <span style={{
              fontFamily: "'Chakra Petch', sans-serif", fontWeight: 700,
              fontSize: 11, letterSpacing: "0.14em", color: "#E8EAF6",
            }}>
              WASQ
              <span style={{
                fontFamily: "'Noto Kufi Arabic', sans-serif", fontWeight: 400,
                marginInlineStart: 6, color: "#C9A534",
              }}>
                وَسْق
              </span>
            </span>
          </span>
        </a>
      </div>
    </>
  );
}
