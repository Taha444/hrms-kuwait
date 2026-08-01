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

export function EmptyState({
  message, icon = "doc", hint, action,
}: {
  message?: string;
  icon?: string;
  hint?: string;
  action?: { label: string; onClick: () => void };
}) {
  const { t } = useI18n();
  return (
    <div className="state-box">
      <div className="state-icon">
        <Icon name={icon} size={40} />
      </div>
      <div className="state-title">{message || t("no_data")}</div>
      {hint && <div className="state-hint">{hint}</div>}
      {action && (
        <button onClick={action.onClick} style={{ marginTop: 8 }}>
          {action.label}
        </button>
      )}
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
