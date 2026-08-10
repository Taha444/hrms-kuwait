import { useEffect, useState } from "react";
import api, { errMsg } from "../api";
import { useI18n } from "../i18n";

// P0-#9 — إعادة تصميم: مافيش demo defaults. الحساب يبدأ بـEmployee selection.
// Salary/Hire Date من الـEmployee record (read-only). المستخدم يدخل فقط:
// end_date, reason, used_leave_days.
export default function Eos() {
  const { t } = useI18n();
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [employees, setEmployees] = useState<any[]>([]);
  const [empId, setEmpId] = useState<number | "">("");
  const [selectedEmp, setSelectedEmp] = useState<any>(null);
  const [form, setForm] = useState<any>({
    end_date: "", reason: "termination", used_leave_days: 0,
  });
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/eos/reasons").then((r) => setReasons(r.data));
    api.get("/employees").then((r) => setEmployees(r.data));
  }, []);

  useEffect(() => {
    if (!empId) { setSelectedEmp(null); return; }
    const emp = employees.find((e) => e.id === empId);
    setSelectedEmp(emp || null);
    setRes(null);  // امسح النتيجة القديمة عند تغيير الموظف
  }, [empId, employees]);

  const calc = async () => {
    if (!empId || !selectedEmp) {
      setErr("اختر موظف أولاً — الحساب من قيم افتراضية غير مسموح");
      return;
    }
    if (!selectedEmp.basic_salary || !selectedEmp.hire_date) {
      setErr(`الموظف ${selectedEmp.name} — بياناته ناقصة (salary/hire_date). أكمل الملف أولاً.`);
      return;
    }
    if (!form.end_date) {
      setErr("تاريخ انتهاء الخدمة مطلوب");
      return;
    }
    setErr(""); setBusy(true);
    try {
      const r = await api.post("/eos/for-employee", {
        employee_id: empId,
        end_date: form.end_date,
        reason: form.reason,
        used_leave_days: form.used_leave_days,
      });
      setRes(r.data);
    } catch (e: any) {
      setErr(errMsg(e, t("error")));
    } finally { setBusy(false); }
  };

  return (
    <div>
      <h2>{t("eos_title") || "حساب مكافأة نهاية الخدمة"}</h2>
      <div className="card">
        {/* اختيار الموظف — إلزامي */}
        <div className="field">
          <label htmlFor="eos-emp">اختر الموظف *</label>
          <select id="eos-emp" value={empId}
                  onChange={(e) => setEmpId(e.target.value ? +e.target.value : "")}>
            <option value="">— اختر —</option>
            {employees.map((e) => (
              <option key={e.id} value={e.id}>
                {e.employee_no ? `[${e.employee_no}] ` : ""}{e.name} — {e.job_title || "—"}
              </option>
            ))}
          </select>
        </div>

        {/* بيانات الموظف — read-only من الـrecord */}
        {selectedEmp && (
          <div className="card" style={{ background: "#f0f6fa", padding: 12, marginBottom: 12 }}>
            <b>بيانات {selectedEmp.name} (من السجل — لا تُعدَّل):</b>
            <div className="row" style={{ marginTop: 8, gap: 20, fontSize: 14 }}>
              <div><b>الراتب الأساسي:</b> {selectedEmp.basic_salary
                ? `${selectedEmp.basic_salary} د.ك` : <span style={{ color: "var(--danger)" }}>غير محدد</span>}</div>
              <div><b>تاريخ التعيين:</b> {selectedEmp.hire_date
                || <span style={{ color: "var(--danger)" }}>غير محدد</span>}</div>
              <div><b>نوع العقد:</b> {selectedEmp.contract_type === "indefinite" ? "غير محدد المدة" : "محدد المدة"}</div>
            </div>
          </div>
        )}

        {/* الحقول اللي المستخدم يدخلها */}
        <div className="row">
          <div className="field" style={{ flex: 1 }}>
            <label htmlFor="eos-end">تاريخ انتهاء الخدمة *</label>
            <input id="eos-end" type="date" value={form.end_date}
                   onChange={(e) => setForm({ ...form, end_date: e.target.value })} required />
          </div>
          <div className="field" style={{ flex: 1 }}>
            <label htmlFor="eos-reason">سبب انتهاء الخدمة</label>
            <select id="eos-reason" value={form.reason}
                    onChange={(e) => setForm({ ...form, reason: e.target.value })}>
              {Object.entries(reasons).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <div className="field" style={{ flex: 1 }}>
            <label htmlFor="eos-used-leave">أيام إجازة مستهلَكة</label>
            <input id="eos-used-leave" type="number" min={0} step={1} value={form.used_leave_days}
                   onChange={(e) => setForm({ ...form, used_leave_days: +e.target.value })} />
          </div>
        </div>

        {err && <div className="err">{err}</div>}
        <button onClick={calc} disabled={busy || !empId}
                style={{ opacity: (!empId ? 0.5 : 1) }}>
          {busy ? "جاري الحساب..." : "احسب المكافأة"}
        </button>
      </div>

      {res && (
        <div className="card">
          <h3>نتيجة الحساب — {res.employee?.name}</h3>
          <div className="grid">
            <div className="stat card"><div className="num">{res.total_settlement}</div><div className="lbl">إجمالي المكافأة</div></div>
            <div className="stat card"><div className="num">{res.indemnity}</div><div className="lbl">تعويض نهاية الخدمة</div></div>
            <div className="stat card"><div className="num">{res.leave_payout}</div><div className="lbl">بدل الإجازات</div></div>
            <div className="stat card"><div className="num">{res.daily_wage}</div><div className="lbl">الأجر اليومي</div></div>
          </div>
          <p><b>مدة الخدمة:</b> {res.service.text} ({res.service.decimal_years} سنة)</p>
          {res.leave && (
            <p><b>الإجازات:</b> مستحق {res.leave.accrued_days} · مستهلَك {res.leave.used_days} · متبقي {res.leave.remaining_days}</p>
          )}
          {res.leave?.advance_note && <p className="err">⚠ {res.leave.advance_note}</p>}
          <p><b>نسبة الاستحقاق:</b> {(res.entitlement_factor * 100).toFixed(2)}% — {res.factor_note}</p>
          {res.cap_applied && <p className="err">{t("eos_cap") || "تم تطبيق الحد الأقصى"}</p>}
          <p className="muted">{res.disclaimer}</p>
        </div>
      )}
    </div>
  );
}
