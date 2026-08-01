import { useState } from "react";
import api, { errMsg } from "../api";
import { useI18n } from "../i18n";

/**
 * V2.2 §2 — Employee Onboarding Wizard
 *
 * 4 خطوات end-to-end:
 *   1. البيانات الأساسية (اسم، رقم مدني، راتب، تعيين)
 *   2. البيانات التنظيمية (فرع، قسم، وردية، مدير، سياسة حضور)
 *   3. جواز السفر والوثائق (OCR اختياري → مراجعة → حفظ)
 *   4. الإقامة وأذونات العمل
 * الخطوة النهائية: نجاح مع employee_no المُولَّد + أزرار رفع مستندات.
 */

type Props = {
  branches: any[];
  departments: any[];
  onDone: (emp: any) => void;
  onCancel: () => void;
};

const emptyForm = {
  name: "", civil_id: "", basic_salary: 0,
  job_title: "", hire_date: "", contract_type: "indefinite",
  branch_id: null as number | null,
  actual_branch_id: null as number | null,
  department_id: null as number | null,
  attendance_mode: "qr", // V2.2 §17 — نبدأ بـqr كافتراضي عوض none
  attendance_exempt: false,
  attendance_exempt_reason: "",
  nationality: "", gender: "" as string,
  date_of_birth: "" as string,
  passport_number: "", passport_expiry: "" as string,
  phone: "", email: "", worker_type: "موظف",
};

export default function EmployeeOnboarding({ branches, departments, onDone, onCancel }: Props) {
  const { t, lang } = useI18n();
  const isEn = lang === "en";
  const [step, setStep] = useState(1);
  const [form, setForm] = useState<any>(emptyForm);
  const [savedEmp, setSavedEmp] = useState<any>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  // OCR state
  const [ocrFile, setOcrFile] = useState<File | null>(null);
  const [ocrType, setOcrType] = useState("passport");
  const [ocrSuggested, setOcrSuggested] = useState<any>(null);
  const [ocrMsg, setOcrMsg] = useState("");

  // Permits state
  const [permits, setPermits] = useState<any[]>([]);
  const [permitForm, setPermitForm] = useState({
    kind: "residency", number: "", start_date: "", expiry_date: "",
  });

  // Documents state
  const [docFile, setDocFile] = useState<File | null>(null);
  const [docType, setDocType] = useState("passport");
  const [docExpiry, setDocExpiry] = useState("");
  const [uploadedDocs, setUploadedDocs] = useState<string[]>([]);

  // User account state — يُنشأ تلقائيًا بعد الحفظ (checkbox قابل للإلغاء)
  const [createUserAccount, setCreateUserAccount] = useState(true);
  const [userCredentials, setUserCredentials] = useState<{
    civil_id: string; password: string; user_id: number;
  } | null>(null);
  const [copyToast, setCopyToast] = useState("");

  const setField = (k: string, v: any) => setForm({ ...form, [k]: v });

  // كلمة سر عشوائية قوية: 12 حرف، حروف كبيرة/صغيرة/أرقام/رموز
  const genPassword = (): string => {
    const upper = "ABCDEFGHJKLMNPQRSTUVWXYZ"; // بلا I/O لتجنب اللبس
    const lower = "abcdefghjkmnpqrstuvwxyz";
    const digits = "23456789";
    const symbols = "!@#$%&*";
    const all = upper + lower + digits + symbols;
    // تضمين نوع واحد على الأقل من كل فئة
    const required = [
      upper[Math.floor(Math.random() * upper.length)],
      lower[Math.floor(Math.random() * lower.length)],
      digits[Math.floor(Math.random() * digits.length)],
      symbols[Math.floor(Math.random() * symbols.length)],
    ];
    const rest = Array.from({ length: 8 }, () => all[Math.floor(Math.random() * all.length)]);
    return [...required, ...rest].sort(() => Math.random() - 0.5).join("");
  };

  const copyToClipboard = async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopyToast(isEn ? `${label} copied ✓` : `تم نسخ ${label} ✓`);
      setTimeout(() => setCopyToast(""), 2000);
    } catch {
      setErr(isEn ? "Copy failed — select and copy manually" : "فشل النسخ — حدد واسحب يدويًا");
    }
  };

  // ============ Step 1 validation ============
  const validateStep1 = () => {
    if (!form.name?.trim()) return isEn ? "Full name is required" : "الاسم الكامل مطلوب";
    if (!form.civil_id?.trim()) return isEn ? "Civil ID is required" : "الرقم المدني مطلوب";
    if (!/^\d{6,12}$/.test(form.civil_id.trim()))
      return isEn ? "Civil ID must be 6-12 digits" : "الرقم المدني يجب أن يكون 6-12 خانة رقمية";
    if (!form.basic_salary || +form.basic_salary <= 0)
      return isEn ? "Basic salary must be > 0" : "الراتب الأساسي يجب أن يكون أكبر من صفر";
    if (!form.hire_date) return isEn ? "Hire date is required" : "تاريخ التعيين مطلوب";
    if (!form.job_title?.trim()) return isEn ? "Job title is required" : "المسمى الوظيفي مطلوب";
    return null;
  };

  const validateStep2 = () => {
    if (!form.branch_id) return isEn ? "Branch is required" : "الفرع مطلوب";
    // SEC2-17: mode=none يشترط exempt + reason
    if (form.attendance_mode === "none" && !form.attendance_exempt)
      return isEn
        ? "'None' attendance requires explicit exemption + reason"
        : "نمط 'بلا حضور' يشترط إعفاء صريح + سبب";
    if (form.attendance_exempt && !form.attendance_exempt_reason?.trim())
      return isEn ? "Exemption reason is required" : "سبب الإعفاء مطلوب";
    return null;
  };

  const nextStep = () => {
    setErr("");
    if (step === 1) {
      const e = validateStep1(); if (e) { setErr(e); return; }
    }
    if (step === 2) {
      const e = validateStep2(); if (e) { setErr(e); return; }
    }
    setStep(step + 1);
  };

  // ============ OCR ============
  const runOcr = async () => {
    if (!ocrFile) { setErr(isEn ? "Choose a file first" : "اختر الملف أولاً"); return; }
    setErr(""); setOcrMsg(""); setBusy(true);
    try {
      const fd = new FormData();
      fd.append("document_type_code", ocrType);
      fd.append("file", ocrFile);
      const r = await api.post("/documents/ocr-preview", fd);
      setOcrSuggested(r.data.suggested);
      setOcrMsg(r.data.note || (isEn ? "Review the values below" : "راجع القيم أدناه"));
    } catch (e: any) { setErr(errMsg(e, isEn ? "OCR failed" : "فشل قراءة المستند")); }
    finally { setBusy(false); }
  };

  const applyOcrToForm = () => {
    if (!ocrSuggested) return;
    // نطبّق على form مباشرة قبل حفظ الموظف
    const updates: any = {};
    if (ocrType === "passport") {
      if (ocrSuggested.passport_number) updates.passport_number = ocrSuggested.passport_number;
      if (ocrSuggested.expiry_date) updates.passport_expiry = ocrSuggested.expiry_date;
      if (ocrSuggested.nationality) updates.nationality = ocrSuggested.nationality;
      if (ocrSuggested.date_of_birth) updates.date_of_birth = ocrSuggested.date_of_birth;
      if (ocrSuggested.full_name && !form.name) updates.name = ocrSuggested.full_name;
    }
    if (ocrType === "civil_id") {
      if (ocrSuggested.civil_id) updates.civil_id = ocrSuggested.civil_id;
      if (ocrSuggested.nationality) updates.nationality = ocrSuggested.nationality;
    }
    setForm({ ...form, ...updates });
    setOcrMsg(isEn ? "Values applied to the form" : "تم تطبيق القيم على الفورم");
  };

  // ============ Save employee (Step 3 end) ============
  const saveEmployee = async () => {
    setErr(""); setBusy(true);
    try {
      const active = localStorage.getItem("active_company_id");
      const payload: any = { ...form };
      // نظّف حقول التاريخ الفارغة
      Object.keys(payload).forEach(k => {
        if (payload[k] === "") payload[k] = null;
      });
      if (active && active !== "all") payload.company_id = Number(active);
      const r = await api.post("/employees", payload);
      setSavedEmp(r.data);
      setStep(4);
      // إنشاء حساب المستخدم تلقائيًا لو HR اختار (الافتراضي)
      if (createUserAccount) {
        const pw = genPassword();
        try {
          const userR = await api.post("/users", {
            civil_id: r.data.civil_id,
            full_name: r.data.name,
            role: "employee",
            company_id: r.data.company_id,
            employee_id: r.data.id,
            password: pw,
          });
          setUserCredentials({
            civil_id: r.data.civil_id,
            password: pw,
            user_id: userR.data.id,
          });
        } catch (userErr: any) {
          // فشل إنشاء الحساب لا يعطل الفلو — يظهر تنبيه بالأسباب
          const msg = errMsg(userErr, isEn ? "User account creation failed" : "فشل إنشاء حساب المستخدم");
          setErr(isEn
            ? `Employee saved, but user account failed: ${msg}. Create manually later.`
            : `تم حفظ الموظف، لكن فشل إنشاء الحساب: ${msg}. أنشئه يدويًا لاحقًا.`);
        }
      }
    } catch (e: any) { setErr(errMsg(e, t("error"))); }
    finally { setBusy(false); }
  };

  // ============ Add permit (Step 4) ============
  const addPermit = async () => {
    if (!savedEmp?.id) return;
    if (!permitForm.expiry_date) {
      setErr(isEn ? "Expiry date required" : "تاريخ الانتهاء مطلوب"); return;
    }
    setErr(""); setBusy(true);
    try {
      const params: any = {
        kind: permitForm.kind, number: permitForm.number || undefined,
        start_date: permitForm.start_date || undefined,
        expiry_date: permitForm.expiry_date,
      };
      const r = await api.post(`/employees/${savedEmp.id}/permits`, null, { params });
      setPermits([...permits, { ...permitForm, id: r.data.id }]);
      setPermitForm({ kind: "residency", number: "", start_date: "", expiry_date: "" });
    } catch (e: any) { setErr(errMsg(e, isEn ? "Failed to add permit" : "فشل إضافة الإذن")); }
    finally { setBusy(false); }
  };

  // ============ Upload document (Step 4) ============
  const uploadDoc = async () => {
    if (!savedEmp?.id || !docFile) {
      setErr(isEn ? "Choose a document type and file" : "اختر نوع المستند والملف"); return;
    }
    setErr(""); setBusy(true);
    try {
      const fd = new FormData();
      fd.append("entity_type", "employee");
      fd.append("entity_id", String(savedEmp.id));
      fd.append("document_type_code", docType);
      if (docExpiry) fd.append("expiry_date", docExpiry);
      fd.append("file", docFile);
      await api.post("/documents/upload", fd);
      setUploadedDocs([...uploadedDocs, `${docType} — ${docFile.name}`]);
      setDocFile(null); setDocExpiry("");
      (document.getElementById("wiz-doc-file") as HTMLInputElement)?.form?.reset();
    } catch (e: any) { setErr(errMsg(e, isEn ? "Upload failed" : "فشل الرفع")); }
    finally { setBusy(false); }
  };

  // ============ Render progress ============
  const Steps = () => (
    <div className="row" style={{ gap: 6, marginBottom: 16, flexWrap: "wrap" }}>
      {[
        { n: 1, label: isEn ? "1 · Basic info" : "1 · البيانات الأساسية" },
        { n: 2, label: isEn ? "2 · Organization" : "2 · التنظيمية" },
        { n: 3, label: isEn ? "3 · Passport & OCR" : "3 · الجواز/OCR" },
        { n: 4, label: isEn ? "4 · Documents & Permits" : "4 · المستندات/الإقامة" },
      ].map(s => (
        <span key={s.n} className={`pill ${step === s.n ? "info" : step > s.n ? "success" : ""}`}>
          {s.label}
        </span>
      ))}
    </div>
  );

  return (
    <div className="card" role="region" aria-labelledby="wiz-title">
      <h3 id="wiz-title">
        {isEn ? "New Employee Onboarding" : "تسجيل موظف جديد"}
        {savedEmp && (
          <span className="pill success" style={{ marginRight: 12, fontSize: 12 }}>
            {savedEmp.employee_no}
          </span>
        )}
      </h3>
      <Steps />
      {err && <div className="err" role="alert" aria-live="assertive">{err}</div>}

      {/* ============ STEP 1: Basic info ============ */}
      {step === 1 && (
        <>
          <div className="row">
            <div className="field" style={{ flex: 2 }}>
              <label htmlFor="wiz-name">{isEn ? "Full name" : "الاسم الكامل"} *</label>
              <input id="wiz-name" value={form.name}
                onChange={(e) => setField("name", e.target.value)} required aria-required="true" />
            </div>
            <div className="field" style={{ flex: 1 }}>
              <label htmlFor="wiz-civil-id">{isEn ? "Civil ID" : "الرقم المدني"} *</label>
              <input id="wiz-civil-id" value={form.civil_id} dir="ltr"
                inputMode="numeric" pattern="[0-9]{6,12}"
                onChange={(e) => setField("civil_id", e.target.value.replace(/\D/g, ""))}
                required aria-required="true" />
            </div>
          </div>
          <div className="row">
            <div className="field" style={{ flex: 1 }}>
              <label htmlFor="wiz-job">{isEn ? "Job title" : "المسمى الوظيفي"} *</label>
              <input id="wiz-job" value={form.job_title}
                onChange={(e) => setField("job_title", e.target.value)} required />
            </div>
            <div className="field" style={{ flex: 1 }}>
              <label htmlFor="wiz-salary">{isEn ? "Basic salary (KWD)" : "الراتب الأساسي (د.ك)"} *</label>
              <input id="wiz-salary" type="number" min={0.001} step="0.001"
                value={form.basic_salary || ""}
                onChange={(e) => setField("basic_salary", e.target.value ? +e.target.value : 0)} required />
            </div>
            <div className="field" style={{ flex: 1 }}>
              <label htmlFor="wiz-hire">{isEn ? "Hire date" : "تاريخ التعيين"} *</label>
              <input id="wiz-hire" type="date" value={form.hire_date}
                onChange={(e) => setField("hire_date", e.target.value)} required />
            </div>
            <div className="field" style={{ flex: 1 }}>
              <label htmlFor="wiz-contract">{isEn ? "Contract type" : "نوع العقد"}</label>
              <select id="wiz-contract" value={form.contract_type}
                onChange={(e) => setField("contract_type", e.target.value)}>
                <option value="indefinite">{isEn ? "Indefinite" : "غير محدد المدة"}</option>
                <option value="definite">{isEn ? "Definite" : "محدد المدة"}</option>
              </select>
            </div>
          </div>
          <div className="row">
            <div className="field" style={{ flex: 1 }}>
              <label htmlFor="wiz-nat">{isEn ? "Nationality" : "الجنسية"}</label>
              <input id="wiz-nat" value={form.nationality}
                onChange={(e) => setField("nationality", e.target.value)} />
            </div>
            <div className="field" style={{ flex: 1 }}>
              <label htmlFor="wiz-gender">{isEn ? "Gender" : "الجنس"}</label>
              <select id="wiz-gender" value={form.gender}
                onChange={(e) => setField("gender", e.target.value)}>
                <option value="">—</option>
                <option value="male">{isEn ? "Male" : "ذكر"}</option>
                <option value="female">{isEn ? "Female" : "أنثى"}</option>
              </select>
            </div>
            <div className="field" style={{ flex: 1 }}>
              <label htmlFor="wiz-dob">{isEn ? "Date of birth" : "تاريخ الميلاد"}</label>
              <input id="wiz-dob" type="date" value={form.date_of_birth}
                onChange={(e) => setField("date_of_birth", e.target.value)} />
            </div>
            <div className="field" style={{ flex: 1 }}>
              <label htmlFor="wiz-phone">{isEn ? "Phone" : "الهاتف"}</label>
              <input id="wiz-phone" value={form.phone} dir="ltr"
                onChange={(e) => setField("phone", e.target.value)} />
            </div>
          </div>
        </>
      )}

      {/* ============ STEP 2: Organization ============ */}
      {step === 2 && (
        <>
          <div className="row">
            <div className="field" style={{ flex: 1 }}>
              <label htmlFor="wiz-branch">{isEn ? "Official branch" : "الفرع الرسمي"} *</label>
              <select id="wiz-branch" value={form.branch_id ?? ""}
                onChange={(e) => setField("branch_id", e.target.value ? +e.target.value : null)}>
                <option value="">—</option>
                {branches.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
              </select>
            </div>
            <div className="field" style={{ flex: 1 }}>
              <label htmlFor="wiz-actual-branch">{isEn ? "Actual work branch" : "فرع العمل الفعلي"}</label>
              <select id="wiz-actual-branch" value={form.actual_branch_id ?? ""}
                onChange={(e) => setField("actual_branch_id", e.target.value ? +e.target.value : null)}>
                <option value="">{isEn ? "Same as official" : "نفس الرسمي"}</option>
                {branches.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
              </select>
            </div>
            <div className="field" style={{ flex: 1 }}>
              <label htmlFor="wiz-dept">{isEn ? "Department" : "القسم"}</label>
              <select id="wiz-dept" value={form.department_id ?? ""}
                onChange={(e) => setField("department_id", e.target.value ? +e.target.value : null)}>
                <option value="">—</option>
                {departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </div>
          </div>
          <div className="row">
            <div className="field" style={{ flex: 1 }}>
              <label htmlFor="wiz-att">{isEn ? "Attendance mode" : "نمط الحضور"} *</label>
              <select id="wiz-att" value={form.attendance_mode}
                onChange={(e) => setField("attendance_mode", e.target.value)}>
                <option value="qr">QR</option>
                <option value="gps">GPS</option>
                <option value="both">{isEn ? "QR + GPS" : "QR + GPS"}</option>
                <option value="none">{isEn ? "None (requires exemption)" : "بلا (يشترط إعفاء)"}</option>
              </select>
            </div>
            {form.attendance_mode === "none" && (
              <>
                <div className="field" style={{ flex: 0 }}>
                  <label>
                    <input type="checkbox" checked={form.attendance_exempt}
                      onChange={(e) => setField("attendance_exempt", e.target.checked)} />
                    {" "}{isEn ? "Exempt" : "معفى"}
                  </label>
                </div>
                <div className="field" style={{ flex: 2 }}>
                  <label htmlFor="wiz-exempt-reason">
                    {isEn ? "Exemption reason" : "سبب الإعفاء"} *
                  </label>
                  <input id="wiz-exempt-reason" value={form.attendance_exempt_reason}
                    onChange={(e) => setField("attendance_exempt_reason", e.target.value)}
                    placeholder={isEn ? "e.g. Field manager, no fixed shift" : "مثال: مدير ميداني بلا شفت ثابت"} />
                </div>
              </>
            )}
          </div>
          <div className="muted" style={{ fontSize: 12 }}>
            {isEn
              ? "SEC2-17: every active employee needs an explicit attendance policy or a documented exemption."
              : "SEC2-17: كل موظف Active يجب أن يكون له سياسة حضور صريحة أو إعفاء موثّق."}
          </div>
        </>
      )}

      {/* ============ STEP 3: Passport + OCR ============ */}
      {step === 3 && (
        <>
          <div className="row">
            <div className="field" style={{ flex: 1 }}>
              <label htmlFor="wiz-passport">{isEn ? "Passport number" : "رقم الجواز"}</label>
              <input id="wiz-passport" value={form.passport_number} dir="ltr"
                onChange={(e) => setField("passport_number", e.target.value)} />
            </div>
            <div className="field" style={{ flex: 1 }}>
              <label htmlFor="wiz-passport-exp">{isEn ? "Passport expiry" : "انتهاء الجواز"}</label>
              <input id="wiz-passport-exp" type="date" value={form.passport_expiry}
                onChange={(e) => setField("passport_expiry", e.target.value)} />
            </div>
          </div>

          <hr />
          <h4>{isEn ? "OCR (optional — scan passport/civil ID)" : "قراءة تلقائية OCR (اختياري — امسح الجواز/المدنية)"}</h4>
          <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
            {isEn
              ? "Upload image; system suggests values; you review then apply."
              : "ارفع الصورة؛ النظام يقترح القيم؛ راجعها ثم طبّقها."}
          </div>
          <div className="row">
            <div className="field" style={{ flex: 0, minWidth: 140 }}>
              <label htmlFor="wiz-ocr-type">{isEn ? "Document type" : "نوع المستند"}</label>
              <select id="wiz-ocr-type" value={ocrType} onChange={(e) => setOcrType(e.target.value)}>
                <option value="passport">{isEn ? "Passport (MRZ)" : "جواز سفر (MRZ)"}</option>
                <option value="civil_id">{isEn ? "Civil ID" : "بطاقة مدنية"}</option>
              </select>
            </div>
            <div className="field" style={{ flex: 1 }}>
              <label htmlFor="wiz-ocr-file">{isEn ? "Image / PDF" : "صورة أو PDF"}</label>
              <input id="wiz-ocr-file" type="file" accept="image/*,application/pdf,.txt"
                onChange={(e) => setOcrFile(e.target.files?.[0] || null)} />
            </div>
            <div className="field" style={{ flex: 0 }}>
              <label>&nbsp;</label>
              <button onClick={runOcr} disabled={busy || !ocrFile} aria-busy={busy}>
                {busy ? (isEn ? "Reading..." : "جارٍ...") : (isEn ? "Read" : "اقرأ")}
              </button>
            </div>
          </div>

          {ocrSuggested && (
            <div className="card" style={{ background: "#f7fafc", marginTop: 8 }}>
              <div style={{ fontWeight: 600, marginBottom: 6 }}>
                {isEn ? "OCR suggested values (review before applying):" : "قيم مُقترحة من OCR (راجع قبل التطبيق):"}
              </div>

              {/* لافتة تشخيص واضحة لما OCR يفشل — تُوضّح السبب الحقيقي */}
              {(ocrSuggested._confidence === 0 || ocrSuggested._note) && ocrSuggested._diag && (
                <div style={{
                  background: ocrSuggested._diag.available ? "#fef3c7" : "#fee2e2",
                  border: `1px solid ${ocrSuggested._diag.available ? "#fbbf24" : "#ef4444"}`,
                  padding: 10, borderRadius: 6, marginBottom: 8, fontSize: 13,
                }}>
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>
                    {ocrSuggested._diag.available
                      ? (isEn ? "OCR engine OK but no text extracted" : "محرّك OCR شغّال لكن لم يستخرج نصًا")
                      : (isEn ? "OCR engine unavailable" : "محرّك OCR غير متاح على الخادم")}
                  </div>
                  {ocrSuggested._note && <div style={{ marginBottom: 4 }}>{ocrSuggested._note}</div>}
                  <div style={{ fontFamily: "monospace", fontSize: 11, color: "#555" }}>
                    Tesseract: {ocrSuggested._diag.version || "—"}
                    {" · "}
                    {isEn ? "Languages" : "اللغات"}: {(ocrSuggested._diag.languages || []).join(", ") || "—"}
                    {ocrSuggested._diag.text_length_en !== undefined && (
                      <> · en={ocrSuggested._diag.text_length_en} chars · ar={ocrSuggested._diag.text_length_ar} chars</>
                    )}
                    {ocrSuggested._diag.error && <> · error: {ocrSuggested._diag.error}</>}
                  </div>
                </div>
              )}

              <pre style={{ direction: "ltr", fontSize: 12, background: "white",
                padding: 8, overflow: "auto" }}>
                {JSON.stringify(ocrSuggested, null, 2)}
              </pre>
              {ocrMsg && <div className="muted" style={{ fontSize: 12 }}>{ocrMsg}</div>}
              <button onClick={applyOcrToForm}>
                {isEn ? "Apply to form" : "طبّق على الفورم"}
              </button>
            </div>
          )}
        </>
      )}

      {/* ============ STEP 4: Save + permits + documents ============ */}
      {step === 4 && (
        <>
          {!savedEmp ? (
            <div>
              <p>{isEn
                ? "Ready to save the employee. Permits and documents can be added after."
                : "جاهز لحفظ الموظف. أذونات الإقامة والمستندات ستُضاف بعد الحفظ."}</p>
              <div className="field" style={{ marginTop: 12, marginBottom: 12 }}>
                <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                  <input type="checkbox" checked={createUserAccount}
                    onChange={(e) => setCreateUserAccount(e.target.checked)} />
                  <span>
                    <strong>{isEn ? "Auto-create login account for this employee" : "أنشئ حساب دخول للموظف تلقائيًا"}</strong>
                    <div className="muted" style={{ fontSize: 12 }}>
                      {isEn
                        ? "Username = civil ID, strong random password shown once for you to copy and send to the employee."
                        : "اسم المستخدم = الرقم المدني، وكلمة سر عشوائية قوية تظهر مرة واحدة لتنسخها وترسلها للموظف."}
                    </div>
                  </span>
                </label>
              </div>
              <button onClick={saveEmployee} disabled={busy} aria-busy={busy}>
                {busy
                  ? (isEn ? "Saving..." : "جارٍ الحفظ...")
                  : (isEn ? "Save employee" : "احفظ الموظف")}
              </button>
            </div>
          ) : (
            <>
              <div className="ok" role="status" style={{ marginBottom: 12 }}>
                {isEn
                  ? `✓ Employee saved. ID: ${savedEmp.employee_no}`
                  : `✓ تم حفظ الموظف. الرقم الوظيفي: ${savedEmp.employee_no}`}
              </div>

              {/* بيانات حساب الدخول — تظهر مرة واحدة فقط */}
              {userCredentials && (
                <div className="card" style={{
                  background: "#fff8e1",
                  border: "2px solid #f59e0b",
                  marginBottom: 12,
                }} role="region" aria-labelledby="creds-title">
                  <h4 id="creds-title" style={{ margin: "0 0 8px" }}>
                    🔐 {isEn ? "Login credentials (shown once)" : "بيانات الدخول (تظهر مرة واحدة فقط)"}
                  </h4>
                  <p className="muted" style={{ fontSize: 12, marginTop: 0 }}>
                    {isEn
                      ? "Copy these NOW and send them to the employee. The password won't appear again — HR would need to reset it if lost. The employee will be forced to change it on first login."
                      : "انسخها الآن وأرسلها للموظف. كلمة السر لن تظهر مرة أخرى — HR يحتاج لإعادة تعيينها لو ضاعت. الموظف سيُجبر على تغييرها في أول دخول."}
                  </p>

                  <div className="row" style={{ marginBottom: 8 }}>
                    <div className="field" style={{ flex: 2 }}>
                      <label>{isEn ? "Username (Civil ID)" : "اسم المستخدم (الرقم المدني)"}</label>
                      <div style={{ display: "flex", gap: 8 }}>
                        <input readOnly value={userCredentials.civil_id} dir="ltr"
                          style={{ flex: 1, fontFamily: "monospace", fontSize: 16, letterSpacing: 1 }}
                          onFocus={(e) => e.currentTarget.select()} />
                        <button onClick={() => copyToClipboard(userCredentials.civil_id,
                          isEn ? "Username" : "اسم المستخدم")}>
                          📋 {isEn ? "Copy" : "نسخ"}
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="row" style={{ marginBottom: 8 }}>
                    <div className="field" style={{ flex: 2 }}>
                      <label>{isEn ? "Password" : "كلمة السر"}</label>
                      <div style={{ display: "flex", gap: 8 }}>
                        <input readOnly value={userCredentials.password} dir="ltr"
                          style={{ flex: 1, fontFamily: "monospace", fontSize: 16, letterSpacing: 2 }}
                          onFocus={(e) => e.currentTarget.select()} />
                        <button onClick={() => copyToClipboard(userCredentials.password,
                          isEn ? "Password" : "كلمة السر")}>
                          📋 {isEn ? "Copy" : "نسخ"}
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="row">
                    <button onClick={() => copyToClipboard(
                      `${isEn ? "Username" : "اسم المستخدم"}: ${userCredentials.civil_id}\n` +
                      `${isEn ? "Password" : "كلمة السر"}: ${userCredentials.password}`,
                      isEn ? "Both" : "الاثنين")}>
                      📋 {isEn ? "Copy both" : "نسخ الاثنين معًا"}
                    </button>
                  </div>

                  {copyToast && (
                    <div className="ok" role="status" aria-live="polite"
                         style={{ marginTop: 8, padding: "4px 8px", fontSize: 12 }}>
                      {copyToast}
                    </div>
                  )}
                </div>
              )}

              {/* Permits */}
              <div className="card" style={{ background: "#fafafa" }}>
                <h4>{isEn ? "Residency & Work Permit" : "الإقامة وإذن العمل"}</h4>
                <div className="row">
                  <div className="field" style={{ flex: 1 }}>
                    <label htmlFor="wiz-permit-kind">{isEn ? "Type" : "النوع"}</label>
                    <select id="wiz-permit-kind" value={permitForm.kind}
                      onChange={(e) => setPermitForm({ ...permitForm, kind: e.target.value })}>
                      <option value="residency">{isEn ? "Residency" : "إقامة"}</option>
                      <option value="work_permit">{isEn ? "Work permit" : "إذن عمل"}</option>
                    </select>
                  </div>
                  <div className="field" style={{ flex: 1 }}>
                    <label htmlFor="wiz-permit-num">{isEn ? "Number" : "الرقم"}</label>
                    <input id="wiz-permit-num" dir="ltr" value={permitForm.number}
                      onChange={(e) => setPermitForm({ ...permitForm, number: e.target.value })} />
                  </div>
                  <div className="field" style={{ flex: 1 }}>
                    <label htmlFor="wiz-permit-start">{isEn ? "Issue date" : "تاريخ الإصدار"}</label>
                    <input id="wiz-permit-start" type="date" value={permitForm.start_date}
                      onChange={(e) => setPermitForm({ ...permitForm, start_date: e.target.value })} />
                  </div>
                  <div className="field" style={{ flex: 1 }}>
                    <label htmlFor="wiz-permit-exp">{isEn ? "Expiry" : "الانتهاء"} *</label>
                    <input id="wiz-permit-exp" type="date" value={permitForm.expiry_date}
                      onChange={(e) => setPermitForm({ ...permitForm, expiry_date: e.target.value })}
                      required />
                  </div>
                  <div className="field" style={{ flex: 0 }}>
                    <label>&nbsp;</label>
                    <button onClick={addPermit} disabled={busy || !permitForm.expiry_date}>
                      {isEn ? "+ Add" : "+ إضافة"}
                    </button>
                  </div>
                </div>
                {permits.length > 0 && (
                  <ul style={{ marginTop: 8 }}>
                    {permits.map((p, i) => (
                      <li key={i}>{p.kind} · {p.number || "—"} · {isEn ? "expires" : "ينتهي"} {p.expiry_date}</li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Document upload */}
              <div className="card" style={{ background: "#fafafa", marginTop: 12 }}>
                <h4>{isEn ? "Attach document images" : "إرفاق صور المستندات"}</h4>
                <div className="row">
                  <div className="field" style={{ flex: 1 }}>
                    <label htmlFor="wiz-doc-type">{isEn ? "Document type" : "نوع المستند"}</label>
                    <select id="wiz-doc-type" value={docType}
                      onChange={(e) => setDocType(e.target.value)}>
                      <option value="passport">{isEn ? "Passport" : "جواز السفر"}</option>
                      <option value="civil_id">{isEn ? "Civil ID" : "البطاقة المدنية"}</option>
                      <option value="residency">{isEn ? "Residency" : "الإقامة"}</option>
                      <option value="work_permit">{isEn ? "Work permit" : "إذن العمل"}</option>
                      <option value="contract">{isEn ? "Contract" : "عقد العمل"}</option>
                    </select>
                  </div>
                  <div className="field" style={{ flex: 1 }}>
                    <label htmlFor="wiz-doc-exp">{isEn ? "Expiry (if any)" : "الانتهاء (إن وجد)"}</label>
                    <input id="wiz-doc-exp" type="date" value={docExpiry}
                      onChange={(e) => setDocExpiry(e.target.value)} />
                  </div>
                  <div className="field" style={{ flex: 1 }}>
                    <label htmlFor="wiz-doc-file">{isEn ? "File" : "الملف"}</label>
                    <input id="wiz-doc-file" type="file" accept="image/*,application/pdf"
                      onChange={(e) => setDocFile(e.target.files?.[0] || null)} />
                  </div>
                  <div className="field" style={{ flex: 0 }}>
                    <label>&nbsp;</label>
                    <button onClick={uploadDoc} disabled={busy || !docFile}>
                      {isEn ? "Upload" : "رفع"}
                    </button>
                  </div>
                </div>
                {uploadedDocs.length > 0 && (
                  <ul style={{ marginTop: 8 }}>
                    {uploadedDocs.map((d, i) => <li key={i}>✓ {d}</li>)}
                  </ul>
                )}
              </div>
            </>
          )}
        </>
      )}

      {/* ============ Navigation buttons ============ */}
      <div className="row" style={{ marginTop: 16, justifyContent: "space-between" }}>
        <div>
          {step > 1 && !savedEmp && (
            <button className="ghost" onClick={() => { setErr(""); setStep(step - 1); }}>
              {isEn ? "← Previous" : "→ السابق"}
            </button>
          )}
        </div>
        <div className="row" style={{ gap: 8 }}>
          {!savedEmp && step < 4 && (
            <button onClick={nextStep}>
              {isEn ? "Next →" : "التالي ←"}
            </button>
          )}
          {savedEmp && (
            <button onClick={() => onDone(savedEmp)} className="primary">
              {isEn ? "Done — view employee" : "تم — افتح الملف"}
            </button>
          )}
          <button className="ghost" onClick={onCancel}>
            {isEn ? "Cancel" : "إلغاء"}
          </button>
        </div>
      </div>
    </div>
  );
}
