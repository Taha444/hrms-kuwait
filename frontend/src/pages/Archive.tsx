import { useEffect, useState } from "react";
import api, { downloadFile, errMsg } from "../api";
import DocumentVersions from "../components/DocumentVersions";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import Icon from "../Icon";
import { fmtKuwaitDate } from "../utils/datetime";
import NeedsCompany, { useNeedsCompany } from "../components/NeedsCompany";

// أرشيف الشركة والفروع: المستندات الرسمية (عقد التأسيس، السجل التجاري، الرخص…)
// R8 §2 — بالإضافة للمستندات الثابتة، يدعم مستندات مخصّصة ديناميكية (custom docs)
// كل واحد له metadata كاملة + version history + expiry notifications.
type CustomDocForm = {
  name_ar: string; name_en: string; doc_number: string;
  issue_date: string; expiry_date: string; issuing_authority: string;
  notes: string; notify_on_expiry: boolean;
  assigned_pro_id: number | null; file: File | null;
};

export default function Archive() {
  const { can } = useAuth();
  const needsCompany = useNeedsCompany();
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
    issuing_authority: "", notes: "", notify_on_expiry: false,
    assigned_pro_id: null, file: null,
  });
  // R9 — PRO users للتعيين على مستندات مخصّصة
  const [proUsers, setProUsers] = useState<any[]>([]);

  const loadCompany = () => api.get("/archive/company").then((r) => { setData(r.data); setFileNo(r.data.company.file_number || ""); });
  const loadBranch = (id: number) => api.get(`/archive/branch/${id}`).then((r) => setBranchData(r.data));
  useEffect(() => {
    loadCompany().catch(() => {});
    api.get("/branches").then((r) => { setBranches(r.data); if (r.data[0]) { setBranchId(r.data[0].id); loadBranch(r.data[0].id); } });
    // R9 — قائمة المندوبين للتعيين على مستندات مخصّصة
    api.get("/users").then((r) => setProUsers(
      (r.data || []).filter((u: any) => u.role === "delegate" && u.is_active !== false)
    )).catch(() => {});
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
      if (customData.assigned_pro_id) fd.append("assigned_pro_id", String(customData.assigned_pro_id));
      fd.append("file", customData.file);
      await api.post("/archive/custom-doc", fd);
      setMsg(isEn ? `Added: ${customData.name_ar}` : `تمت الإضافة: ${customData.name_ar}`);
      setCustomForm(null);
      setCustomData({ name_ar: "", name_en: "", doc_number: "", issue_date: "",
                      expiry_date: "", issuing_authority: "", notes: "",
                      notify_on_expiry: false, assigned_pro_id: null, file: null });
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

  // R9 §3 — Edit metadata (بدون تغيير الملف)
  const [editForm, setEditForm] = useState<any | null>(null);
  const openEdit = (doc: any) => {
    setEditForm({
      id: doc.id,
      name_ar: doc.title || "",
      name_en: doc.name_en || "",
      doc_number: doc.doc_number || "",
      issuing_authority: doc.issuing_authority || "",
      notes: doc.notes || "",
      expiry_date: doc.expiry_date || "",
      notify_on_expiry: !!doc.notify_on_expiry,
      assigned_pro_id: doc.assigned_pro_id ?? null,
      _entityType: doc._entityType,
      _entityId: doc._entityId,
    });
  };
  const submitEdit = async () => {
    if (!editForm) return;
    const fd = new FormData();
    fd.append("name_ar", editForm.name_ar);
    fd.append("name_en", editForm.name_en);
    fd.append("doc_number", editForm.doc_number);
    fd.append("issuing_authority", editForm.issuing_authority);
    fd.append("notes", editForm.notes);
    if (editForm.expiry_date) fd.append("expiry_date", editForm.expiry_date);
    fd.append("notify_on_expiry", String(editForm.notify_on_expiry));
    if (editForm.assigned_pro_id) fd.append("assigned_pro_id", String(editForm.assigned_pro_id));
    else fd.append("clear_assigned_pro", "true");
    try {
      await api.put(`/archive/custom-doc/${editForm.id}`, fd);
      setMsg(isEn ? "Updated" : "تم التحديث");
      setEditForm(null);
      if (editForm._entityType === "company") loadCompany();
      else loadBranch(editForm._entityId);
    } catch (e: any) { setErr(errMsg(e, t("error"))); }
  };

  // R9 §3 — Delete نهائي
  const deleteCustomDoc = async (doc: any) => {
    const confirmMsg = isEn
      ? `Delete "${doc.title}" and ALL its versions? This cannot be undone.`
      : `حذف "${doc.title}" وكل نسخه؟ هذا الإجراء لا يمكن التراجع عنه.`;
    if (!window.confirm(confirmMsg)) return;
    try {
      await api.delete(`/archive/custom-doc/${doc.id}`);
      setMsg(isEn ? "Deleted" : "تم الحذف");
      if (doc._entityType === "company") loadCompany();
      else loadBranch(doc._entityId);
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
              {/* ARC-01/ARC-02 — الحالي على وجه البطاقة، والتاريخ خلف زر.
                  والمكوّن نفسه لأرشيف الشركة والفرع: نسختان منه تفترقان
                  عند أول تعديل. */}
              {cur && <DocumentVersions entityType={entityType} entityId={entityId}
                                        documentTypeCode={dt.code}
                                        currentVersion={cur.version} />}
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

      {/* QA-16 — الأرشيف يخص شركة واحدة. مع "كل الشركات" كانت الصفحة تعرض
          فراًغا برسالة "لا توجد مستندات بعد" — صحيحة نحوًيا وخاطئة معنى. */}
      {needsCompany ? <NeedsCompany /> : (<>

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
            documents={data.documents.filter((d: any) => d.is_custom)
              .map((d: any) => ({ ...d, _entityType: "company", _entityId: data.company.id }))}
            reload={loadCompany}
            onAdd={() => setCustomForm({ entityType: "company", entityId: data.company.id })}
            onReplace={replaceCustomDoc}
            onEdit={openEdit} onDelete={deleteCustomDoc}
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
                documents={branchData.documents.filter((d: any) => d.is_custom)
                  .map((d: any) => ({ ...d, _entityType: "branch", _entityId: branchData.branch.id }))}
                reload={() => loadBranch(branchData.branch.id)}
                onAdd={() => setCustomForm({ entityType: "branch", entityId: branchData.branch.id })}
                onReplace={replaceCustomDoc}
                onEdit={openEdit} onDelete={deleteCustomDoc}
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
            {customData.notify_on_expiry && (
              <div className="field">
                <label>{isEn ? "Assign to PRO (optional)" : "المندوب المسؤول عن المتابعة (اختياري)"}</label>
                <select value={customData.assigned_pro_id ?? ""}
                        onChange={(e) => setCustomData({ ...customData,
                          assigned_pro_id: e.target.value ? +e.target.value : null })}>
                  <option value="">{isEn ? "All PROs in the company" : "كل المندوبين في الشركة"}</option>
                  {proUsers.map((u) => (
                    <option key={u.id} value={u.id}>{u.full_name || u.civil_id}</option>
                  ))}
                </select>
                <small className="muted">
                  {isEn ? "If empty, all delegates receive the alert."
                        : "لو فارغ، كل مندوبي الشركة يستلمون التنبيه."}
                </small>
              </div>
            )}
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

      {/* R9 §3 — Modal: تعديل metadata لمستند مخصّص */}
      {editForm && (
        <div role="dialog" aria-modal="true" onClick={() => setEditForm(null)}
             style={{ position: "fixed", inset: 0, background: "rgba(11,59,84,0.5)",
                     display: "grid", placeItems: "center", zIndex: 1000, padding: 20 }}>
          <div onClick={(e) => e.stopPropagation()}
               style={{ background: "white", borderRadius: 12, padding: 24, maxWidth: 640,
                       width: "100%", maxHeight: "90vh", overflowY: "auto" }}>
            <h3 style={{ marginTop: 0 }}>
              {isEn ? "Edit custom document" : "تعديل المستند المخصّص"}
            </h3>
            {err && <div className="err">{err}</div>}
            <div className="field">
              <label>{isEn ? "Name (Arabic)" : "الاسم بالعربية"}</label>
              <input value={editForm.name_ar}
                     onChange={(e) => setEditForm({ ...editForm, name_ar: e.target.value })} />
            </div>
            <div className="field">
              <label>{isEn ? "Name (English)" : "الاسم بالإنجليزية"}</label>
              <input value={editForm.name_en}
                     onChange={(e) => setEditForm({ ...editForm, name_en: e.target.value })} />
            </div>
            <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
              <div className="field" style={{ flex: 1, minWidth: 180 }}>
                <label>{isEn ? "Document number" : "رقم المستند"}</label>
                <input value={editForm.doc_number}
                       onChange={(e) => setEditForm({ ...editForm, doc_number: e.target.value })} />
              </div>
              <div className="field" style={{ flex: 1, minWidth: 180 }}>
                <label>{isEn ? "Issuing authority" : "جهة الإصدار"}</label>
                <input value={editForm.issuing_authority}
                       onChange={(e) => setEditForm({ ...editForm, issuing_authority: e.target.value })} />
              </div>
            </div>
            <div className="field">
              <label>{isEn ? "Expiry date" : "تاريخ الانتهاء"}</label>
              <input type="date" value={editForm.expiry_date}
                     onChange={(e) => setEditForm({ ...editForm, expiry_date: e.target.value })} />
            </div>
            <div className="field">
              <label>{isEn ? "Notes" : "ملاحظات"}</label>
              <textarea rows={2} value={editForm.notes}
                        onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })} />
            </div>
            <div className="field">
              <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                <input type="checkbox" checked={editForm.notify_on_expiry}
                       onChange={(e) => setEditForm({ ...editForm, notify_on_expiry: e.target.checked })} />
                {isEn ? "Send expiry notification 30 days before"
                      : "إشعار قبل 30 يومًا من الانتهاء"}
              </label>
            </div>
            {editForm.notify_on_expiry && (
              <div className="field">
                <label>{isEn ? "Assign to PRO (optional)" : "المندوب المسؤول (اختياري)"}</label>
                <select value={editForm.assigned_pro_id ?? ""}
                        onChange={(e) => setEditForm({ ...editForm,
                          assigned_pro_id: e.target.value ? +e.target.value : null })}>
                  <option value="">{isEn ? "All PROs" : "كل المندوبين"}</option>
                  {proUsers.map((u) => (
                    <option key={u.id} value={u.id}>{u.full_name || u.civil_id}</option>
                  ))}
                </select>
              </div>
            )}
            <div className="row" style={{ justifyContent: "flex-end", gap: 8, marginTop: 12 }}>
              <button className="ghost" onClick={() => setEditForm(null)}>
                {isEn ? "Cancel" : "إلغاء"}
              </button>
              <button onClick={submitEdit}>
                {isEn ? "Save changes" : "حفظ التعديلات"}
              </button>
            </div>
          </div>
        </div>
      )}
      </>)}
    </div>
  );
}

// R8 §2 — قسم عرض المستندات المخصّصة (custom docs) لأي كيان (شركة/فرع)
// R9 §3 — إضافة onEdit + onDelete
function CustomDocsSection({ entityType, entityId, documents, onAdd, onReplace,
                             onEdit, onDelete, can, isEn, lang }: any) {
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
                {d.assigned_pro_name && (
                  <div style={{ color: "#0b3b54" }}>
                    {isEn ? "PRO: " : "المسؤول: "}<b>{d.assigned_pro_name}</b>
                  </div>
                )}
                {d.notes && <div className="muted">{d.notes}</div>}
              </div>
              <div className="row" style={{ marginTop: 8, gap: 6, flexWrap: "wrap" }}>
                <a href={`/api/documents/latest?entity_type=${entityType}&entity_id=${entityId}&document_type_code=${encodeURIComponent(d.type)}`}
                   target="_blank" rel="noopener noreferrer" className="btn ghost sm"
                   style={{ textDecoration: "none" }}>
                  <Icon name="doc" size={14} /> {isEn ? "Download" : "تنزيل"}
                </a>
                {/* ARC-01 — النسخ السابقة: الخادم يحتفظ بها والواجهة لم
                    يكن فيها باب إليها. الزر يختفي تلقائيًّا عند الإصدار
                    الأول، فلا تُفتح قائمة تُوهم بوجود تاريخ. */}
                <DocumentVersions entityType={entityType} entityId={entityId}
                                  documentTypeCode={d.type}
                                  currentVersion={d.version} />
                {can("upload_documents") && (
                  <label className="btn ghost sm" style={{ cursor: "pointer" }}>
                    {isEn ? "Replace" : "استبدال"}
                    <input type="file" style={{ display: "none" }}
                           onChange={(e) => e.target.files &&
                             onReplace(d.id, e.target.files[0], () => window.location.reload())} />
                  </label>
                )}
                {can("upload_documents") && onEdit && (
                  <button className="btn ghost sm" onClick={() => onEdit(d)}
                          title={isEn ? "Edit metadata" : "تعديل البيانات"}>
                    ✎ {isEn ? "Edit" : "تعديل"}
                  </button>
                )}
                {can("upload_documents") && onDelete && (
                  <button className="btn ghost sm" onClick={() => onDelete(d)}
                          style={{ color: "var(--danger, #b91c1c)" }}
                          title={isEn ? "Delete document" : "حذف المستند"}>
                    🗑 {isEn ? "Delete" : "حذف"}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
