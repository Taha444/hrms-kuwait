import Icon from "../Icon";

// مسار الطلب الهرمي: يعرض كل مرحلة وحالتها (تمّ/الحالي/قادم/مرفوض) بوضوح.
type Stage = {
  order: number; label: string; role_label: string; kind: string;
  state: "done" | "current" | "pending" | "rejected" | "cancelled" | "skipped" | "returned";
  approver_name?: string | null; decided_at?: string | null; note?: string | null;
};

const CURRENT_SUBLABEL: Record<string, string> = {
  awaiting_signature: "بانتظار حضور الموظف للتوقيع",
  awaiting_delegate: "قيد إجراءات المندوب (إذن المغادرة)",
  ready_for_pickup: "جاهز للاستلام",
  pending: "بانتظار الاعتماد",
};

const STATE_PILL: Record<string, string> = {
  done: "تمّ الاعتماد", current: "الآن", pending: "لم يصل بعد",
  rejected: "مرفوض", cancelled: "أُلغي", skipped: "غير مطلوب", returned: "أُعيد للتصحيح",
};

export function ProgressMini({ current, total, status }: { current: number; total: number; status: string }) {
  const done = ["completed"].includes(status) ? total : current;
  return (
    <span className="progress-mini" title={`المرحلة ${Math.min(current + 1, total)} من ${total}`}>
      {Array.from({ length: total }).map((_, i) => (
        <span key={i} className={`seg ${i < done ? "on" : i === current && !["rejected", "cancelled", "completed", "returned"].includes(status) ? "cur" : ""}`} />
      ))}
    </span>
  );
}

export default function RequestSteps({ stages, status }: { stages: Stage[]; status: string }) {
  if (!stages?.length) return <div className="empty">لا توجد مراحل معرّفة لهذا الطلب.</div>;
  const fmt = (d?: string | null) => (d ? new Date(d).toLocaleString("ar", { dateStyle: "medium", timeStyle: "short" }) : "");

  return (
    <div className="steps">
      {stages.map((s, i) => {
        const sub = s.state === "current" ? (CURRENT_SUBLABEL[status] || CURRENT_SUBLABEL.pending) : "";
        return (
          <div key={s.order} className={`step ${s.state}`}>
            <div className="rail">
              <div className="node">
                {s.state === "done" ? <Icon name="check" size={16} />
                  : s.state === "rejected" || s.state === "cancelled" || s.state === "returned" ? <Icon name="x" size={16} />
                  : i + 1}
              </div>
              <div className="connector" />
            </div>
            <div className="body">
              <div className="s-title">{s.label}</div>
              <div className="s-meta">
                <span className="pill neutral">{s.role_label}</span>
                <span className={`pill ${s.state === "done" ? "success" : s.state === "current" ? "gold"
                  : s.state === "rejected" || s.state === "cancelled" ? "danger"
                  : s.state === "returned" ? "warning" : "neutral"}`}>
                  {STATE_PILL[s.state]}
                </span>
                {s.approver_name && <span>· {s.approver_name}</span>}
                {s.decided_at && <span>· {fmt(s.decided_at)}</span>}
              </div>
              {sub && <div className="s-meta" style={{ color: "var(--gold)" }}>⏳ {sub}</div>}
              {s.note && <div className="s-note">📝 {s.note}</div>}
            </div>
          </div>
        );
      })}
    </div>
  );
}
