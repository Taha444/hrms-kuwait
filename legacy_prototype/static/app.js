/* ============================================================================
   نظام إدارة الموارد البشرية متعدد الشركات — واجهة المستخدم (SPA)
   JavaScript خام (بدون مكتبات). يتواصل مع واجهة REST في app.py
   ============================================================================ */

"use strict";

/* ----------------------------------------------------------------------------
   1) الحالة العامة (State)
---------------------------------------------------------------------------- */
const state = {
  user: null,          // بيانات المستخدم الحالي (id, role, permissions, company...)
  companies: [],       // قائمة الشركات (للإدارة العليا في المنتقي والنماذج)
  companyFilter: null, // الشركة المختارة للإدارة العليا (null = الكل)
  view: "dashboard",   // الشاشة الحالية
  catalog: null,       // كتالوج الصلاحيات (يُحمّل عند الحاجة)
  csrf: null,          // رمز حماية CSRF
};

/* ----------------------------------------------------------------------------
   2) أدوات مساعدة عامة
---------------------------------------------------------------------------- */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function esc(s) {
  if (s === null || s === undefined) return "";
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

function fmtMoney(n) {
  const v = Number(n || 0);
  return v.toLocaleString("en-US", { minimumFractionDigits: 3, maximumFractionDigits: 3 }) + " د.ك";
}

function fmtDate(s) {
  if (!s) return "—";
  return String(s).slice(0, 10);
}

function can(perm) {
  if (!state.user) return false;
  if (state.user.role === "super_admin") return true;
  return (state.user.permissions || []).includes(perm);
}

const isAdmin = () => state.user && state.user.role === "super_admin";
const isManagerOrAdmin = () =>
  state.user && (state.user.role === "super_admin" || state.user.role === "company_manager");

/* منتقي الشركة (للإدارة العليا): يرجع نص الـ query أو فراغ */
function companyQuery(prefix = "?") {
  if (isAdmin() && state.companyFilter) return prefix + "company_id=" + encodeURIComponent(state.companyFilter);
  return "";
}

/* الشركة الفعّالة لاستخدامها في النماذج (إنشاء موظف/ترخيص/مستخدم) */
function activeCompanyId() {
  if (isAdmin()) return state.companyFilter || null;
  return state.user.company_id;
}

/* ----------------------------------------------------------------------------
   3) طبقة الاتصال بالـ API
---------------------------------------------------------------------------- */
async function api(method, path, data) {
  const opts = { method, credentials: "same-origin", headers: {} };
  // رمز حماية CSRF لطرق التعديل
  if (!["GET", "HEAD", "OPTIONS"].includes(method) && state.csrf) {
    opts.headers["X-CSRF-Token"] = state.csrf;
  }
  if (data instanceof FormData) {
    opts.body = data;
  } else if (data !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(data);
  }
  let res, json;
  try {
    res = await fetch(path, opts);
  } catch (e) {
    return { ok: false, status: 0, data: { error: "تعذّر الاتصال بالخادم" } };
  }
  try { json = await res.json(); } catch (e) { json = {}; }
  return { ok: res.ok, status: res.status, data: json };
}

const apiGet = (p) => api("GET", p);
const apiPost = (p, d) => api("POST", p, d);
const apiPut = (p, d) => api("PUT", p, d);
const apiDel = (p) => api("DELETE", p);

async function downloadCsv(url, filename) {
  try {
    const res = await fetch(url, { credentials: "same-origin" });
    if (!res.ok) { toast("فشل تصدير الملف", "error"); return; }
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(a.href);
  } catch (e) {
    toast("فشل تصدير الملف", "error");
  }
}

/* ----------------------------------------------------------------------------
   4) إشعارات (Toast) + مودال
---------------------------------------------------------------------------- */
let toastTimer = null;
function toast(msg, type = "success") {
  let box = $("#toast");
  if (!box) {
    box = el('<div id="toast" style="position:fixed;top:18px;left:50%;transform:translateX(-50%);z-index:9999;"></div>');
    document.body.appendChild(box);
  }
  const color = type === "error" ? "#dc2626" : (type === "info" ? "#2563eb" : "#16a34a");
  box.innerHTML = `<div style="background:${color};color:#fff;padding:11px 22px;border-radius:10px;
      box-shadow:0 8px 24px rgba(0,0,0,.2);font-size:14px;font-weight:600;">${esc(msg)}</div>`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { box.innerHTML = ""; }, 3200);
}

function openModal(title, bodyHtml, footHtml) {
  const root = $("#modal-root");
  root.innerHTML = `
    <div class="modal-overlay" id="modal-overlay">
      <div class="modal">
        <div class="modal-head">
          <h3>${esc(title)}</h3>
          <button class="close" id="modal-close">&times;</button>
        </div>
        <div class="modal-body" id="modal-body">${bodyHtml}</div>
        ${footHtml ? `<div class="modal-foot">${footHtml}</div>` : ""}
      </div>
    </div>`;
  $("#modal-close").onclick = closeModal;
  $("#modal-overlay").onclick = (e) => { if (e.target.id === "modal-overlay") closeModal(); };
  return root;
}
function closeModal() { $("#modal-root").innerHTML = ""; }

/* قراءة قيم النموذج داخل المودال حسب data-field */
function readForm(root = document) {
  const out = {};
  $$("[data-field]", root).forEach((inp) => {
    let v = inp.type === "checkbox" ? inp.checked : inp.value;
    if (typeof v === "string") v = v.trim();
    out[inp.dataset.field] = v;
  });
  return out;
}

function badge(text, cls) { return `<span class="badge ${cls}">${esc(text)}</span>`; }

function statusBadge(status) {
  const map = {
    active: ["نشط", "green"], inactive: ["معطّل", "gray"], archived: ["مؤرشف", "gray"],
    terminated: ["مفصول", "red"], resigned: ["مستقيل", "amber"],
    pending: ["قيد الانتظار", "amber"], approved: ["مقبول", "green"], rejected: ["مرفوض", "red"],
    expired: ["منتهي", "red"],
  };
  const [t, c] = map[status] || [status || "—", "gray"];
  return badge(t, c);
}

const ROLE_LABELS = { super_admin: "إدارة عليا", company_manager: "مدير شركة", employee: "موظف" };

/* ----------------------------------------------------------------------------
   5) الإقلاع والمصادقة
---------------------------------------------------------------------------- */
async function boot() {
  const { data } = await apiGet("/api/me");
  if (data && data.authenticated) {
    state.user = data;
    state.csrf = data.csrf_token || null;
    await enterApp();
  } else {
    showLogin();
  }
}

function showLogin() {
  $("#app").classList.add("hidden");
  $("#login-screen").classList.remove("hidden");
  $("#login-username").focus();
}

async function doLogin() {
  const username = $("#login-username").value.trim();
  const password = $("#login-password").value;
  const errBox = $("#login-error");
  errBox.classList.add("hidden");
  if (!username || !password) {
    errBox.textContent = "أدخل اسم المستخدم وكلمة المرور";
    errBox.classList.remove("hidden");
    return;
  }
  $("#login-btn").disabled = true;
  $("#login-btn").textContent = "جارٍ الدخول...";
  const { ok, data } = await apiPost("/api/login", { username, password });
  $("#login-btn").disabled = false;
  $("#login-btn").textContent = "تسجيل الدخول";
  if (!ok) {
    errBox.textContent = data.error || "تعذّر تسجيل الدخول";
    errBox.classList.remove("hidden");
    return;
  }
  state.user = data;
  state.csrf = data.csrf_token || null;
  $("#login-password").value = "";
  await enterApp();
}

async function doLogout() {
  await apiPost("/api/logout", {});
  state.user = null;
  state.companyFilter = null;
  state.companies = [];
  showLogin();
}

async function enterApp() {
  $("#login-screen").classList.add("hidden");
  $("#app").classList.remove("hidden");

  // ترويسة المستخدم
  const u = state.user;
  $("#user-name").textContent = u.full_name || u.username;
  $("#user-role").textContent = ROLE_LABELS[u.role] || u.role;
  $("#user-avatar").textContent = (u.full_name || u.username || "؟").trim().charAt(0);

  // منتقي الشركات للإدارة العليا
  if (isAdmin()) {
    const { data } = await apiGet("/api/companies");
    state.companies = Array.isArray(data) ? data : [];
    buildCompanySelect();
  } else if (u.company) {
    state.companies = [u.company];
  }

  buildNav();
  setupNotifications();
  navigate("dashboard");
}

/* ---------- جرس الإشعارات ---------- */
async function setupNotifications() {
  let bell = $("#notif-bell");
  if (!bell) {
    const area = $(".user-area");
    bell = el(`<div id="notif-bell" style="position:relative; cursor:pointer; font-size:20px; margin-inline-end:6px;" title="الإشعارات">
        🔔<span id="notif-count" class="badge red" style="position:absolute; top:-8px; left:-8px; display:none;"></span>
      </div>`);
    area.insertBefore(bell, area.firstChild);
    bell.onclick = toggleNotifications;
  }
  await refreshNotifCount();
}

async function refreshNotifCount() {
  const { ok, data } = await apiGet("/api/notifications?unread=1");
  if (!ok) return;
  const c = $("#notif-count");
  if (data.unread > 0) { c.textContent = data.unread; c.style.display = "inline-block"; }
  else c.style.display = "none";
}

async function toggleNotifications() {
  const { data } = await apiGet("/api/notifications");
  const items = (data.items || []);
  const body = items.length ? items.map((n) => `
    <div style="padding:10px 0; border-bottom:1px solid #e2e8f0; ${n.is_read ? "opacity:.6;" : ""}">
      <div style="font-weight:600;">${esc(n.title)}</div>
      <div class="muted" style="font-size:13px;">${esc(n.body)}</div>
      <div class="muted" style="font-size:11px;">${fmtDate(n.created_at)}</div>
    </div>`).join("") : `<div class="empty">لا إشعارات</div>`;
  openModal("الإشعارات", body,
    `<button class="btn ghost" onclick="closeModal()">إغلاق</button>
     <button class="btn" id="notif-read-all">تعليم الكل كمقروء</button>`);
  $("#notif-read-all").onclick = async () => {
    await apiPost("/api/notifications/read-all", {});
    await refreshNotifCount();
    closeModal();
  };
}

function buildCompanySelect() {
  const sel = $("#company-select");
  sel.classList.remove("hidden");
  sel.innerHTML = `<option value="">كل الشركات</option>` +
    state.companies.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("");
  sel.value = state.companyFilter || "";
  sel.onchange = () => {
    state.companyFilter = sel.value || null;
    navigate(state.view); // إعادة تحميل الشاشة الحالية بالنطاق الجديد
  };
}

/* ----------------------------------------------------------------------------
   6) القائمة الجانبية (مبنية حسب الصلاحيات)
---------------------------------------------------------------------------- */
function navItems() {
  return [
    { key: "dashboard", label: "لوحة التحكم", icon: "📊", show: true },
    { key: "companies", label: "الشركات", icon: "🏢", show: isAdmin() },
    { key: "employees", label: "الموظفون", icon: "👥", show: can("view_employee") },
    { key: "licenses", label: "التراخيص", icon: "📜", show: can("manage_licenses") || isManagerOrAdmin() },
    { key: "users", label: "المستخدمون والصلاحيات", icon: "🔑", show: can("manage_users") },
    { key: "eos", label: "حاسبة نهاية الخدمة", icon: "🧮", show: can("calculate_eos") },
    { key: "payroll", label: "مسيّر الرواتب", icon: "💰", show: can("view_payroll") || can("run_payroll") },
    { key: "reports", label: "التقارير", icon: "📈", show: can("view_reports") },
    { key: "audit", label: "سجل التدقيق", icon: "🛡️", show: isManagerOrAdmin() },
    { key: "settings", label: "الإعدادات", icon: "⚙️", show: true },
  ].filter((i) => i.show);
}

function buildNav() {
  const nav = $("#nav");
  nav.innerHTML = navItems().map((i) =>
    `<div class="nav-item" data-nav="${i.key}">
       <span class="icon">${i.icon}</span><span>${i.label}</span>
     </div>`).join("");
  $$(".nav-item", nav).forEach((item) => {
    item.onclick = () => navigate(item.dataset.nav);
  });
}

function setActiveNav() {
  $$(".nav-item").forEach((n) => n.classList.toggle("active", n.dataset.nav === state.view));
}

const VIEW_TITLES = {
  dashboard: "لوحة التحكم", companies: "إدارة الشركات", employees: "الموظفون",
  licenses: "التراخيص", users: "المستخدمون والصلاحيات", eos: "حاسبة مكافأة نهاية الخدمة",
  payroll: "مسيّر الرواتب", reports: "التقارير", audit: "سجل التدقيق", settings: "الإعدادات",
};

/* ----------------------------------------------------------------------------
   7) الموجّه (Router)
---------------------------------------------------------------------------- */
function navigate(view) {
  state.view = view;
  setActiveNav();
  $("#page-title").textContent = VIEW_TITLES[view] || "—";
  const target = $("#view");
  target.innerHTML = `<div class="empty">جارٍ التحميل…</div>`;
  const fn = VIEWS[view];
  if (fn) fn(target);
  else target.innerHTML = `<div class="empty">الشاشة غير متاحة</div>`;
}

const VIEWS = {};

/* ============================================================================
   8) الشاشات (Views)
   ============================================================================ */

/* ---------- لوحة التحكم ---------- */
VIEWS.dashboard = async function (root) {
  const [{ data: summary }, { data: alerts }] = await Promise.all([
    apiGet("/api/reports/summary" + companyQuery()),
    can("view_alerts") ? apiGet("/api/alerts" + companyQuery()) : Promise.resolve({ data: [] }),
  ]);

  const cards = [
    { label: "إجمالي الموظفين", value: summary.total_employees ?? 0 },
    { label: "الموظفون النشطون", value: summary.active_employees ?? 0 },
    { label: "التراخيص", value: summary.total_licenses ?? 0 },
    { label: "إقامات/أذونات منتهية", value: summary.expired_permits ?? 0, cls: "danger" },
    { label: "تراخيص منتهية", value: summary.expired_licenses ?? 0, cls: "danger" },
    { label: "التنبيهات النشطة", value: summary.alerts_count ?? 0, cls: "warning" },
  ];
  if (isAdmin()) cards.push({ label: "الشركات", value: summary.companies ?? 0 });

  const statsHtml = `<div class="stats-grid">` + cards.map((c) =>
    `<div class="stat-card ${c.cls || ""}">
       <div class="value">${c.value}</div>
       <div class="label">${c.label}</div>
     </div>`).join("") + `</div>`;

  let alertsHtml = "";
  if (can("view_alerts")) {
    const items = (alerts || []).slice(0, 20);
    alertsHtml = `
      <div class="card">
        <div class="card-header"><h2>🔔 التنبيهات</h2>
          <span class="muted">${(alerts || []).length} تنبيه</span></div>
        ${items.length ? items.map(alertRow).join("") :
          `<div class="empty">لا توجد تنبيهات حالية ✅</div>`}
      </div>`;
  }

  root.innerHTML = statsHtml + alertsHtml;
};

function alertRow(a) {
  const icons = { permit: "🪪", license: "📜", document: "📄", capacity: "⚠️" };
  const days = a.days_left;
  let daysTxt = "";
  if (days === null || days === undefined) daysTxt = "";
  else if (days < 0) daysTxt = `<span class="a-days neg">منذ ${Math.abs(days)} يوم</span>`;
  else daysTxt = `<span class="a-days">باقٍ ${days} يوم</span>`;
  return `
    <div class="alert-item ${esc(a.severity)}">
      <span class="a-icon">${icons[a.type] || "🔔"}</span>
      <div class="a-body">
        <div class="a-title">${esc(a.title)}</div>
        <div class="a-detail">${esc(a.detail)}</div>
      </div>
      ${daysTxt}
    </div>`;
}

/* ---------- الشركات (إدارة عليا) ---------- */
VIEWS.companies = async function (root) {
  const { data } = await apiGet("/api/companies");
  const rows = Array.isArray(data) ? data : [];
  root.innerHTML = `
    <div class="toolbar">
      <button class="btn" id="add-company">➕ إضافة شركة</button>
      <div class="spacer"></div>
    </div>
    <div class="card">
      <table>
        <thead><tr>
          <th>#</th><th>الاسم</th><th>السجل التجاري</th><th>الموظفون</th>
          <th>التراخيص</th><th>مقسوم EOS</th><th>الحالة</th><th>إجراءات</th>
        </tr></thead>
        <tbody>
          ${rows.length ? rows.map(companyRow).join("") :
            `<tr><td colspan="8"><div class="empty">لا توجد شركات</div></td></tr>`}
        </tbody>
      </table>
    </div>`;
  $("#add-company").onclick = () => companyModal();
  $$("[data-edit-company]").forEach((b) => b.onclick = () => {
    const c = rows.find((x) => x.id == b.dataset.editCompany); companyModal(c);
  });
  $$("[data-toggle-company]").forEach((b) => b.onclick = async () => {
    const r = await apiPost(`/api/companies/${b.dataset.toggleCompany}/toggle`, {});
    if (r.ok) { toast("تم تحديث الحالة"); refreshCompaniesEverywhere(); navigate("companies"); }
    else toast(r.data.error || "خطأ", "error");
  });
  $$("[data-archive-company]").forEach((b) => b.onclick = async () => {
    if (!confirm("أرشفة هذه الشركة؟ لن تظهر في القوائم النشطة.")) return;
    const r = await apiPost(`/api/companies/${b.dataset.archiveCompany}/archive`, {});
    if (r.ok) { toast("تمت الأرشفة"); refreshCompaniesEverywhere(); navigate("companies"); }
    else toast(r.data.error || "خطأ", "error");
  });
};

function companyRow(c) {
  return `<tr>
    <td>${c.id}</td>
    <td><strong>${esc(c.name)}</strong>${c.name_en ? `<div class="muted" style="font-size:11px;">${esc(c.name_en)}</div>` : ""}</td>
    <td>${esc(c.commercial_reg) || "—"}</td>
    <td>${c.employees_count ?? 0}</td>
    <td>${c.licenses_count ?? 0}</td>
    <td>${c.eos_day_divisor} يوم</td>
    <td>${statusBadge(c.status)}</td>
    <td><div class="row-actions">
      <button class="btn sm ghost" data-edit-company="${c.id}">تعديل</button>
      <button class="btn sm secondary" data-toggle-company="${c.id}">${c.status === "active" ? "تعطيل" : "تفعيل"}</button>
      <button class="btn sm danger" data-archive-company="${c.id}">أرشفة</button>
    </div></td>
  </tr>`;
}

function companyModal(c) {
  const edit = !!c;
  c = c || {};
  openModal(edit ? "تعديل شركة" : "إضافة شركة", `
    <div class="form-grid">
      <div class="field full"><label>اسم الشركة *</label><input data-field="name" value="${esc(c.name)}"></div>
      <div class="field"><label>الاسم بالإنجليزية</label><input data-field="name_en" value="${esc(c.name_en)}"></div>
      <div class="field"><label>السجل التجاري</label><input data-field="commercial_reg" value="${esc(c.commercial_reg)}"></div>
      <div class="field"><label>نوع الكيان القانوني</label><input data-field="entity_type" value="${esc(c.entity_type)}" placeholder="ذ.م.م / مساهمة..."></div>
      <div class="field"><label>مقسوم اليوم (EOS)</label>
        <select data-field="eos_day_divisor">
          <option value="26" ${(c.eos_day_divisor||26)==26?"selected":""}>26 (المعتمد غالبًا)</option>
          <option value="30" ${c.eos_day_divisor==30?"selected":""}>30</option>
        </select></div>
      <div class="field"><label>الحد الأقصى (أشهر)</label><input type="number" data-field="eos_max_months" value="${c.eos_max_months||18}"></div>
      <div class="field"><label>التنبيه قبل الانتهاء (يوم)</label><input type="number" data-field="alert_lead_days" value="${c.alert_lead_days||30}"></div>
    </div>
  `, `<button class="btn" id="save-company">حفظ</button>
      <button class="btn secondary" onclick="closeModal()">إلغاء</button>`);

  $("#save-company").onclick = async () => {
    const d = readForm($("#modal-body"));
    if (!d.name) { toast("اسم الشركة مطلوب", "error"); return; }
    const r = edit ? await apiPut(`/api/companies/${c.id}`, d) : await apiPost("/api/companies", d);
    if (r.ok) { closeModal(); toast("تم الحفظ"); await refreshCompaniesEverywhere(); navigate("companies"); }
    else toast(r.data.error || "خطأ في الحفظ", "error");
  };
}

async function refreshCompaniesEverywhere() {
  if (isAdmin()) {
    const { data } = await apiGet("/api/companies");
    state.companies = Array.isArray(data) ? data : [];
    buildCompanySelect();
  }
}

/* ---------- الموظفون ---------- */
VIEWS.employees = async function (root) {
  root.innerHTML = `
    <div class="toolbar">
      ${can("create_employee") ? `<button class="btn" id="add-emp">➕ إضافة موظف</button>` : ""}
      <input id="emp-search" placeholder="بحث بالاسم أو الرقم المدني…" style="min-width:240px;">
      <select id="emp-status">
        <option value="">كل الحالات</option>
        <option value="active">نشط</option>
        <option value="terminated">مفصول</option>
        <option value="resigned">مستقيل</option>
      </select>
      <div class="spacer"></div>
    </div>
    <div id="emp-table-wrap"></div>`;

  async function load() {
    const q = $("#emp-search").value.trim();
    const status = $("#emp-status").value;
    let url = "/api/employees" + companyQuery();
    const params = [];
    if (q) params.push("q=" + encodeURIComponent(q));
    if (status) params.push("status=" + encodeURIComponent(status));
    if (params.length) url += (url.includes("?") ? "&" : "?") + params.join("&");
    const { data } = await apiGet(url);
    const rows = Array.isArray(data) ? data : [];
    $("#emp-table-wrap").innerHTML = `
      <div class="card">
        <table>
          <thead><tr>
            <th>#</th><th>الاسم</th><th>الرقم المدني</th><th>الجنسية</th><th>الوظيفة</th>
            <th>الراتب</th><th>الشركة</th><th>الحالة</th><th></th>
          </tr></thead>
          <tbody>${rows.length ? rows.map(empRow).join("") :
            `<tr><td colspan="9"><div class="empty">لا يوجد موظفون</div></td></tr>`}</tbody>
        </table>
      </div>`;
    $$("[data-emp]").forEach((tr) => tr.onclick = () => openEmployee(tr.dataset.emp));
  }

  if (can("create_employee")) $("#add-emp").onclick = () => employeeModal(null, load);
  let t = null;
  $("#emp-search").oninput = () => { clearTimeout(t); t = setTimeout(load, 300); };
  $("#emp-status").onchange = load;
  load();
};

function empRow(e) {
  return `<tr data-emp="${e.id}" style="cursor:pointer;">
    <td>${e.id}</td>
    <td><strong>${esc(e.name)}</strong></td>
    <td>${esc(e.civil_id) || "—"}</td>
    <td>${esc(e.nationality) || "—"}</td>
    <td>${esc(e.job_title) || "—"}</td>
    <td>${fmtMoney(e.basic_salary)}</td>
    <td>${esc(e.company_name) || "—"}</td>
    <td>${statusBadge(e.status)}</td>
    <td><button class="btn sm ghost">عرض ›</button></td>
  </tr>`;
}

function companyPickerField(selectedId) {
  // يظهر للإدارة العليا فقط؛ غير ذلك تُحدَّد الشركة تلقائيًا
  if (!isAdmin()) return "";
  const opts = state.companies
    .filter((c) => c.status !== "archived")
    .map((c) => `<option value="${c.id}" ${selectedId == c.id ? "selected" : ""}>${esc(c.name)}</option>`).join("");
  return `<div class="field"><label>الشركة *</label>
    <select data-field="company_id"><option value="">— اختر —</option>${opts}</select></div>`;
}

async function employeeModal(emp, onDone) {
  const edit = !!emp;
  emp = emp || {};
  // قائمة التراخيص للشركة الفعّالة (لربط الموظف)
  const cid = edit ? emp.company_id : activeCompanyId();
  let licenses = [];
  if (cid || !isAdmin()) {
    const { data } = await apiGet("/api/licenses" + (cid ? "?company_id=" + cid : ""));
    licenses = Array.isArray(data) ? data : [];
  }
  const licOpts = `<option value="">— بدون —</option>` + licenses.map((l) =>
    `<option value="${l.id}" ${emp.license_id == l.id ? "selected" : ""}>${esc(l.name)}</option>`).join("");

  openModal(edit ? "تعديل موظف" : "إضافة موظف", `
    <div class="form-grid">
      ${edit ? "" : companyPickerField(cid)}
      <div class="field"><label>الاسم *</label><input data-field="name" value="${esc(emp.name)}"></div>
      <div class="field"><label>الرقم المدني</label><input data-field="civil_id" value="${esc(emp.civil_id)}"></div>
      <div class="field"><label>الجنسية</label><input data-field="nationality" value="${esc(emp.nationality)}"></div>
      <div class="field"><label>نوع العامل</label><input data-field="worker_type" value="${esc(emp.worker_type)}" placeholder="وافد / محلي"></div>
      <div class="field"><label>الوظيفة</label><input data-field="job_title" value="${esc(emp.job_title)}"></div>
      <div class="field"><label>الراتب الأساسي (د.ك)</label><input type="number" step="0.001" data-field="basic_salary" value="${emp.basic_salary || ""}"></div>
      <div class="field"><label>تاريخ التعيين</label><input type="date" data-field="hire_date" value="${fmtDateInput(emp.hire_date)}"></div>
      <div class="field"><label>نوع العقد</label>
        <select data-field="contract_type">
          <option value="indefinite" ${emp.contract_type!=="definite"?"selected":""}>غير محدد المدة</option>
          <option value="definite" ${emp.contract_type==="definite"?"selected":""}>محدد المدة</option>
        </select></div>
      <div class="field"><label>الترخيص</label><select data-field="license_id">${licOpts}</select></div>
    </div>
  `, `<button class="btn" id="save-emp">حفظ</button>
      <button class="btn secondary" onclick="closeModal()">إلغاء</button>`);

  $("#save-emp").onclick = async () => {
    const d = readForm($("#modal-body"));
    if (!d.name) { toast("اسم الموظف مطلوب", "error"); return; }
    if (!edit && isAdmin() && !d.company_id) { toast("اختر الشركة", "error"); return; }
    if (!edit && !isAdmin()) d.company_id = state.user.company_id;
    const r = edit ? await apiPut(`/api/employees/${emp.id}`, d) : await apiPost("/api/employees", d);
    if (r.ok) { closeModal(); toast("تم الحفظ"); onDone && onDone(); }
    else toast(r.data.error || "خطأ في الحفظ", "error");
  };
}

function fmtDateInput(s) { return s ? String(s).slice(0, 10) : ""; }

async function openEmployee(id) {
  const { ok, data: e } = await apiGet(`/api/employees/${id}`);
  if (!ok) { toast(e.error || "تعذّر الفتح", "error"); return; }

  const info = `
    <div class="detail-grid">
      ${detail("الاسم", e.name)}
      ${detail("الرقم المدني", e.civil_id)}
      ${detail("الجنسية", e.nationality)}
      ${detail("الوظيفة", e.job_title)}
      ${detail("نوع العامل", e.worker_type)}
      ${detail("الراتب الأساسي", fmtMoney(e.basic_salary))}
      ${detail("تاريخ التعيين", fmtDate(e.hire_date))}
      ${detail("نوع العقد", e.contract_type === "definite" ? "محدد المدة" : "غير محدد المدة")}
      ${detail("الحالة", statusBadgeText(e.status))}
      ${e.end_date ? detail("تاريخ انتهاء الخدمة", fmtDate(e.end_date)) : ""}
    </div>`;

  const permits = (e.permits || []);
  const permitsHtml = `
    <div class="tag-section-title">🪪 الإقامات وأذونات العمل</div>
    ${can("manage_permits") ? `<button class="btn sm" id="add-permit" style="margin-bottom:10px;">➕ إضافة إقامة/إذن</button>` : ""}
    ${permits.length ? `<table><thead><tr><th>النوع</th><th>الرقم</th><th>تبدأ</th><th>تنتهي</th><th>الحالة</th></tr></thead>
      <tbody>${permits.map((p) => `<tr>
        <td>${p.kind === "work_permit" ? "إذن عمل" : "إقامة"}</td>
        <td>${esc(p.number) || "—"}</td>
        <td>${fmtDate(p.start_date)}</td>
        <td>${fmtDate(p.expiry_date)} ${expiryFlag(p.expiry_date)}</td>
        <td>${statusBadge(p.status)}</td></tr>`).join("")}</tbody></table>`
      : `<div class="muted" style="padding:6px;">لا توجد سجلات</div>`}`;

  const deductions = (e.deductions || []);
  const dedHtml = `
    <div class="tag-section-title">💰 الخصومات</div>
    ${can("manage_deductions") ? `<button class="btn sm" id="add-ded" style="margin-bottom:10px;">➕ إضافة خصم</button>` : ""}
    ${deductions.length ? `<table><thead><tr><th>المبلغ</th><th>السبب</th><th>النوع</th><th>التاريخ</th></tr></thead>
      <tbody>${deductions.map((x) => `<tr><td>${fmtMoney(x.amount)}</td><td>${esc(x.reason)||"—"}</td>
        <td>${x.ded_type === "violation" ? "مخالفة" : "يدوي"}</td><td>${fmtDate(x.date)}</td></tr>`).join("")}</tbody></table>`
      : `<div class="muted" style="padding:6px;">لا توجد خصومات</div>`}`;

  const leaves = (e.leaves || []);
  const leavesHtml = `
    <div class="tag-section-title">🌴 الإجازات</div>
    ${can("manage_leaves") ? `<button class="btn sm" id="add-leave" style="margin-bottom:10px;">➕ تسجيل إجازة</button>` : ""}
    ${leaves.length ? `<table><thead><tr><th>النوع</th><th>من</th><th>إلى</th><th>الأيام</th><th>مدفوعة</th><th>الحالة</th><th></th></tr></thead>
      <tbody>${leaves.map((l) => `<tr><td>${esc(l.leave_type)||"—"}</td><td>${fmtDate(l.start_date)}</td>
        <td>${fmtDate(l.end_date)}</td><td>${l.days||0}</td><td>${l.paid ? "نعم":"لا"}</td>
        <td>${statusBadge(l.status)}</td>
        <td>${can("manage_leaves") && l.status==="pending" ? `
          <button class="btn sm" data-leave-ok="${l.id}">قبول</button>
          <button class="btn sm danger" data-leave-no="${l.id}">رفض</button>`:""}</td></tr>`).join("")}</tbody></table>`
      : `<div class="muted" style="padding:6px;">لا توجد إجازات</div>`}`;

  const actions = `
    <div style="margin-top:18px; display:flex; gap:8px; flex-wrap:wrap;">
      ${can("edit_employee") ? `<button class="btn ghost" id="edit-emp">✏️ تعديل البيانات</button>` : ""}
      ${can("edit_employee") && e.status === "active" ? `<button class="btn danger" id="end-service">⛔ إنهاء الخدمة</button>` : ""}
      ${can("calculate_eos") ? `<button class="btn secondary" id="calc-eos">🧮 حساب نهاية الخدمة</button>` : ""}
      ${can("view_reports") ? `<button class="btn ghost" id="salary-cert">📄 شهادة راتب (PDF)</button>` : ""}
      ${can("calculate_eos") ? `<button class="btn ghost" id="eos-pdf">📄 مخالصة (PDF)</button>` : ""}
      ${isAdmin() ? `<button class="btn secondary" id="transfer-emp">🔄 نقل لشركة أخرى</button>` : ""}
      ${can("delete_employee") ? `<button class="btn danger" id="del-emp">🗑️ حذف الموظف</button>` : ""}
    </div>`;

  openModal(`👤 ${e.name}`, info + permitsHtml + dedHtml + leavesHtml + actions, "");

  // أزرار الإجراءات
  const reload = () => openEmployee(id);
  if (can("edit_employee")) $("#edit-emp").onclick = () => employeeModal(e, reload);
  if (can("edit_employee") && e.status === "active") $("#end-service").onclick = () => endServiceModal(e, reload);
  if (can("calculate_eos")) $("#calc-eos").onclick = () => { closeModal(); navigate("eos"); setTimeout(() => prefillEos(e), 60); };
  if (can("view_reports")) $("#salary-cert").onclick = () => downloadCsv(`/api/reports/salary-certificate/${e.id}.pdf`, `salary_cert_${e.id}.pdf`);
  if (can("calculate_eos")) $("#eos-pdf").onclick = () => downloadCsv(`/api/reports/eos-settlement/${e.id}.pdf`, `eos_${e.id}.pdf`);
  if (isAdmin()) $("#transfer-emp").onclick = () => transferModal(e, reload);
  if (can("delete_employee")) $("#del-emp").onclick = async () => {
    if (!confirm("هل أنت متأكد من حذف الموظف وكل سجلاته؟ لا يمكن التراجع.")) return;
    const r = await apiDel(`/api/employees/${e.id}`);
    if (r.ok) { toast("تم حذف الموظف"); closeModal(); navigate("employees"); }
    else toast(r.data.error || "تعذّر الحذف", "error");
  };
  if (can("manage_permits")) $("#add-permit").onclick = () => permitModal(e, reload);
  if (can("manage_deductions")) $("#add-ded").onclick = () => deductionModal(e, reload);
  if (can("manage_leaves")) $("#add-leave").onclick = () => leaveModal(e, reload);
  $$("[data-leave-ok]").forEach((b) => b.onclick = () => leaveDecision(b.dataset.leaveOk, "approved", reload));
  $$("[data-leave-no]").forEach((b) => b.onclick = () => leaveDecision(b.dataset.leaveNo, "rejected", reload));
}

function detail(k, v) {
  return `<div class="detail-item"><span class="k">${esc(k)}</span><span class="v">${v === undefined || v === null || v === "" ? "—" : (String(v).startsWith("<") ? v : esc(v))}</span></div>`;
}
function statusBadgeText(s) { return statusBadge(s); }

function expiryFlag(d) {
  if (!d) return "";
  const days = Math.ceil((new Date(d) - new Date()) / 86400000);
  if (isNaN(days)) return "";
  if (days < 0) return badge("منتهي", "red");
  if (days <= 30) return badge(`باقٍ ${days}ي`, "amber");
  return "";
}

async function endServiceModal(emp, onDone) {
  const { data: reasons } = await apiGet("/api/eos/reasons");
  const opts = Object.entries(reasons || {}).map(([k, v]) =>
    `<option value="${k}">${esc(v)}</option>`).join("");
  openModal("إنهاء خدمة الموظف", `
    <p class="muted" style="margin-bottom:14px;">سيتم تغيير حالة الموظف وتسجيل سبب وتاريخ انتهاء الخدمة.</p>
    <div class="form-grid">
      <div class="field"><label>سبب انتهاء الخدمة</label><select data-field="reason">${opts}</select></div>
      <div class="field"><label>تاريخ انتهاء الخدمة</label><input type="date" data-field="end_date" value="${new Date().toISOString().slice(0,10)}"></div>
    </div>
  `, `<button class="btn danger" id="confirm-end">تأكيد إنهاء الخدمة</button>
      <button class="btn secondary" onclick="closeModal()">إلغاء</button>`);
  $("#confirm-end").onclick = async () => {
    const d = readForm($("#modal-body"));
    const r = await apiPost(`/api/employees/${emp.id}/end-service`, d);
    if (r.ok) { closeModal(); toast("تم إنهاء الخدمة"); onDone && onDone(); }
    else toast(r.data.error || "خطأ", "error");
  };
}

async function transferModal(emp, onDone) {
  const opts = state.companies.filter((c) => c.id != emp.company_id && c.status !== "archived")
    .map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("");
  openModal("نقل الموظف لشركة أخرى", `
    <div class="form-grid single">
      <div class="field"><label>الشركة الهدف *</label><select data-field="to_company_id"><option value="">— اختر —</option>${opts}</select></div>
      <div class="field"><label>ملاحظة</label><input data-field="note" placeholder="سبب النقل (اختياري)"></div>
    </div>
  `, `<button class="btn" id="do-transfer">نقل</button>
      <button class="btn secondary" onclick="closeModal()">إلغاء</button>`);
  $("#do-transfer").onclick = async () => {
    const d = readForm($("#modal-body"));
    if (!d.to_company_id) { toast("اختر الشركة الهدف", "error"); return; }
    const r = await apiPost(`/api/employees/${emp.id}/transfer`, d);
    if (r.ok) { closeModal(); toast("تم النقل"); onDone && onDone(); }
    else toast(r.data.error || "خطأ", "error");
  };
}

function permitModal(emp, onDone) {
  openModal("إضافة إقامة / إذن عمل", `
    <div class="form-grid">
      <div class="field"><label>النوع</label><select data-field="kind">
        <option value="residency">إقامة</option><option value="work_permit">إذن عمل</option></select></div>
      <div class="field"><label>الرقم</label><input data-field="number"></div>
      <div class="field"><label>تاريخ البداية</label><input type="date" data-field="start_date"></div>
      <div class="field"><label>تاريخ الانتهاء</label><input type="date" data-field="expiry_date"></div>
    </div>
  `, `<button class="btn" id="save-permit">حفظ</button>
      <button class="btn secondary" onclick="closeModal()">إلغاء</button>`);
  $("#save-permit").onclick = async () => {
    const d = readForm($("#modal-body")); d.employee_id = emp.id;
    const r = await apiPost("/api/permits", d);
    if (r.ok) { closeModal(); toast("تمت الإضافة"); onDone && onDone(); }
    else toast(r.data.error || "خطأ", "error");
  };
}

function deductionModal(emp, onDone) {
  openModal("إضافة خصم", `
    <div class="form-grid">
      <div class="field"><label>المبلغ (د.ك) *</label><input type="number" step="0.001" data-field="amount"></div>
      <div class="field"><label>النوع</label><select data-field="ded_type">
        <option value="manual">يدوي</option><option value="violation">مخالفة مالية</option></select></div>
      <div class="field full"><label>السبب</label><input data-field="reason"></div>
      <div class="field"><label>التاريخ</label><input type="date" data-field="date" value="${new Date().toISOString().slice(0,10)}"></div>
    </div>
  `, `<button class="btn" id="save-ded">حفظ</button>
      <button class="btn secondary" onclick="closeModal()">إلغاء</button>`);
  $("#save-ded").onclick = async () => {
    const d = readForm($("#modal-body")); d.employee_id = emp.id;
    if (!d.amount) { toast("أدخل المبلغ", "error"); return; }
    const r = await apiPost("/api/deductions", d);
    if (r.ok) { closeModal(); toast("تمت الإضافة"); onDone && onDone(); }
    else toast(r.data.error || "خطأ", "error");
  };
}

function leaveModal(emp, onDone) {
  openModal("تسجيل إجازة", `
    <div class="form-grid">
      <div class="field"><label>نوع الإجازة</label><input data-field="leave_type" placeholder="سنوية / مرضية..."></div>
      <div class="field"><label>عدد الأيام</label><input type="number" data-field="days"></div>
      <div class="field"><label>من</label><input type="date" data-field="start_date"></div>
      <div class="field"><label>إلى</label><input type="date" data-field="end_date"></div>
      <div class="field"><label>مدفوعة؟</label><select data-field="paid"><option value="true">نعم</option><option value="false">لا</option></select></div>
    </div>
  `, `<button class="btn" id="save-leave">حفظ</button>
      <button class="btn secondary" onclick="closeModal()">إلغاء</button>`);
  $("#save-leave").onclick = async () => {
    const d = readForm($("#modal-body"));
    d.employee_id = emp.id; d.paid = d.paid === "true" || d.paid === true;
    const r = await apiPost("/api/leaves", d);
    if (r.ok) { closeModal(); toast("تم التسجيل"); onDone && onDone(); }
    else toast(r.data.error || "خطأ", "error");
  };
}

async function leaveDecision(id, decision, onDone) {
  const r = await apiPost(`/api/leaves/${id}/decision`, { decision });
  if (r.ok) { toast(decision === "approved" ? "تم القبول" : "تم الرفض"); onDone && onDone(); }
  else toast(r.data.error || "خطأ", "error");
}

/* ---------- التراخيص ---------- */
VIEWS.licenses = async function (root) {
  const { data } = await apiGet("/api/licenses" + companyQuery());
  const rows = Array.isArray(data) ? data : [];
  root.innerHTML = `
    <div class="toolbar">
      ${can("manage_licenses") ? `<button class="btn" id="add-lic">➕ إضافة ترخيص</button>` : ""}
      <div class="spacer"></div>
    </div>
    <div class="card">
      <table>
        <thead><tr><th>#</th><th>الاسم</th><th>الرقم</th><th>الجهة</th><th>النوع</th>
          <th>الانتهاء</th><th>السعة (فعلي/مسموح)</th><th>الحالة</th>${can("manage_licenses")?"<th></th>":""}</tr></thead>
        <tbody>${rows.length ? rows.map(licRow).join("") :
          `<tr><td colspan="9"><div class="empty">لا توجد تراخيص</div></td></tr>`}</tbody>
      </table>
    </div>`;
  if (can("manage_licenses")) {
    $("#add-lic").onclick = () => licenseModal(null);
    $$("[data-edit-lic]").forEach((b) => b.onclick = () => licenseModal(rows.find((x) => x.id == b.dataset.editLic)));
    $$("[data-del-lic]").forEach((b) => b.onclick = async () => {
      if (!confirm("حذف هذا الترخيص؟ سيُفصل ربط الموظفين به.")) return;
      const r = await apiDel(`/api/licenses/${b.dataset.delLic}`);
      if (r.ok) { toast("تم الحذف"); navigate("licenses"); } else toast(r.data.error || "خطأ", "error");
    });
  }
};

function licRow(l) {
  const allowed = l.allowed_workers || 0;
  const actual = l.actual_workers || 0;
  const pct = allowed ? Math.min(100, Math.round(actual / allowed * 100)) : 0;
  const over = l.over_capacity;
  const cap = `
    <div>${actual} / ${allowed || "∞"} ${over ? badge("تجاوز", "red") : ""}</div>
    ${allowed ? `<div class="capacity-bar"><div class="capacity-fill ${over?"over":""}" style="width:${over?100:pct}%"></div></div>` : ""}`;
  return `<tr>
    <td>${l.id}</td>
    <td><strong>${esc(l.name)}</strong></td>
    <td>${esc(l.license_no) || "—"}</td>
    <td>${esc(l.issuing_authority) || "—"}</td>
    <td>${l.license_type === "sub" ? "فرعي" : "رئيسي"}</td>
    <td>${fmtDate(l.expiry_date)} ${expiryFlag(l.expiry_date)}</td>
    <td>${cap}</td>
    <td>${statusBadge(l.status)}</td>
    ${can("manage_licenses") ? `<td><div class="row-actions">
      <button class="btn sm ghost" data-edit-lic="${l.id}">تعديل</button>
      <button class="btn sm danger" data-del-lic="${l.id}">حذف</button></div></td>` : ""}
  </tr>`;
}

function licenseModal(l) {
  const edit = !!l; l = l || {};
  openModal(edit ? "تعديل ترخيص" : "إضافة ترخيص", `
    <div class="form-grid">
      ${edit ? "" : companyPickerField(activeCompanyId())}
      <div class="field"><label>اسم الترخيص *</label><input data-field="name" value="${esc(l.name)}"></div>
      <div class="field"><label>رقم الترخيص</label><input data-field="license_no" value="${esc(l.license_no)}"></div>
      <div class="field"><label>الجهة المصدرة</label><input data-field="issuing_authority" value="${esc(l.issuing_authority)}"></div>
      <div class="field"><label>النوع</label><select data-field="license_type">
        <option value="main" ${l.license_type!=="sub"?"selected":""}>رئيسي</option>
        <option value="sub" ${l.license_type==="sub"?"selected":""}>فرعي</option></select></div>
      <div class="field"><label>تاريخ الإصدار</label><input type="date" data-field="issue_date" value="${fmtDateInput(l.issue_date)}"></div>
      <div class="field"><label>تاريخ الانتهاء</label><input type="date" data-field="expiry_date" value="${fmtDateInput(l.expiry_date)}"></div>
      <div class="field"><label>عدد العمال المسموح</label><input type="number" data-field="allowed_workers" value="${l.allowed_workers||0}"></div>
      <div class="field full"><label>العنوان</label><input data-field="address" value="${esc(l.address)}"></div>
    </div>
  `, `<button class="btn" id="save-lic">حفظ</button>
      <button class="btn secondary" onclick="closeModal()">إلغاء</button>`);
  $("#save-lic").onclick = async () => {
    const d = readForm($("#modal-body"));
    if (!d.name) { toast("اسم الترخيص مطلوب", "error"); return; }
    if (!edit && isAdmin() && !d.company_id) { toast("اختر الشركة", "error"); return; }
    if (!edit && !isAdmin()) d.company_id = state.user.company_id;
    const r = edit ? await apiPut(`/api/licenses/${l.id}`, d) : await apiPost("/api/licenses", d);
    if (r.ok) { closeModal(); toast("تم الحفظ"); navigate("licenses"); }
    else toast(r.data.error || "خطأ", "error");
  };
}

/* ---------- المستخدمون والصلاحيات ---------- */
VIEWS.users = async function (root) {
  if (!state.catalog) {
    const { data } = await apiGet("/api/permissions-catalog");
    state.catalog = data || { permissions: {}, templates: {} };
  }
  const { data } = await apiGet("/api/users" + companyQuery());
  const rows = Array.isArray(data) ? data : [];
  root.innerHTML = `
    <div class="toolbar">
      <button class="btn" id="add-user">➕ إضافة مستخدم</button>
      <div class="spacer"></div>
    </div>
    <div class="card">
      <table>
        <thead><tr><th>#</th><th>المستخدم</th><th>الاسم</th><th>الدور</th><th>عدد الصلاحيات</th><th>الحالة</th><th>إجراءات</th></tr></thead>
        <tbody>${rows.length ? rows.map(userRow).join("") :
          `<tr><td colspan="7"><div class="empty">لا يوجد مستخدمون</div></td></tr>`}</tbody>
      </table>
    </div>`;
  $("#add-user").onclick = () => userModal(rows);
  $$("[data-perm-user]").forEach((b) => b.onclick = () => permissionsModal(rows.find((x) => x.id == b.dataset.permUser), rows));
  $$("[data-toggle-user]").forEach((b) => b.onclick = async () => {
    const r = await apiPost(`/api/users/${b.dataset.toggleUser}/toggle`, {});
    if (r.ok) { toast("تم التحديث"); navigate("users"); } else toast(r.data.error || "خطأ", "error");
  });
};

function userRow(u) {
  const permCount = u.role === "employee" ? (u.permissions || []).length : "—";
  return `<tr>
    <td>${u.id}</td>
    <td><strong>${esc(u.username)}</strong></td>
    <td>${esc(u.full_name) || "—"}</td>
    <td>${badge(ROLE_LABELS[u.role] || u.role, u.role === "super_admin" ? "blue" : (u.role === "company_manager" ? "green" : "gray"))}</td>
    <td>${u.role === "employee" ? permCount : `<span class="muted">كل الصلاحيات</span>`}</td>
    <td>${u.is_active ? badge("نشط", "green") : badge("معطّل", "gray")}</td>
    <td><div class="row-actions">
      ${u.role === "employee" ? `<button class="btn sm ghost" data-perm-user="${u.id}">الصلاحيات</button>` : ""}
      <button class="btn sm secondary" data-toggle-user="${u.id}">${u.is_active ? "تعطيل" : "تفعيل"}</button>
    </div></td>
  </tr>`;
}

function userModal(existing) {
  const perms = state.catalog.permissions || {};
  const roleOptions = isAdmin()
    ? `<option value="employee">موظف</option>
       <option value="company_manager">مدير شركة</option>
       <option value="super_admin">إدارة عليا</option>`
    : `<option value="employee">موظف</option>
       <option value="company_manager">مدير شركة</option>`;

  const permChecks = Object.entries(perms).map(([code, label]) =>
    `<label class="perm-check" data-perm-wrap><input type="checkbox" data-perm="${code}"> <span>${esc(label)}</span></label>`).join("");

  openModal("إضافة مستخدم", `
    <div class="form-grid">
      ${isAdmin() ? companyPickerField(activeCompanyId()) : ""}
      <div class="field"><label>اسم المستخدم *</label><input data-field="username"></div>
      <div class="field"><label>كلمة المرور *</label><input type="password" data-field="password"></div>
      <div class="field"><label>الاسم الكامل</label><input data-field="full_name"></div>
      <div class="field"><label>الدور</label><select data-field="role" id="role-sel">${roleOptions}</select></div>
    </div>
    <div id="perm-section">
      <div class="tag-section-title">الصلاحيات (للموظف فقط)</div>
      <p class="muted" style="font-size:12px;margin-bottom:8px;">مدير الشركة يملك كل الصلاحيات تلقائيًا. حدّد صلاحيات الموظف:</p>
      <div class="perm-list">${permChecks}</div>
    </div>
  `, `<button class="btn" id="save-user">إنشاء</button>
      <button class="btn secondary" onclick="closeModal()">إلغاء</button>`);

  const togglePermSection = () => {
    const role = $("#role-sel").value;
    $("#perm-section").style.display = role === "employee" ? "" : "none";
  };
  $("#role-sel").onchange = togglePermSection;
  togglePermSection();

  $$("[data-perm-wrap]").forEach((w) => {
    const cb = $("input", w);
    cb.onchange = () => w.classList.toggle("checked", cb.checked);
  });

  $("#save-user").onclick = async () => {
    const d = readForm($("#modal-body"));
    if (!d.username || !d.password) { toast("اسم المستخدم وكلمة المرور مطلوبان", "error"); return; }
    if (isAdmin() && d.role !== "super_admin" && !d.company_id) { toast("اختر الشركة", "error"); return; }
    if (!isAdmin()) d.company_id = state.user.company_id;
    d.permissions = $$('[data-perm]:checked', $("#modal-body")).map((c) => c.dataset.perm);
    const r = await apiPost("/api/users", d);
    if (r.ok) { closeModal(); toast("تم إنشاء المستخدم"); navigate("users"); }
    else toast(r.data.error || "خطأ", "error");
  };
}

function permissionsModal(user, allUsers) {
  const perms = state.catalog.permissions || {};
  const templates = state.catalog.templates || {};
  const current = new Set((user.permissions || []).map((p) => p.perm_code));
  const expiryMap = {};
  (user.permissions || []).forEach((p) => { if (p.expires_at) expiryMap[p.perm_code] = p.expires_at; });

  const permChecks = Object.entries(perms).map(([code, label]) =>
    `<label class="perm-check ${current.has(code) ? "checked" : ""}" data-perm-wrap>
       <input type="checkbox" data-perm="${code}" ${current.has(code) ? "checked" : ""}>
       <span>${esc(label)}</span>
     </label>`).join("");

  const tplOptions = `<option value="">— تطبيق قالب —</option>` +
    Object.entries(templates).map(([k, v]) => `<option value="${k}">${esc(v.label)}</option>`).join("");

  const copyOptions = `<option value="">— نسخ من مستخدم —</option>` +
    (allUsers || []).filter((x) => x.id !== user.id && x.role === "employee")
      .map((x) => `<option value="${x.id}">${esc(x.username)}</option>`).join("");

  openModal(`صلاحيات: ${user.username}`, `
    <div class="toolbar">
      <select id="tpl-sel">${tplOptions}</select>
      <select id="copy-sel">${copyOptions}</select>
      <div class="spacer"></div>
      <label class="perm-check" style="cursor:pointer;"><input type="checkbox" id="exp-toggle"> صلاحية مؤقتة</label>
      <input type="date" id="exp-date" class="hidden">
    </div>
    <div class="perm-list" id="perm-list">${permChecks}</div>
    <p class="muted" style="font-size:11px;margin-top:10px;">عند تفعيل "صلاحية مؤقتة" وتحديد تاريخ، تُطبَّق مدة الانتهاء على الصلاحيات المحددة حديثًا.</p>
  `, `<button class="btn" id="save-perms">حفظ الصلاحيات</button>
      <button class="btn secondary" onclick="closeModal()">إلغاء</button>`);

  const wraps = $$("[data-perm-wrap]");
  wraps.forEach((w) => {
    const cb = $("input", w);
    cb.onchange = () => w.classList.toggle("checked", cb.checked);
  });

  $("#tpl-sel").onchange = (e) => {
    const tpl = templates[e.target.value];
    if (!tpl) return;
    const set = new Set(tpl.perms);
    wraps.forEach((w) => {
      const cb = $("input", w);
      cb.checked = set.has(cb.dataset.perm);
      w.classList.toggle("checked", cb.checked);
    });
  };

  $("#copy-sel").onchange = async (e) => {
    if (!e.target.value) return;
    if (!confirm("نسخ صلاحيات هذا المستخدم؟ سيستبدل التحديد الحالي.")) { e.target.value = ""; return; }
    const r = await apiPost(`/api/users/${user.id}/copy-permissions`, { source_user_id: e.target.value });
    if (r.ok) { closeModal(); toast("تم نسخ الصلاحيات"); navigate("users"); }
    else toast(r.data.error || "خطأ", "error");
  };

  $("#exp-toggle").onchange = (e) => { $("#exp-date").classList.toggle("hidden", !e.target.checked); };

  $("#save-perms").onclick = async () => {
    const useExp = $("#exp-toggle").checked;
    const expDate = $("#exp-date").value;
    const selected = $$('[data-perm]:checked', $("#perm-list")).map((c) => c.dataset.perm);
    const payload = selected.map((code) => {
      // الإبقاء على تاريخ سابق إن وُجد، أو تطبيق تاريخ جديد
      let exp = expiryMap[code] || null;
      if (useExp && expDate) exp = expDate;
      return { code, expires_at: exp };
    });
    const r = await apiPut(`/api/users/${user.id}/permissions`, { permissions: payload });
    if (r.ok) { closeModal(); toast("تم حفظ الصلاحيات"); navigate("users"); }
    else toast(r.data.error || "خطأ", "error");
  };
}

/* ---------- حاسبة نهاية الخدمة ---------- */
VIEWS.eos = async function (root) {
  const [{ data: reasons }, empsRes] = await Promise.all([
    apiGet("/api/eos/reasons"),
    apiGet("/api/employees" + companyQuery()),
  ]);
  const emps = Array.isArray(empsRes.data) ? empsRes.data : [];
  const reasonOpts = Object.entries(reasons || {}).map(([k, v]) =>
    `<option value="${k}">${esc(v)}</option>`).join("");
  const empOpts = `<option value="">— إدخال يدوي —</option>` +
    emps.map((e) => `<option value="${e.id}">${esc(e.name)} (${esc(e.company_name || "")})</option>`).join("");

  root.innerHTML = `
    <div class="card">
      <div class="card-header"><h2>🧮 حساب مكافأة نهاية الخدمة (قانون الكويت 6/2010)</h2></div>
      <div class="form-grid">
        <div class="field full"><label>اختيار موظف (اختياري)</label><select id="eos-emp" data-field="employee_id">${empOpts}</select></div>
        <div class="field"><label>الراتب الأساسي الشهري (د.ك)</label><input type="number" step="0.001" id="eos-salary" data-field="basic_salary"></div>
        <div class="field"><label>سبب انتهاء الخدمة</label><select id="eos-reason" data-field="reason">${reasonOpts}</select></div>
        <div class="field"><label>تاريخ التعيين</label><input type="date" id="eos-hire" data-field="hire_date"></div>
        <div class="field"><label>تاريخ انتهاء الخدمة</label><input type="date" id="eos-end" data-field="end_date" value="${new Date().toISOString().slice(0,10)}"></div>
        <div class="field"><label>نوع العقد</label><select id="eos-contract" data-field="contract_type">
          <option value="indefinite">غير محدد المدة</option><option value="definite">محدد المدة</option></select></div>
        <div class="field"><label>رصيد إجازات غير مستخدمة (أيام)</label><input type="number" id="eos-leave" data-field="unused_leave_days" value="0"></div>
        <div class="field"><label>مقسوم اليوم</label><select id="eos-divisor" data-field="day_divisor">
          <option value="26">26 (المعتمد غالبًا)</option><option value="30">30</option></select></div>
        <div class="field"><label>الحد الأقصى (أشهر)</label><input type="number" id="eos-max" data-field="max_months" value="18"></div>
      </div>
      <div style="margin-top:16px;"><button class="btn" id="eos-calc">احسب المكافأة</button></div>
    </div>
    <div id="eos-output"></div>`;

  // عند اختيار موظف نملأ الحقول من بياناته
  $("#eos-emp").onchange = async (e) => {
    if (!e.target.value) return;
    const { ok, data: emp } = await apiGet(`/api/employees/${e.target.value}`);
    if (!ok) return;
    $("#eos-salary").value = emp.basic_salary || "";
    $("#eos-hire").value = fmtDateInput(emp.hire_date);
    if (emp.end_date) $("#eos-end").value = fmtDateInput(emp.end_date);
    $("#eos-contract").value = emp.contract_type === "definite" ? "definite" : "indefinite";
    if (emp.end_reason) $("#eos-reason").value = emp.end_reason;
  };

  $("#eos-calc").onclick = async () => {
    const d = readForm(root);
    // تنظيف: حقول رقمية
    if (d.employee_id) {
      // عند اختيار موظف نرسل المعرف فقط ونترك الباقي للخادم إن لم يُعدّل
    } else if (!d.basic_salary || !d.hire_date) {
      toast("أدخل الراتب وتاريخ التعيين", "error"); return;
    }
    const r = await apiPost("/api/eos/calculate", d);
    if (!r.ok) { toast(r.data.error || "تعذّر الحساب", "error"); return; }
    renderEosResult($("#eos-output"), r.data);
  };
};

function prefillEos(emp) {
  const sel = $("#eos-emp");
  if (sel) { sel.value = emp.id; sel.dispatchEvent(new Event("change")); }
}

function renderEosResult(root, res) {
  const s = res.service;
  root.innerHTML = `
    <div class="card">
      <div class="card-header"><h2>📄 نتيجة الحساب</h2>
        <span class="muted">${esc(res.inputs.reason_label)}</span></div>
      <div class="eos-result">
        <div class="eos-row"><span>مدة الخدمة</span><strong>${esc(s.text)} (${s.decimal_years} سنة)</strong></div>
        <div class="eos-row"><span>أجر اليوم (الراتب ÷ ${res.inputs.day_divisor})</span><strong>${fmtMoney(res.daily_wage)}</strong></div>
        <div class="eos-row"><span>مكافأة أول 5 سنوات (15 يوم/سنة)</span><strong>${fmtMoney(res.first_period_amount)}</strong></div>
        <div class="eos-row"><span>مكافأة ما بعد 5 سنوات (30 يوم/سنة)</span><strong>${fmtMoney(res.after_period_amount)}</strong></div>
        <div class="eos-row"><span>إجمالي المكافأة قبل نسبة الاستحقاق</span><strong>${fmtMoney(res.full_indemnity)} ${res.cap_applied ? badge("طُبّق السقف", "amber") : ""}</strong></div>
        <div class="eos-row"><span>نسبة الاستحقاق</span><strong>${Math.round(res.entitlement_factor * 100)}%</strong></div>
        <div class="eos-row"><span>قيمة المكافأة المستحقة</span><strong>${fmtMoney(res.indemnity)}</strong></div>
        <div class="eos-row"><span>بدل رصيد الإجازات</span><strong>${fmtMoney(res.leave_payout)}</strong></div>
        <div class="eos-row" style="margin-top:6px;"><span class="eos-total">الإجمالي النهائي</span><span class="eos-total">${fmtMoney(res.total_settlement)}</span></div>
        <div style="margin-top:10px;font-size:12px;color:var(--primary-dark);">${esc(res.factor_note)}</div>
        <div class="eos-disclaimer">${esc(res.disclaimer)}</div>
      </div>
    </div>`;
}

/* ---------- التقارير ---------- */
VIEWS.reports = async function (root) {
  const { data: summary } = await apiGet("/api/reports/summary" + companyQuery());
  const cq = companyQuery();
  root.innerHTML = `
    <div class="stats-grid">
      <div class="stat-card"><div class="value">${summary.total_employees ?? 0}</div><div class="label">إجمالي الموظفين</div></div>
      <div class="stat-card"><div class="value">${summary.active_employees ?? 0}</div><div class="label">الموظفون النشطون</div></div>
      <div class="stat-card"><div class="value">${summary.total_licenses ?? 0}</div><div class="label">التراخيص</div></div>
      <div class="stat-card danger"><div class="value">${summary.expired_permits ?? 0}</div><div class="label">إقامات منتهية</div></div>
      <div class="stat-card danger"><div class="value">${summary.expired_licenses ?? 0}</div><div class="label">تراخيص منتهية</div></div>
      <div class="stat-card warning"><div class="value">${summary.alerts_count ?? 0}</div><div class="label">تنبيهات</div></div>
    </div>
    <div class="card" id="eos-liability-card">
      <div class="card-header"><h2>🏦 إجمالي التزامات نهاية الخدمة</h2></div>
      <div class="empty">جارٍ الحساب…</div>
    </div>
    <div class="card">
      <div class="card-header"><h2>📤 تصدير التقارير</h2></div>
      <p class="muted" style="margin-bottom:16px;">تُصدَّر الملفات بترميز يدعم العربية (CSV/Excel)، والمستندات بصيغة PDF.</p>
      <div style="display:flex; gap:12px; flex-wrap:wrap;">
        ${can("export_reports") ? `
          <button class="btn" id="exp-emps">⬇️ الموظفون (CSV)</button>
          <button class="btn secondary" id="exp-emps-xlsx">⬇️ الموظفون (Excel)</button>
          <button class="btn secondary" id="exp-expiring">⬇️ المنتهيات (CSV)</button>
          <button class="btn secondary" id="exp-expiring-xlsx">⬇️ المنتهيات (Excel)</button>
        ` : `<p class="muted">لا تملك صلاحية تصدير التقارير.</p>`}
      </div>
    </div>`;

  // تقرير الالتزامات
  (async () => {
    const card = $("#eos-liability-card");
    const { ok, data } = await apiGet("/api/eos/liability" + cq);
    if (!ok) { card.querySelector(".empty").textContent = "تعذّر حساب الالتزامات"; return; }
    const rows = (data.breakdown || []).slice(0, 15);
    card.innerHTML = `
      <div class="card-header"><h2>🏦 إجمالي التزامات نهاية الخدمة</h2></div>
      <div class="stats-grid" style="margin-bottom:14px;">
        <div class="stat-card"><div class="value">${fmtMoney(data.total_liability)}</div><div class="label">إجمالي الالتزام التقديري</div></div>
        <div class="stat-card"><div class="value">${data.employees ?? 0}</div><div class="label">موظفون محتسبون</div></div>
      </div>
      <table>
        <thead><tr><th>الموظف</th><th>الشركة</th><th>مدة الخدمة</th><th>المكافأة التقديرية</th></tr></thead>
        <tbody>${rows.length ? rows.map((x) => `<tr>
          <td>${esc(x.name)}</td><td>${esc(x.company)}</td><td>${esc(x.service)}</td>
          <td>${fmtMoney(x.indemnity)}</td></tr>`).join("") :
          `<tr><td colspan="4"><div class="empty">لا بيانات</div></td></tr>`}</tbody>
      </table>`;
  })();

  if (can("export_reports")) {
    $("#exp-emps").onclick = () => downloadCsv("/api/reports/export/employees" + cq, "employees.csv");
    $("#exp-emps-xlsx").onclick = () => downloadCsv("/api/reports/export/employees" + (cq ? cq + "&" : "?") + "format=xlsx", "employees.xlsx");
    $("#exp-expiring").onclick = () => downloadCsv("/api/reports/export/expiring" + cq, "expiring.csv");
    $("#exp-expiring-xlsx").onclick = () => downloadCsv("/api/reports/export/expiring" + (cq ? cq + "&" : "?") + "format=xlsx", "expiring.xlsx");
  }
};

/* ---------- مسيّر الرواتب ---------- */
VIEWS.payroll = async function (root) {
  const cq = companyQuery();
  const { data } = await apiGet("/api/payroll/runs" + cq);
  const runs = Array.isArray(data) ? data : [];
  root.innerHTML = `
    ${can("run_payroll") ? `
    <div class="card">
      <div class="card-header"><h2>▶️ تشغيل مسيّر رواتب جديد</h2></div>
      <div style="display:flex; gap:12px; align-items:flex-end; flex-wrap:wrap;">
        <div class="field"><label>الشهر (YYYY-MM)</label><input type="month" id="pay-period"></div>
        <button class="btn" id="run-pay">تشغيل المسيّر</button>
      </div>
    </div>` : ""}
    <div class="card">
      <div class="card-header"><h2>📑 مسيّرات سابقة</h2></div>
      <table>
        <thead><tr><th>#</th><th>الشهر</th><th>الحالة</th><th>التاريخ</th><th></th></tr></thead>
        <tbody>${runs.length ? runs.map((r) => `<tr>
          <td>${r.id}</td><td>${esc(r.period)}</td><td>${badge(r.status, "blue")}</td>
          <td>${fmtDate(r.created_at)}</td>
          <td><button class="btn sm ghost" data-run="${r.id}">عرض ›</button></td>
        </tr>`).join("") : `<tr><td colspan="5"><div class="empty">لا مسيّرات بعد</div></td></tr>`}</tbody>
      </table>
    </div>
    <div id="pay-detail"></div>`;

  if (can("run_payroll")) {
    $("#run-pay").onclick = async () => {
      const period = $("#pay-period").value;
      if (!period) { toast("اختر الشهر", "error"); return; }
      const cid = activeCompanyId();
      if (!cid) { toast("اختر شركة من الأعلى أولًا", "error"); return; }
      const r = await apiPost("/api/payroll/run", { company_id: cid, period });
      if (r.ok) { toast("تم تشغيل المسيّر ✅"); navigate("payroll"); }
      else toast(r.data.error || "فشل التشغيل", "error");
    };
  }
  $$("[data-run]").forEach((b) => b.onclick = () => showPayrollRun(b.dataset.run));
};

async function showPayrollRun(runId) {
  const { ok, data } = await apiGet("/api/payroll/runs/" + runId);
  if (!ok) { toast("تعذّر العرض", "error"); return; }
  const slips = data.payslips || [];
  $("#pay-detail").innerHTML = `
    <div class="card">
      <div class="card-header"><h2>قسائم مسيّر #${runId} — ${esc(data.run.period)}</h2></div>
      <table>
        <thead><tr><th>الموظف</th><th>الأساسي</th><th>البدلات</th><th>الإضافي</th><th>الخصومات</th><th>التأمينات</th><th>الصافي</th></tr></thead>
        <tbody>${slips.map((s) => `<tr>
          <td>${esc(s.employee_name)}</td><td>${fmtMoney(s.basic_salary)}</td>
          <td>${fmtMoney(s.allowances)}</td><td>${fmtMoney(s.overtime_pay)}</td>
          <td>${fmtMoney(s.deductions)}</td><td>${fmtMoney(s.gosi)}</td>
          <td><strong>${fmtMoney(s.net)}</strong></td></tr>`).join("")}</tbody>
      </table>
    </div>`;
}

/* ---------- سجل التدقيق ---------- */
VIEWS.audit = async function (root) {
  const { data } = await apiGet("/api/audit" + companyQuery());
  const rows = Array.isArray(data) ? data : [];
  root.innerHTML = `
    <div class="card">
      <div class="card-header"><h2>🛡️ سجل التدقيق (آخر 200 عملية)</h2></div>
      <table>
        <thead><tr><th>#</th><th>التاريخ</th><th>المستخدم</th><th>العملية</th><th>الكيان</th><th>تفاصيل</th></tr></thead>
        <tbody>${rows.length ? rows.map((a) => `<tr>
          <td>${a.id}</td>
          <td style="white-space:nowrap;">${esc((a.created_at || "").replace("T", " ").slice(0, 16))}</td>
          <td>${esc(a.username) || "—"}</td>
          <td>${badge(actionLabel(a.action), "blue")}</td>
          <td>${esc(a.entity_type) || "—"}${a.entity_id ? " #" + a.entity_id : ""}</td>
          <td>${esc(a.details) || "—"}</td>
        </tr>`).join("") : `<tr><td colspan="6"><div class="empty">لا توجد سجلات</div></td></tr>`}</tbody>
      </table>
    </div>`;
};

const ACTION_LABELS = {
  login: "دخول", change_password: "تغيير كلمة المرور", create_company: "إنشاء شركة",
  update_company: "تعديل شركة", toggle_company: "تفعيل/تعطيل شركة", archive_company: "أرشفة شركة",
  create_user: "إنشاء مستخدم", set_permissions: "ضبط صلاحيات", copy_permissions: "نسخ صلاحيات",
  create_employee: "إضافة موظف", update_employee: "تعديل موظف", end_service: "إنهاء خدمة",
  transfer_employee: "نقل موظف", create_license: "إضافة ترخيص", update_license: "تعديل ترخيص",
  delete_license: "حذف ترخيص", create_permit: "إضافة إقامة/إذن", update_permit: "تعديل إقامة/إذن",
  upload_document: "رفع مستند", create_deduction: "إضافة خصم", create_leave: "تسجيل إجازة",
  leave_decision: "قرار إجازة", delete_employee: "حذف موظف", delete_license: "حذف ترخيص",
  delete_permit: "حذف إقامة/إذن", delete_document: "حذف مستند", delete_deduction: "حذف خصم",
  create_department: "إنشاء قسم", update_department: "تعديل قسم", delete_department: "حذف قسم",
  create_allowance: "إضافة بدل", create_attendance: "تسجيل حضور", create_disciplinary: "جزاء تأديبي",
  create_asset: "تسجيل عهدة", create_review: "تقييم أداء", run_payroll: "تشغيل مسيّر رواتب",
  enable_2fa: "تفعيل مصادقة ثنائية", disable_2fa: "تعطيل مصادقة ثنائية", toggle_user: "تفعيل/تعطيل مستخدم",
};
function actionLabel(a) { return ACTION_LABELS[a] || a || "—"; }

/* ---------- الإعدادات ---------- */
VIEWS.settings = async function (root) {
  const u = state.user;
  root.innerHTML = `
    <div class="card" style="max-width:560px;">
      <div class="card-header"><h2>👤 بيانات الحساب</h2></div>
      <div class="detail-grid">
        ${detail("اسم المستخدم", u.username)}
        ${detail("الاسم الكامل", u.full_name)}
        ${detail("الدور", ROLE_LABELS[u.role] || u.role)}
        ${detail("الشركة", u.company ? u.company.name : "— (إدارة عليا)")}
      </div>
    </div>
    <div class="card" style="max-width:560px;">
      <div class="card-header"><h2>🔒 تغيير كلمة المرور</h2></div>
      <div id="pw-msg"></div>
      <div class="form-grid single">
        <div class="field"><label>كلمة المرور الحالية</label><input type="password" data-field="old_password"></div>
        <div class="field"><label>كلمة المرور الجديدة</label><input type="password" data-field="new_password"></div>
        <div class="field"><label>تأكيد كلمة المرور الجديدة</label><input type="password" id="pw-confirm"></div>
      </div>
      <div style="margin-top:14px;"><button class="btn" id="change-pw">تغيير كلمة المرور</button></div>
    </div>
    <div class="card" style="max-width:560px;">
      <div class="card-header"><h2>🔐 المصادقة الثنائية (2FA)</h2></div>
      <div id="twofa-box">
        <p class="muted">${u.totp_enabled ? "المصادقة الثنائية مفعّلة على حسابك." : "أضف طبقة حماية إضافية عبر تطبيق مصادقة (Google Authenticator)."}</p>
        ${u.totp_enabled
          ? `<button class="btn danger" id="twofa-disable">تعطيل المصادقة الثنائية</button>`
          : `<button class="btn" id="twofa-setup">تفعيل المصادقة الثنائية</button>`}
        <div id="twofa-setup-area" style="margin-top:14px;"></div>
      </div>
    </div>`;

  if ($("#twofa-disable")) $("#twofa-disable").onclick = async () => {
    const r = await apiPost("/api/2fa/disable", {});
    if (r.ok) { toast("تم تعطيل المصادقة الثنائية"); state.user.totp_enabled = false; navigate("settings"); }
  };
  if ($("#twofa-setup")) $("#twofa-setup").onclick = async () => {
    const r = await apiPost("/api/2fa/setup", {});
    if (!r.ok) { toast(r.data.error || "تعذّر التفعيل", "error"); return; }
    $("#twofa-setup-area").innerHTML = `
      <div class="field"><label>المفتاح السري (أدخله في تطبيق المصادقة)</label>
        <input type="text" value="${esc(r.data.secret)}" readonly></div>
      <div class="field"><label>أدخل الرمز المكوّن من 6 أرقام للتأكيد</label>
        <input type="text" id="twofa-otp" maxlength="6"></div>
      <button class="btn" id="twofa-enable">تأكيد وتفعيل</button>`;
    $("#twofa-enable").onclick = async () => {
      const otp = $("#twofa-otp").value.trim();
      const rr = await apiPost("/api/2fa/enable", { otp });
      if (rr.ok) { toast("تم تفعيل المصادقة الثنائية ✅"); state.user.totp_enabled = true; navigate("settings"); }
      else toast(rr.data.error || "رمز غير صحيح", "error");
    };
  };

  $("#change-pw").onclick = async () => {
    const d = readForm($("#view"));
    const confirm2 = $("#pw-confirm").value;
    const msg = $("#pw-msg");
    if (!d.old_password || !d.new_password) { msg.innerHTML = `<div class="error-msg">أدخل كلمتي المرور</div>`; return; }
    if (d.new_password.length < 8) { msg.innerHTML = `<div class="error-msg">كلمة المرور الجديدة 8 أحرف على الأقل وتجمع أحرفًا وأرقامًا</div>`; return; }
    if (d.new_password !== confirm2) { msg.innerHTML = `<div class="error-msg">تأكيد كلمة المرور غير مطابق</div>`; return; }
    const r = await apiPost("/api/change-password", d);
    if (r.ok) { msg.innerHTML = `<div class="success-msg">تم تغيير كلمة المرور بنجاح ✅</div>`;
      $$('[data-field]', $("#view")).forEach((i) => i.value = ""); $("#pw-confirm").value = ""; }
    else msg.innerHTML = `<div class="error-msg">${esc(r.data.error || "خطأ")}</div>`;
  };
};

/* ----------------------------------------------------------------------------
   9) ربط الأحداث العامة + الإقلاع
---------------------------------------------------------------------------- */
window.closeModal = closeModal; // لاستخدامها في onclick داخل المودال

document.addEventListener("DOMContentLoaded", () => {
  $("#login-btn").onclick = doLogin;
  $("#logout-btn").onclick = doLogout;
  ["login-username", "login-password"].forEach((id) => {
    $("#" + id).addEventListener("keydown", (e) => { if (e.key === "Enter") doLogin(); });
  });
  boot();
});
