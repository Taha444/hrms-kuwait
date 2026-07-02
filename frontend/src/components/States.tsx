import { useI18n } from "../i18n";
import Icon from "../Icon";

// حالات مشتركة: هيكل تحميل (Skeleton)، حالة فارغة، وخطأ مع إعادة المحاولة.

export function Skeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="sk-wrap" aria-busy="true">
      <div className="sk sk-head" />
      {Array.from({ length: rows }).map((_, i) => (
        <div className="sk sk-row" key={i} style={{ width: `${92 - (i % 3) * 12}%` }} />
      ))}
    </div>
  );
}

export function EmptyState({ message, icon = "doc" }: { message?: string; icon?: string }) {
  const { t } = useI18n();
  return (
    <div className="state-box">
      <Icon name={icon} size={30} />
      <div>{message || t("no_data")}</div>
    </div>
  );
}

export function ErrorRetry({ onRetry, message }: { onRetry?: () => void; message?: string }) {
  const { t } = useI18n();
  return (
    <div className="state-box err">
      <Icon name="x" size={28} />
      <div>{message || t("load_failed")}</div>
      {onRetry && <button className="ghost sm" onClick={onRetry}>{t("retry")}</button>}
    </div>
  );
}
