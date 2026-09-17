import api from "./api";
import { tr } from "./i18n";

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

/** آخر سبب فشل في قراءة الإعدادات — يُقرأ لا يُخمَّن. */
let lastConfigError = "";

export async function loadConfig(): Promise<PushConfig | null> {
  try {
    const r = await api.get("/notifications/push-config");
    lastConfigError = "";
    return r.data as PushConfig;
  } catch (e: any) {
    // **لا ``catch`` صامت.** كان الفشل هنا يُبتلَع، فتقول الشاشة
    // «غير مضبوطة على الخادم» أًيا كان السبب — وهي رسالة تتّهم الإعداد
    // بينما قد يكون الطلب نفسه رُدّ بـ401 أو 500. فيبحث المالك في
    // متغيّرات البيئة عن عطل ليس فيها.
    const status = e?.response?.status;
    const detail = e?.response?.data?.detail;
    lastConfigError = status
      ? tr("push_cfg_error", { status: `${status}${detail ? ": " + detail : ""}` })
      : tr("push_unreachable");
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
    return tr("push_unsupported");
  }
  if (state === "denied") {
    // الرفض دائم في Chrome — ولا يُعاد السؤال. فيُقال أين يُغيَّر.
    return tr("push_denied");
  }

  const cfg = await loadConfig();
  if (!cfg) return lastConfigError || tr("push_cfg_unreadable");
  if (!cfg.enabled) {
    // سبب الخادم أدقّ من أي نصّ نكتبه هنا: يسمّي الناقص بعينه.
    return cfg.reason || tr("push_not_configured");
  }

  const granted = state === "granted"
    ? "granted"
    : await Notification.requestPermission();
  if (granted !== "granted") return tr("push_not_granted");

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
    if (!token) return tr("push_no_token");

    await api.post("/notifications/devices", {
      token,
      platform: "web",
      // وصف يقرؤه صاحب الجهاز ليعرف أيّها يُلغي — لا بصمة تتبُّع.
      label: label || navigator.userAgent.slice(0, 60),
    });
    return null;
  } catch (e: any) {
    return e?.message || tr("push_register_failed");
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
      onMessage(n.title || tr("push_update"), n.body || "",
                (payload.data as any)?.link || "/tasks");
    });
  } catch {
    /* التطبيق يعمل بلا هذا — الإشعار الداخلي موجود في كل الأحوال */
  }
}
