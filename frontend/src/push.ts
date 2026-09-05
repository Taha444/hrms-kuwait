import api from "./api";

/**
 * الإشعارات الفورية — طلب الإذن، وتسجيل الجهاز، واستقبال الرسالة.
 *
 * **الإذن لا يُطلب عند فتح الصفحة**: متصفّح يسأل «السماح بالإشعارات؟»
 * قبل أن يفهم المستخدم لماذا يُرفض غالًبا — والرفض في Chrome **دائم**
 * ولا يُعاد سؤاله. فالطلب يقع بضغطة صريحة من شاشة الإعدادات.
 *
 * **والإعدادات من الخادم لا من متغيّرات البناء**: تفعيل الدفع يصير
 * متغيّر بيئة، لا نشرة واجهة جديدة.
 */

export type PushConfig = {
  enabled: boolean;
  vapid_key: string;
  firebase: Record<string, string>;
  reason: string | null;
};

/** حالة الإذن كما يراها المتصفّح — لا كما نتمنّاها. */
export function permissionState(): NotificationPermission | "unsupported" {
  if (typeof Notification === "undefined" || !("serviceWorker" in navigator)) {
    return "unsupported";
  }
  return Notification.permission;
}

export async function loadConfig(): Promise<PushConfig | null> {
  try {
    const r = await api.get("/notifications/push-config");
    return r.data as PushConfig;
  } catch {
    return null;
  }
}

/** يسجّل عامل خدمة Firebase على نطاقه الخاص — لا يمسّ عامل الـPWA. */
async function registerWorker(cfg: PushConfig) {
  const q = new URLSearchParams(cfg.firebase).toString();
  return navigator.serviceWorker.register(
    `/firebase-messaging-sw.js?${q}`,
    { scope: "/firebase-cloud-messaging-push-scope" }
  );
}

/**
 * يطلب الإذن ويُسجّل الجهاز. يعيد سبب الفشل نًصا — لا `false` صامًتا:
 * من يضغط الزرّ ولا يحدث شيء يحتاج أن يعرف لماذا.
 */
export async function enablePush(label?: string): Promise<string | null> {
  const state = permissionState();
  if (state === "unsupported") {
    return "هذا المتصفّح لا يدعم الإشعارات الفورية";
  }
  if (state === "denied") {
    // الرفض دائم في Chrome — ولا يُعاد السؤال. فيُقال أين يُغيَّر.
    return "الإشعارات محظورة لهذا الموقع — غيّرها من إعدادات المتصفّح";
  }

  const cfg = await loadConfig();
  if (!cfg || !cfg.enabled) {
    return cfg?.reason || "الإشعارات الفورية غير مضبوطة على الخادم";
  }

  const granted = state === "granted"
    ? "granted"
    : await Notification.requestPermission();
  if (granted !== "granted") return "لم يُمنَح الإذن";

  try {
    const { initializeApp, getApps } = await import("firebase/app");
    const { getMessaging, getToken } = await import("firebase/messaging");

    const appInstance = getApps().length
      ? getApps()[0]
      : initializeApp(cfg.firebase as any);
    const reg = await registerWorker(cfg);
    const token = await getToken(getMessaging(appInstance), {
      vapidKey: cfg.vapid_key,
      serviceWorkerRegistration: reg,
    });
    if (!token) return "لم يُصدر المتصفّح رمز جهاز";

    await api.post("/notifications/devices", {
      token,
      platform: "web",
      // وصف يقرؤه صاحب الجهاز ليعرف أيّها يُلغي — لا بصمة تتبُّع.
      label: label || navigator.userAgent.slice(0, 60),
    });
    return null;
  } catch (e: any) {
    return e?.message || "تعذّر تسجيل الجهاز";
  }
}

/**
 * يعرض الإشعار **داخل الصفحة** حين تكون مفتوحة.
 *
 * الرسالة الواصلة والتطبيق مفتوح لا يعرضها النظام — يتلقّاها التطبيق.
 * وبلا هذا يبدو الدفع معطًَّلا لمن يجلس أمام الشاشة.
 */
export async function listenInApp(onMessage: (t: string, b: string, link: string) => void) {
  const cfg = await loadConfig();
  if (!cfg?.enabled) return;
  try {
    const { initializeApp, getApps } = await import("firebase/app");
    const { getMessaging, onMessage: onMsg } = await import("firebase/messaging");
    const appInstance = getApps().length
      ? getApps()[0]
      : initializeApp(cfg.firebase as any);
    onMsg(getMessaging(appInstance), (payload) => {
      const n = payload.notification || {};
      onMessage(n.title || "تحديث", n.body || "",
                (payload.data as any)?.link || "/tasks");
    });
  } catch {
    /* التطبيق يعمل بلا هذا — الإشعار الداخلي موجود في كل الأحوال */
  }
}
