import { useEffect, useState } from "react";
import api, { errMsg } from "../api";

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
};

type Enrollment = {
  secret: string;
  uri: string;
  qr_png_base64: string;
  issuer: string;
};

export default function TwoFactor() {
  const [status, setStatus] = useState<Status | null>(null);
  const [enrollment, setEnrollment] = useState<Enrollment | null>(null);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const loadStatus = () => api.get("/2fa/status").then((r) => setStatus(r.data))
    .catch((e) => setErr(errMsg(e, "فشل تحميل حالة 2FA")));

  useEffect(() => { loadStatus(); }, []);

  const startEnroll = async () => {
    setErr(""); setMsg(""); setBusy(true);
    try {
      const r = await api.post("/2fa/enroll");
      setEnrollment(r.data);
    } catch (e: any) { setErr(errMsg(e, "فشل بدء التسجيل")); }
    finally { setBusy(false); }
  };

  const confirm = async () => {
    if (!/^\d{6}$/.test(code)) { setErr("الرمز 6 أرقام"); return; }
    setErr(""); setBusy(true);
    try {
      await api.post("/2fa/confirm", { code });
      setMsg("تم تفعيل 2FA بنجاح");
      setEnrollment(null);
      setCode("");
      await loadStatus();
    } catch (e: any) { setErr(errMsg(e, "الرمز غير صحيح")); }
    finally { setBusy(false); }
  };

  const disable = async () => {
    if (!password) { setErr("أدخل كلمة السر الحالية"); return; }
    if (!window.confirm("هل أنت متأكد من تعطيل 2FA؟ سيقلّل ذلك من حماية حسابك.")) return;
    setErr(""); setBusy(true);
    try {
      await api.post("/2fa/disable", { password });
      setMsg("تم تعطيل 2FA");
      setPassword("");
      await loadStatus();
    } catch (e: any) { setErr(errMsg(e, "فشل التعطيل")); }
    finally { setBusy(false); }
  };

  if (!status) return <div className="loading">جارٍ التحميل...</div>;

  return (
    <div aria-labelledby="tfa-title">
      <div className="page-head">
        <div>
          <div className="eyebrow">الأمان</div>
          <h2 id="tfa-title">التحقق الثنائي (2FA)</h2>
          <div className="sub">
            {status.enabled
              ? "التحقق الثنائي مفعّل لحسابك — احتفظ بتطبيق Authenticator آمنًا"
              : status.sensitive_role
              ? "دورك حساس (مثل HR أو المحاسب) — يوصى بشدة بتفعيل 2FA"
              : "تفعيل 2FA اختياري لحسابك، لكنه يزيد أمانك بشكل كبير"}
          </div>
        </div>
      </div>

      {msg && <div className="ok" role="status" aria-live="polite">{msg}</div>}
      {err && <div className="err" role="alert" aria-live="assertive">{err}</div>}

      {/* حالة مفعّل: عرض معلومات + خيار التعطيل */}
      {status.enabled && (
        <div className="card">
          <h3>حالة الحساب</h3>
          <div className="kv"><span>الحالة:</span><strong style={{ color: "green" }}>مفعّل ✓</strong></div>
          {status.last_used_at && (
            <div className="kv"><span>آخر استخدام:</span>
              <span>{new Date(status.last_used_at).toLocaleString("ar-KW")}</span></div>
          )}
          <hr />
          <h4>تعطيل 2FA</h4>
          <div className="field">
            <label htmlFor="tfa-pw">كلمة السر الحالية</label>
            <input id="tfa-pw" type="password" value={password} dir="ltr"
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password" />
          </div>
          <button onClick={disable} disabled={busy || !password}
            className="danger" aria-busy={busy}>
            {busy ? "جارٍ التعطيل..." : "تعطيل 2FA"}
          </button>
        </div>
      )}

      {/* حالة غير مفعّل: خطوة enroll */}
      {!status.enabled && !enrollment && (
        <div className="card">
          <h3>الخطوة 1: بدء الإعداد</h3>
          <p>
            سنعرض لك رمز QR — امسحه بتطبيق Authenticator (Google Authenticator أو Authy أو Microsoft Authenticator).
          </p>
          <button onClick={startEnroll} disabled={busy} aria-busy={busy}>
            {busy ? "جارٍ..." : "بدء الإعداد"}
          </button>
        </div>
      )}

      {/* حالة enroll جارٍ: عرض QR + input للتأكيد */}
      {!status.enabled && enrollment && (
        <div className="card">
          <h3>الخطوة 2: امسح رمز QR</h3>
          <div style={{ textAlign: "center", padding: 16 }}>
            <img
              src={`data:image/png;base64,${enrollment.qr_png_base64}`}
              alt="رمز QR للتحقق الثنائي"
              style={{ maxWidth: 250, height: "auto", border: "1px solid #ccc" }}
            />
          </div>
          <p className="muted" style={{ fontSize: 12 }}>
            أو أدخل السرّي يدوياً في التطبيق:
          </p>
          <code style={{ display: "block", padding: 8, background: "#f0f0f0",
                        textAlign: "center", direction: "ltr", fontSize: 14,
                        letterSpacing: 2, wordBreak: "break-all" }}>
            {enrollment.secret}
          </code>

          <hr />
          <h3>الخطوة 3: أدخل الرمز للتأكيد</h3>
          <div className="field">
            <label htmlFor="tfa-code">الرمز الظاهر في التطبيق (6 خانات)</label>
            <input id="tfa-code" value={code} dir="ltr"
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              inputMode="numeric" pattern="[0-9]{6}" maxLength={6}
              placeholder="123456" autoComplete="one-time-code"
              style={{ textAlign: "center", letterSpacing: 6, fontSize: 20 }} />
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={confirm} disabled={busy || code.length !== 6} aria-busy={busy}>
              {busy ? "جارٍ التأكيد..." : "تأكيد وتفعيل"}
            </button>
            <button onClick={() => { setEnrollment(null); setCode(""); }} className="secondary">
              إلغاء
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
