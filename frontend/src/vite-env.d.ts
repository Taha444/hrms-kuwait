/// <reference types="vite/client" />
/// <reference types="vite-plugin-pwa/client" />

// V2.2 §9 — env vars الخاصة بالتطوير (تُقرأ من frontend/.env.local)
interface ImportMetaEnv {
  readonly VITE_SHOW_DEMO_HINT?: string; // "true" لعرض بيانات demo على شاشة الدخول
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
