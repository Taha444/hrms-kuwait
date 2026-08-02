/**
 * R1-C — طبقة عرض بتوقيت الكويت (Asia/Kuwait = UTC+3، بلا daylight saving).
 *
 * قاعدة صارمة:
 *  - الـbackend يخزن كل تواريخ audit/timestamps بـUTC (المصدر الأصلي).
 *  - أي عرض للمستخدم لازم يمر عبر fmtKuwait*() هنا — عشان لا يشوف المستخدم
 *    توقيت جهازه/متصفحه ولا UTC عاري.
 *  - "Asia/Kuwait" = UTC+3 دائمًا (بلا تحويل صيفي/شتوي في الكويت).
 */

const KUWAIT_TZ = "Asia/Kuwait";

function _parse(raw: string | Date | null | undefined): Date | null {
  if (!raw) return null;
  const d = raw instanceof Date ? raw : new Date(raw);
  return isNaN(d.getTime()) ? null : d;
}

/** يوم + وقت كامل بتوقيت الكويت: "2026-08-02 14:35" */
export function fmtKuwaitDateTime(raw: string | Date | null | undefined,
                                  lang: "ar" | "en" = "ar"): string {
  const d = _parse(raw);
  if (!d) return "—";
  const locale = lang === "en" ? "en-GB" : "ar-EG";
  // en-GB يعطي DD/MM/YYYY HH:mm — مناسب دوليًا وأوضح من MM/DD الأمريكي
  return d.toLocaleString(locale, {
    timeZone: KUWAIT_TZ,
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hour12: false,
  });
}

/** يوم فقط بتوقيت الكويت: "2026-08-02" */
export function fmtKuwaitDate(raw: string | Date | null | undefined,
                              lang: "ar" | "en" = "ar"): string {
  const d = _parse(raw);
  if (!d) return "—";
  const locale = lang === "en" ? "en-GB" : "ar-EG";
  return d.toLocaleDateString(locale, {
    timeZone: KUWAIT_TZ,
    year: "numeric", month: "2-digit", day: "2-digit",
  });
}

/** وقت فقط بتوقيت الكويت: "14:35" */
export function fmtKuwaitTime(raw: string | Date | null | undefined): string {
  const d = _parse(raw);
  if (!d) return "—";
  return d.toLocaleTimeString("en-GB", {
    timeZone: KUWAIT_TZ,
    hour: "2-digit", minute: "2-digit", hour12: false,
  });
}

/** "منذ 3 دقائق / منذ ساعتين" — للـtimelines. */
export function fmtRelative(raw: string | Date | null | undefined,
                            lang: "ar" | "en" = "ar"): string {
  const d = _parse(raw);
  if (!d) return "—";
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return lang === "en" ? "just now" : "الآن";
  if (diff < 3600) {
    const m = Math.floor(diff / 60);
    return lang === "en" ? `${m} min ago` : `منذ ${m} دقيقة`;
  }
  if (diff < 86400) {
    const h = Math.floor(diff / 3600);
    return lang === "en" ? `${h} h ago` : `منذ ${h} ساعة`;
  }
  return fmtKuwaitDateTime(raw, lang);
}

/** لوحة تفريقية توضح "بتوقيت الكويت" (badge صغير) — تُلحق بالجداول الحسّاسة. */
export const KUWAIT_TZ_LABEL = "بتوقيت الكويت (UTC+3)";
export const KUWAIT_TZ_LABEL_EN = "Kuwait Time (UTC+3)";
