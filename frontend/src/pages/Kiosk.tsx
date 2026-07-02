import { useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import QRCode from "qrcode";

// صفحة عرض QR للفرع (Kiosk) — مستقلة بلا تسجيل دخول، مُصرّحة بمفتاح الفرع فقط.
// الرمز ثابت لكل فرع (لا يتغيّر) — يُجلب مرة واحدة ويُعاد المحاولة فقط عند الانقطاع.
export default function Kiosk() {
  const { branchId } = useParams();
  const [params] = useSearchParams();
  const key = params.get("key") || "";
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [branchName, setBranchName] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  const fetching = useRef(false);

  const fetchToken = async () => {
    if (fetching.current) return;
    fetching.current = true;
    try {
      const res = await fetch(`/api/kiosk/${branchId}/qr?key=${encodeURIComponent(key)}`);
      if (!res.ok) throw new Error(String(res.status));
      const data = await res.json();
      setBranchName(data.branch_name);
      setError("");
      if (canvasRef.current)
        await QRCode.toCanvas(canvasRef.current, data.token, { width: 320, margin: 1 });
      setLoaded(true);
    } catch (e: any) {
      setError(e.message === "403" ? "مفتاح الشاشة غير صالح" : "إعادة الاتصال…");
    } finally {
      fetching.current = false;
    }
  };

  // جلب واحد فقط — الرمز ثابت
  useEffect(() => { fetchToken(); }, [branchId, key]);

  // إعادة محاولة فقط لو لسه ما اتحمّلش وفيه انقطاع
  useEffect(() => {
    if (loaded || !error || error.includes("غير صالح")) return;
    const r = setInterval(fetchToken, 4000);
    return () => clearInterval(r);
  }, [error, loaded]);

  return (
    <div style={{
      minHeight: "100vh", display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center", gap: 18,
      background: "#0b3b38", color: "#fff", direction: "rtl",
    }}>
      <h1 style={{ fontSize: 40, margin: 0 }}>{branchName || "شاشة الحضور"}</h1>
      <p style={{ opacity: 0.8, margin: 0 }}>امسح الرمز من تطبيق الموظف لتسجيل الحضور</p>
      <div style={{ background: "#fff", padding: 20, borderRadius: 20 }}>
        {error && !error.includes("غير صالح") && !loaded
          ? <div style={{ width: 320, height: 320, display: "grid", placeItems: "center", color: "#0b3b38" }}>{error}</div>
          : <canvas ref={canvasRef} />}
      </div>
      {error.includes("غير صالح")
        ? <div style={{ color: "#fecaca", fontSize: 22 }}>⚠ {error}</div>
        : <div style={{ fontSize: 22, opacity: 0.85 }}>رمز الفرع الثابت — علّقه في مكان الحضور</div>}
    </div>
  );
}
