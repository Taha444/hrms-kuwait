import { Fragment, useEffect, useState } from "react";
import api from "../api";
import { useI18n } from "../i18n";
import { roleAr } from "../labels";
import { fmtKuwaitDateTime, KUWAIT_TZ_LABEL, KUWAIT_TZ_LABEL_EN } from "../utils/datetime";

export default function Audit() {
  const { t, lang } = useI18n();
  const actionLabel = (a: string) => {
    const key = `audit_act_${a}`;
    const lbl = t(key);
    return lbl === key ? a : lbl;
  };
  const [rows, setRows] = useState<any[]>([]);
  const [action, setAction] = useState("");
  const [loading, setLoading] = useState(true);
  const [openId, setOpenId] = useState<number | null>(null);
  // نتيجةُ الفعل كما خُزِّنت: نجح/فشل/تعارض/مرفوض — والقيمة الغريبة تُعرض كما هي لا تُخفى.
  const resultLabel = (res: string | null) => {
    if (!res) return "";
    const key = `audit_res_${res}`;
    const lbl = t(key);
    return lbl === key ? res : lbl;
  };
  const resultClass = (res: string | null) =>
    res === "success" ? "pill ok" : res ? "pill bad" : "pill neutral";
  const pretty = (v: any) => (v == null ? "" : JSON.stringify(v, null, 2));

  const load = () => {
    setLoading(true);
    api.get("/audit", { params: { limit: 200, action: action || undefined } })
      .then((r) => setRows(r.data)).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, [action]);

  const actions = Array.from(new Set(rows.map((r) => r.action)));

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="eyebrow">{t("audit_eyebrow")}</div>
          <h2 style={{ margin: "2px 0 0" }}>{t("audit_title")}</h2>
          <div className="sub">
            {t("audit_sub")}
            <span style={{
              marginInlineStart: 8, background: "#e0ece8", color: "#0b3b38",
              padding: "1px 8px", borderRadius: 10, fontSize: 11, fontWeight: 600,
            }}>{lang === "en" ? KUWAIT_TZ_LABEL_EN : KUWAIT_TZ_LABEL}</span>
          </div>
        </div>
        <select aria-label={t("audit_all")} value={action} onChange={(e) => setAction(e.target.value)} style={{ width: 200 }}>
          <option value="">{t("audit_all")}</option>
          {actions.map((a) => <option key={a} value={a}>{actionLabel(a)}</option>)}
        </select>
      </div>

      <div className="table-wrap">
        <table>
          <thead><tr><th>{t("col_operation")}</th><th>{t("audit_result")}</th><th>{t("col_entity")}</th><th>{t("col_detail")}</th><th>{t("col_actor")}</th><th>IP</th><th>{t("col_time")}</th><th></th></tr></thead>
          <tbody>
            {loading ? <tr><td colSpan={8} className="empty">{t("loading")}</td></tr>
              : rows.map((r) => (
                <Fragment key={r.id}>
                  <tr>
                    <td><span className="pill neutral">{actionLabel(r.action)}</span></td>
                    <td>{r.result ? <span className={resultClass(r.result)}>{resultLabel(r.result)}</span> : null}</td>
                    <td className="muted">{r.entity_type}{r.entity_id ? ` #${r.entity_id}` : ""}</td>
                    <td className="muted">{r.detail}</td>
                    <td>
                      {r.by_system ? <span className="muted">{t("audit_system")}</span> : r.by}
                      {r.actor_role ? <div className="muted" style={{ fontSize: 11 }}>{roleAr(r.actor_role)}</div> : null}
                      {r.on_behalf && r.acted_by
                        ? <div className="muted" style={{ fontSize: 11 }}>{t("audit_acted_by")} {r.acted_by}</div> : null}
                    </td>
                    <td className="muted">{r.ip}</td>
                    <td className="muted">{fmtKuwaitDateTime(r.at, lang)}</td>
                    <td>
                      <button className="ghost sm" aria-expanded={openId === r.id}
                              onClick={() => setOpenId(openId === r.id ? null : r.id)}>
                        {openId === r.id ? t("audit_less") : t("audit_more")}
                      </button>
                    </td>
                  </tr>
                  {openId === r.id && (
                    <tr>
                      <td colSpan={8} className="muted" style={{ background: "#f6f9f8" }}>
                        {r.reason ? <div><strong>{t("audit_reason")}:</strong> {r.reason}</div> : null}
                        {r.actor_role ? <div><strong>{t("audit_role_at")}:</strong> {roleAr(r.actor_role)}</div> : null}
                        {r.before ? <div><strong>{t("audit_before")}:</strong><pre dir="ltr" style={{ margin: 0 }}>{pretty(r.before)}</pre></div> : null}
                        {r.after ? <div><strong>{t("audit_after")}:</strong><pre dir="ltr" style={{ margin: 0 }}>{pretty(r.after)}</pre></div> : null}
                        {r.correlation_id ? <div><strong>{t("audit_corr")}:</strong> <code dir="ltr">{r.correlation_id}</code></div> : null}
                        {r.user_agent ? <div><strong>{t("audit_agent")}:</strong> <span dir="ltr">{r.user_agent}</span></div> : null}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            {!loading && !rows.length && <tr><td colSpan={8} className="empty">{t("no_data")}</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
