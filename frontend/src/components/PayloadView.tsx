import { useEffect, useState } from "react";
import api from "../api";
import { useI18n } from "../i18n";
import { fmtKuwaitDate, fmtKuwaitDateTime } from "../utils/datetime";

/**
 * QA-07 — عرض تفاصيل الطلب بلغة الناس لا JSON خام.
 *
 * ROOT CAUSE: صفحة الطلب كانت تطبع `JSON.stringify(req.payload)`، فيرى
 * المعتمِد `{"leave_type":"annual","start_date":"2026-08-01"}` ويُطلب منه أن
 * يقرّر على أساسه.
 *
 * لم نبنِ خريطة تسميات في الواجهة: الـschema في الخادم يحمل label ونوع كل
 * حقل لكل نوع طلب أصًلا (وهو ما يبني به النموذج). خريطة ثانية هنا كانت
 * ستنحرف عنه مع أول حقل يُضاف — وهو نمط الخلل المتكرر في هذا النظام.
 * الحقول التي لا يعرفها الـschema (طلبات قديمة، حقول أُزيلت) تُعرض بكودها
 * بدل إخفائها: معلومة ناقصة التسمية خير من معلومة مفقودة.
 */
type Field = { code: string; label: string; type: string; options?: { value: string; label: string }[] };

export default function PayloadView({ typeCode, payload }: { typeCode?: string; payload: any }) {
  const { t, lang } = useI18n();
  const [fields, setFields] = useState<Field[] | null>(null);

  useEffect(() => {
    if (!typeCode) { setFields([]); return; }
    let alive = true;
    api.get(`/requests/types/${typeCode}/schema`)
      .then((r) => { if (alive) setFields(r.data?.schema?.fields || []); })
      .catch(() => { if (alive) setFields([]); });
    return () => { alive = false; };
  }, [typeCode]);

  const entries = Object.entries(payload || {}).filter(
    ([, v]) => v !== null && v !== undefined && v !== ""
  );
  if (!entries.length) return <p className="muted">{t("rd_data")}: —</p>;
  if (fields === null) return <p className="muted">{t("rd_data")}: {t("loading")}</p>;

  const byCode = new Map(fields.map((f) => [f.code, f]));

  const render = (code: string, value: any): string => {
    const f = byCode.get(code);
    if (typeof value === "boolean") return value ? t("yes") : t("no");
    if (Array.isArray(value)) return value.map((v) => render(code, v)).join("، ");
    if (f?.options?.length) {
      const opt = f.options.find((o) => String(o.value) === String(value));
      if (opt) return opt.label;
    }
    if (f?.type === "date") return fmtKuwaitDate(String(value), lang);
    if (f?.type === "datetime") return fmtKuwaitDateTime(String(value), lang);
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  };

  return (
    <div style={{ marginTop: 6 }}>
      <div className="muted" style={{ marginBottom: 4 }}>{t("rd_data")}:</div>
      <table className="kv">
        <tbody>
          {entries.map(([code, value]) => (
            <tr key={code}>
              <td className="muted" style={{ paddingInlineEnd: 12, whiteSpace: "nowrap" }}>
                {byCode.get(code)?.label || code}
              </td>
              <td>{render(code, value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
