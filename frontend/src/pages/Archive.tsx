import { useEffect, useState } from "react";
import api, { downloadFile } from "../api";
import { useAuth } from "../auth";
import Icon from "../Icon";

// أرشيف الشركة والفروع: المستندات الرسمية (عقد التأسيس، السجل التجاري، الرخص…).
export default function Archive() {
  const { can } = useAuth();
  const [tab, setTab] = useState<"company" | "branch">("company");
  const [data, setData] = useState<any>(null);          // أرشيف الشركة
  const [branches, setBranches] = useState<any[]>([]);
  const [branchId, setBranchId] = useState<number | "">("");
  const [branchData, setBranchData] = useState<any>(null);
  const [fileNo, setFileNo] = useState("");
  const [msg, setMsg] = useState("");

  const loadCompany = () => api.get("/archive/company").then((r) => { setData(r.data); setFileNo(r.data.company.file_number || ""); });
  const loadBranch = (id: number) => api.get(`/archive/branch/${id}`).then((r) => setBranchData(r.data));
  useEffect(() => {
    loadCompany().catch(() => {});
    api.get("/branches").then((r) => { setBranches(r.data); if (r.data[0]) { setBranchId(r.data[0].id); loadBranch(r.data[0].id); } });
  }, []);

  const saveFileNo = async () => {
    await api.put("/archive/company/info", null, { params: { file_number: fileNo } });
    setMsg("تم حفظ رقم الملف"); loadCompany();
  };

  const upload = async (entityType: string, entityId: number, code: string, name: string, file: File, reload: () => void) => {
    const fd = new FormData();
    fd.append("entity_type", entityType);
    fd.append("entity_id", String(entityId));
    fd.append("document_type_code", code);
    fd.append("title", name);
    fd.append("file", file);
    await api.post("/documents/upload", fd);
    setMsg(`تم رفع: ${name}`); reload();
  };

  const download = (entityType: string, entityId: number, code: string, name: string) =>
    downloadFile("/documents/latest", { entity_type: entityType, entity_id: entityId, document_type_code: code }, name);

  // شبكة خانات المستندات الرسمية
  const DocGrid = ({ entityType, entityId, docTypes, documents, reload }: any) => (
    <div className="grid cards">
      {docTypes.map((dt: any) => {
        const cur = documents.find((d: any) => d.type === dt.code);
        return (
          <div className="card" key={dt.code} style={{ borderTop: cur ? "3px solid var(--success)" : "3px solid var(--line)" }}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <b>{dt.name}</b>
              {cur ? <span className="pill success">مرفوع v{cur.version}</span> : <span className="pill neutral">غير مرفوع</span>}
            </div>
            {cur && <p className="muted" style={{ fontSize: 12 }}>أُضيف: {new Date(cur.created_at).toLocaleDateString("ar")}{cur.expiry_date ? ` · ينتهي ${cur.expiry_date}` : ""}</p>}
            <div className="row" style={{ marginTop: 8 }}>
              {cur && <button className="ghost sm" onClick={() => download(entityType, entityId, dt.code, dt.name)}><Icon name="doc" size={14} /> تنزيل</button>}
              {can("upload_documents") && (
                <label className="btn ghost sm" style={{ cursor: "pointer" }}>
                  {cur ? "استبدال" : "رفع"}
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
          <div className="eyebrow">الأرشيف</div>
          <h2 style={{ margin: "2px 0 0" }}>أرشيف المستندات الرسمية</h2>
          <div className="sub">عقد التأسيس · السجل التجاري · الرخص · مستندات الفروع</div>
        </div>
      </div>
      {msg && <div className="ok">{msg}</div>}

      <div className="row" style={{ marginBottom: 14 }}>
        <button className={tab === "company" ? "" : "ghost"} onClick={() => setTab("company")}>أرشيف الشركة</button>
        <button className={tab === "branch" ? "" : "ghost"} onClick={() => setTab("branch")}>أرشيف الفروع</button>
      </div>

      {tab === "company" && data && (
        <>
          <div className="card">
            <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap" }}>
              <div>
                <h3 style={{ margin: 0 }}>{data.company.name}</h3>
                <p className="muted" style={{ margin: "4px 0" }}>السجل التجاري: {data.company.commercial_reg || "—"} · النوع: {data.company.entity_type || "—"}</p>
              </div>
              <div className="row" style={{ alignItems: "flex-end" }}>
                <div className="field" style={{ margin: 0 }}><label>رقم ملف الشركة (القوى العاملة)</label>
                  <input value={fileNo} onChange={(e) => setFileNo(e.target.value)} style={{ width: 200 }} /></div>
                {can("manage_company") && <button onClick={saveFileNo}>حفظ</button>}
              </div>
            </div>
          </div>
          <DocGrid entityType="company" entityId={data.company.id} docTypes={data.doc_types}
            documents={data.documents} reload={loadCompany} />
        </>
      )}

      {tab === "branch" && (
        <>
          <div className="field" style={{ maxWidth: 320 }}>
            <label>اختر الفرع</label>
            <select value={branchId} onChange={(e) => { const id = +e.target.value; setBranchId(id); loadBranch(id); }}>
              {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          </div>
          {branchData && (
            <DocGrid entityType="branch" entityId={branchData.branch.id} docTypes={branchData.doc_types}
              documents={branchData.documents} reload={() => loadBranch(branchData.branch.id)} />
          )}
        </>
      )}
    </div>
  );
}
