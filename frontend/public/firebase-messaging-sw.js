/*
 * عامل خدمة الإشعارات الفورية.
 *
 * **لماذا ملف منفصل عن عامل PWA**: التطبيق يستعمل Workbox على نطاق
 * الجذر. وFirebase تسجّل عاملها على نطاق خاصّ
 * (`/firebase-cloud-messaging-push-scope`) فيتعايشان — أما دمجُهما
 * فيتطلّب تحويل البناء إلى `injectManifest` وإعادة كتابة عامل الـPWA،
 * وذلك تغيير في بنية النشر لا حاجة إليه.
 *
 * **والإعدادات من معاملات التسجيل لا مثبَّتة هنا**: الواجهة تقرؤها من
 * الخادم ثم تُمرّرها في رابط التسجيل. فتفعيل الدفع يصير متغيّر بيئة
 * على الخادم، لا نشرة واجهة جديدة.
 *
 * وقيم Firebase للويب علنية بطبعها — تُشحن في حزمة أي تطبيق ويب،
 * وأمنُها من قواعد المشروع لا من إخفائها.
 */
/* eslint-env serviceworker */
/* global importScripts, firebase, clients */

const params = new URL(self.location).searchParams;
const cfg = {
  apiKey: params.get("apiKey") || "",
  projectId: params.get("projectId") || "",
  appId: params.get("appId") || "",
  messagingSenderId: params.get("messagingSenderId") || "",
};

if (cfg.apiKey && cfg.projectId && cfg.appId && cfg.messagingSenderId) {
  importScripts(
    "https://www.gstatic.com/firebasejs/10.14.1/firebase-app-compat.js"
  );
  importScripts(
    "https://www.gstatic.com/firebasejs/10.14.1/firebase-messaging-compat.js"
  );

  firebase.initializeApp(cfg);
  const messaging = firebase.messaging();

  // الرسالة تصل والتطبيق مغلق — وهذا هو الغرض كلّه.
  messaging.onBackgroundMessage((payload) => {
    const n = payload.notification || {};
    const d = payload.data || {};
    // النصّ يصل **معتًَّما من الخادم** (push_policy.redact): لا يُبنى هنا
    // ولا يُضاف إليه شيء، فشاشة القفل لا تُظهر ما لم يُقرَّر إظهاره.
    self.registration.showNotification(n.title || "تحديث", {
      body: n.body || "",
      icon: "/icon.svg",
      badge: "/icon.svg",
      dir: "rtl",
      lang: "ar",
      // الرابط في البيانات لا في النصّ: لا يظهر مسار داخلي على الشاشة.
      data: { link: d.link || "/tasks" },
      // إشعارات متتابعة لنفس النوع تحلّ محلّ بعضها بدل أن تتكدّس.
      tag: d.kind || "hrms",
    });
  });
}

// الضغط يفتح ما يخصّ الإشعار — ويُعيد استعمال نافذة مفتوحة إن وُجدت،
// فلا تتكاثر التبويبات مع كل إشعار.
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const link = (event.notification.data && event.notification.data.link) || "/tasks";
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const c of list) {
        if (c.url.includes(self.location.origin) && "focus" in c) {
          c.navigate(link);
          return c.focus();
        }
      }
      return clients.openWindow(link);
    })
  );
});
