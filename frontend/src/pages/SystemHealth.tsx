import { useEffect, useState } from "react";
import api, { errMsg } from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import Icon from "../Icon";

/**
 * DEMO-3: صفحة "حالة النظام" — لوحة واحدة تعرض كل ما يهم فتحه قبل عرض توضيحي:
 *   ✅ DB متصل  ✅ Tesseract eng+ara  ✅ 13 موظف  ✅ Alembic head  ...
 *
 * DEMO-1: زر "إعادة تعيين بيانات الديمو" (لـsuper_admin + بيئة مسموحة فقط)
 */
type HealthCheck = {
  status: "ok" | "fail" | "disabled";
  [k: string]: any;
};
type Health = {
  status: "ok" | "degraded";
  service: string;
  checks: Record<string, HealthCheck>;
};

export default function SystemHealth() {
  const { t, lang } = useI18n();
  const isEn = lang === "en";
  const { user } = useAuth();
  const isSuper = user?.role === "super_admin";

  const [health, setHealth] = useState<Health | null>(null);
  const [manifest, setManifest] = useState<any>(null);
  const [resetInfo, setResetInfo] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [resetting, setResetting] = useState(false);
  const [msg, setMsg] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const [h, m] = await Promise.all([
        api.get("/health/deep").then(r => r.data).catch(e => e.response?.data),
        api.get("/manifest").then(r => r.data).catch(() => null),
      ]);
      setHealth(h);
      setManifest(m);
      if (isSuper) {
        api.get("/admin/reset-status").then(r => setResetInfo(r.data)).catch(() => {});
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const doReset = async () => {
    const ok = window.confirm(isEn
      ? "This will WIPE all data and re-seed the demo. Continue?"
      : "سيتم مسح كل البيانات وإعادة تعبئة بيانات الديمو. متابعة؟");
    if (!ok) return;
    setResetting(true);
    setMsg("");
    try {
      const r = await api.post("/admin/reset-demo-data");
      setMsg(isEn
        ? `✓ Reset done in ${r.data.duration_seconds}s. Please log out and log in again.`
        : `✓ تمت إعادة التعيين في ${r.data.duration_seconds} ثانية. سجّل خروجًا ثم دخولًا من جديد.`);
      await load();
    } catch (e: any) {
      setMsg("✗ " + errMsg(e, isEn ? "Reset failed" : "فشلت إعادة التعيين"));
    } finally {
      setResetting(false);
    }
  };

  const Badge = ({ status }: { status: string }) => {
    const map: Record<string, { bg: string; fg: string; label: string }> = {
      ok: { bg: "#d1fae5", fg: "#065f46", label: isEn ? "OK" : "شغّال" },
      fail: { bg: "#fee2e2", fg: "#991b1b", label: isEn ? "FAIL" : "فشل" },
      disabled: { bg: "#e5e7eb", fg: "#374151", label: isEn ? "OFF" : "معطّل" },
    };
    const s = map[status] || map.disabled;
    return (
      <span style={{
        background: s.bg, color: s.fg, padding: "2px 10px", borderRadius: 12,
        fontSize: 12, fontWeight: 600,
      }}>{s.label}</span>
    );
  };

  const Card = ({ title, status, children }: { title: string; status: string; children?: any }) => (
    <div style={{
      background: "white", border: "1px solid #e5e7eb", borderRadius: 10,
      padding: 16, minHeight: 120,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center",
        marginBottom: 10 }}>
        <div style={{ fontWeight: 600, fontSize: 14 }}>{title}</div>
        <Badge status={status} />
      </div>
      <div style={{ fontSize: 13, color: "#4b5563", lineHeight: 1.7 }}>{children}</div>
    </div>
  );

  if (loading) return <div className="card">{t("loading")}</div>;
  if (!health) return <div className="card">{t("load_failed") || "فشل تحميل الحالة"}</div>;

  const c = health.checks;
  const allGreen = health.status === "ok";

  return (
    <div>
      {/* رأس اللوحة — النتيجة الإجمالية بارزة */}
      <div style={{
        background: allGreen ? "#065f46" : "#991b1b", color: "white",
        padding: "20px 24px", borderRadius: 12, marginBottom: 16,
        display: "flex", alignItems: "center", gap: 16,
      }}>
        <div style={{ fontSize: 42 }}>{allGreen ? "✓" : "⚠"}</div>
        <div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>
            {allGreen
              ? (isEn ? "All systems operational" : "كل الأنظمة تعمل بشكل سليم")
              : (isEn ? "Some checks failed" : "بعض الفحوصات فشلت")}
          </div>
          <div style={{ opacity: 0.85, fontSize: 13, marginTop: 4 }}>
            {health.service} · {manifest?.version || "?"}
            {manifest?.commit && ` · ${manifest.commit.slice(0, 7)}`}
          </div>
        </div>
        <div style={{ marginInlineStart: "auto" }}>
          <button onClick={load} className="ghost" style={{ background: "rgba(255,255,255,0.15)",
            color: "white", border: "1px solid rgba(255,255,255,0.3)" }}>
            {isEn ? "Refresh" : "تحديث"}
          </button>
        </div>
      </div>

      {/* شبكة البطاقات */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
        gap: 12 }}>
        <Card title={isEn ? "Database" : "قاعدة البيانات"} status={c.database?.status || "fail"}>
          {c.database?.error || (isEn ? "Connection healthy" : "الاتصال سليم")}
        </Card>

        <Card title={isEn ? "OCR Engine (Tesseract)" : "محرّك OCR (Tesseract)"}
              status={c.ocr?.status || "fail"}>
          {c.ocr?.version
            ? <>
                v{c.ocr.version}<br />
                {isEn ? "Languages" : "اللغات"}: <b>{(c.ocr.languages || []).join(", ") || "—"}</b><br />
                {c.ocr.arabic_ready
                  ? <span style={{ color: "#065f46" }}>✓ {isEn ? "Arabic ready" : "العربية جاهزة"}</span>
                  : <span style={{ color: "#991b1b" }}>✗ {isEn ? "Arabic pack missing" : "الحزمة العربية ناقصة"}</span>
                }
              </>
            : (isEn ? "Not installed" : "غير مثبَّت")
          }
        </Card>

        <Card title={isEn ? "Data" : "البيانات"} status={c.data?.status || "fail"}>
          {c.data?.status === "ok" && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 4 }}>
              <span>{isEn ? "Companies" : "شركات"}</span><b>{c.data.companies}</b>
              <span>{isEn ? "Employees" : "موظفون"}</span><b>{c.data.employees}</b>
              <span>{isEn ? "Users" : "مستخدمون"}</span><b>{c.data.users}</b>
              <span>{isEn ? "Requests" : "طلبات"}</span><b>{c.data.requests}</b>
              <span>{isEn ? "Templates" : "قوالب"}</span><b>{c.data.templates}</b>
              <span>{isEn ? "Documents" : "مستندات"}</span><b>{c.data.documents}</b>
            </div>
          )}
        </Card>

        <Card title={isEn ? "Storage" : "التخزين"} status={c.storage?.status || "fail"}>
          <span style={{ fontFamily: "monospace", fontSize: 11 }}>{c.storage?.path}</span><br />
          {c.storage?.writable
            ? <span style={{ color: "#065f46" }}>✓ {isEn ? "Writable" : "قابل للكتابة"}</span>
            : <span style={{ color: "#991b1b" }}>✗ {isEn ? "Not writable" : "غير قابل للكتابة"}</span>
          }
        </Card>

        <Card title={isEn ? "Scheduler" : "المجدوِل"} status={c.scheduler?.status || "fail"}>
          {c.scheduler?.status === "ok"
            ? (isEn ? "Background jobs running" : "المهام الخلفية تعمل")
            : (isEn ? "Disabled (dev mode)" : "معطّل (وضع تطوير)")
          }
        </Card>

        <Card title={isEn ? "Migrations" : "الهجرات"} status={c.alembic?.status || "fail"}>
          {c.alembic?.head
            ? <>{isEn ? "Head" : "الرأس"}: <code style={{ fontSize: 11 }}>{c.alembic.head.slice(0, 12)}</code></>
            : (isEn ? "No version" : "لا يوجد إصدار")
          }
        </Card>

        <Card title={isEn ? "Canonical Registry" : "السجل الرسمي"} status={c.registry?.status || "fail"}>
          {c.registry?.status === "ok" && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 4 }}>
              <span>Layouts</span><b>{c.registry.layouts || 9}</b>
              <span>{isEn ? "Documents" : "مستندات"}</span><b>{c.registry.canonical_documents || 25}</b>
              <span>{isEn ? "Reports" : "تقارير"}</span><b>{c.registry.reports || "—"}</b>
              <span>{isEn ? "Legacy aliases" : "أسماء قديمة"}</span><b>{c.registry.legacy_prn_aliases || "—"}</b>
            </div>
          )}
        </Card>
      </div>

      {/* منطقة الخطر — Reset (super_admin + مسموح فقط) */}
      {isSuper && resetInfo && (
        <div style={{
          marginTop: 24, background: "#fef2f2", border: "2px solid #fca5a5",
          borderRadius: 12, padding: 20,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
            <Icon name="lock" size={20} />
            <h3 style={{ margin: 0, color: "#991b1b" }}>
              {isEn ? "Danger Zone" : "منطقة الخطر"}
            </h3>
          </div>
          <p style={{ fontSize: 13, color: "#7f1d1d", marginBottom: 12 }}>
            {isEn
              ? "Reset Demo Data will DELETE all companies, employees, requests, documents, and re-seed the demo dataset. Use before starting a fresh demo presentation."
              : "زر إعادة التعيين سيمسح كل الشركات والموظفين والطلبات والمستندات، ويعيد تعبئة بيانات الديمو من الصفر. استخدمه قبل بداية عرض توضيحي جديد."
            }
          </p>
          {resetInfo.allowed ? (
            <button onClick={doReset} disabled={resetting}
              style={{ background: "#dc2626", color: "white" }}>
              {resetting
                ? (isEn ? "Resetting..." : "جارٍ إعادة التعيين...")
                : (isEn ? "Reset Demo Data" : "إعادة تعيين بيانات الديمو")}
            </button>
          ) : (
            <div style={{ background: "#fecaca", padding: 10, borderRadius: 6,
              fontSize: 12, color: "#7f1d1d" }}>
              <b>{isEn ? "Disabled:" : "معطّل:"}</b> {resetInfo.reason}
            </div>
          )}
          {msg && <div style={{ marginTop: 10, fontSize: 13, fontWeight: 500,
            color: msg.startsWith("✓") ? "#065f46" : "#991b1b" }}>{msg}</div>}
        </div>
      )}
    </div>
  );
}
