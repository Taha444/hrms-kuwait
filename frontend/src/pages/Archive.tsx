import { useEffect, useState } from "react";
import api, { downloadFile, errMsg } from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import Icon from "../Icon";
import { fmtKuwaitDate } from "../utils/datetime";

// أرشيف الشركة والفروع: المستندات الرسمية (عقد التأسيس، السجل التجاري، الرخص…)
// R8 §2 — بالإضافة للمستندات الثابتة، يدعم مستندات مخصّصة ديناميكية (custom docs)
// كل واحد له metadata كاملة + version history + expiry notifications.
type CustomDocForm = {
  name_ar: string; name_en: string; doc_number: string;
  issue_date: string; expiry_date: string; issuing_authority: string;
  notes: string; notify_on_expiry: boolean; file: File | null;
};

export default function Archive() {
  const { can } = useAuth();
  const { t, lang } = useI18n();
  const isEn = lang === "en";
  const [tab, setTab] = useState<"company" | "branch">("company");
  const [data, setData] = useState<any>(null);          // أرشيف الشركة
  const [branches, setBranches] = useState<any[]>([]);
  const [branchId, setBranchId] = useState<number | "">("");
  const [branchData, setBranchData] = useState<any>(null);
  const [fileNo, setFileNo] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  // R8 §2 — custom doc form state
  const [customForm, setCustomForm] = useState<{ entityType: string; entityId: number } | null>(null);
  const [customData, setCustomData] = useState<CustomDocForm>({
    name_ar: "", name_en: "", doc_number: "", issue_date: "", expiry_date: "",
    issuing_authority: "", notes: "", notify_on_expiry: false, file: null,
  });

  const loadCompany = () => api.get("/archive/company").then((r) => { setData(r.data); setFileNo(r.data.company.file_number || ""); });
  const loadBranch = (id: number) => api.get(`/archive/branch/${id}`).then((r) => setBranchData(r.data));
  useEffect(() => {
    loadCompany().catch(() => {});
    api.get("/branches").then((r) => { setBranches(r.data); if (r.data[0]) { setBranchId(r.data[0].id); loadBranch(r.data[0].id); } });
  }, []);

  const saveFileNo = async () => {
    await api.put("/archive/company/info", null, { params: { file_number: fileNo } });
    setMsg(t("arch_file_saved")); loadCompany();
  };

  const upload = async (entityType: string, entityId: number, code: string, name: string, file: File, reload: () => void) => {
    const fd = new FormData();
    fd.append("entity_type", entityType);
    fd.append("entity_id", String(entityId));
    fd.append("document_type_code", code);
    fd.append("title", name);
    fd.append("file", file);
    await api.post("/documents/upload", fd);
    setMsg(t("arch_uploaded", { name })); reload();
  };

  const download = (entityType: string, entityId: number, code: string, name: string) =>
    downloadFile("/documents/latest", { entity_type: entityType, entity_id: entityId, document_type_code: code }, name);

  // R8 §2 — رفع custom doc
  const submitCustomDoc = async () => {
    if (!customForm || !customData.file || !customData.name_ar.trim()) {
      setErr(isEn ? "Arabic name + file required" : "اسم المستند بالعربية والملف مطلوبان");
      return;
    }
    setErr(""); setMsg("");
    try {
      const fd = new FormData();
      fd.append("entity_type", customForm.entityType);
      fd.append("entity_id", String(customForm.entityId));
      fd.append("name_ar", customData.name_ar);
      if (customData.name_en) fd.append("name_en", customData.name_en);
      if (customData.doc_number) fd.append("doc_number", customData.doc_number);
      if (customData.issue_date) fd.append("issue_date", customData.issue_date);
      if (customData.expiry_date) fd.append("expiry_date", customData.expiry_date);
      if (customData.issuing_authority) fd.append("issuing_authority", customData.issuing_authority);
      if (customData.notes) fd.append("notes", customData.notes);
      fd.append("notify_on_expiry", String(customData.notify_on_expiry));
      fd.append("file", customData.file);
      await api.post("/archive/custom-doc", fd);
      setMsg(isEn ? `Added: ${customData.name_ar}` : `تمت الإضافة: ${customData.name_ar}`);
      setCustomForm(null);
      setCustomData({ name_ar: "", name_en: "", doc_number: "", issue_date: "",
                      expiry_date: "", issuing_authority: "", notes: "",
                      notify_on_expiry: false, file: null });
      if (customForm.entityType === "company") loadCompany();
      else loadBranch(customForm.entityId);
    } catch (e: any) { setErr(errMsg(e, t("error"))); }
  };

  // R8 §2 — استبدال ملف custom doc (يحفظ القديم history)
  const replaceCustomDoc = async (docId: number, file: File, reload: () => void) => {
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api.post(`/archive/custom-doc/${docId}/replace`, fd);
      setMsg(isEn ? "Replaced (old kept as history)" : "تم الاستبدال (القديم محفوظ History)");
      reload();
    } catch (e: any) { setErr(errMsg(e, t("error"))); }
  };

  // شبكة خانات المستندات الرسمية
  const DocGrid = ({ entityType, entityId, docTypes, documents, reload }: any) => (
    <div className="grid cards">
      {docTypes.map((dt: any) => {
        const cur = documents.find((d: any) => d.type === dt.code);
        return (
          <div className="card" key={dt.code} style={{ borderTop: cur ? "3px solid var(--success)" : "3px solid var(--line)" }}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <b>{dt.name}</b>
              {cur ? <span className="pill success">{t("arch_uploaded_v", { v: cur.version })}</span> : <span className="pill neutral">{t("arch_not_uploaded")}</span>}
            </div>
            {cur && <p className="muted" style={{ fontSize: 12 }}>{t("arch_added", { date: fmtKuwaitDate(cur.created_at, lang) })}{cur.expiry_date ? ` · ${t("arch_expires", { date: cur.expiry_date })}` : ""}</p>}
            <div className="row" style={{ marginTop: 8 }}>
              {cur && <button className="ghost sm" onClick={() => download(entityType, entityId, dt.code, dt.name)}><Icon name="doc" size={14} /> {t("arch_download")}</button>}
              {can("upload_documents") && (
                <label className="btn ghost sm" style={{ cursor: "pointer" }}>
                  {cur ? t("arch_replace") : t("arch_upload")}
                  <input type="file" style={{ display: "none" }}
                    onChange={(e) => e.target.files && upload(entityType, entityId, dt.code, dt.name, e.target.files[0], reload)} />
                </label>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="eyebrow">{t("arch_eyebrow")}</div>
          <h2 style={{ margin: "2px 0 0" }}>{t("arch_title")}</h2>
          <div className="sub">{t("arch_sub")}</div>
        </div>
      </div>
      {msg && <div className="ok">{msg}</div>}

      <div className="row" style={{ marginBottom: 14 }}>
        <button className={tab === "company" ? "" : "ghost"} onClick={() => setTab("company")}>{t("arch_tab_company")}</button>
        <button className={tab === "branch" ? "" : "ghost"} onClick={() => setTab("branch")}>{t("arch_tab_branch")}</button>
      </div>

      {tab === "company" && data && (
        <>
          <div className="card">
            <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap" }}>
              <div>
                <h3 style={{ margin: 0 }}>{data.company.name}</h3>
                <p className="muted" style={{ margin: "4px 0" }}>{t("arch_commercial_reg")}: {data.company.commercial_reg || "—"} · {t("arch_entity_type")}: {data.company.entity_type || "—"}</p>
              </div>
              <div className="row" style={{ alignItems: "flex-end" }}>
                <div className="field" style={{ margin: 0 }}><label htmlFor="arch-file-no">{t("arch_file_number")}</label>
                  <input id="arch-file-no" value={fileNo} onChange={(e) => setFileNo(e.target.value)} style={{ width: 200 }} /></div>
                {can("manage_company") && <button onClick={saveFileNo}>{t("save")}</button>}
              </div>
            </div>
          </div>
          <DocGrid entityType="company" entityId={data.company.id} docTypes={data.doc_types}
            documents={data.documents} reload={loadCompany} />

          {/* R8 §2 — Custom Docs section */}
          <CustomDocsSection
            entityType="company" entityId={data.company.id}
            documents={data.documents.filter((d: any) => d.is_custom)}
            reload={loadCompany}
            onAdd={() => setCustomForm({ entityType: "company", entityId: data.company.id })}
            onReplace={replaceCustomDoc}
            can={can} isEn={isEn} lang={lang}
          />
        </>
      )}

      {tab === "branch" && (
        <>
          <div className="field" style={{ maxWidth: 320 }}>
            <label htmlFor="arch-branch">{t("arch_select_branch")}</label>
            <select id="arch-branch" value={branchId} onChange={(e) => { const id = +e.target.value; setBranchId(id); loadBranch(id); }}>
              {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          </div>
          {branchData && (
            <>
              <DocGrid entityType="branch" entityId={branchData.branch.id} docTypes={branchData.doc_types}
                documents={branchData.documents} reload={() => loadBranch(branchData.branch.id)} />

              {/* R8 §2 — Custom docs for this branch */}
              <CustomDocsSection
                entityType="branch" entityId={branchData.branch.id}
                documents={branchData.documents.filter((d: any) => d.is_custom)}
                reload={() => loadBranch(branchData.branch.id)}
                onAdd={() => setCustomForm({ entityType: "branch", entityId: branchData.branch.id })}
                onReplace={replaceCustomDoc}
                can={can} isEn={isEn} lang={lang}
              />
            </>
          )}
        </>
      )}

      {/* R8 §2 — Modal: نموذج إضافة custom doc */}
      {customForm && (
        <div role="dialog" aria-modal="true" onClick={() => setCustomForm(null)}
             style={{ position: "fixed", inset: 0, background: "rgba(11,59,84,0.5)",
                     display: "grid", placeItems: "center", zIndex: 1000, padding: 20 }}>
          <div onClick={(e) => e.stopPropagation()}
               style={{ background: "white", borderRadius: 12, padding: 24, maxWidth: 640,
                       width: "100%", maxHeight: "90vh", overflowY: "auto" }}>
            <h3 style={{ marginTop: 0 }}>
              {isEn ? "Add custom document" : "إضافة مستند مخصّص"}
            </h3>
            {err && <div className="err">{err}</div>}
            <div className="field">
              <label>{isEn ? "Document name (Arabic) *" : "اسم المستند بالعربية *"}</label>
              <input value={customData.name_ar} required
                     onChange={(e) => setCustomData({ ...customData, name_ar: e.target.value })}
                     placeholder={isEn ? "e.g. Import license" : "مثال: رخصة استيراد"} />
            </div>
            <div className="field">
              <label>{isEn ? "Name (English)" : "الاسم بالإنجليزية"}</label>
              <input value={customData.name_en}
                     onChange={(e) => setCustomData({ ...customData, name_en: e.target.value })} />
            </div>
            <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
              <div className="field" style={{ flex: 1, minWidth: 180 }}>
                <label>{isEn ? "Document number" : "رقم المستند"}</label>
                <input value={customData.doc_number}
                       onChange={(e) => setCustomData({ ...customData, doc_number: e.target.value })} />
              </div>
              <div className="field" style={{ flex: 1, minWidth: 180 }}>
                <label>{isEn ? "Issuing authority" : "جهة الإصدار"}</label>
                <input value={customData.issuing_authority}
                       onChange={(e) => setCustomData({ ...customData, issuing_authority: e.target.value })} />
              </div>
            </div>
            <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
              <div className="field" style={{ flex: 1, minWidth: 180 }}>
                <label>{isEn ? "Issue date" : "تاريخ الإصدار"}</label>
                <input type="date" value={customData.issue_date}
                       onChange={(e) => setCustomData({ ...customData, issue_date: e.target.value })} />
              </div>
              <div className="field" style={{ flex: 1, minWidth: 180 }}>
                <label>{isEn ? "Expiry date" : "تاريخ الانتهاء"}</label>
                <input type="date" value={customData.expiry_date}
                       onChange={(e) => setCustomData({ ...customData, expiry_date: e.target.value })} />
              </div>
            </div>
            <div className="field">
              <label>{isEn ? "Notes" : "ملاحظات"}</label>
              <textarea rows={2} value={customData.notes}
                        onChange={(e) => setCustomData({ ...customData, notes: e.target.value })} />
            </div>
            <div className="field">
              <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                <input type="checkbox" checked={customData.notify_on_expiry}
                       onChange={(e) => setCustomData({ ...customData, notify_on_expiry: e.target.checked })} />
                {isEn ? "Send expiry notification 30 days before"
                      : "إشعار قبل 30 يومًا من الانتهاء"}
              </label>
            </div>
            <div className="field">
              <label>{isEn ? "File *" : "الملف *"}</label>
              <input type="file" required
                     onChange={(e) => setCustomData({ ...customData, file: e.target.files?.[0] || null })} />
            </div>
            <div className="row" style={{ justifyContent: "flex-end", gap: 8, marginTop: 12 }}>
              <button className="ghost" onClick={() => setCustomForm(null)}>
                {isEn ? "Cancel" : "إلغاء"}
              </button>
              <button onClick={submitCustomDoc}>
                {isEn ? "Add document" : "إضافة"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// R8 §2 — قسم عرض المستندات المخصّصة (custom docs) لأي كيان (شركة/فرع)
function CustomDocsSection({ entityType, entityId, documents, onAdd, onReplace,
                             can, isEn, lang }: any) {
  return (
    <div className="card" style={{ marginTop: 16, borderTop: "3px solid var(--gold, #c8a24a)" }}>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <h3 style={{ margin: 0 }}>
          {isEn ? "Custom documents" : "مستندات أخرى مخصّصة"}
          <span className="muted" style={{ fontSize: 12, marginInlineStart: 8 }}>
            ({documents.length})
          </span>
        </h3>
        {can("upload_documents") && (
          <button onClick={onAdd}>
            {isEn ? "+ Add custom doc" : "+ إضافة مستند"}
          </button>
        )}
      </div>
      {documents.length === 0 ? (
        <p className="muted">
          {isEn ? "No custom documents added yet."
                : "لا توجد مستندات مخصّصة بعد. اضغط الزر لإضافة أول مستند."}
        </p>
      ) : (
        <div className="grid cards">
          {documents.map((d: any) => (
            <div key={d.id} className="card" style={{ background: "#fafcfb" }}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <b>{d.title}</b>
                <span className="pill success">v{d.version}</span>
              </div>
              {d.name_en && <div className="muted" style={{ fontSize: 12 }}>{d.name_en}</div>}
              <div style={{ fontSize: 12, color: "#4b5563", marginTop: 6 }}>
                {d.doc_number && <div>{isEn ? "No.: " : "رقم: "}<code>{d.doc_number}</code></div>}
                {d.issuing_authority && <div>{isEn ? "By: " : "الجهة: "}{d.issuing_authority}</div>}
                {d.expiry_date && (
                  <div style={{ color: new Date(d.expiry_date) < new Date() ? "var(--danger)" : "inherit" }}>
                    {isEn ? "Expires: " : "ينتهي: "}{d.expiry_date}
                    {d.notify_on_expiry && <span style={{ marginInlineStart: 6 }}>🔔</span>}
                  </div>
                )}
                {d.notes && <div className="muted">{d.notes}</div>}
              </div>
              <div className="row" style={{ marginTop: 8, gap: 6 }}>
                <a href={`/api/documents/latest?entity_type=${entityType}&entity_id=${entityId}&document_type_code=${encodeURIComponent(d.type)}`}
                   target="_blank" rel="noopener noreferrer" className="btn ghost sm"
                   style={{ textDecoration: "none" }}>
                  <Icon name="doc" size={14} /> {isEn ? "Download" : "تنزيل"}
                </a>
                {can("upload_documents") && (
                  <label className="btn ghost sm" style={{ cursor: "pointer" }}>
                    {isEn ? "Replace" : "استبدال"}
                    <input type="file" style={{ display: "none" }}
                           onChange={(e) => e.target.files &&
                             onReplace(d.id, e.target.files[0], () => window.location.reload())} />
                  </label>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
