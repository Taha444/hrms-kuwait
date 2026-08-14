import { useAuth } from "../auth";
import { useI18n } from "../i18n";

/**
 * QA-16 — حالة فارغة موحّدة للصفحات التي تحتاج شركة محددة.
 *
 * ROOT CAUSE: صفحات مثل الأرشيف تعمل على شركة واحدة، فإذا اختار المالك
 * "كل الشركات" رجعت النتيجة فارغة — وعُرضت برسالة "لا توجد مستندات بعد".
 * الرسالة صحيحة نحوًيا وخاطئة معنى: لا شيء ناقص، الشركة فقط لم تُحدَّد.
 * المستخدم يقرأ الفراغ كعطل أو كفقدان بيانات.
 *
 * `needsCompany()` يخبر الصفحة أن تعرض هذا بدل قائمتها، حتى لا تتكرر
 * الرسالة (وتتباين) في كل صفحة على حدة.
 */
export function useNeedsCompany(): boolean {
  const { activeCompanyId, user } = useAuth();
  if (!user) return false;
  // "all" = عرض مجمَّع لا يصلح لصفحة تخص شركة واحدة
  return activeCompanyId === "all";
}

export default function NeedsCompany() {
  const { t } = useI18n();
  return (
    <div className="card" style={{ textAlign: "center", padding: 32 }}>
      <p className="muted" style={{ margin: 0 }}>{t("needs_company")}</p>
    </div>
  );
}
