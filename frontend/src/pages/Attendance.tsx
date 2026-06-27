import { useEffect, useRef, useState } from "react";
import jsQR from "jsqr";
import api from "../api";
import { attAr } from "../labels";
import { useI18n } from "../i18n";

// تدفّق من خطوتين: (1) مسح الـ QR بالكاميرا الخلفية → تحقّق ← تذكرة،
// (2) فتح كاميرا السيلفي الأمامية ← التقاط ← تسجيل حضور/انصراف.
export default function Attendance() {
  const { t, lang } = useI18n();
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const scanningRef = useRef(false);
  const coords = useRef<{ lat?: number; lng?: number }>({});

  const [step, setStep] = useState<1 | 2>(1);
  const [scanningUI, setScanningUI] = useState(false);
  const [branchName, setBranchName] = useState("");
  const [ticket, setTicket] = useState("");
  const [selfie, setSelfie] = useState<Blob | null>(null);
  const [selfiePreview, setSelfiePreview] = useState("");
  const [records, setRecords] = useState<any[]>([]);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const loadRecords = () => api.get("/attendance/my").then((r) => setRecords(r.data)).catch(() => {});

  useEffect(() => {
    loadRecords();
    navigator.geolocation?.getCurrentPosition(
      (p) => (coords.current = { lat: p.coords.latitude, lng: p.coords.longitude }),
      () => {}
    );
    return () => stopCamera();
  }, []);

  const stopCamera = () => {
    scanningRef.current = false;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  };

  // ---------- الخطوة 1: مسح الـ QR ----------
  const startScan = async () => {
    setErr(""); setMsg("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      streamRef.current = stream;
      if (videoRef.current) { videoRef.current.srcObject = stream; await videoRef.current.play(); }
      scanningRef.current = true;
      setScanningUI(true);
      scanLoop();
    } catch { setErr(t("att_cam_err")); }
  };

  const scanLoop = () => {
    if (!scanningRef.current) return;
    const v = videoRef.current, c = canvasRef.current;
    if (v && c && v.videoWidth) {
      c.width = v.videoWidth; c.height = v.videoHeight;
      const ctx = c.getContext("2d")!;
      ctx.drawImage(v, 0, 0, c.width, c.height);
      const img = ctx.getImageData(0, 0, c.width, c.height);
      const found = jsQR(img.data, img.width, img.height);
      if (found?.data) { validateQr(found.data); return; }
    }
    requestAnimationFrame(scanLoop);
  };

  const validateQr = async (qrToken: string) => {
    scanningRef.current = false;
    setScanningUI(false);
    try {
      const r = await api.post("/attendance/validate-qr", {
        qr_token: qrToken, lat: coords.current.lat, lng: coords.current.lng,
      });
      stopCamera();
      setBranchName(r.data.branch.name);
      setTicket(r.data.checkin_ticket);
      setStep(2);
      setMsg(t("att_verified_msg", { branch: r.data.branch.name }));
      startSelfieCam();
    } catch (e: any) {
      setErr(e.response?.data?.detail || t("att_invalid_qr"));
      // استئناف المسح
      scanningRef.current = true; setScanningUI(true); scanLoop();
    }
  };

  // ---------- الخطوة 2: السيلفي ----------
  const startSelfieCam = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
      streamRef.current = stream;
      if (videoRef.current) { videoRef.current.srcObject = stream; await videoRef.current.play(); }
    } catch { setErr(t("att_selfie_cam_err")); }
  };

  const capture = () => {
    const v = videoRef.current, c = canvasRef.current;
    if (!v || !c || !v.videoWidth) return;
    c.width = v.videoWidth; c.height = v.videoHeight;
    c.getContext("2d")!.drawImage(v, 0, 0, c.width, c.height);
    setSelfiePreview(c.toDataURL("image/jpeg", 0.7));
    c.toBlob((b) => b && setSelfie(b), "image/jpeg", 0.7);
  };

  const submit = async (action: "in" | "out") => {
    setErr(""); setMsg("");
    if (!selfie) return setErr(t("att_need_selfie"));
    const fd = new FormData();
    fd.append("checkin_ticket", ticket);
    fd.append("action", action);
    fd.append("selfie", selfie, "selfie.jpg");
    try {
      const r = await api.post("/attendance/check-in", fd);
      setMsg(action === "in"
        ? t("att_checkin_done", { status: attAr(r.data.status) })
        : t("att_checkout_done", { minutes: r.data.worked_minutes }));
      reset(); loadRecords();
    } catch (e: any) { setErr(e.response?.data?.detail || t("error")); }
  };

  const reset = () => {
    stopCamera();
    setStep(1); setTicket(""); setBranchName(""); setSelfie(null); setSelfiePreview("");
  };

  return (
    <div>
      <h2>{t("att_self_title")}</h2>

      <div className="card">
        <div className="row" style={{ gap: 6, marginBottom: 10 }}>
          <span className={`pill ${step === 1 ? "info" : "success"}`}>1 · {t("att_step_scan")}</span>
          <span>{lang === "ar" ? "←" : "→"}</span>
          <span className={`pill ${step === 2 ? "info" : "pending"}`}>2 · {t("att_step_selfie")}</span>
        </div>

        {step === 1 && (
          <div>
            <p className="muted">{t("att_scan_hint")}</p>
            <video ref={videoRef} playsInline muted style={{ display: scanningUI ? "block" : "none" }} />
            {!scanningUI && <button onClick={startScan}>{t("att_scan_btn")}</button>}
            {scanningUI && <p className="muted">{t("att_searching")}</p>}
          </div>
        )}

        {step === 2 && (
          <div>
            <p className="ok">✓ {t("att_branch_confirmed")}: <b>{branchName}</b></p>
            {!selfiePreview
              ? <video ref={videoRef} playsInline muted />
              : <img src={selfiePreview} className="cam" alt="selfie" style={{ maxWidth: 320, borderRadius: 12 }} />}
            <div className="row" style={{ marginTop: 10 }}>
              {!selfiePreview && <button onClick={capture}>{t("att_capture")}</button>}
              {selfiePreview && (
                <>
                  <button onClick={() => submit("in")}>{t("att_checkin")}</button>
                  <button className="warn" onClick={() => submit("out")}>{t("att_checkout")}</button>
                  <button className="ghost" onClick={() => { setSelfie(null); setSelfiePreview(""); startSelfieCam(); }}>{t("att_recapture")}</button>
                </>
              )}
              <button className="ghost" onClick={reset}>{t("cancel")}</button>
            </div>
          </div>
        )}

        <canvas ref={canvasRef} style={{ display: "none" }} />
        {err && <div className="err">{err}</div>}
        {msg && <div className="ok">{msg}</div>}
      </div>

      <div className="card">
        <h3>{t("att_my_log")}</h3>
        <table><thead><tr><th>{t("col_in")}</th><th>{t("col_out")}</th><th>{t("status")}</th><th>{t("col_worked")}</th><th>{t("col_overtime")}</th></tr></thead>
          <tbody>{records.map((r) => (
            <tr key={r.id}><td>{r.check_in_at && new Date(r.check_in_at).toLocaleString(lang)}</td>
              <td>{r.check_out_at ? new Date(r.check_out_at).toLocaleString(lang) : "—"}</td>
              <td><span className={`pill ${r.status === "late" ? "warning" : "success"}`}>{attAr(r.status)}</span></td>
              <td>{r.worked_minutes}</td><td>{r.overtime_minutes}</td></tr>
          ))}{!records.length && <tr><td colSpan={5} className="muted">{t("att_no_records")}</td></tr>}</tbody></table>
      </div>
    </div>
  );
}
