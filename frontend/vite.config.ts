import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// إعداد Vite + PWA (service worker + manifest) + بروكسي لواجهة الـ API
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      manifest: {
        name: "نظام الموارد البشرية - الكويت",
        short_name: "HRMS",
        description: "نظام ERP لإدارة الموارد البشرية متعدد الشركات",
        lang: "ar",
        dir: "rtl",
        theme_color: "#0f766e",
        background_color: "#ffffff",
        display: "standalone",
        start_url: "/",
        icons: [
          { src: "icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
          { src: "icon.svg", sizes: "any", type: "image/svg+xml", purpose: "maskable" }
        ]
      },
      workbox: {
        navigateFallbackDenylist: [/^\/api/, /^\/uploads/],
        // R3-B §4 — تفعيل فوري بعد أي deployment جديد:
        //   skipWaiting: SW الجديد يتخطى مرحلة "waiting" ويحل محل القديم فورًا
        //   clientsClaim: يسيطر على الـtabs المفتوحة الآن (ما ننتظرش reload يدوي)
        //   cleanupOutdatedCaches: يمسح ملفات الـcache القديمة اللي ما بقتش مطلوبة
        // النتيجة: لما ندفع build جديد، متصفحات المستخدمين تحدّث خلال ثوانٍ
        // (بدل يظلوا يشوفوا النسخة القديمة لغاية ما يعملوا refresh يدوي)
        skipWaiting: true,
        clientsClaim: true,
        cleanupOutdatedCaches: true
      }
    })
  ],
  server: {
    port: 5173,
    proxy: {
      // المنفذ 8000 محجوز على بعض أجهزة ويندوز (Hyper-V/WSL) — نستخدم 8001 للتطوير
      "/api": { target: "http://127.0.0.1:8001", changeOrigin: true },
      "/uploads": { target: "http://127.0.0.1:8001", changeOrigin: true }
    }
  }
});
