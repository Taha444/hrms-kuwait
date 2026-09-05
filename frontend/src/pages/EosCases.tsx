import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import api, { errMsg } from "../api";
import { useI18n } from "../i18n";
import { fmtKuwaitDateTime } from "../utils/datetime";

/**
 * P6-27 — شاشة حالات نهاية الخدمة.
 *
 * **قرار المالك**: حالة نهاية الخدمة هي المرجع في مسار الخروج. وكان
 * المرجع بلا شاشة إطلاًقا: ثمانية نقاط نهاية تسوق المعاملة من الفتح إلى
 * الحفظ، ولا واجهة تصل إليها. والمعروض الوحيد صفحة `/eos` — وهي
 * **حاسبة تقديرية** لا تلمس المعاملة.
 *
 * فمن أراد إنهاء خدمة لم يجد إلا المسودة على ملف الموظف، وهي المسار
 * الذي قرّر المالك ألّا يكون المرجع.
 *
 * **والصلاحيات تُقرأ من الخادم لا تُحسب هنا** (درس APP-01): الأدوار
 * المخوّلة لكل خطوة تأتي من `/eos/cases/stage-roles`. ومنطق صلاحيات
 * مكرَّر في مكانين ينحرف أحدهما عن الآخر — فيظهر زرّ يرفضه الخادم، أو
 * يُخفى إجراء يملكه صاحبه.
 */

type Case = {
  id: number; reference_no: string | null; status: string;
  stage_index: number; total_stages: number;
  employee_id: number; employee_name: string | null; employee_no: string | null;
  termination_date: string | null; termination_reason: string | null;
  settlement: any; source_request_id: number | null;
  clearance_notes: string | null; acknowledgment_note: string | null;
  payment_reference: string | null; filing_location: string | null;
  document_status: string;
  initiated_at: string | null; calculated_at: string | null;
  approved_at: string | null; clearance_at: string | null;
  acknowledged_at: string | null; settled_at: string | null;
  printed_at: string | null; filed_at: string | null;
};

type Policy = {
  flow: string[]; roles: Record<string, string[]>;
  role_labels: Record<string, string>; reasons: Record<string, string>;
  you: string; you_label: string;
};

const STAGE_AR: Record<string, string> = {
  initiated: "فُتحت", calculated: "حُسبت", approved: "اعتُمدت",
  clearance: "أُخلي الطرف", acknowledged: "أقرّ الموظف", settled: "صُرفت",
};

/** الخطوة التالية لكل حالة — من ترتيب المسار لا من قائمة مكتوبة ثانية. */
function nextStep(flow: string[], status: string): string | null {
  const i = flow.indexOf(status);
  return i >= 0 && i + 1 < flow.length ? flow[i + 1] : null;
}

const ACTION_LABEL: Record<string, string> = {
  calculated: "احسب التسوية", approved: "اعتمد", clearance: "سجّل إخلاء الطرف",
  acknowledged: "أقرّ بالاطلاع", settled: "سجّل الصرف",
};

const ACTION_PATH: Record<string, string> = {
  calculated: "calculate", approved: "approve", clearance: "clearance",
  acknowledged: "acknowledge", settled: "settle",
};

export default function EosCases() {
  const { lang } = useI18n();
  const [params, setParams] = useSearchParams();
  const [rows, setRows] = useState<Case[]>([]);
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [sel, setSel] = useState<Case | null>(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  const statusFilter = params.get("status") || "";

  const load = () =>
    api.get("/eos/cases", { params: statusFilter ? { status: statusFilter } : {} })
      .then((r) => setRows(r.data))
      .catch((e) => setErr(errMsg(e, "تعذّر تحميل الحالات")));

  useEffect(() => { load(); }, [statusFilter]);
  useEffect(() => {
    api.get("/eos/cases/stage-roles").then((r) => setPolicy(r.data)).catch(() => {});
  }, []);

  const open = (id: number) =>
    api.get(`/eos/cases/${id}`).then((r) => { setSel(r.data); setNote(""); })
      .catch((e) => setErr(errMsg(e, "تعذّر فتح الحالة")));

  /** هل يملك هذا المستخدم الخطوة التالية؟ — بقائمة الخادم لا بقائمة هنا. */
  const mayDo = (step: string) =>
    !!policy && (policy.you === "super_admin" ||
                 (policy.roles[step] || []).includes(policy.you));

  const act = async (step: string) => {
    if (!sel) return;
    setErr(""); setMsg(""); setBusy(true);
    // المعاملات التي يشترطها كل مسار — مقروءة من رسالة الخادم عند نقصها،
    // ومُرسَلة هنا صراحًة كي لا يُردّ الطلب 422 بعد ضغطة المستخدم.
    const q: Record<string, string> = {};
    if (step === "clearance") q.notes = note.trim();
    if (step === "acknowledged" && note.trim()) q.note = note.trim();
    if (step === "settled") q.payment_reference = note.trim();
    try {
      await api.post(`/eos/cases/${sel.id}/${ACTION_PATH[step]}`, null, { params: q });
      setMsg("تمّ تسجيل الخطوة");
      await load();
      await open(sel.id);
    } catch (e: any) {
      setErr(errMsg(e, "تعذّر تنفيذ الخطوة"));
    } finally { setBusy(false); }
  };

  const money = (n: any) =>
    typeof n === "number" ? `${n.toFixed(3)} د.ك` : "—";

  return (
    <div aria-labelledby="eosc-title">
      <div className="page-head">
        <div>
          <div className="eyebrow">نهاية الخدمة</div>
          <h2 id="eosc-title">معاملات نهاية الخدمة</h2>
          <div className="sub">
            المرجع الرسمي لمسار الخروج — تُفتح من الاستقالة أو طلب التسوية،
            أو مباشرة من هنا.
          </div>
        </div>
        <select value={statusFilter}
                onChange={(e) => setParams(e.target.value ? { status: e.target.value } : {})}
                aria-label="تصفية بالحالة">
          <option value="">كل الحالات</option>
          {(policy?.flow || []).map((s) => (
            <option key={s} value={s}>{STAGE_AR[s] || s}</option>
          ))}
        </select>
      </div>

      {err && <div className="err" role="alert">{err}</div>}
      {msg && <div className="ok" role="status">{msg}</div>}

      <div className="card" style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th style={{ textAlign: "right", padding: 8 }}>المرجع</th>
              <th style={{ textAlign: "right", padding: 8 }}>الموظف</th>
              <th style={{ padding: 8 }}>تاريخ المغادرة</th>
              <th style={{ padding: 8 }}>المرحلة</th>
              <th style={{ padding: 8 }}>المصدر</th>
              <th style={{ padding: 8 }} />
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.id} style={{ borderTop: "1px solid var(--border, #e2e8f0)" }}>
                <td style={{ padding: 8 }}>{c.reference_no || `#${c.id}`}</td>
                <td style={{ padding: 8 }}>
                  {c.employee_name}
                  {c.employee_no && <span className="muted"> · {c.employee_no}</span>}
                </td>
                <td style={{ padding: 8, textAlign: "center" }}>
                  {c.termination_date || "—"}
                </td>
                <td style={{ padding: 8, textAlign: "center" }}>
                  <span className={`pill ${c.status === "settled" ? "success" : "gold"}`}>
                    {STAGE_AR[c.status] || c.status}
                  </span>
                  <div className="muted" style={{ fontSize: 11 }}>
                    {c.stage_index + 1} / {c.total_stages}
                  </div>
                </td>
                <td style={{ padding: 8, textAlign: "center" }}>
                  {/* P6-27 — الرابط: من يقرأ المرجع يعرف من أين جاء. */}
                  {c.source_request_id
                    ? <a href={`/requests/${c.source_request_id}`}>
                        طلب #{c.source_request_id}
                      </a>
                    : <span className="muted">فُتحت مباشرة</span>}
                </td>
                <td style={{ padding: 8, textAlign: "center" }}>
                  <button className="ghost" onClick={() => open(c.id)}>تفاصيل</button>
                </td>
              </tr>
            ))}
            {!rows.length && (
              <tr><td colSpan={6} style={{ padding: 16 }} className="muted">
                لا معاملات نهاية خدمة {statusFilter ? "بهذه الحالة" : "بعد"}.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {sel && (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h3 style={{ margin: 0 }}>
              {sel.reference_no || `#${sel.id}`} — {sel.employee_name}
            </h3>
            <button className="ghost" onClick={() => setSel(null)}>إغلاق</button>
          </div>

          <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
            {/* التسمية من الخادم: قائمة ترجمة هنا تتقادم مع أول سبب يُضاف. */}
            {policy?.reasons?.[sel.termination_reason || ""]
              || sel.termination_reason} · المغادرة {sel.termination_date}
            {sel.source_request_id
              ? <> · بموجب <a href={`/requests/${sel.source_request_id}`}>
                  طلب #{sel.source_request_id}</a></>
              : <> · فُتحت مباشرة</>}
          </div>

          {/* خطّ المراحل: ما تمّ ومتى — والفراغ يعني «لم يقع بعد» لا خطأ. */}
          <div style={{ marginTop: 14 }}>
            {(policy?.flow || []).map((s) => {
              const at = (sel as any)[`${s === "initiated" ? "initiated" : s}_at`]
                || (s === "clearance" ? sel.clearance_at : null);
              const done = (policy?.flow || []).indexOf(s) <= sel.stage_index;
              return (
                <div key={s} className="timeline-item"
                     style={{ opacity: done ? 1 : 0.45, paddingBottom: 10 }}>
                  <strong>{STAGE_AR[s] || s}</strong>
                  {at && <span className="muted"> · {fmtKuwaitDateTime(at, lang)}</span>}
                </div>
              );
            })}
          </div>

          {sel.settlement && (
            <div style={{ marginTop: 14 }}>
              <h4 style={{ margin: "0 0 6px" }}>التسوية</h4>
              <div className="muted" style={{ fontSize: 12 }}>
                الإجمالي: {money(sel.settlement?.total_settlement)}
              </div>
            </div>
          )}

          {sel.clearance_notes && (
            <div className="s-note" style={{ marginTop: 10 }}>
              إخلاء الطرف: {sel.clearance_notes}
            </div>
          )}
          {sel.payment_reference && (
            <div className="s-note">مرجع الدفع: {sel.payment_reference}</div>
          )}

          {/* الخطوة التالية — وحدها. ولا يُعرض ما لا يملكه هذا المستخدم. */}
          {(() => {
            const step = policy ? nextStep(policy.flow, sel.status) : null;
            if (!step) {
              return <div className="muted" style={{ marginTop: 14 }}>
                بلغت المعاملة نهايتها المالية (صُرفت).
              </div>;
            }
            if (!mayDo(step)) {
              return <div className="muted" style={{ marginTop: 14 }}>
                الخطوة التالية «{ACTION_LABEL[step] || step}» من صلاحية:
                {" "}{(policy?.roles[step] || [])
                       .map((r) => policy?.role_labels?.[r] || r)
                       .join("، ") || "—"} — لست منهم.
              </div>;
            }
            const needsNote = step === "clearance" || step === "settled";
            return (
              <div style={{ marginTop: 14, display: "grid", gap: 8, maxWidth: 460 }}>
                {needsNote && (
                  <input value={note} onChange={(e) => setNote(e.target.value)}
                         placeholder={step === "settled"
                           ? "مرجع الدفع (إلزامي)"
                           : "ملاحظات إخلاء الطرف (إلزامية)"} />
                )}
                <div>
                  <button disabled={busy || (needsNote && !note.trim())}
                          onClick={() => act(step)}>
                    {ACTION_LABEL[step] || step}
                  </button>
                </div>
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}
