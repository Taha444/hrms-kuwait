import { useEffect, useState } from "react";
import api, { errMsg } from "../api";
import { useI18n } from "../i18n";
import { fmtKuwaitDateTime } from "../utils/datetime";

// V2.2 §9 — نصوص ثنائية اللغة (dictionary صغير محلي للـpage)
const L = {
  ar: {
    security: "الأمان",
    two_factor: "التحقق الثنائي (2FA)",
    enabled_desc: "التحقق الثنائي مفعّل لحسابك — احتفظ بتطبيق Authenticator آمنًا",
    sensitive_desc: "دورك حساس (مثل HR أو المحاسب) — يوصى بشدة بتفعيل 2FA",
    optional_desc: "تفعيل 2FA اختياري لحسابك، لكنه يزيد أمانك بشكل كبير",
    account_status: "حالة الحساب",
    status: "الحالة:",
    enabled_ok: "مفعّل ✓",
    last_used: "آخر استخدام:",
    disable_2fa: "تعطيل 2FA",
    current_password: "كلمة السر الحالية",
    disabling: "جارٍ التعطيل...",
    step1_start: "الخطوة 1: بدء الإعداد",
    step1_desc: "سنعرض لك رمز QR — امسحه بتطبيق Authenticator (Google Authenticator أو Authy أو Microsoft Authenticator).",
    start_setup: "بدء الإعداد",
    processing: "جارٍ...",
    step2_scan: "الخطوة 2: امسح رمز QR",
    qr_alt: "رمز QR للتحقق الثنائي",
    manual_hint: "أو أدخل السرّي يدوياً في التطبيق:",
    step3_confirm: "الخطوة 3: أدخل الرمز للتأكيد",
    code_label: "الرمز الظاهر في التطبيق (6 خانات)",
    confirming: "جارٍ التأكيد...",
    confirm_enable: "تأكيد وتفعيل",
    cancel: "إلغاء",
    loading: "جارٍ التحميل...",
    err_load_status: "فشل تحميل حالة 2FA",
    err_start: "فشل بدء التسجيل",
    err_code_6_digits: "الرمز 6 أرقام",
    enabled_success: "تم تفعيل 2FA بنجاح",
    err_code_invalid: "الرمز غير صحيح",
    err_need_password: "أدخل كلمة السر الحالية",
    confirm_disable: "هل أنت متأكد من تعطيل 2FA؟ سيقلّل ذلك من حماية حسابك.",
    disabled: "تم تعطيل 2FA",
    err_disable: "فشل التعطيل",
    rec_title: "رموز الاسترداد",
    rec_hint: "احفظها في مكان آمن الآن — لن تُعرض مرة أخرى. كل رمز يُستخدم مرة واحدة، ويُغنيك عن التطبيق إن فقدت هاتفك.",
    rec_copy: "نسخ الرموز",
    rec_copied: "تم النسخ",
    rec_done: "حفظتها",
    rec_remaining: "المتبقّي من رموز الاسترداد",
    rec_regen: "توليد رموز جديدة",
    rec_regen_confirm: "سيتم إبطال كل الرموز القديمة. هل تتابع؟",
  },
  en: {
    security: "Security",
    two_factor: "Two-Factor Authentication (2FA)",
    enabled_desc: "2FA is enabled on your account — keep your Authenticator app safe",
    sensitive_desc: "Your role is sensitive (HR/Accountant) — 2FA is strongly recommended",
    optional_desc: "2FA is optional but greatly improves your account security",
    account_status: "Account status",
    status: "Status:",
    enabled_ok: "Enabled ✓",
    last_used: "Last used:",
    disable_2fa: "Disable 2FA",
    current_password: "Current password",
    disabling: "Disabling...",
    step1_start: "Step 1: Start setup",
    step1_desc: "We will show a QR code — scan it with an Authenticator app (Google Authenticator, Authy or Microsoft Authenticator).",
    start_setup: "Start setup",
    processing: "Processing...",
    step2_scan: "Step 2: Scan the QR code",
    qr_alt: "2FA QR code",
    manual_hint: "Or enter the secret manually in the app:",
    step3_confirm: "Step 3: Enter code to confirm",
    code_label: "Code from the app (6 digits)",
    confirming: "Confirming...",
    confirm_enable: "Confirm & enable",
    cancel: "Cancel",
    loading: "Loading...",
    err_load_status: "Failed to load 2FA status",
    err_start: "Failed to start enrollment",
    err_code_6_digits: "Code must be 6 digits",
    enabled_success: "2FA enabled successfully",
    err_code_invalid: "Invalid code",
    err_need_password: "Enter your current password",
    confirm_disable: "Are you sure you want to disable 2FA? This will reduce your account protection.",
    disabled: "2FA disabled",
    err_disable: "Failed to disable",
    rec_title: "Recovery codes",
    rec_hint: "Save these now — they will not be shown again. Each code works once and replaces the app if you lose your phone.",
    rec_copy: "Copy codes",
    rec_copied: "Copied",
    rec_done: "I saved them",
    rec_remaining: "Recovery codes remaining",
    rec_regen: "Generate new codes",
    rec_regen_confirm: "All old codes will be invalidated. Continue?",
  },
};

/**
 * V2.2 §9 — إعداد التحقق الثنائي (TOTP RFC 6238)
 *  1. Enroll → يعرض QR + السرّي للإدخال اليدوي في تطبيق Authenticator
 *  2. Confirm → المستخدم يدخل رمز 6 خانات لتأكيد التسجيل
 *  3. Disable → يحتاج كلمة السر الحالية للتأكيد
 */
type Status = {
  enabled: boolean;
  sensitive_role: boolean;
  last_used_at: string | null;
  role?: string;
  role_label_ar?: string;
  recovery_codes_remaining?: number;
};

type Enrollment = {
  secret: string;
  uri: string;
  qr_png_base64: string;
  issuer: string;
};

export default function TwoFactor() {
  const { lang } = useI18n();
  const t = L[lang === "en" ? "en" : "ar"];
  const [status, setStatus] = useState<Status | null>(null);
  const [enrollment, setEnrollment] = useState<Enrollment | null>(null);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  // QA-30 — تُعرض مرة واحدة فقط بعد التفعيل؛ لا تُخزَّن ولا تُطلَب من الخادم ثانيًة
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);

  const loadStatus = () => api.get("/2fa/status").then((r) => setStatus(r.data))
    .catch((e) => setErr(errMsg(e, t.err_load_status)));

  useEffect(() => { loadStatus(); }, []);

  const startEnroll = async () => {
    setErr(""); setMsg(""); setBusy(true);
    try {
      const r = await api.post("/2fa/enroll");
      setEnrollment(r.data);
    } catch (e: any) { setErr(errMsg(e, t.err_start)); }
    finally { setBusy(false); }
  };

  const confirm = async () => {
    if (!/^\d{6}$/.test(code)) { setErr(t.err_code_6_digits); return; }
    setErr(""); setBusy(true);
    try {
      const r = await api.post("/2fa/confirm", { code });
      setRecoveryCodes(r.data?.recovery_codes || null);
      setMsg(t.enabled_success);
      setEnrollment(null);
      setCode("");
      await loadStatus();
    } catch (e: any) { setErr(errMsg(e, t.err_code_invalid)); }
    finally { setBusy(false); }
  };

  const regenerate = async () => {
    if (!password) { setErr(t.err_need_password); return; }
    if (!window.confirm(t.rec_regen_confirm)) return;
    setErr(""); setBusy(true);
    try {
      const r = await api.post("/2fa/recovery/regenerate", { password });
      setRecoveryCodes(r.data?.recovery_codes || null);
      setPassword("");
      await loadStatus();
    } catch (e: any) { setErr(errMsg(e, t.err_disable)); }
    finally { setBusy(false); }
  };

  const disable = async () => {
    if (!password) { setErr(t.err_need_password); return; }
    if (!window.confirm(t.confirm_disable)) return;
    setErr(""); setBusy(true);
    try {
      await api.post("/2fa/disable", { password });
      setMsg(t.disabled);
      setPassword("");
      await loadStatus();
    } catch (e: any) { setErr(errMsg(e, t.err_disable)); }
    finally { setBusy(false); }
  };

  if (!status) return <div className="loading">{t.loading}</div>;

  return (
    <div aria-labelledby="tfa-title">
      <div className="page-head">
        <div>
          <div className="eyebrow">{t.security}</div>
          <h2 id="tfa-title">{t.two_factor}</h2>
          <div className="sub">
            {status.enabled ? t.enabled_desc
              : status.sensitive_role
                ? (lang === "en"
                    ? `Your role (${status.role || ""}) handles sensitive data — 2FA is strongly recommended.`
                    : `دورك (${status.role_label_ar || status.role || ""}) يتعامل مع بيانات حساسة — يوصى بشدة بتفعيل 2FA.`)
                : (lang === "en"
                    ? `2FA is optional for your role (${status.role || ""}) but greatly improves security.`
                    : `تفعيل 2FA اختياري لدورك (${status.role_label_ar || status.role || ""})، لكنه يزيد أمانك بشكل كبير.`)
            }
          </div>
        </div>
      </div>

      {msg && <div className="ok" role="status" aria-live="polite">{msg}</div>}
      {err && <div className="err" role="alert" aria-live="assertive">{err}</div>}

      {/* QA-30 — رموز الاسترداد: تُعرض مرة واحدة فور توليدها ثم لا سبيل إليها.
          بدونها كان فقدان الهاتف قفًلا تاًما لا مخرج منه إلا تعديل يدوي في
          قاعدة البيانات. */}
      {recoveryCodes && (
        <div className="card" style={{ borderTop: "3px solid var(--warning)" }}>
          <h3 style={{ marginTop: 0 }}>{t.rec_title}</h3>
          <p className="muted" style={{ marginTop: 0 }}>{t.rec_hint}</p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
                        gap: 8, direction: "ltr", fontFamily: "monospace", fontSize: 15 }}>
            {recoveryCodes.map((c) => (
              <div key={c} style={{ padding: "6px 10px", background: "var(--surface-2, #f4f6f8)",
                                    borderRadius: 6, textAlign: "center" }}>{c}</div>
            ))}
          </div>
          <div className="row" style={{ marginTop: 12 }}>
            <button className="ghost" onClick={() => {
              navigator.clipboard?.writeText(recoveryCodes.join("\n"));
              setMsg(t.rec_copied);
            }}>{t.rec_copy}</button>
            <button onClick={() => setRecoveryCodes(null)}>{t.rec_done}</button>
          </div>
        </div>
      )}

      {status?.enabled && !recoveryCodes && (
        <div className="card">
          <div className="row" style={{ justifyContent: "space-between", alignItems: "center", flexWrap: "wrap" }}>
            <div>
              <b>{t.rec_title}</b>
              <div className="muted" style={{ fontSize: 13 }}>
                {t.rec_remaining}: {status.recovery_codes_remaining ?? 0}
              </div>
            </div>
            <button className="ghost" disabled={busy} onClick={regenerate}>{t.rec_regen}</button>
          </div>
        </div>
      )}

      {status.enabled && (
        <div className="card">
          <h3>{t.account_status}</h3>
          <div className="kv"><span>{t.status}</span><strong style={{ color: "green" }}>{t.enabled_ok}</strong></div>
          {status.last_used_at && (
            <div className="kv"><span>{t.last_used}</span>
              <span>{fmtKuwaitDateTime(status.last_used_at, lang)}</span></div>
          )}
          <hr />
          <h4>{t.disable_2fa}</h4>
          <div className="field">
            <label htmlFor="tfa-pw">{t.current_password}</label>
            <input id="tfa-pw" type="password" value={password} dir="ltr"
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password" />
          </div>
          <button onClick={disable} disabled={busy || !password}
            className="danger" aria-busy={busy}>
            {busy ? t.disabling : t.disable_2fa}
          </button>
        </div>
      )}

      {!status.enabled && !enrollment && (
        <div className="card">
          <h3>{t.step1_start}</h3>
          <p>{t.step1_desc}</p>
          <button onClick={startEnroll} disabled={busy} aria-busy={busy}>
            {busy ? t.processing : t.start_setup}
          </button>
        </div>
      )}

      {!status.enabled && enrollment && (
        <div className="card">
          <h3>{t.step2_scan}</h3>
          <div style={{ textAlign: "center", padding: 16 }}>
            <img
              src={`data:image/png;base64,${enrollment.qr_png_base64}`}
              alt={t.qr_alt}
              style={{ maxWidth: 250, height: "auto", border: "1px solid #ccc" }}
            />
          </div>
          <p className="muted" style={{ fontSize: 12 }}>{t.manual_hint}</p>
          <code style={{ display: "block", padding: 8, background: "#f0f0f0",
                        textAlign: "center", direction: "ltr", fontSize: 14,
                        letterSpacing: 2, wordBreak: "break-all" }}>
            {enrollment.secret}
          </code>

          <hr />
          <h3>{t.step3_confirm}</h3>
          <div className="field">
            <label htmlFor="tfa-code">{t.code_label}</label>
            <input id="tfa-code" value={code} dir="ltr"
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              inputMode="numeric" pattern="[0-9]{6}" maxLength={6}
              placeholder="123456" autoComplete="one-time-code"
              style={{ textAlign: "center", letterSpacing: 6, fontSize: 20 }} />
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={confirm} disabled={busy || code.length !== 6} aria-busy={busy}>
              {busy ? t.confirming : t.confirm_enable}
            </button>
            <button onClick={() => { setEnrollment(null); setCode(""); }} className="secondary">
              {t.cancel}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
