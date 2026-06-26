import { useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import QRCode from "qrcode";

// صفحة عرض QR للفرع (Kiosk) — مستقلة بلا تسجيل دخول، مُصرّحة بمفتاح الفرع فقط.
// تجلب الرمز من الخادم وتعيد رسمه تلقائيًا قبل انتهاء صلاحيته. الخادم مصدر الحقيقة.
export default function Kiosk() {
  const { branchId } = useParams();
  const [params] = useSearchParams();
  const key = params.get("key") || "";
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [branchName, setBranchName] = useState("");
  const [countdown, setCountdown] = useState(0);
  const [error, setError] = useState("");
  const [clock, setClock] = useState(new Date());
  const fetching = useRef(false);

  const fetchToken = async () => {
    if (fetching.current) return;
    fetching.current = true;
    try {
      const res = await fetch(`/api/kiosk/${branchId}/qr?key=${encodeURIComponent(key)}`);
      if (!res.ok) throw new Error(String(res.status));
      const data = await res.json();
      setBranchName(data.branch_name);
      setCountdown(data.refresh_in_seconds);
      setError("");
      if (canvasRef.current)
        await QRCode.toCanvas(canvasRef.current, data.token, { width: 320, margin: 1 });
    } catch (e: any) {
      setError(e.message === "403" ? "مفتاح الشاشة غير صالح" : "إعادة الاتصال…");
    } finally {
      fetching.current = false;
    }
  };

  useEffect(() => { fetchToken(); /* أول جلب */ }, [branchId, key]);

  useEffect(() => {
    const t = setInterval(() => {
      setClock(new Date());
      setCountdown((c) => {
        if (c <= 10) { fetchToken(); return c <= 1 ? 0 : c - 1; }
        return c - 1;
      });
    }, 1000);
    return () => clearInterval(t);
  }, []);

  // إعادة محاولة دورية عند الانقطاع
  useEffect(() => {
    if (!error || error.includes("غير صالح")) return;
    const r = setInterval(fetchToken, 4000);
    return () => clearInterval(r);
  }, [error]);

  return (
    <div style={{
      minHeight: "100vh", display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center", gap: 18,
      background: "#0b3b38", color: "#fff", direction: "rtl",
    }}>
      <h1 style={{ fontSize: 40, margin: 0 }}>{branchName || "شاشة الحضور"}</h1>
      <p style={{ opacity: 0.8, margin: 0 }}>امسح الرمز من تطبيق الموظف لتسجيل الحضور</p>
      <div style={{ background: "#fff", padding: 20, borderRadius: 20 }}>
        {error && !error.includes("غير صالح")
          ? <div style={{ width: 320, height: 320, display: "grid", placeItems: "center", color: "#0b3b38" }}>{error}</div>
          : <canvas ref={canvasRef} />}
      </div>
      {error.includes("غير صالح")
        ? <div style={{ color: "#fecaca", fontSize: 22 }}>⚠ {error}</div>
        : <div style={{ fontSize: 26 }}>يتجدّد خلال <b>{countdown}</b> ثانية</div>}
      <div style={{ position: "fixed", bottom: 20, opacity: 0.7, fontSize: 18 }}>
        {clock.toLocaleString("ar")}
      </div>
    </div>
  );
}
