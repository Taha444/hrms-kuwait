import { useEffect, useState } from "react";
import api from "../api";
import { useI18n } from "../i18n";
import { statusAr } from "../labels";

// الخدمة الذاتية: ملف الموظف الشخصي — بياناته/عقده/مستنداته/إجازاته/إنذاراته فقط.
export default function MyProfile() {
  const { t, lang } = useI18n();
  const [p, setP] = useState<any>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.get("/me/profile").then((r) => setP(r.data))
      .catch((e) => setErr(e.response?.data?.detail || t("error")));
  }, []);

  const download = (type: string) =>
    window.open(`/api/me/document/${encodeURIComponent(type)}`, "_blank");

  if (err) return <div className="card empty">{err}</div>;
  if (!p) return <div className="empty">{t("loading")}</div>;
  const e = p.employee;
  const kwd = t("kwd_currency");

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="eyebrow">{t("my_profile")}</div>
          <h2 style={{ margin: "2px 0 0" }}>{e.name}</h2>
          <div className="sub">{e.job_title || "—"}</div>
        </div>
      </div>

      <div className="grid cards">
        <div className="card">
          <h3>{t("tab_personal")}</h3>
          <b>{t("fld_civil_id")}:</b> {e.civil_id || "—"}<br />
          <b>{t("epf_nationality")}:</b> {e.nationality || "—"}<br />
          <b>{t("epf_gender")}:</b> {e.gender === "male" ? t("gender_male") : e.gender === "female" ? t("gender_female") : "—"}<br />
          <b>{t("epf_dob")}:</b> {e.date_of_birth || "—"}<br />
          <b>{t("epf_email")}:</b> {e.email || "—"}<br />
          <b>{t("emp_phone")}:</b> {e.phone || "—"}
        </div>
        <div className="card">
          <h3>{t("my_contract")}</h3>
          <b>{t("epf_job")}:</b> {e.job_title || "—"}<br />
          <b>{t("epf_salary")}:</b> {e.basic_salary} {kwd}<br />
          <b>{t("epf_hire")}:</b> {e.hire_date || "—"}<br />
          <b>{t("epf_contract")}:</b> {e.contract_type}<br />
          <b>{t("epf_passport")}:</b> {e.passport_number || "—"}
        </div>
      </div>

      <div className="card">
        <h3>{t("my_documents")}</h3>
        <table>
          <thead><tr><th>{t("epf_col_type")}</th><th>{t("col_title")}</th><th>{t("epf_col_version")}</th><th>{t("pro_col_expiry")}</th><th></th></tr></thead>
          <tbody>
            {p.documents.map((d: any) => (
              <tr key={d.id}><td>{d.type}</td><td>{d.title}</td><td>v{d.version}</td><td>{d.expiry_date || "—"}</td>
                <td><button className="ghost sm" onClick={() => download(d.type)}>{t("my_download")}</button></td></tr>
            ))}
            {!p.documents.length && <tr><td colSpan={5} className="muted">{t("att_no_records")}</td></tr>}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>{t("my_leaves")}</h3>
        <table>
          <thead><tr><th>{t("req_type")}</th><th>{t("req_from")}</th><th>{t("req_to")}</th><th>{t("req_days")}</th><th>{t("status")}</th></tr></thead>
          <tbody>
            {p.leaves.map((l: any) => (
              <tr key={l.id}><td>{l.type}</td><td>{l.start_date}</td><td>{l.end_date}</td><td>{l.days}</td>
                <td><span className="pill info">{statusAr(l.status)}</span></td></tr>
            ))}
            {!p.leaves.length && <tr><td colSpan={5} className="muted">{t("att_no_records")}</td></tr>}
          </tbody>
        </table>
      </div>

      <div className="card" style={{ borderTop: "3px solid var(--warning)" }}>
        <h3>{t("my_warnings")}</h3>
        {p.warnings.map((w: any) => (
          <div key={w.id} className="timeline-item">
            <span className="pill warning">{t("ev_warning")}</span> {w.title}
            {w.detail ? <div className="muted">{w.detail}</div> : null}
            <div className="muted">{new Date(w.date).toLocaleDateString(lang, { dateStyle: "medium" })}</div>
          </div>
        ))}
        {!p.warnings.length && <div className="muted">{t("my_no_warnings")}</div>}
      </div>
    </div>
  );
}
