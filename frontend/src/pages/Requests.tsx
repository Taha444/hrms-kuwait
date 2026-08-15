import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import api, { errMsg } from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import { ProgressMini } from "../components/RequestSteps";
import { Skeleton, ErrorRetry, EmptyState } from "../components/States";
import { statusAr } from "../labels";
import SchemaForm, { missingFields, type Schema } from "../components/SchemaForm";

// الأنواع التي لها نموذج مبرمج هنا بدل بنائه من الـschema. صارت فارغة: كل نوع
// يُبنى نموذجه الآن من تعريف الخادم عبر SchemaForm. لا بد أن تطابق مفاتيح
// REQUIRED_PAYLOAD_FIELDS في backend/app/routers/requests.py — الخادم يعفي هذه
// الأكواد من التحقق بمفردات الـschema. اختبار في الخادم يحرس التطابق.
const HARDCODED_FORM_TYPES: string[] = [];

export default function Requests() {
  const { t } = useI18n();
  const { can, user } = useAuth();
  const [params] = useSearchParams();
  const [tab, setTab] = useState<"mine" | "inbox">("mine");
  const [mine, setMine] = useState<any[]>([]);
  const [inbox, setInbox] = useState<any[]>([]);
  const [types, setTypes] = useState<any[]>([]);
  const [employees, setEmployees] = useState<any[]>([]);
  const [onBehalfOf, setOnBehalfOf] = useState<number | "">("");
  const [state, setState] = useState<"loading" | "ok" | "error">("loading");
  const [showNew, setShowNew] = useState(false);
  const [typeCode, setTypeCode] = useState("");
  // الخدمة التي ينتمي إليها الكود المختار — الكود المُرسَل يبقى كود النوع
  // الفرعي نفسه، فلا يتغيّر شيء في الخادم ولا في الطلبات المحفوظة.
  const serviceOf = (code: string) =>
    types.find((x: any) => x.code === code
      || (x.subtypes || []).some((s: any) => s.code === code));
  const [payload, setPayload] = useState<any>({});
  // schema النوع المختار (null = لا schema، undefined = لم يُحمَّل بعد)
  const [activeSchema, setActiveSchema] = useState<Schema | null | undefined>(undefined);
  const [err, setErr] = useState("");
  // خطأ قادم من رابط عميق (?type=) — لا يُمحى مع تغيير النوع مثل err
  const [linkErr, setLinkErr] = useState("");
  // التقديم نيابًة عن موظف آخر — العلم يأتي من الخادم (/auth/me) لا باستنتاج هنا.
  // كان can("view_employee")، فظهرت القائمة للمحاسب وفيها المدير العام وHR ومندوب
  // حكومي: صلاحية *رؤية* الموظفين ليست تفويًضا بالتصرف باسمهم.
  const canActOnBehalf = !!user?.can_submit_on_behalf;
  // V2.2 §3 — المستخدم الإداري بدون employee_id لا يمكنه تقديم "لنفسه"،
  // يجب اختيار موظف صراحة. لو عنده employee_id (مثل موظف/HR مربوط) → يقدر يختار نفسه.
  const hasOwnEmployeeProfile = !!user?.employee_id;

  const load = () => {
    setState("loading");
    api.get("/requests/mine").then((r) => { setMine(r.data); setState("ok"); })
      .catch(() => setState("error"));
    if (can("approve_request") || can("process_delegate_tasks"))
      api.get("/requests/inbox").then((r) => setInbox(r.data)).catch(() => {});
  };
  useEffect(() => {
    load();
    // FIX — كتالوج الإنشاء: الأنواع التي يقبلها POST فعليًا فقط (بلا legacy aliases)
    // V2.2 §12 — grouped: خدمة واحدة لكل مسار canonical والنوع الفرعي خيار
    // داخلها. ستة أنواع كانت تمثّل "تغيير وظيفي" واحًدا وستة أخرى "طلب عام"،
    // فيرى المستخدم اثني عشر خياًرا منفصًلا ويختار الخطأ فيُرجَع طلبه.
    api.get("/requests/types", { params: { creatable_only: true, grouped: true } })
      .then((r) => {
        setTypes(r.data);
        // ?type=&new=1 — يصل من زر "استبدال التوقيع" في الملف الشخصي: يفتح
        // النموذج على النوع المطلوب مباشرة بدل أن يبحث عنه المستخدم في القائمة.
        const wanted = params.get("type");
        // ?type= قد يشير لنوع فرعي داخل خدمة (مثل REQSIG داخل "طلب عام")
        const exists = wanted && r.data.some((x: any) =>
          x.code === wanted || (x.subtypes || []).some((s: any) => s.code === wanted));
        setTypeCode(exists ? wanted! : (r.data[0]?.code || ""));
        if (params.get("new") === "1") setShowNew(true);
        // حالة منفصلة عن err: تأثير [typeCode] يمسح err عند تغيير النوع، فكانت
        // هذه الرسالة تُمحى في نفس اللحظة التي تُعرض فيها.
        if (wanted && !exists)
          setLinkErr(`نوع الطلب «${wanted}» غير متاح لحسابك — اختر نوًعا من القائمة`);
      });
    if (canActOnBehalf) api.get("/employees").then((r) => setEmployees(r.data)).catch(() => {});
  }, []);

  // نمسح الـschema مع تغيير النوع حتى لا يُقيَّم نوع جديد بقواعد النوع السابق
  useEffect(() => { setActiveSchema(undefined); }, [typeCode]);

  // PILOT-P0-2: كل ما يتغير نوع الطلب نمسح الـpayload — كانت الحقول من نوع سابق
  // (مثل amount من "سلفة") تفضل في state، والاختبار على "leave" بيسقط لأن الحقول
  // المطلوبة start_date/end_date مش موجودة في state (رغم إن المستخدم يعتقد إنه أدخلها
  // في نوع مختلف قبل ما يبدّل النوع).
  useEffect(() => { setPayload({}); setErr(""); }, [typeCode]);

  // حقول إلزامية بأسماء تخص نموذجًا مبرمجًا — فارغة الآن لأن كل النماذج تُبنى من
  // الـschema، فتُشتق حقولها الإلزامية منه عبر missingFields (QA-P0-WF-01: منع
  // تقديم طلب فارغ برسالة واضحة قبل وصوله للخادم).
  const REQUIRED_FIELDS: Record<string, [string, string][]> = {};

  const submit = async () => {
    setErr("");
    // V2.2 §3 — منع تقديم "لنفسي" من مستخدم غير مرتبط بملف موظف قبل إرسال الطلب
    if (canActOnBehalf && !onBehalfOf && !hasOwnEmployeeProfile) {
      setErr("حسابك غير مرتبط بملف موظف — اختر موظفًا محددًا من القائمة");
      return;
    }
    const clean = Object.fromEntries(
      Object.entries(payload).filter(([, v]) => v !== "" && v !== undefined && v !== null)
    );
    // ترتيب المصادر يطابق الخادم: نموذج مبرمج ← REQUIRED_FIELDS، وإلا الـschema.
    const required = REQUIRED_FIELDS[typeCode];
    const missing = required
      ? required.filter(([k]) => clean[k] === undefined || clean[k] === "").map(([, label]) => label)
      : activeSchema
      ? missingFields(activeSchema, clean).map((f) => f.label)
      : Object.keys(clean).length === 0 ? [t("req_details")] : [];
    if (missing.length) {
      setErr(`${t("req_missing_fields")}: ${missing.join("، ")}`);
      return;
    }
    try {
      const body: any = { request_type_code: typeCode, payload_json: clean };
      if (onBehalfOf) body.employee_id = onBehalfOf;
      await api.post("/requests", body);
      setShowNew(false); setPayload({}); load();
    } catch (e: any) { setErr(errMsg(e, t("error"))); }
  };

  const list = tab === "mine" ? mine : inbox;

  return (
    <div aria-labelledby="requests-title">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2 id="requests-title">{t("requests")}</h2>
        {can("submit_request") && (
          <button onClick={() => setShowNew((s) => !s)}
                 aria-expanded={showNew}
                 aria-controls="new-request-panel">
            + {t("new_request")}
          </button>
        )}
      </div>

      {showNew && (
        <div className="card" id="new-request-panel" role="region" aria-labelledby="new-request-title">
          <h3 id="new-request-title">{t("new_request")}</h3>
          {linkErr && <div className="err">{linkErr}</div>}
          <div className="field">
            <label htmlFor="req-type">{t("req_type")}</label>
            <select id="req-type" value={serviceOf(typeCode)?.code || typeCode}
                    onChange={(e) => {
                      const svc = types.find((x) => x.code === e.target.value);
                      setTypeCode(svc?.subtypes?.[0]?.code || e.target.value);
                    }}>
              {types.map((x) => <option key={x.code} value={x.code}>{x.name}</option>)}
            </select>
          </div>
          {/* النوع الفرعي: لا يظهر إلا للخدمات التي لها أكثر من واحد */}
          {(() => {
            const svc = serviceOf(typeCode);
            if (!svc?.has_subtypes) return null;
            return (
              <div className="field">
                <label htmlFor="req-subtype">{t("req_service_subtype")}</label>
                <select id="req-subtype" value={typeCode}
                        onChange={(e) => setTypeCode(e.target.value)}>
                  {svc.subtypes.map((s: any) => (
                    <option key={s.code} value={s.code}>{s.label}</option>
                  ))}
                </select>
              </div>
            );
          })()}
          {canActOnBehalf && (
            <div className="field">
              <label htmlFor="req-on-behalf">{t("req_on_behalf_of")}</label>
              <select id="req-on-behalf" value={onBehalfOf} onChange={(e) => setOnBehalfOf(e.target.value ? +e.target.value : "")}>
                {hasOwnEmployeeProfile
                  ? <option value="">{t("req_myself")}</option>
                  : <option value="" disabled>— اختر موظفًا —</option>}
                {employees.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.employee_no ? `[${e.employee_no}] ` : ""}{e.name} — {e.job_title || "—"}
                  </option>
                ))}
              </select>
              {!hasOwnEmployeeProfile && (
                <span className="muted" style={{ fontSize: 12 }}>
                  حسابك الإداري غير مرتبط بملف موظف — يجب اختيار موظف محدد
                </span>
              )}
            </div>
          )}
          {/* الأنواع بلا نموذج مبرمج: يُبنى نموذجها من الـschema الذي يعرّفه الخادم.
              كان هنا نموذج عام من ثلاثة حقول (date/amount/details) يُعرض لـ44 نوعًا،
              وحمولته لا تُرضي تحقق الخادم العامل بحقول الـschema. */}
          {!HARDCODED_FORM_TYPES.includes(typeCode) && typeCode && (
            <>
              <SchemaForm
                typeCode={typeCode}
                payload={payload}
                onChange={setPayload}
                onSchemaLoaded={setActiveSchema}
              />
              {/* لا schema لهذا النوع (نماذج ADM* الإدارية) — تبقى الحقول العامة */}
              {activeSchema === null && (
                <>
                  <div className="row">
                    <div className="field" style={{ flex: 1 }}><label htmlFor="req-generic-date">{t("req_date")}</label>
                      <input id="req-generic-date" type="date" value={payload.date || ""}
                             onChange={(e) => setPayload({ ...payload, date: e.target.value })} /></div>
                    <div className="field" style={{ flex: 1 }}><label htmlFor="req-generic-amount">{t("req_amount")}</label>
                      <input id="req-generic-amount" type="number" min={0} value={payload.amount ?? ""}
                             onChange={(e) => setPayload({ ...payload, amount: e.target.value ? +e.target.value : undefined })} /></div>
                  </div>
                  <div className="field"><label htmlFor="req-generic-details">{t("req_details")} *</label>
                    <textarea id="req-generic-details" rows={3} required value={payload.details || ""}
                              onChange={(e) => setPayload({ ...payload, details: e.target.value })} /></div>
                  <p className="muted">{t("req_details_hint")}</p>
                </>
              )}
            </>
          )}
          {err && <div className="err">{err}</div>}
          <button onClick={submit}>{t("submit")}</button>
        </div>
      )}

      <div className="row" style={{ marginBottom: 12 }}>
        <button className={tab === "mine" ? "" : "ghost"} onClick={() => setTab("mine")}>{t("my_requests")}</button>
        {(can("approve_request") || can("process_delegate_tasks")) && (
          <button className={tab === "inbox" ? "" : "ghost"} onClick={() => setTab("inbox")}>
            {t("approval_inbox")} {inbox.length ? `(${inbox.length})` : ""}
          </button>
        )}
      </div>

      {state === "loading" ? <Skeleton rows={4} />
        : state === "error" ? <ErrorRetry onRetry={load} />
        : !list.length ? <EmptyState icon="requests" />
        : <div className="table-wrap">
        <table>
          <thead><tr><th>#</th><th>{t("col_type")}</th><th>{t("col_employee")}</th><th>{t("status")}</th><th>{t("req_path")}</th><th></th></tr></thead>
          <tbody>
            {list.map((r) => (
              <tr key={r.id}>
                <td className="num">{r.id}</td>
                <td>{r.type_name}</td>
                <td>{r.employee_name}</td>
                <td><span className={`pill ${r.status}`}>{statusAr(r.status)}</span></td>
                <td><ProgressMini current={r.current_stage} total={r.total_stages} status={r.status} /></td>
                <td><Link to={`/requests/${r.id}`}>{t("view")} →</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>}
    </div>
  );
}
