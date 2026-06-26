import { useEffect, useState } from "react";
import api from "../api";

const ACTION_AR: Record<string, string> = {
  login: "تسجيل دخول", create_employee: "إضافة موظف", update_employee: "تعديل موظف",
  terminate_employee: "إنهاء خدمة", transfer_employee: "نقل موظف", create_user: "إضافة مستخدم",
  reset_password: "إعادة تعيين كلمة مرور", change_password: "تغيير كلمة المرور",
  run_payroll: "تشغيل مسيّر رواتب", upload_document: "رفع مستند", render_template: "توليد صيغة",
  submit_request: "تقديم طلب", request_approved: "اعتماد طلب", request_rejected: "رفض طلب",
  request_cancel: "إلغاء طلب", check_in: "تسجيل حضور", check_out: "تسجيل انصراف",
  rotate_kiosk_key: "تدوير مفتاح شاشة", create_company: "إضافة شركة", create_branch: "إضافة فرع",
};

export default function Audit() {
  const [rows, setRows] = useState<any[]>([]);
  const [action, setAction] = useState("");
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    api.get("/audit", { params: { limit: 200, action: action || undefined } })
      .then((r) => setRows(r.data)).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, [action]);

  const actions = Array.from(new Set(rows.map((r) => r.action)));

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="eyebrow">الأمان</div>
          <h2 style={{ margin: "2px 0 0" }}>سجل التدقيق</h2>
          <div className="sub">كل العمليات الحسّاسة مع المنفّذ والوقت وعنوان IP</div>
        </div>
        <select value={action} onChange={(e) => setAction(e.target.value)} style={{ width: 200 }}>
          <option value="">كل العمليات</option>
          {actions.map((a) => <option key={a} value={a}>{ACTION_AR[a] || a}</option>)}
        </select>
      </div>

      <div className="table-wrap">
        <table>
          <thead><tr><th>العملية</th><th>الكيان</th><th>التفاصيل</th><th>المنفّذ</th><th>IP</th><th>الوقت</th></tr></thead>
          <tbody>
            {loading ? <tr><td colSpan={6} className="empty">جارِ التحميل…</td></tr>
              : rows.map((r) => (
                <tr key={r.id}>
                  <td><span className="pill neutral">{ACTION_AR[r.action] || r.action}</span></td>
                  <td className="muted">{r.entity_type}{r.entity_id ? ` #${r.entity_id}` : ""}</td>
                  <td className="muted">{r.detail}</td>
                  <td>{r.by}</td>
                  <td className="muted">{r.ip}</td>
                  <td className="muted">{new Date(r.at).toLocaleString("ar")}</td>
                </tr>
              ))}
            {!loading && !rows.length && <tr><td colSpan={6} className="empty">لا توجد سجلات</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
