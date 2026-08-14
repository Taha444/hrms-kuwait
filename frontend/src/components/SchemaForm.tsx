import { useEffect, useState } from "react";
import api from "../api";

/**
 * يبني نموذج الطلب من الـschema الذي يعرّفه الخادم (GET /requests/types/{code}/schema).
 *
 * قبل هذا المكوّن كانت الواجهة تعرض لكل نوع لا يملك نموذجًا مبرمجًا نموذجًا عامًا
 * من ثلاثة حقول (date/amount/details) — 44 نوعًا من 53. والخادم يتحقق بحقول
 * الـschema، فلا حمولة ذلك النموذج العام تُرضيه.
 *
 * القواعد المطبَّقة هنا هي نفسها التي يفرضها الخادم، لتُعرض للمستخدم قبل الإرسال
 * لا بعده:
 *  - required           حقل إلزامي
 *  - conditional.require حقل يصير إلزاميًا حسب قيمة حقل آخر
 *  - conditional.hide    حقل يُخفى فلا يُطالَب به ولا يُرسَل
 *  - read_only           يُعرض للاطلاع ولا يُرسَل
 * التحقق النهائي يبقى على الخادم؛ هذا لتحسين التجربة فقط.
 */

export type SchemaField = {
  code: string;
  label: string;
  type: string;
  required?: boolean;
  options?: { value: string; label: string }[];
  min?: number;
  max?: number;
  max_length?: number;
  read_only?: boolean;
};

export type Schema = {
  fields: SchemaField[];
  conditional?: {
    when: Record<string, any>;
    require?: string[];
    hide?: string[];
    show?: string[];
  }[];
  attachments?: { required?: string[]; optional?: string[] };
  validation?: { end_gte_start?: [string, string] };
};

/** يقيّم قواعد conditional — يطابق conditional_requirements في الخادم. */
export function evalConditionals(schema: Schema, payload: Record<string, any>) {
  const required = new Set<string>();
  const hidden = new Set<string>();
  const gated = new Set<string>(); // كل حقل تحكمه show
  const shown = new Set<string>(); // ومنها ما تحقق شرطه
  for (const cond of schema.conditional || []) {
    (cond.show || []).forEach((f) => gated.add(f));
    const matches = Object.entries(cond.when || {}).every(
      ([k, v]) => payload[k] === v
    );
    if (matches) {
      (cond.require || []).forEach((f) => required.add(f));
      (cond.hide || []).forEach((f) => hidden.add(f));
      (cond.show || []).forEach((f) => shown.add(f));
    }
  }
  gated.forEach((f) => {
    if (!shown.has(f)) hidden.add(f);
  });
  return { required, hidden };
}

/** الحقول الإلزامية الناقصة — نفس ترتيب النموذج، كما يفعل الخادم. */
export function missingFields(schema: Schema, payload: Record<string, any>): SchemaField[] {
  const { required: condReq, hidden } = evalConditionals(schema, payload);
  return (schema.fields || []).filter((f) => {
    if (hidden.has(f.code) || f.read_only) return false;
    if (!f.required && !condReq.has(f.code)) return false;
    const v = payload[f.code];
    return v === undefined || v === null || (typeof v === "string" && !v.trim());
  });
}

export default function SchemaForm({
  typeCode,
  payload,
  onChange,
  onSchemaLoaded,
}: {
  typeCode: string;
  payload: Record<string, any>;
  onChange: (next: Record<string, any>) => void;
  onSchemaLoaded?: (schema: Schema | null) => void;
}) {
  const [schema, setSchema] = useState<Schema | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "none">("loading");

  useEffect(() => {
    if (!typeCode) return;
    let cancelled = false;
    setState("loading");
    api
      .get(`/requests/types/${encodeURIComponent(typeCode)}/schema`)
      .then((r) => {
        if (cancelled) return;
        const s: Schema = r.data.schema;
        setSchema(s);
        setState("ready");
        onSchemaLoaded?.(s);
      })
      .catch(() => {
        if (cancelled) return;
        setSchema(null);
        setState("none");
        onSchemaLoaded?.(null);
      });
    return () => {
      cancelled = true;
    };
  }, [typeCode]);

  if (state === "loading") return <p className="muted">جاري تحميل النموذج…</p>;
  if (!schema) return null;

  const { required: condRequired, hidden } = evalConditionals(schema, payload);
  const set = (code: string, value: any) => onChange({ ...payload, [code]: value });

  return (
    <>
      {schema.fields.map((f) => {
        if (hidden.has(f.code)) return null;
        const isRequired = !!f.required || condRequired.has(f.code);
        const id = `sf-${f.code}`;
        const val = payload[f.code] ?? "";
        const label = (
          <label htmlFor={id}>
            {f.label} {isRequired && <span aria-hidden="true">*</span>}
          </label>
        );

        // حقول للاطلاع فقط (مثل البصمة المسجَّلة حاليًا) — لا تُرسَل
        if (f.read_only) {
          return (
            <div className="field" key={f.code}>
              {label}
              <input id={id} value={val} readOnly disabled />
            </div>
          );
        }

        if (f.type === "select") {
          return (
            <div className="field" key={f.code}>
              {label}
              <select
                id={id}
                value={val}
                required={isRequired}
                onChange={(e) => set(f.code, e.target.value || undefined)}
              >
                <option value="">— اختر —</option>
                {(f.options || []).map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
          );
        }

        if (f.type === "checkbox") {
          return (
            <div className="field" key={f.code}>
              <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                <input
                  id={id}
                  type="checkbox"
                  checked={!!payload[f.code]}
                  onChange={(e) => set(f.code, e.target.checked)}
                />
                {f.label}
              </label>
            </div>
          );
        }

        if (f.type === "textarea") {
          return (
            <div className="field" key={f.code}>
              {label}
              <textarea
                id={id}
                rows={3}
                value={val}
                required={isRequired}
                maxLength={f.max_length}
                onChange={(e) => set(f.code, e.target.value || undefined)}
              />
            </div>
          );
        }

        // number / amount / date / time / datetime / text ومراجع الكيانات
        const htmlType =
          f.type === "number" || f.type === "amount"
            ? "number"
            : f.type === "date"
            ? "date"
            : f.type === "time"
            ? "time"
            : f.type === "datetime"
            ? "datetime-local"
            : "text";
        const isNumeric = htmlType === "number";
        // مراجع الكيانات (branch_ref/license_ref/shift_ref/employee_ref) تُرسَل كرقم
        const isRef = f.type.endsWith("_ref");

        return (
          <div className="field" key={f.code}>
            {label}
            <input
              id={id}
              type={isRef ? "number" : htmlType}
              value={val}
              required={isRequired}
              min={f.min}
              max={f.max}
              maxLength={f.max_length}
              step={f.type === "amount" ? "0.001" : undefined}
              onChange={(e) => {
                const raw = e.target.value;
                if (raw === "") return set(f.code, undefined);
                set(f.code, isNumeric || isRef ? Number(raw) : raw);
              }}
            />
          </div>
        );
      })}

      {!!schema.attachments?.required?.length && (
        <p className="muted" style={{ fontSize: 12 }}>
          مرفقات مطلوبة: {schema.attachments.required.join("، ")} — ترفعها من صفحة
          الطلب بعد الإنشاء.
        </p>
      )}
    </>
  );
}
