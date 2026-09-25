/**
 * بصمة WASQ — ختم مصغّر يتفتّح عند اللمس، لا شريط ثابت.
 *
 * الفكرة: بصمة حقيقية لا تُقرأ إلا حين تُقصَد — دائرة زجاجية شبه شفافة لا
 * تحمل غير الشعار في حالة السكون، وعند المرور/اللمس تتفتّح أفقيًا فتكشف
 * الاسم، ويلمع الشعار بدورة كاملة، وتتوهّج الحافة بذهب الهوية — كأنها ختمٌ
 * يُقلَب ليُري وجهه لحظة أن يُلمَس. الألوان بترول+ذهب الموقع نفسه (styles.css)
 * لا ألوان WASQ الأصلية (النيلي) — فالختم موقّع بلون هذا الموقع بالذات، لا
 * ملصقٌ مستورد عليه.
 *
 * الموضع والسلوك الأساسي محفوظان من البصمة السابقة (Operon ثم WASQ الأولى):
 * - نفس نقطة الإزاحة (26px، 18px على الموبايل) على شبكة المحتوى نفسها.
 * - نفس الطبقة (z-index 900) تحت أي نافذة حوار أو جولة تعليمية.
 * - تختفي عند الطباعة.
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
        }
        @media (max-width: 900px) {
          #wasq-signature { inset-inline-end: 18px; bottom: 18px; }
        }
        @media print { #wasq-signature { display: none !important; } }

        .wasq-seal {
          position: relative;
          display: inline-flex;
          align-items: center;
          height: 36px;
          padding-inline: 8px;
          border-radius: 999px;
          text-decoration: none;
          overflow: hidden;
          white-space: nowrap;
          background: rgba(14,90,84,0.10);
          border: 1px solid rgba(201,162,39,0.28);
          backdrop-filter: blur(7px);
          -webkit-backdrop-filter: blur(7px);
          box-shadow: 0 0 0 0 rgba(201,162,39,0);
          opacity: .68;
          transition: opacity .3s ease, background .4s ease, border-color .4s ease,
                      box-shadow .4s ease, padding-inline-end .4s ease;
        }
        .wasq-seal:hover, .wasq-seal:focus-visible {
          opacity: 1;
          padding-inline-end: 14px;
          background: linear-gradient(135deg, rgba(14,90,84,0.94), rgba(8,37,35,0.94));
          border-color: var(--gold, #c9a227);
          box-shadow: 0 6px 22px rgba(201,162,39,.32), 0 0 0 3px rgba(201,162,39,.10);
          outline: none;
        }

        .wasq-seal-icon {
          flex: none;
          display: flex;
          width: 20px; height: 20px;
        }
        .wasq-seal-icon svg { display: block; transition: transform .7s cubic-bezier(.2,.8,.2,1); }
        .wasq-seal:hover .wasq-seal-icon svg,
        .wasq-seal:focus-visible .wasq-seal-icon svg { transform: rotate(360deg); }

        .wasq-seal-text {
          display: flex;
          flex-direction: column;
          line-height: 1.15;
          max-width: 0;
          opacity: 0;
          margin-inline-start: 0;
          overflow: hidden;
          transition: max-width .4s ease, opacity .3s ease .05s, margin-inline-start .4s ease;
        }
        .wasq-seal:hover .wasq-seal-text,
        .wasq-seal:focus-visible .wasq-seal-text {
          max-width: 160px;
          opacity: 1;
          margin-inline-start: 9px;
        }

        .wasq-seal-label {
          font-family: 'JetBrains Mono', monospace;
          font-size: 8px;
          letter-spacing: .1em;
          color: rgba(243,230,184,0.65);
        }
        .wasq-seal-name {
          font-family: 'Chakra Petch', sans-serif;
          font-weight: 700;
          font-size: 11px;
          letter-spacing: .1em;
          color: #f3e6b8;
        }
        .wasq-seal-name .ar {
          font-family: 'Noto Kufi Arabic', sans-serif;
          font-weight: 400;
          margin-inline-start: 5px;
          color: var(--gold, #c9a227);
        }

        @media (prefers-reduced-motion: reduce) {
          .wasq-seal, .wasq-seal-icon svg, .wasq-seal-text { transition: none !important; }
          .wasq-seal:hover .wasq-seal-icon svg { transform: none; }
        }
      `}</style>
      <div id="wasq-signature">
        <a
          href="https://wasq-4d58f.web.app"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Built by WASQ"
          className="wasq-seal"
        >
          <span className="wasq-seal-icon">
            <svg viewBox="0 0 18 18" width="20" height="20" fill="none" aria-hidden="true">
              <polygon
                points="9,1 16.5,5 16.5,13 9,17 1.5,13 1.5,5"
                stroke="#c9a227" strokeWidth="1" fill="rgba(14,90,84,0.35)"
              />
              <polygon
                points="9,4.5 13,6.8 13,11.2 9,13.5 5,11.2 5,6.8"
                fill="#c9a227" fillOpacity="0.85"
              />
            </svg>
          </span>
          <span className="wasq-seal-text">
            <span className="wasq-seal-label">BUILT BY</span>
            <span className="wasq-seal-name">
              WASQ<span className="ar">وَسْق</span>{/* i18n: data — اسمُ العلامة التجارية (وَسْق) يُكتب بالعربية والإنجليزية معًا عمدًا */}
            </span>
          </span>
        </a>
      </div>
    </>
  );
}
