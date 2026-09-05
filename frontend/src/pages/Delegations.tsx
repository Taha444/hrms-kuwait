import { useEffect, useState } from "react";
import api, { errMsg } from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import { roleAr } from "../labels";

/**
 * V1.5 §3 — التفويض المؤقت لصلاحية الاعتماد.
 *
 * **لماذا شاشة**: المحرّك يقرأ التفويضات في ثلاثة مواضع
 * (`expand_approvers_with_delegates`) فيوسّع دائرة من يعتمد المرحلة، ولا
 * سبيل إلى إنشائها إلا بالواجهة البرمجية. فمن يسافر تقف طلباته عنده.
 *
 * **ولا ضابط نطاق هنا بقصد**: عمود `scope` يُخزَّن ولا يقرؤه أحد — لا
 * وحدة التفويض ولا المحرّك. فقائمة اختيار «الإجازات فقط» كانت ستَعِد
 * بتقييد لا يفرضه شيء، والمفوَّض إليه يأخذ كل شيء. والصفحة تقول ذلك
 * صراحًة بدل أن تسكت عنه.
 */

type Row = {
  id: number;
  delegator_user_id: number; delegator_name: string | null;
  delegate_user_id: number; delegate_name: string | null;
  reason: string | null; starts_at: string; ends_at: string;
  is_active: boolean; in_effect: boolean; revoked_at: string | null;
};

function localNow(plusDays = 0) {
  const d = new Date();
  d.setDate(d.getDate() + plusDays);
  d.setSeconds(0, 0);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

/**
 * **فارق التوقيت ليس تفصيًلا هنا**: الخادم يخزّن بالـUTC ويقارن بـ
 * `utcnow()`، وحقل `datetime-local` يعطي توقيت الجهاز. فتفويض يبدأ
 * «الآن» في الكويت كان يُخزَّن متقدًما ثلاث ساعات: لا يسري، ويختفي من
 * القائمة الافتراضية — فيظنّ المستخدم أن الحفظ فشل.
 *
 * قِستُها حّية: الخادم عند 21:22Z والصفّ يبدأ 00:21.
 */
const toUtc = (local: string) =>
  local ? new Date(local).toISOString().slice(0, 19) : local;

/** والعكس عند العرض: ما يعود ساذًجا يُقرأ UTC ثم يُعرض بتوقيت القارئ. */
function toLocalText(iso: string) {
  if (!iso) return "—";
  const d = new Date(/[zZ]|[+-]\d{2}:\d{2}$/.test(iso) ? iso : `${iso}Z`);
  if (isNaN(d.getTime())) return iso.slice(0, 16).replace("T", " ");
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} `
    + `${p(d.getHours())}:${p(d.getMinutes())}`;
}

export default function Delegations() {
  const { t } = useI18n();
  const { user } = useAuth();
  // الخادم يسمح لهذين وحدهما بالتفويض **باسم غيرهما** (``_may_manage``).
  const onBehalf = ["hr", "super_admin"].includes(user?.role || "");

  const [rows, setRows] = useState<Row[]>([]);
  const [people, setPeople] = useState<any[]>([]);
  const [showPast, setShowPast] = useState(false);
  const [form, setForm] = useState({
    delegator_user_id: "", delegate_user_id: "",
    starts_at: localNow(), ends_at: localNow(7), reason: "",
  });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const load = () => {
    api.get("/delegations", { params: { only_active: !showPast } })
      .then((r) => setRows(r.data))
      .catch((e) => setErr(errMsg(e, t("error"))));
  };
  useEffect(() => { load(); }, [showPast]);
  useEffect(() => {
    // لا ``catch`` صامت: فشل هنا يترك قائمة فارغة بلا سبب، فيظنّ
    // المستخدم أن لا زملاء له. (قِستُها حّية على خادم قديم: 404
    // مبتلَع وقائمة خاوية.)
    api.get("/delegations/candidates")
      .then((r) => setPeople(r.data))
      .catch((e) => setErr(errMsg(e, t("dlg_candidates_failed"))));
  }, []);

  const create = async () => {
    setErr(""); setMsg("");
    if (!form.delegate_user_id) { setErr(t("dlg_pick_delegate")); return; }
    // الخادم يرفض النهاية قبل البداية — يُقال هنا بدل أن يُردّ الطلب.
    if (new Date(form.ends_at) <= new Date(form.starts_at)) {
      setErr(t("dlg_bad_period")); return;
    }
    setBusy(true);
    try {
      await api.post("/delegations", {
        delegate_user_id: Number(form.delegate_user_id),
        starts_at: toUtc(form.starts_at), ends_at: toUtc(form.ends_at),
        reason: form.reason.trim() || null,
      }, {
        params: form.delegator_user_id
          ? { delegator_user_id: Number(form.delegator_user_id) } : {},
      });
      setMsg(t("dlg_created"));
      setForm({ ...form, delegate_user_id: "", reason: "" });
      load();
    } catch (e: any) { setErr(errMsg(e, t("error"))); }
    finally { setBusy(false); }
  };

  const revoke = async (r: Row) => {
    const who = r.delegate_name || `#${r.delegate_user_id}`;
    if (!window.confirm(t("dlg_revoke_confirm").replace("{n}", who))) return;
    setBusy(true); setErr(""); setMsg("");
    try {
      await api.post(`/delegations/${r.id}/revoke`);
      setMsg(t("dlg_revoked")); load();
    } catch (e: any) { setErr(errMsg(e, t("error"))); }
    finally { setBusy(false); }
  };

  const when = toLocalText;
  const mine = (r: Row) => r.delegator_user_id === user?.id;

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="eyebrow">{t("requests")}</div>
          <h2 style={{ margin: "2px 0 0" }}>{t("dlg_title")}</h2>
          <div className="sub">{t("dlg_sub")}</div>
        </div>
        <div className="row">
          <label style={{ display: "inline-flex", alignItems: "center",
                          gap: 6, fontSize: 13, whiteSpace: "nowrap" }}>
            <input type="checkbox" checked={showPast}
                   onChange={(e) => setShowPast(e.target.checked)} />
            {t("dlg_show_past")}
          </label>
          <button className="ghost" onClick={load}>{t("refresh")}</button>
        </div>
      </div>

      {msg && <div className="ok">{msg}</div>}
      {err && <div className="err">{err}</div>}

      <div className="card">
        <table className="table">
          <thead>
            <tr>
              <th>{t("dlg_delegator")}</th>
              <th>{t("dlg_delegate")}</th>
              <th>{t("dlg_period")}</th>
              <th>{t("dlg_reason")}</th>
              <th>{t("status")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr><td colSpan={6} className="muted">{t("dlg_none")}</td></tr>
            )}
            {rows.map((r) => (
              <tr key={r.id} style={{ opacity: r.is_active ? 1 : 0.55 }}>
                <td>{r.delegator_name || `#${r.delegator_user_id}`}</td>
                <td>{r.delegate_name || `#${r.delegate_user_id}`}</td>
                <td className="sub">{when(r.starts_at)} → {when(r.ends_at)}</td>
                <td className="sub">{r.reason || "—"}</td>
                <td>
                  {/* «سارٍ» ≠ «غير ملغى»: صفٌّ لم تبدأ مدّته يبدو فعّاًلا
                      والمحرّك لا يعتدّ به — فالتمييز معروض لا محسوب ذهنًيا. */}
                  <span className={`pill ${r.in_effect ? "completed"
                                    : r.is_active ? "pending" : "neutral"}`}>
                    {r.in_effect ? t("dlg_in_effect")
                      : r.is_active ? t("dlg_scheduled") : t("dlg_revoked_state")}
                  </span>
                </td>
                <td>
                  {r.is_active && (mine(r) || onBehalf) && (
                    <button className="ghost sm" disabled={busy}
                            style={{ color: "var(--danger)" }}
                            onClick={() => revoke(r)}>{t("dlg_revoke")}</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>{t("dlg_add_title")}</h3>
        <div className="row">
          {onBehalf && (
            <div className="field">
              <label htmlFor="dlg-from">{t("dlg_delegator")}</label>
              <select id="dlg-from" value={form.delegator_user_id}
                      onChange={(e) => setForm({ ...form, delegator_user_id: e.target.value })}>
                <option value="">{t("dlg_myself")}</option>
                {people.map((p) => (
                  <option key={p.id} value={p.id}>{p.full_name} — {roleAr(p.role)}</option>
                ))}
              </select>
            </div>
          )}
          <div className="field">
            <label htmlFor="dlg-to">{t("dlg_delegate")} *</label>
            <select id="dlg-to" value={form.delegate_user_id}
                    onChange={(e) => setForm({ ...form, delegate_user_id: e.target.value })}>
              <option value="">—</option>
              {people.map((p) => (
                <option key={p.id} value={p.id}>{p.full_name} — {roleAr(p.role)}</option>
              ))}
            </select>
            {people.length === 0 && (
              <div className="sub">{t("dlg_no_candidates")}</div>
            )}
          </div>
          <div className="field">
            <label htmlFor="dlg-start">{t("dlg_from")} *</label>
            <input id="dlg-start" type="datetime-local" value={form.starts_at}
                   onChange={(e) => setForm({ ...form, starts_at: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="dlg-end">{t("dlg_to")} *</label>
            <input id="dlg-end" type="datetime-local" value={form.ends_at}
                   onChange={(e) => setForm({ ...form, ends_at: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="dlg-reason">{t("dlg_reason")}</label>
            <input id="dlg-reason" value={form.reason}
                   onChange={(e) => setForm({ ...form, reason: e.target.value })} />
          </div>
        </div>

        {/* ما يشمله التفويض — مكتوب لأن لا ضابط له */}
        <div className="sub" style={{ marginBottom: 8 }}>{t("dlg_scope_note")}</div>

        <button disabled={busy} onClick={create}>{t("dlg_create")}</button>
      </div>
    </div>
  );
}
