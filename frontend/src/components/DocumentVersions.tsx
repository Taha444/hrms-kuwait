import { useState } from "react";
import api, { downloadFile } from "../api";
import Icon from "../Icon";
import { useI18n } from "../i18n";

/**
 * ARC-01 — النسخ السابقة لمستند.
 *
 * الخادم يحتفظ بكل إصدار، والتنزيل والتدقيق يعملان — ولم يكن في الواجهة
 * باب إليها. فالنسخة القديمة "محفوظة" ولا سبيل إلى فتحها، ووجودها في
 * القاعدة وحده لا يفيد من يحتاجها.
 *
 * ومكوّن واحد لا ثلاثة: أرشيف الشركة والفرع ومستندات الموظف تعرض الشيء
 * نفسه، ونسخ ثلاث منه تفترق عند أول تعديل.
 *
 * القواعد المطبَّقة هنا:
 * - القائمة تُحمَّل عند الطلب لا مع الصفحة: قراءة إصدارات كل مستند سلًفا
 *   تُبطئ شاشة لا يحتاجها أكثر الناس.
 * - إصدار واحد ⇒ لا زر. فتح قائمة فيها الحالي وحده يُوهم بوجود تاريخ.
 * - التنزيل يمرّ بنقطة الإصدار المحدَّد، فيُسجَّل في التدقيق كما يُسجَّل
 *   تنزيل الحالي. رابط مباشر إلى التخزين يتجاوز ذلك.
 */
export default function DocumentVersions({
  entityType, entityId, documentTypeCode, currentVersion,
}: {
  entityType: string;
  entityId: number;
  documentTypeCode: string;
  currentVersion?: number;
}) {
  const { lang } = useI18n();
  const isEn = lang === "en";
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<any[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  // إصدار واحد معروف سلًفا ⇒ لا داعي حتى للسؤال
  if (currentVersion !== undefined && currentVersion <= 1 && !open && rows === null) {
    return null;
  }

  const load = async () => {
    setBusy(true); setErr("");
    try {
      const r = await api.get("/documents/history", {
        params: { entity_type: entityType, entity_id: entityId,
                  document_type_code: documentTypeCode },
      });
      setRows(r.data);
      setOpen(true);
    } catch {
      // حالة الخطأ ليست حالة الفراغ: من لا يملك الصلاحية يُخبَر، ولا
      // يُترك أمام قائمة فارغة يظنّها «لا نسخ سابقة».
      setErr(isEn ? "Could not load versions — you may lack permission."
                  : "تعذّر تحميل النسخ — قد لا تملك صلاحية عرض هذا المستند.");
    } finally {
      setBusy(false);
    }
  };

  const older = (rows || []).filter((d) => !d.is_current);

  const fmtSize = (n: number | null) => {
    if (n === null || n === undefined) return "—";
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
    return `${(n / 1024 / 1024).toFixed(1)} MB`;
  };

  return (
    <>
      <button className="btn ghost sm" disabled={busy}
              onClick={() => (open ? setOpen(false) : load())}>
        <Icon name="doc" size={14} />{" "}
        {busy ? (isEn ? "Loading…" : "جارٍ…")
              : open ? (isEn ? "Hide versions" : "إخفاء النسخ")
                     : (isEn ? "Previous versions" : "النسخ السابقة")}
      </button>

      {err && <div className="err" style={{ fontSize: 12, marginTop: 6 }}>{err}</div>}

      {open && rows !== null && (
        older.length === 0 ? (
          <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>
            {isEn ? "No previous versions — this is the first."
                  : "لا نسخ سابقة — هذه أول نسخة."}
          </div>
        ) : (
          <div className="table-wrap" style={{ marginTop: 8 }}>
            <table>
              <thead>
                <tr>
                  <th>{isEn ? "Version" : "الإصدار"}</th>
                  <th>{isEn ? "Date" : "التاريخ"}</th>
                  <th>{isEn ? "Uploaded by" : "رفعها"}</th>
                  <th>{isEn ? "Size" : "الحجم"}</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {older.map((d) => (
                  <tr key={d.id}>
                    <td>v{d.version}</td>
                    <td>{d.created_at ? String(d.created_at).slice(0, 10) : "—"}</td>
                    <td>{d.uploaded_by_name || "—"}</td>
                    <td>{fmtSize(d.size_bytes)}</td>
                    <td>
                      <button className="btn ghost sm"
                              onClick={() => downloadFile(
                                `/documents/${d.id}/download`, {},
                                `${documentTypeCode}-v${d.version}`)}>
                        <Icon name="doc" size={13} />{" "}
                        {isEn ? "Download" : "تنزيل"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}
    </>
  );
}
