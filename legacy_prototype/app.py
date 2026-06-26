# -*- coding: utf-8 -*-
"""
نظام إدارة الموارد البشرية متعدد الشركات (الكويت) — التطبيق الرئيسي (Flask).
يشغّل واجهة REST API + يخدم واجهة المستخدم (SPA).

طبقات الأمان: تحصين الكوكي، حماية CSRF، رؤوس أمنية، حدّ معدّل الطلبات،
التحقق من رفع الملفات، قفل الحساب، وسياسة كلمات مرور.
"""
import csv
import io
import json
import logging
import os
import secrets
import time
from collections import defaultdict
from datetime import date, datetime, timedelta

from flask import Flask, Response, jsonify, render_template, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import db
import leave_service
import notify
import payroll as payroll_engine
from alerts import generate_alerts
from config import config
from eos import TERMINATION_REASONS, calculate_eos, notice_pay
from permissions import (
    PERMISSION_TEMPLATES,
    PERMISSIONS,
    current_user,
    get_user_permissions,
    has_permission,
    login_required,
    require_perm,
    scope_company_id,
    super_admin_required,
)

try:
    import pyotp
    _HAS_PYOTP = True
except Exception:
    _HAS_PYOTP = False

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("hrms")

BASE_DIR = os.path.dirname(__file__)
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
SECRET_FILE = os.path.join(BASE_DIR, "instance", ".secret_key")

app = Flask(__name__)


def _load_secret():
    if config.SECRET_KEY:
        return config.SECRET_KEY
    os.makedirs(os.path.dirname(SECRET_FILE), exist_ok=True)
    if os.path.exists(SECRET_FILE):
        return open(SECRET_FILE).read().strip()
    key = secrets.token_hex(32)
    with open(SECRET_FILE, "w") as f:
        f.write(key)
    return key


app.secret_key = _load_secret()
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=config.SESSION_COOKIE_SECURE,
)
app.permanent_session_lifetime = timedelta(hours=config.SESSION_LIFETIME_HOURS)
app.teardown_appcontext(db.close_db)

MAX_LOGIN_ATTEMPTS = config.MAX_LOGIN_ATTEMPTS
LOCK_MINUTES = config.LOCK_MINUTES

# ---------------------------------------------------------------------------
# حدّ معدّل الطلبات (Rate limiting) — في الذاكرة، نافذة دقيقة واحدة
# ---------------------------------------------------------------------------
_rate_buckets = defaultdict(list)


def _rate_limited(key, limit):
    now = time.time()
    window = [t for t in _rate_buckets[key] if now - t < 60]
    window.append(now)
    _rate_buckets[key] = window
    return len(window) > limit


# ---------------------------------------------------------------------------
# CSRF (Double-submit عبر رأس X-CSRF-Token) + خمول الجلسة
# ---------------------------------------------------------------------------
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSRF_EXEMPT = {"/api/login"}


def _get_csrf_token():
    tok = session.get("csrf_token")
    if not tok:
        tok = secrets.token_hex(32)
        session["csrf_token"] = tok
    return tok


@app.before_request
def _security_gate():
    # خمول الجلسة
    if session.get("uid"):
        last = session.get("last_seen")
        now = time.time()
        if last and config.SESSION_IDLE_MINUTES and (now - last) > config.SESSION_IDLE_MINUTES * 60:
            session.clear()
            return jsonify({"error": "انتهت الجلسة بسبب الخمول. سجّل الدخول مجددًا."}), 401
        session["last_seen"] = now

    if app.testing or not config.CSRF_ENABLED:
        return
    # حماية CSRF لطرق التعديل على مسارات الـ API
    if request.method not in SAFE_METHODS and request.path.startswith("/api/"):
        if request.path in CSRF_EXEMPT:
            return
        sent = request.headers.get("X-CSRF-Token", "")
        if not sent or sent != session.get("csrf_token"):
            return jsonify({"error": "رمز الحماية (CSRF) غير صالح. حدّث الصفحة."}), 403


@app.after_request
def _security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    resp.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
    if config.SESSION_COOKIE_SECURE:
        resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return resp


# ---------------------------------------------------------------------------
# معالجات أخطاء موحّدة (JSON)
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def _404(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "المسار غير موجود"}), 404
    return render_template("index.html")


@app.errorhandler(413)
def _413(e):
    return jsonify({"error": "حجم الملف يتجاوز الحد المسموح"}), 413


@app.errorhandler(500)
def _500(e):
    log.exception("خطأ داخلي")
    return jsonify({"error": "حدث خطأ داخلي في الخادم"}), 500


# ---------------------------------------------------------------------------
# أدوات مساعدة
# ---------------------------------------------------------------------------
def body():
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form.to_dict()


def me():
    return current_user()


def ensure_company_access(entity_company_id):
    u = me()
    if u["role"] == "super_admin":
        return True
    return u["company_id"] == entity_company_id


def deny():
    return jsonify({"error": "غير مصرح بالوصول لبيانات هذه الشركة"}), 403


def _int_or_none(v):
    try:
        return int(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# الصفحة الرئيسية + الملفات
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/uploads/<path:fname>")
@login_required
def uploaded_file(fname):
    # تفويض: لا يُخدم الملف إلا إذا كان لمستند ضمن نطاق المستخدم
    doc = db.query("SELECT * FROM documents WHERE file_path=?", (fname,), one=True)
    if doc and not ensure_company_access(doc["company_id"]):
        return deny()
    return send_from_directory(UPLOAD_DIR, fname, as_attachment=True)


# ===========================================================================
# المصادقة (Authentication)
# ===========================================================================
@app.post("/api/login")
def api_login():
    ip = request.remote_addr or "?"
    if not app.testing and _rate_limited(f"login:{ip}", config.LOGIN_RATE_LIMIT_PER_MINUTE):
        return jsonify({"error": "محاولات كثيرة جدًا. انتظر قليلًا."}), 429

    data = body()
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    row = db.query("SELECT * FROM users WHERE username=?", (username,), one=True)

    generic_err = jsonify({"error": "بيانات الدخول غير صحيحة"}), 401
    if not row:
        return generic_err
    user = db.row_to_dict(row)

    if user["locked_until"]:
        try:
            if datetime.fromisoformat(user["locked_until"]) > datetime.now():
                return jsonify({"error": "الحساب محظور مؤقتًا بسبب محاولات فاشلة. حاول لاحقًا."}), 423
        except ValueError:
            pass

    # حساب معطّل: نُرجع رسالة عامة لمنع كشف الحسابات (User Enumeration)
    if not user["is_active"]:
        return generic_err

    if not check_password_hash(user["password_hash"], password):
        attempts = user["failed_attempts"] + 1
        locked = None
        if attempts >= MAX_LOGIN_ATTEMPTS:
            locked = (datetime.now() + timedelta(minutes=LOCK_MINUTES)).isoformat()
            attempts = 0
        db.execute("UPDATE users SET failed_attempts=?, locked_until=? WHERE id=?",
                   (attempts, locked, user["id"]))
        if locked:
            return jsonify({"error": f"تم حظر الحساب مؤقتًا لمدة {LOCK_MINUTES} دقيقة بعد عدة محاولات فاشلة."}), 401
        return generic_err

    # مصادقة ثنائية إن كانت مفعّلة
    if user.get("totp_enabled") and _HAS_PYOTP:
        otp = (data.get("otp") or "").strip()
        if not otp:
            return jsonify({"needs_2fa": True}), 200
        if not pyotp.TOTP(user["totp_secret"]).verify(otp, valid_window=1):
            return jsonify({"error": "رمز التحقق غير صحيح", "needs_2fa": True}), 401

    db.execute("UPDATE users SET failed_attempts=0, locked_until=NULL, last_login=? WHERE id=?",
               (datetime.now().isoformat(), user["id"]))
    session.permanent = True
    session["uid"] = user["id"]
    session["last_seen"] = time.time()
    token = _get_csrf_token()
    db.log_action(user["company_id"], user, "login")
    return jsonify({"csrf_token": token, **_user_payload(user)})


@app.post("/api/logout")
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/me")
def api_me():
    u = me()
    if not u:
        return jsonify({"authenticated": False}), 200
    return jsonify({"authenticated": True, "csrf_token": _get_csrf_token(),
                    "unread_notifications": notify.unread_count(u["id"]), **_user_payload(u)})


@app.get("/api/csrf")
@login_required
def api_csrf():
    return jsonify({"csrf_token": _get_csrf_token()})


def _user_payload(user):
    company = None
    if user["company_id"]:
        c = db.query("SELECT id, name, status FROM companies WHERE id=?", (user["company_id"],), one=True)
        company = db.row_to_dict(c)
    return {
        "id": user["id"],
        "username": user["username"],
        "full_name": user["full_name"],
        "role": user["role"],
        "company_id": user["company_id"],
        "company": company,
        "employee_id": user.get("employee_id"),
        "must_change_password": bool(user.get("must_change_password")),
        "totp_enabled": bool(user.get("totp_enabled")),
        "permissions": sorted(get_user_permissions(user)),
    }


def _validate_password(pw):
    if len(pw or "") < config.PASSWORD_MIN_LEN:
        return f"كلمة المرور قصيرة ({config.PASSWORD_MIN_LEN} أحرف على الأقل)"
    if pw.isdigit() or pw.isalpha():
        return "كلمة المرور يجب أن تجمع أحرفًا وأرقامًا"
    return None


@app.post("/api/change-password")
@login_required
def change_password():
    data = body()
    u = me()
    if not check_password_hash(u["password_hash"], data.get("old_password") or ""):
        return jsonify({"error": "كلمة المرور الحالية غير صحيحة"}), 400
    new = data.get("new_password") or ""
    err = _validate_password(new)
    if err:
        return jsonify({"error": err}), 400
    db.execute("UPDATE users SET password_hash=?, must_change_password=0 WHERE id=?",
               (generate_password_hash(new), u["id"]))
    db.log_action(u["company_id"], u, "change_password")
    return jsonify({"ok": True})


# ---- المصادقة الثنائية (2FA / TOTP) ----
@app.post("/api/2fa/setup")
@login_required
def twofa_setup():
    if not _HAS_PYOTP:
        return jsonify({"error": "وحدة TOTP غير مثبّتة (pyotp)"}), 501
    u = me()
    secret = pyotp.random_base32()
    db.execute("UPDATE users SET totp_secret=? WHERE id=?", (secret, u["id"]))
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=u["username"], issuer_name="HRMS Kuwait")
    return jsonify({"secret": secret, "otpauth_uri": uri})


@app.post("/api/2fa/enable")
@login_required
def twofa_enable():
    if not _HAS_PYOTP:
        return jsonify({"error": "وحدة TOTP غير مثبّتة"}), 501
    u = me()
    otp = (body().get("otp") or "").strip()
    if not u.get("totp_secret") or not pyotp.TOTP(u["totp_secret"]).verify(otp, valid_window=1):
        return jsonify({"error": "رمز التحقق غير صحيح"}), 400
    db.execute("UPDATE users SET totp_enabled=1 WHERE id=?", (u["id"],))
    db.log_action(u["company_id"], u, "enable_2fa")
    return jsonify({"ok": True})


@app.post("/api/2fa/disable")
@login_required
def twofa_disable():
    u = me()
    db.execute("UPDATE users SET totp_enabled=0, totp_secret=NULL WHERE id=?", (u["id"],))
    db.log_action(u["company_id"], u, "disable_2fa")
    return jsonify({"ok": True})


# ===========================================================================
# الشركات (Companies)
# ===========================================================================
@app.get("/api/companies")
@login_required
def list_companies():
    u = me()
    if u["role"] == "super_admin":
        rows = db.query("SELECT * FROM companies ORDER BY id")
    else:
        rows = db.query("SELECT * FROM companies WHERE id=?", (u["company_id"],))
    result = []
    for c in db.rows_to_list(rows):
        c["employees_count"] = db.query(
            "SELECT COUNT(*) AS n FROM employees WHERE company_id=?", (c["id"],), one=True)["n"]
        c["licenses_count"] = db.query(
            "SELECT COUNT(*) AS n FROM licenses WHERE company_id=?", (c["id"],), one=True)["n"]
        result.append(c)
    return jsonify(result)


@app.post("/api/companies")
@super_admin_required
def create_company():
    d = body()
    if not d.get("name"):
        return jsonify({"error": "اسم الشركة مطلوب"}), 400
    cid = db.execute(
        """INSERT INTO companies (name, name_en, commercial_reg, entity_type, status,
                                  eos_day_divisor, eos_max_months, alert_lead_days,
                                  annual_leave_days, workweek_hours, gosi_rate)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (d.get("name"), d.get("name_en"), d.get("commercial_reg"), d.get("entity_type"),
         d.get("status", "active"), int(d.get("eos_day_divisor", 26)),
         int(d.get("eos_max_months", 18)), int(d.get("alert_lead_days", 30)),
         int(d.get("annual_leave_days", 30)), int(d.get("workweek_hours", 48)),
         float(d.get("gosi_rate", 0) or 0)),
    )
    db.log_action(cid, me(), "create_company", "company", cid, d.get("name"))
    return jsonify({"id": cid}), 201


_INT_FIELDS = {"eos_day_divisor", "eos_max_months", "alert_lead_days", "annual_leave_days",
               "workweek_hours", "allowed_workers", "days", "score"}
_FLOAT_FIELDS = {"basic_salary", "amount", "gosi_rate"}


def _coerce(field, value):
    if value == "":
        return None
    if field in _INT_FIELDS:
        return _int_or_none(value)
    if field in _FLOAT_FIELDS:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return value


@app.put("/api/companies/<int:cid>")
@login_required
def update_company(cid):
    u = me()
    if u["role"] != "super_admin" and not (u["company_id"] == cid and has_permission(u, "manage_company")):
        return deny()
    d = body()
    fields, vals = [], []
    for f in ["name", "name_en", "commercial_reg", "entity_type", "status",
              "eos_day_divisor", "eos_max_months", "alert_lead_days",
              "annual_leave_days", "workweek_hours", "gosi_rate"]:
        if f in d:
            fields.append(f"{f}=?")
            vals.append(_coerce(f, d[f]))
    if not fields:
        return jsonify({"error": "لا توجد حقول للتحديث"}), 400
    vals.append(cid)
    db.execute(f"UPDATE companies SET {', '.join(fields)} WHERE id=?", vals)
    db.log_action(cid, u, "update_company", "company", cid)
    return jsonify({"ok": True})


@app.post("/api/companies/<int:cid>/toggle")
@super_admin_required
def toggle_company(cid):
    c = db.query("SELECT status FROM companies WHERE id=?", (cid,), one=True)
    if not c:
        return jsonify({"error": "الشركة غير موجودة"}), 404
    new_status = "inactive" if c["status"] == "active" else "active"
    db.execute("UPDATE companies SET status=? WHERE id=?", (new_status, cid))
    db.log_action(cid, me(), "toggle_company", "company", cid, new_status)
    return jsonify({"status": new_status})


@app.post("/api/companies/<int:cid>/archive")
@super_admin_required
def archive_company(cid):
    db.execute("UPDATE companies SET status='archived' WHERE id=?", (cid,))
    db.log_action(cid, me(), "archive_company", "company", cid)
    return jsonify({"ok": True})


# ===========================================================================
# المستخدمون والصلاحيات
# ===========================================================================
@app.get("/api/permissions-catalog")
@login_required
def permissions_catalog():
    return jsonify({
        "permissions": PERMISSIONS,
        "templates": {k: {"label": v["label"], "perms": v["perms"]}
                      for k, v in PERMISSION_TEMPLATES.items()},
    })


@app.get("/api/users")
@require_perm("manage_users")
def list_users():
    u = me()
    if u["role"] == "super_admin":
        cid = request.args.get("company_id")
        if cid:
            rows = db.query("SELECT * FROM users WHERE company_id=? ORDER BY id", (cid,))
        else:
            rows = db.query("SELECT * FROM users ORDER BY id")
    else:
        rows = db.query("SELECT * FROM users WHERE company_id=? ORDER BY id", (u["company_id"],))
    out = []
    for r in db.rows_to_list(rows):
        r.pop("password_hash", None)
        r.pop("totp_secret", None)
        perms = db.query("SELECT perm_code, expires_at FROM user_permissions WHERE user_id=?", (r["id"],))
        r["permissions"] = db.rows_to_list(perms)
        out.append(r)
    return jsonify(out)


@app.post("/api/users")
@require_perm("manage_users")
def create_user():
    u = me()
    d = body()
    username = (d.get("username") or "").strip()
    if not username or not d.get("password"):
        return jsonify({"error": "اسم المستخدم وكلمة المرور مطلوبان"}), 400
    err = _validate_password(d.get("password"))
    if err:
        return jsonify({"error": err}), 400
    if db.query("SELECT 1 FROM users WHERE username=?", (username,), one=True):
        return jsonify({"error": "اسم المستخدم مستخدم بالفعل"}), 400

    role = d.get("role", "employee")
    if u["role"] == "super_admin":
        company_id = d.get("company_id")
        if role != "super_admin" and not company_id:
            return jsonify({"error": "يجب تحديد الشركة"}), 400
        company_id = int(company_id) if company_id else None
    else:
        company_id = u["company_id"]
        if role == "super_admin":
            return jsonify({"error": "لا يمكنك إنشاء مستخدم إدارة عليا"}), 403
        role = "employee" if role == "super_admin" else role

    uid = db.execute(
        """INSERT INTO users (company_id, username, password_hash, full_name, email, phone,
                              role, employee_id, must_change_password)
           VALUES (?,?,?,?,?,?,?,?,1)""",
        (company_id, username, generate_password_hash(d["password"]), d.get("full_name"),
         d.get("email"), d.get("phone"), role, _int_or_none(d.get("employee_id"))),
    )
    for p in d.get("permissions", []):
        if p in PERMISSIONS:
            db.execute("INSERT OR IGNORE INTO user_permissions (user_id, perm_code) VALUES (?,?)", (uid, p))
    db.log_action(company_id, u, "create_user", "user", uid, username)
    return jsonify({"id": uid}), 201


@app.put("/api/users/<int:uid>/permissions")
@require_perm("manage_users")
def set_user_permissions(uid):
    u = me()
    target = db.query("SELECT * FROM users WHERE id=?", (uid,), one=True)
    if not target:
        return jsonify({"error": "المستخدم غير موجود"}), 404
    if u["role"] != "super_admin" and target["company_id"] != u["company_id"]:
        return deny()
    d = body()
    perms = d.get("permissions", [])
    db.execute("DELETE FROM user_permissions WHERE user_id=?", (uid,))
    for item in perms:
        code = item.get("code") if isinstance(item, dict) else item
        exp = item.get("expires_at") if isinstance(item, dict) else None
        if code in PERMISSIONS:
            db.execute("INSERT OR IGNORE INTO user_permissions (user_id, perm_code, expires_at) VALUES (?,?,?)",
                       (uid, code, exp))
    db.log_action(target["company_id"], u, "set_permissions", "user", uid)
    return jsonify({"ok": True})


@app.post("/api/users/<int:uid>/copy-permissions")
@require_perm("manage_users")
def copy_permissions(uid):
    u = me()
    d = body()
    source_id = d.get("source_user_id")
    target = db.query("SELECT * FROM users WHERE id=?", (uid,), one=True)
    source = db.query("SELECT * FROM users WHERE id=?", (source_id,), one=True)
    if not target or not source:
        return jsonify({"error": "مستخدم غير موجود"}), 404
    if u["role"] != "super_admin" and (target["company_id"] != u["company_id"] or source["company_id"] != u["company_id"]):
        return deny()
    src_perms = db.query("SELECT perm_code, expires_at FROM user_permissions WHERE user_id=?", (source_id,))
    db.execute("DELETE FROM user_permissions WHERE user_id=?", (uid,))
    for p in src_perms:
        db.execute("INSERT OR IGNORE INTO user_permissions (user_id, perm_code, expires_at) VALUES (?,?,?)",
                   (uid, p["perm_code"], p["expires_at"]))
    db.log_action(target["company_id"], u, "copy_permissions", "user", uid, f"from {source_id}")
    return jsonify({"ok": True})


@app.post("/api/users/<int:uid>/toggle")
@require_perm("manage_users")
def toggle_user(uid):
    u = me()
    target = db.query("SELECT * FROM users WHERE id=?", (uid,), one=True)
    if not target:
        return jsonify({"error": "غير موجود"}), 404
    if u["role"] != "super_admin" and target["company_id"] != u["company_id"]:
        return deny()
    if target["id"] == u["id"]:
        return jsonify({"error": "لا يمكنك تعطيل حسابك"}), 400
    # منع تعطيل آخر إدارة عليا فعّالة
    if target["role"] == "super_admin" and target["is_active"]:
        active_admins = db.query(
            "SELECT COUNT(*) AS n FROM users WHERE role='super_admin' AND is_active=1", one=True)["n"]
        if active_admins <= 1:
            return jsonify({"error": "لا يمكن تعطيل آخر مستخدم إدارة عليا"}), 400
    new = 0 if target["is_active"] else 1
    db.execute("UPDATE users SET is_active=? WHERE id=?", (new, uid))
    db.log_action(target["company_id"], u, "toggle_user", "user", uid, str(new))
    return jsonify({"is_active": new})


# ===========================================================================
# الأقسام (Departments)
# ===========================================================================
@app.get("/api/departments")
@login_required
def list_departments():
    u = me()
    cid = scope_company_id(u, request.args.get("company_id"))
    sql = "SELECT d.*, e.name AS manager_name FROM departments d LEFT JOIN employees e ON e.id=d.manager_id WHERE 1=1"
    params = []
    if cid:
        sql += " AND d.company_id=?"
        params.append(cid)
    sql += " ORDER BY d.id"
    return jsonify(db.rows_to_list(db.query(sql, params)))


@app.post("/api/departments")
@require_perm("manage_departments")
def create_department():
    u = me()
    d = body()
    cid = scope_company_id(u, d.get("company_id")) or u["company_id"]
    if not ensure_company_access(cid):
        return deny()
    if not d.get("name"):
        return jsonify({"error": "اسم القسم مطلوب"}), 400
    did = db.execute(
        "INSERT INTO departments (company_id, name, parent_id, manager_id) VALUES (?,?,?,?)",
        (cid, d.get("name"), _int_or_none(d.get("parent_id")), _int_or_none(d.get("manager_id"))))
    db.log_action(cid, u, "create_department", "department", did, d.get("name"))
    return jsonify({"id": did}), 201


@app.put("/api/departments/<int:did>")
@require_perm("manage_departments")
def update_department(did):
    u = me()
    dep = db.query("SELECT * FROM departments WHERE id=?", (did,), one=True)
    if not dep:
        return jsonify({"error": "غير موجود"}), 404
    if not ensure_company_access(dep["company_id"]):
        return deny()
    d = body()
    fields, vals = [], []
    for f in ["name", "parent_id", "manager_id"]:
        if f in d:
            fields.append(f"{f}=?")
            vals.append(_int_or_none(d[f]) if f != "name" else d[f])
    if fields:
        vals.append(did)
        db.execute(f"UPDATE departments SET {', '.join(fields)} WHERE id=?", vals)
    db.log_action(dep["company_id"], u, "update_department", "department", did)
    return jsonify({"ok": True})


@app.delete("/api/departments/<int:did>")
@require_perm("manage_departments")
def delete_department(did):
    u = me()
    dep = db.query("SELECT * FROM departments WHERE id=?", (did,), one=True)
    if not dep:
        return jsonify({"error": "غير موجود"}), 404
    if not ensure_company_access(dep["company_id"]):
        return deny()
    db.execute("UPDATE employees SET department_id=NULL WHERE department_id=?", (did,))
    db.execute("DELETE FROM departments WHERE id=?", (did,))
    db.log_action(dep["company_id"], u, "delete_department", "department", did)
    return jsonify({"ok": True})


# ===========================================================================
# الموظفون (Employees)
# ===========================================================================
@app.get("/api/employees")
@require_perm("view_employee")
def list_employees():
    u = me()
    cid = scope_company_id(u, request.args.get("company_id"))
    status = request.args.get("status")
    q = request.args.get("q", "").strip()
    limit = min(_int_or_none(request.args.get("limit")) or 100, 500)
    offset = max(_int_or_none(request.args.get("offset")) or 0, 0)

    sql = "SELECT e.*, c.name AS company_name, l.name AS license_name, d.name AS department_name " \
          "FROM employees e JOIN companies c ON c.id=e.company_id " \
          "LEFT JOIN licenses l ON l.id=e.license_id " \
          "LEFT JOIN departments d ON d.id=e.department_id WHERE 1=1"
    params = []
    if cid:
        sql += " AND e.company_id=?"
        params.append(cid)
    if status:
        sql += " AND e.status=?"
        params.append(status)
    if q:
        sql += " AND (e.name LIKE ? OR e.civil_id LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY e.id DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    return jsonify(db.rows_to_list(db.query(sql, params)))


@app.get("/api/employees/<int:eid>")
@require_perm("view_employee")
def get_employee(eid):
    row = db.query("SELECT * FROM employees WHERE id=?", (eid,), one=True)
    if not row:
        return jsonify({"error": "غير موجود"}), 404
    emp = db.row_to_dict(row)
    if not ensure_company_access(emp["company_id"]):
        return deny()
    emp["permits"] = db.rows_to_list(db.query("SELECT * FROM permits WHERE employee_id=? ORDER BY expiry_date", (eid,)))
    emp["deductions"] = db.rows_to_list(db.query("SELECT * FROM deductions WHERE employee_id=? ORDER BY date DESC", (eid,)))
    emp["leaves"] = db.rows_to_list(db.query("SELECT * FROM leaves WHERE employee_id=? ORDER BY start_date DESC", (eid,)))
    emp["allowances"] = db.rows_to_list(db.query("SELECT * FROM allowances WHERE employee_id=? ORDER BY id", (eid,)))
    emp["disciplinary"] = db.rows_to_list(db.query("SELECT * FROM disciplinary_actions WHERE employee_id=? ORDER BY action_date DESC", (eid,)))
    emp["assets"] = db.rows_to_list(db.query("SELECT * FROM assets WHERE employee_id=? ORDER BY id DESC", (eid,)))
    emp["reviews"] = db.rows_to_list(db.query("SELECT * FROM performance_reviews WHERE employee_id=? ORDER BY id DESC", (eid,)))
    emp["history"] = db.rows_to_list(db.query("SELECT * FROM employment_history WHERE employee_id=? ORDER BY id DESC", (eid,)))
    emp["documents"] = db.rows_to_list(db.query(
        "SELECT * FROM documents WHERE entity_type='employee' AND entity_id=?", (eid,)))
    return jsonify(emp)


@app.post("/api/employees")
@require_perm("create_employee")
def create_employee():
    u = me()
    d = body()
    cid = scope_company_id(u, d.get("company_id"))
    if not cid:
        return jsonify({"error": "يجب تحديد الشركة"}), 400
    if not ensure_company_access(cid):
        return deny()
    if not d.get("name"):
        return jsonify({"error": "اسم الموظف مطلوب"}), 400
    eid = db.execute(
        """INSERT INTO employees (company_id, department_id, civil_id, name, email, phone, nationality,
                                  worker_type, job_title, basic_salary, hire_date, status, license_id,
                                  contract_type, contract_end)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (cid, _int_or_none(d.get("department_id")), d.get("civil_id"), d.get("name"), d.get("email"),
         d.get("phone"), d.get("nationality"), d.get("worker_type"), d.get("job_title"),
         float(d.get("basic_salary") or 0), d.get("hire_date"), d.get("status", "active"),
         _int_or_none(d.get("license_id")), d.get("contract_type", "indefinite"), d.get("contract_end")),
    )
    leave_service.recalc_balance(eid)
    db.log_action(cid, u, "create_employee", "employee", eid, d.get("name"))
    return jsonify({"id": eid}), 201


@app.put("/api/employees/<int:eid>")
@require_perm("edit_employee")
def update_employee(eid):
    u = me()
    emp = db.query("SELECT * FROM employees WHERE id=?", (eid,), one=True)
    if not emp:
        return jsonify({"error": "غير موجود"}), 404
    if not ensure_company_access(emp["company_id"]):
        return deny()
    emp = db.row_to_dict(emp)
    d = body()
    fields, vals = [], []
    tracked = {"basic_salary": "salary_change", "job_title": "promotion", "department_id": "department_change"}
    history_events = []
    for f in ["civil_id", "name", "email", "phone", "nationality", "worker_type", "job_title",
              "basic_salary", "hire_date", "status", "license_id", "department_id",
              "contract_type", "contract_end", "end_date", "end_reason"]:
        if f in d:
            new_val = _coerce(f, d[f]) if f in (_INT_FIELDS | _FLOAT_FIELDS) else (d[f] if d[f] != "" else None)
            if f in tracked and str(emp.get(f)) != str(new_val):
                history_events.append((tracked[f], emp.get(f), new_val))
            fields.append(f"{f}=?")
            vals.append(new_val)
    if not fields:
        return jsonify({"error": "لا توجد حقول"}), 400
    vals.append(eid)
    db.execute(f"UPDATE employees SET {', '.join(fields)} WHERE id=?", vals)
    for ev, old, new in history_events:
        db.execute(
            """INSERT INTO employment_history (company_id, employee_id, event_type, old_value, new_value, effective_date)
               VALUES (?,?,?,?,?,?)""",
            (emp["company_id"], eid, ev, str(old), str(new), date.today().isoformat()))
    db.log_action(emp["company_id"], u, "update_employee", "employee", eid)
    return jsonify({"ok": True})


@app.delete("/api/employees/<int:eid>")
@require_perm("delete_employee")
def delete_employee(eid):
    u = me()
    emp = db.query("SELECT * FROM employees WHERE id=?", (eid,), one=True)
    if not emp:
        return jsonify({"error": "غير موجود"}), 404
    if not ensure_company_access(emp["company_id"]):
        return deny()
    db.execute("DELETE FROM employees WHERE id=?", (eid,))  # CASCADE يحذف التابع
    db.log_action(emp["company_id"], u, "delete_employee", "employee", eid, emp["name"])
    return jsonify({"ok": True})


@app.post("/api/employees/<int:eid>/end-service")
@require_perm("edit_employee")
def end_service(eid):
    """إنهاء الخدمة + حساب وتخزين مخالصة EOS تلقائيًا."""
    u = me()
    emp = db.query("SELECT * FROM employees WHERE id=?", (eid,), one=True)
    if not emp:
        return jsonify({"error": "غير موجود"}), 404
    if not ensure_company_access(emp["company_id"]):
        return deny()
    emp = db.row_to_dict(emp)
    d = body()
    reason = d.get("reason", "termination")
    end_dt = d.get("end_date") or date.today().isoformat()
    new_status = "resigned" if reason == "resignation" else "terminated"

    comp = db.row_to_dict(db.query("SELECT * FROM companies WHERE id=?", (emp["company_id"],), one=True))
    settlement = None
    if emp.get("hire_date") and emp.get("basic_salary"):
        try:
            settlement = calculate_eos(
                basic_salary=emp["basic_salary"], hire_date=emp["hire_date"], end_date=end_dt,
                reason=reason, contract_type=emp.get("contract_type", "indefinite"),
                unused_leave_days=emp.get("annual_leave_balance") or 0,
                day_divisor=comp["eos_day_divisor"], max_months=comp["eos_max_months"])
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    with db.transaction() as conn:
        conn.execute("UPDATE employees SET status=?, end_date=?, end_reason=? WHERE id=?",
                     (new_status, end_dt, reason, eid))
        if settlement:
            conn.execute(
                """INSERT INTO eos_settlements (company_id, employee_id, reason, end_date, total_settlement, snapshot)
                   VALUES (?,?,?,?,?,?)""",
                (emp["company_id"], eid, reason, end_dt, settlement["total_settlement"],
                 json.dumps(settlement, ensure_ascii=False)))
    db.log_action(emp["company_id"], u, "end_service", "employee", eid, reason)
    return jsonify({"ok": True, "status": new_status, "settlement": settlement})


@app.post("/api/employees/<int:eid>/transfer")
@super_admin_required
def transfer_employee(eid):
    """نقل موظف بين شركتين مع نقل كل السجلات التابعة (إصلاح تسريب العزل)."""
    d = body()
    emp = db.query("SELECT * FROM employees WHERE id=?", (eid,), one=True)
    if not emp:
        return jsonify({"error": "غير موجود"}), 404
    to_company = _int_or_none(d.get("to_company_id"))
    if not to_company:
        return jsonify({"error": "الشركة الهدف مطلوبة"}), 400
    if not db.query("SELECT 1 FROM companies WHERE id=?", (to_company,), one=True):
        return jsonify({"error": "الشركة الهدف غير موجودة"}), 404
    from_company = emp["company_id"]
    with db.transaction() as conn:
        conn.execute("INSERT INTO transfers (employee_id, from_company, to_company, note) VALUES (?,?,?,?)",
                     (eid, from_company, to_company, d.get("note")))
        conn.execute("UPDATE employees SET company_id=?, license_id=NULL, department_id=NULL WHERE id=?",
                     (to_company, eid))
        # نقل السجلات التابعة لتفادي تسريب العزل
        for tbl in ("permits", "deductions", "leaves", "allowances", "attendance",
                    "disciplinary_actions", "performance_reviews", "assets", "employment_history"):
            conn.execute(f"UPDATE {tbl} SET company_id=? WHERE employee_id=?", (to_company, eid))
        conn.execute("UPDATE documents SET company_id=? WHERE entity_type='employee' AND entity_id=?",
                     (to_company, eid))
    db.log_action(to_company, me(), "transfer_employee", "employee", eid, f"{from_company} -> {to_company}")
    return jsonify({"ok": True})


# ===========================================================================
# التراخيص (Licenses)
# ===========================================================================
@app.get("/api/licenses")
@login_required
def list_licenses():
    u = me()
    cid = scope_company_id(u, request.args.get("company_id"))
    sql = "SELECT * FROM licenses WHERE 1=1"
    params = []
    if cid:
        sql += " AND company_id=?"
        params.append(cid)
    sql += " ORDER BY id DESC"
    rows = db.rows_to_list(db.query(sql, params))
    for lic in rows:
        lic["actual_workers"] = db.query(
            "SELECT COUNT(*) AS n FROM employees WHERE license_id=? AND status='active'",
            (lic["id"],), one=True)["n"]
        lic["over_capacity"] = bool(lic["allowed_workers"]) and lic["actual_workers"] > lic["allowed_workers"]
    return jsonify(rows)


@app.post("/api/licenses")
@require_perm("manage_licenses")
def create_license():
    u = me()
    d = body()
    cid = scope_company_id(u, d.get("company_id"))
    if not cid:
        return jsonify({"error": "يجب تحديد الشركة"}), 400
    if not ensure_company_access(cid):
        return deny()
    if not d.get("name"):
        return jsonify({"error": "اسم الترخيص مطلوب"}), 400
    lid = db.execute(
        """INSERT INTO licenses (company_id, name, license_no, issuing_authority, license_type,
                                 status, issue_date, expiry_date, allowed_workers, address)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (cid, d.get("name"), d.get("license_no"), d.get("issuing_authority"),
         d.get("license_type", "main"), d.get("status", "active"), d.get("issue_date"),
         d.get("expiry_date"), int(d.get("allowed_workers") or 0), d.get("address")),
    )
    db.log_action(cid, u, "create_license", "license", lid, d.get("name"))
    return jsonify({"id": lid}), 201


@app.put("/api/licenses/<int:lid>")
@require_perm("manage_licenses")
def update_license(lid):
    u = me()
    lic = db.query("SELECT * FROM licenses WHERE id=?", (lid,), one=True)
    if not lic:
        return jsonify({"error": "غير موجود"}), 404
    if not ensure_company_access(lic["company_id"]):
        return deny()
    d = body()
    fields, vals = [], []
    for f in ["name", "license_no", "issuing_authority", "license_type", "status",
              "issue_date", "expiry_date", "allowed_workers", "address"]:
        if f in d:
            fields.append(f"{f}=?")
            vals.append(_coerce(f, d[f]))
    vals.append(lid)
    db.execute(f"UPDATE licenses SET {', '.join(fields)} WHERE id=?", vals)
    db.log_action(lic["company_id"], u, "update_license", "license", lid)
    return jsonify({"ok": True})


@app.delete("/api/licenses/<int:lid>")
@require_perm("manage_licenses")
def delete_license(lid):
    u = me()
    lic = db.query("SELECT * FROM licenses WHERE id=?", (lid,), one=True)
    if not lic:
        return jsonify({"error": "غير موجود"}), 404
    if not ensure_company_access(lic["company_id"]):
        return deny()
    db.execute("UPDATE employees SET license_id=NULL WHERE license_id=?", (lid,))
    db.execute("DELETE FROM licenses WHERE id=?", (lid,))
    db.log_action(lic["company_id"], u, "delete_license", "license", lid)
    return jsonify({"ok": True})


# ===========================================================================
# الإقامات وأذونات العمل (Permits) — CRUD كامل
# ===========================================================================
@app.post("/api/permits")
@require_perm("manage_permits")
def create_permit():
    u = me()
    d = body()
    emp = db.query("SELECT * FROM employees WHERE id=?", (d.get("employee_id"),), one=True)
    if not emp:
        return jsonify({"error": "الموظف غير موجود"}), 404
    if not ensure_company_access(emp["company_id"]):
        return deny()
    pid = db.execute(
        """INSERT INTO permits (company_id, employee_id, kind, number, start_date, expiry_date, status)
           VALUES (?,?,?,?,?,?,?)""",
        (emp["company_id"], emp["id"], d.get("kind", "residency"), d.get("number"),
         d.get("start_date"), d.get("expiry_date"), d.get("status", "active")),
    )
    db.log_action(emp["company_id"], u, "create_permit", "permit", pid)
    return jsonify({"id": pid}), 201


@app.put("/api/permits/<int:pid>")
@require_perm("manage_permits")
def update_permit(pid):
    u = me()
    p = db.query("SELECT * FROM permits WHERE id=?", (pid,), one=True)
    if not p:
        return jsonify({"error": "غير موجود"}), 404
    if not ensure_company_access(p["company_id"]):
        return deny()
    d = body()
    fields, vals = [], []
    for f in ["kind", "number", "start_date", "expiry_date", "status"]:
        if f in d:
            fields.append(f"{f}=?")
            vals.append(d[f])
    vals.append(pid)
    db.execute(f"UPDATE permits SET {', '.join(fields)} WHERE id=?", vals)
    db.log_action(p["company_id"], u, "update_permit", "permit", pid)
    return jsonify({"ok": True})


@app.delete("/api/permits/<int:pid>")
@require_perm("manage_permits")
def delete_permit(pid):
    u = me()
    p = db.query("SELECT * FROM permits WHERE id=?", (pid,), one=True)
    if not p:
        return jsonify({"error": "غير موجود"}), 404
    if not ensure_company_access(p["company_id"]):
        return deny()
    db.execute("DELETE FROM permits WHERE id=?", (pid,))
    db.log_action(p["company_id"], u, "delete_permit", "permit", pid)
    return jsonify({"ok": True})


# ===========================================================================
# المستندات (Documents) — مع التحقق من نوع الملف
# ===========================================================================
def _allowed_file(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in config.ALLOWED_UPLOAD_EXTENSIONS


@app.post("/api/documents")
@require_perm("upload_documents")
def create_document():
    u = me()
    d = request.form.to_dict() if request.form else (request.get_json(silent=True) or {})
    cid = scope_company_id(u, d.get("company_id")) or u["company_id"]
    if not ensure_company_access(cid):
        return deny()

    file_path = None
    if "file" in request.files and request.files["file"].filename:
        f = request.files["file"]
        if not _allowed_file(f.filename):
            return jsonify({"error": "نوع الملف غير مسموح"}), 400
        safe = f"{secrets.token_hex(8)}_{secure_filename(f.filename)}"
        f.save(os.path.join(UPLOAD_DIR, safe))
        file_path = safe

    did = db.execute(
        """INSERT INTO documents (company_id, entity_type, entity_id, title, file_path, expiry_date)
           VALUES (?,?,?,?,?,?)""",
        (cid, d.get("entity_type", "company"), _int_or_none(d.get("entity_id")),
         d.get("title"), file_path, d.get("expiry_date")),
    )
    db.log_action(cid, u, "upload_document", "document", did, d.get("title"))
    return jsonify({"id": did, "file_path": file_path}), 201


@app.get("/api/documents")
@login_required
def list_documents():
    u = me()
    cid = scope_company_id(u, request.args.get("company_id"))
    sql = "SELECT * FROM documents WHERE 1=1"
    params = []
    if cid:
        sql += " AND company_id=?"
        params.append(cid)
    sql += " ORDER BY id DESC"
    return jsonify(db.rows_to_list(db.query(sql, params)))


@app.delete("/api/documents/<int:doc_id>")
@require_perm("upload_documents")
def delete_document(doc_id):
    u = me()
    doc = db.query("SELECT * FROM documents WHERE id=?", (doc_id,), one=True)
    if not doc:
        return jsonify({"error": "غير موجود"}), 404
    if not ensure_company_access(doc["company_id"]):
        return deny()
    if doc["file_path"]:
        try:
            os.remove(os.path.join(UPLOAD_DIR, doc["file_path"]))
        except OSError:
            pass
    db.execute("DELETE FROM documents WHERE id=?", (doc_id,))
    db.log_action(doc["company_id"], u, "delete_document", "document", doc_id)
    return jsonify({"ok": True})


# ===========================================================================
# الخصومات والبدلات (Deductions & Allowances) — CRUD
# ===========================================================================
def _employee_in_scope(employee_id):
    emp = db.query("SELECT * FROM employees WHERE id=?", (employee_id,), one=True)
    if not emp:
        return None, (jsonify({"error": "الموظف غير موجود"}), 404)
    if not ensure_company_access(emp["company_id"]):
        return None, deny()
    return db.row_to_dict(emp), None


@app.post("/api/deductions")
@require_perm("manage_deductions")
def create_deduction():
    u = me()
    d = body()
    emp, err = _employee_in_scope(d.get("employee_id"))
    if err:
        return err
    did = db.execute(
        "INSERT INTO deductions (company_id, employee_id, amount, reason, ded_type, date) VALUES (?,?,?,?,?,?)",
        (emp["company_id"], emp["id"], float(d.get("amount") or 0), d.get("reason"),
         d.get("ded_type", "manual"), d.get("date") or date.today().isoformat()),
    )
    db.log_action(emp["company_id"], u, "create_deduction", "deduction", did)
    return jsonify({"id": did}), 201


@app.delete("/api/deductions/<int:ded_id>")
@require_perm("manage_deductions")
def delete_deduction(ded_id):
    u = me()
    row = db.query("SELECT * FROM deductions WHERE id=?", (ded_id,), one=True)
    if not row:
        return jsonify({"error": "غير موجود"}), 404
    if not ensure_company_access(row["company_id"]):
        return deny()
    db.execute("DELETE FROM deductions WHERE id=?", (ded_id,))
    db.log_action(row["company_id"], u, "delete_deduction", "deduction", ded_id)
    return jsonify({"ok": True})


@app.post("/api/allowances")
@require_perm("manage_deductions")
def create_allowance():
    u = me()
    d = body()
    emp, err = _employee_in_scope(d.get("employee_id"))
    if err:
        return err
    aid = db.execute(
        "INSERT INTO allowances (company_id, employee_id, name, amount, recurring) VALUES (?,?,?,?,?)",
        (emp["company_id"], emp["id"], d.get("name"), float(d.get("amount") or 0),
         1 if d.get("recurring", True) else 0))
    db.log_action(emp["company_id"], u, "create_allowance", "allowance", aid)
    return jsonify({"id": aid}), 201


@app.delete("/api/allowances/<int:aid>")
@require_perm("manage_deductions")
def delete_allowance(aid):
    row = db.query("SELECT * FROM allowances WHERE id=?", (aid,), one=True)
    if not row:
        return jsonify({"error": "غير موجود"}), 404
    if not ensure_company_access(row["company_id"]):
        return deny()
    db.execute("DELETE FROM allowances WHERE id=?", (aid,))
    return jsonify({"ok": True})


# ===========================================================================
# الإجازات (Leaves) — مع رصيد الإجازة السنوية
# ===========================================================================
@app.post("/api/leaves")
@require_perm("manage_leaves")
def create_leave():
    u = me()
    d = body()
    emp, err = _employee_in_scope(d.get("employee_id"))
    if err:
        return err
    lid = db.execute(
        """INSERT INTO leaves (company_id, employee_id, leave_type, start_date, end_date, days, paid, status)
           VALUES (?,?,?,?,?,?,?,?)""",
        (emp["company_id"], emp["id"], d.get("leave_type", "annual"), d.get("start_date"),
         d.get("end_date"), int(d.get("days") or 0), 1 if d.get("paid", True) else 0, "pending"),
    )
    db.log_action(emp["company_id"], u, "create_leave", "leave", lid)
    return jsonify({"id": lid}), 201


@app.post("/api/leaves/<int:lid>/decision")
@require_perm("manage_leaves")
def leave_decision(lid):
    u = me()
    lv = db.query("SELECT * FROM leaves WHERE id=?", (lid,), one=True)
    if not lv:
        return jsonify({"error": "غير موجود"}), 404
    if not ensure_company_access(lv["company_id"]):
        return deny()
    lv = db.row_to_dict(lv)
    decision = body().get("decision")
    if decision not in ("approved", "rejected"):
        return jsonify({"error": "قرار غير صالح"}), 400
    db.execute("UPDATE leaves SET status=? WHERE id=?", (decision, lid))
    # خصم الرصيد عند اعتماد إجازة سنوية مدفوعة
    if decision == "approved":
        leave_service.recalc_balance(lv["employee_id"])
    db.log_action(lv["company_id"], u, "leave_decision", "leave", lid, decision)
    return jsonify({"status": decision})


@app.get("/api/employees/<int:eid>/leave-balance")
@require_perm("view_employee")
def leave_balance(eid):
    emp, err = _employee_in_scope(eid)
    if err:
        return err
    bal = leave_service.recalc_balance(eid)
    return jsonify({"employee_id": eid, "balance": bal})


# ===========================================================================
# الحضور والانصراف (Attendance)
# ===========================================================================
@app.get("/api/attendance")
@require_perm("manage_attendance")
def list_attendance():
    u = me()
    cid = scope_company_id(u, request.args.get("company_id"))
    eid = _int_or_none(request.args.get("employee_id"))
    sql = "SELECT a.*, e.name AS employee_name FROM attendance a JOIN employees e ON e.id=a.employee_id WHERE 1=1"
    params = []
    if cid:
        sql += " AND a.company_id=?"
        params.append(cid)
    if eid:
        sql += " AND a.employee_id=?"
        params.append(eid)
    sql += " ORDER BY a.date DESC, a.id DESC LIMIT 500"
    return jsonify(db.rows_to_list(db.query(sql, params)))


@app.post("/api/attendance")
@require_perm("manage_attendance")
def create_attendance():
    u = me()
    d = body()
    emp, err = _employee_in_scope(d.get("employee_id"))
    if err:
        return err
    aid = db.execute(
        """INSERT INTO attendance (company_id, employee_id, date, check_in, check_out, hours,
                                   overtime_hours, status, note)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (emp["company_id"], emp["id"], d.get("date") or date.today().isoformat(),
         d.get("check_in"), d.get("check_out"), float(d.get("hours") or 0),
         float(d.get("overtime_hours") or 0), d.get("status", "present"), d.get("note")))
    db.log_action(emp["company_id"], u, "create_attendance", "attendance", aid)
    return jsonify({"id": aid}), 201


@app.delete("/api/attendance/<int:aid>")
@require_perm("manage_attendance")
def delete_attendance(aid):
    row = db.query("SELECT * FROM attendance WHERE id=?", (aid,), one=True)
    if not row:
        return jsonify({"error": "غير موجود"}), 404
    if not ensure_company_access(row["company_id"]):
        return deny()
    db.execute("DELETE FROM attendance WHERE id=?", (aid,))
    return jsonify({"ok": True})


# ===========================================================================
# الجزاءات التأديبية (Disciplinary)
# ===========================================================================
@app.post("/api/disciplinary")
@require_perm("manage_disciplinary")
def create_disciplinary():
    u = me()
    d = body()
    emp, err = _employee_in_scope(d.get("employee_id"))
    if err:
        return err
    did = db.execute(
        """INSERT INTO disciplinary_actions (company_id, employee_id, action_type, description, action_date, created_by)
           VALUES (?,?,?,?,?,?)""",
        (emp["company_id"], emp["id"], d.get("action_type", "notice"), d.get("description"),
         d.get("action_date") or date.today().isoformat(), u["username"]))
    db.log_action(emp["company_id"], u, "create_disciplinary", "disciplinary", did)
    return jsonify({"id": did}), 201


@app.delete("/api/disciplinary/<int:did>")
@require_perm("manage_disciplinary")
def delete_disciplinary(did):
    row = db.query("SELECT * FROM disciplinary_actions WHERE id=?", (did,), one=True)
    if not row:
        return jsonify({"error": "غير موجود"}), 404
    if not ensure_company_access(row["company_id"]):
        return deny()
    db.execute("DELETE FROM disciplinary_actions WHERE id=?", (did,))
    return jsonify({"ok": True})


# ===========================================================================
# العُهد والأصول (Assets)
# ===========================================================================
@app.get("/api/assets")
@require_perm("manage_assets")
def list_assets():
    u = me()
    cid = scope_company_id(u, request.args.get("company_id"))
    sql = "SELECT a.*, e.name AS employee_name FROM assets a LEFT JOIN employees e ON e.id=a.employee_id WHERE 1=1"
    params = []
    if cid:
        sql += " AND a.company_id=?"
        params.append(cid)
    sql += " ORDER BY a.id DESC"
    return jsonify(db.rows_to_list(db.query(sql, params)))


@app.post("/api/assets")
@require_perm("manage_assets")
def create_asset():
    u = me()
    d = body()
    cid = scope_company_id(u, d.get("company_id")) or u["company_id"]
    if not ensure_company_access(cid):
        return deny()
    aid = db.execute(
        """INSERT INTO assets (company_id, employee_id, name, serial_no, assigned_date, note)
           VALUES (?,?,?,?,?,?)""",
        (cid, _int_or_none(d.get("employee_id")), d.get("name"), d.get("serial_no"),
         d.get("assigned_date") or date.today().isoformat(), d.get("note")))
    db.log_action(cid, u, "create_asset", "asset", aid)
    return jsonify({"id": aid}), 201


@app.post("/api/assets/<int:aid>/return")
@require_perm("manage_assets")
def return_asset(aid):
    row = db.query("SELECT * FROM assets WHERE id=?", (aid,), one=True)
    if not row:
        return jsonify({"error": "غير موجود"}), 404
    if not ensure_company_access(row["company_id"]):
        return deny()
    db.execute("UPDATE assets SET returned_date=? WHERE id=?",
               (body().get("returned_date") or date.today().isoformat(), aid))
    return jsonify({"ok": True})


# ===========================================================================
# تقييم الأداء (Performance)
# ===========================================================================
@app.post("/api/performance")
@require_perm("manage_performance")
def create_review():
    u = me()
    d = body()
    emp, err = _employee_in_scope(d.get("employee_id"))
    if err:
        return err
    rid = db.execute(
        """INSERT INTO performance_reviews (company_id, employee_id, period, score, reviewer, notes)
           VALUES (?,?,?,?,?,?)""",
        (emp["company_id"], emp["id"], d.get("period"), float(d.get("score") or 0),
         u["username"], d.get("notes")))
    db.log_action(emp["company_id"], u, "create_review", "review", rid)
    return jsonify({"id": rid}), 201


# ===========================================================================
# مسيّر الرواتب (Payroll)
# ===========================================================================
@app.post("/api/payroll/run")
@require_perm("run_payroll")
def payroll_run():
    u = me()
    d = body()
    cid = scope_company_id(u, d.get("company_id")) or u["company_id"]
    if not cid or not ensure_company_access(cid):
        return deny()
    period = d.get("period") or date.today().strftime("%Y-%m")
    run_id, slips = payroll_engine.run_payroll(cid, period, created_by=u["username"], note=d.get("note"))
    db.log_action(cid, u, "run_payroll", "payroll_run", run_id, period)
    return jsonify({"run_id": run_id, "period": period, "count": len(slips), "payslips": slips}), 201


@app.get("/api/payroll/runs")
@require_perm("view_payroll")
def payroll_runs():
    u = me()
    cid = scope_company_id(u, request.args.get("company_id"))
    sql = "SELECT * FROM payroll_runs WHERE 1=1"
    params = []
    if cid:
        sql += " AND company_id=?"
        params.append(cid)
    sql += " ORDER BY id DESC LIMIT 100"
    return jsonify(db.rows_to_list(db.query(sql, params)))


@app.get("/api/payroll/runs/<int:run_id>")
@require_perm("view_payroll")
def payroll_run_detail(run_id):
    run = db.query("SELECT * FROM payroll_runs WHERE id=?", (run_id,), one=True)
    if not run:
        return jsonify({"error": "غير موجود"}), 404
    if not ensure_company_access(run["company_id"]):
        return deny()
    slips = db.rows_to_list(db.query(
        "SELECT p.*, e.name AS employee_name FROM payslips p JOIN employees e ON e.id=p.employee_id WHERE run_id=?",
        (run_id,)))
    return jsonify({"run": db.row_to_dict(run), "payslips": slips})


# ===========================================================================
# مكافأة نهاية الخدمة (EOS)
# ===========================================================================
@app.get("/api/eos/reasons")
@login_required
def eos_reasons():
    return jsonify(TERMINATION_REASONS)


@app.post("/api/eos/calculate")
@require_perm("calculate_eos")
def eos_calculate():
    d = body()
    employee_id = d.get("employee_id")
    if employee_id:
        emp = db.query("SELECT * FROM employees WHERE id=?", (employee_id,), one=True)
        if not emp:
            return jsonify({"error": "الموظف غير موجود"}), 404
        if not ensure_company_access(emp["company_id"]):
            return deny()
        comp = db.query("SELECT * FROM companies WHERE id=?", (emp["company_id"],), one=True)
        basic = d.get("basic_salary") or emp["basic_salary"]
        hire = d.get("hire_date") or emp["hire_date"]
        end = d.get("end_date") or emp["end_date"] or date.today().isoformat()
        reason = d.get("reason") or emp["end_reason"] or "termination"
        contract_type = d.get("contract_type") or emp["contract_type"] or "indefinite"
        divisor = comp["eos_day_divisor"]
        max_months = comp["eos_max_months"]
    else:
        basic = d.get("basic_salary")
        hire = d.get("hire_date")
        end = d.get("end_date") or date.today().isoformat()
        reason = d.get("reason", "termination")
        contract_type = d.get("contract_type", "indefinite")
        divisor = int(d.get("day_divisor", 26))
        max_months = int(d.get("max_months", 18))

    if not basic or not hire:
        return jsonify({"error": "الراتب الأساسي وتاريخ التعيين مطلوبان"}), 400

    try:
        result = calculate_eos(
            basic_salary=basic, hire_date=hire, end_date=end, reason=reason,
            contract_type=contract_type, unused_leave_days=d.get("unused_leave_days", 0),
            day_divisor=divisor, max_months=max_months,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    # بدل الإشعار التقديري (المادة 44) للعقود غير محددة المدة
    if contract_type != "definite":
        result["notice_pay"] = notice_pay(basic, day_divisor=divisor,
                                          notice_days=int(d.get("notice_days", 90)))
    return jsonify(result)


@app.get("/api/eos/liability")
@require_perm("view_reports")
def eos_liability():
    """إجمالي التزامات نهاية الخدمة (لو فُصل كل الموظفين النشطين اليوم)."""
    u = me()
    cid = scope_company_id(u, request.args.get("company_id"))
    sql = "SELECT e.*, c.eos_day_divisor, c.eos_max_months, c.name AS company_name " \
          "FROM employees e JOIN companies c ON c.id=e.company_id WHERE e.status='active'"
    params = []
    if cid:
        sql += " AND e.company_id=?"
        params.append(cid)
    rows = db.rows_to_list(db.query(sql, params))
    today = date.today().isoformat()
    total = 0.0
    items = []
    for e in rows:
        if not e.get("hire_date") or not e.get("basic_salary"):
            continue
        try:
            r = calculate_eos(basic_salary=e["basic_salary"], hire_date=e["hire_date"],
                              end_date=today, reason="termination",
                              contract_type=e.get("contract_type", "indefinite"),
                              day_divisor=e["eos_day_divisor"], max_months=e["eos_max_months"])
        except ValueError:
            continue
        total += r["indemnity"]
        items.append({"employee_id": e["id"], "name": e["name"], "company": e["company_name"],
                      "service": r["service"]["text"], "indemnity": r["indemnity"]})
    items.sort(key=lambda x: x["indemnity"], reverse=True)
    return jsonify({"total_liability": round(total, 3), "currency": "KWD",
                    "employees": len(items), "breakdown": items})


# ===========================================================================
# التنبيهات (Alerts)
# ===========================================================================
@app.get("/api/alerts")
@require_perm("view_alerts")
def api_alerts():
    u = me()
    cid = scope_company_id(u, request.args.get("company_id"))
    return jsonify(generate_alerts(cid))


# ===========================================================================
# الإشعارات داخل التطبيق (Notifications)
# ===========================================================================
@app.get("/api/notifications")
@login_required
def list_notifications():
    u = me()
    unread = request.args.get("unread") == "1"
    return jsonify({"unread": notify.unread_count(u["id"]),
                    "items": notify.list_for_user(u["id"], unread_only=unread)})


@app.post("/api/notifications/<int:nid>/read")
@login_required
def read_notification(nid):
    notify.mark_read(nid, me()["id"])
    return jsonify({"ok": True})


@app.post("/api/notifications/read-all")
@login_required
def read_all_notifications():
    notify.mark_all_read(me()["id"])
    return jsonify({"ok": True})


# ===========================================================================
# بوابة الخدمة الذاتية (Self-service) — للمستخدم المرتبط بموظف
# ===========================================================================
@app.get("/api/self/profile")
@login_required
def self_profile():
    u = me()
    if not u.get("employee_id"):
        return jsonify({"error": "لا يوجد ملف موظف مرتبط بحسابك"}), 404
    emp = db.query("SELECT * FROM employees WHERE id=?", (u["employee_id"],), one=True)
    if not emp:
        return jsonify({"error": "غير موجود"}), 404
    emp = db.row_to_dict(emp)
    emp["leaves"] = db.rows_to_list(db.query(
        "SELECT * FROM leaves WHERE employee_id=? ORDER BY id DESC", (u["employee_id"],)))
    emp["payslips"] = db.rows_to_list(db.query(
        "SELECT * FROM payslips WHERE employee_id=? ORDER BY id DESC LIMIT 12", (u["employee_id"],)))
    return jsonify(emp)


@app.post("/api/self/leave-request")
@login_required
def self_leave_request():
    u = me()
    if not u.get("employee_id"):
        return jsonify({"error": "لا يوجد ملف موظف مرتبط"}), 404
    emp = db.row_to_dict(db.query("SELECT * FROM employees WHERE id=?", (u["employee_id"],), one=True))
    d = body()
    lid = db.execute(
        """INSERT INTO leaves (company_id, employee_id, leave_type, start_date, end_date, days, paid, status)
           VALUES (?,?,?,?,?,?,?,'pending')""",
        (emp["company_id"], emp["id"], d.get("leave_type", "annual"), d.get("start_date"),
         d.get("end_date"), int(d.get("days") or 0), 1 if d.get("paid", True) else 0))
    # إشعار مديري الشركة
    for m in db.rows_to_list(db.query(
            "SELECT * FROM users WHERE company_id=? AND role='company_manager' AND is_active=1",
            (emp["company_id"],))):
        notify.push(m["id"], emp["company_id"], "leave_request",
                    "طلب إجازة جديد", f"طلب إجازة من {emp['name']}", email=m.get("email"))
    return jsonify({"id": lid}), 201


# ===========================================================================
# التقارير (Reports) + تصدير CSV / Excel / PDF
# ===========================================================================
@app.get("/api/reports/summary")
@require_perm("view_reports")
def report_summary():
    u = me()
    cid = scope_company_id(u, request.args.get("company_id"))
    cf = "WHERE company_id=?" if cid else ""
    p = (cid,) if cid else ()

    def count(sql, extra=()):
        return db.query(sql, extra, one=True)["n"]

    today = date.today().isoformat()
    if cid:
        companies_count = 1
    else:
        companies_count = count("SELECT COUNT(*) AS n FROM companies WHERE status!='archived'")
    summary = {
        "total_employees": count(f"SELECT COUNT(*) AS n FROM employees {cf}", p),
        "active_employees": count(
            "SELECT COUNT(*) AS n FROM employees WHERE status='active'" + (" AND company_id=?" if cid else ""), p),
        "total_licenses": count(f"SELECT COUNT(*) AS n FROM licenses {cf}", p),
        "expired_permits": count(
            "SELECT COUNT(*) AS n FROM permits WHERE expiry_date < ?" + (" AND company_id=?" if cid else ""),
            (today, cid) if cid else (today,)),
        "expired_licenses": count(
            "SELECT COUNT(*) AS n FROM licenses WHERE expiry_date < ?" + (" AND company_id=?" if cid else ""),
            (today, cid) if cid else (today,)),
        "alerts_count": len(generate_alerts(cid)),
        "companies": companies_count,
    }
    return jsonify(summary)


def _csv_response(rows, headers, filename):
    buf = io.StringIO()
    buf.write("﻿")
    writer = csv.writer(buf)
    writer.writerow(headers)
    for r in rows:
        writer.writerow(r)
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


def _xlsx_response(rows, headers, filename, sheet="Sheet1"):
    try:
        from openpyxl import Workbook
    except Exception:
        return jsonify({"error": "openpyxl غير مثبّت"}), 501
    wb = Workbook()
    ws = wb.active
    ws.title = sheet
    ws.append(headers)
    for r in rows:
        ws.append(list(r))
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return Response(buf.getvalue(),
                    mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


def _employee_export_rows(cid):
    sql = "SELECT e.id, e.name, e.civil_id, e.nationality, e.job_title, e.basic_salary, " \
          "e.hire_date, e.status, c.name AS company FROM employees e JOIN companies c ON c.id=e.company_id"
    params = []
    if cid:
        sql += " WHERE e.company_id=?"
        params.append(cid)
    rows = db.query(sql, params)
    return [[r["id"], r["name"], r["civil_id"], r["nationality"], r["job_title"],
             r["basic_salary"], r["hire_date"], r["status"], r["company"]] for r in rows]


_EMP_HEADERS = ["المعرف", "الاسم", "الرقم المدني", "الجنسية", "الوظيفة", "الراتب", "تاريخ التعيين", "الحالة", "الشركة"]


@app.get("/api/reports/export/employees")
@require_perm("export_reports")
def export_employees():
    u = me()
    cid = scope_company_id(u, request.args.get("company_id"))
    rows = _employee_export_rows(cid)
    if request.args.get("format") == "xlsx":
        return _xlsx_response(rows, _EMP_HEADERS, "employees.xlsx", "الموظفون")
    return _csv_response(rows, _EMP_HEADERS, "employees.csv")


@app.get("/api/reports/export/expiring")
@require_perm("export_reports")
def export_expiring():
    u = me()
    cid = scope_company_id(u, request.args.get("company_id"))
    alerts = generate_alerts(cid)
    data = [[a["category"], a["title"], a["detail"], a["expiry_date"] or "-",
             a["days_left"] if a["days_left"] is not None else "-", a["severity"]] for a in alerts]
    headers = ["النوع", "العنوان", "التفاصيل", "تاريخ الانتهاء", "الأيام المتبقية", "الخطورة"]
    if request.args.get("format") == "xlsx":
        return _xlsx_response(data, headers, "expiring.xlsx", "الانتهاءات")
    return _csv_response(data, headers, "expiring.csv")


@app.get("/api/reports/eos-settlement/<int:eid>.pdf")
@require_perm("calculate_eos")
def export_eos_pdf(eid):
    import pdf_export
    emp = db.query("SELECT * FROM employees WHERE id=?", (eid,), one=True)
    if not emp:
        return jsonify({"error": "غير موجود"}), 404
    if not ensure_company_access(emp["company_id"]):
        return deny()
    emp = db.row_to_dict(emp)
    comp = db.row_to_dict(db.query("SELECT * FROM companies WHERE id=?", (emp["company_id"],), one=True))
    end = request.args.get("end_date") or emp.get("end_date") or date.today().isoformat()
    reason = request.args.get("reason") or emp.get("end_reason") or "termination"
    try:
        result = calculate_eos(
            basic_salary=emp["basic_salary"], hire_date=emp["hire_date"], end_date=end,
            reason=reason, contract_type=emp.get("contract_type", "indefinite"),
            unused_leave_days=emp.get("annual_leave_balance") or 0,
            day_divisor=comp["eos_day_divisor"], max_months=comp["eos_max_months"])
        pdf = pdf_export.eos_settlement_pdf(emp["name"], comp["name"], result)
    except pdf_export.PdfUnavailable as e:
        return jsonify({"error": str(e)}), 501
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return Response(pdf, mimetype="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename=eos_{eid}.pdf"})


@app.get("/api/reports/salary-certificate/<int:eid>.pdf")
@require_perm("view_reports")
def export_salary_cert(eid):
    import pdf_export
    emp = db.query("SELECT * FROM employees WHERE id=?", (eid,), one=True)
    if not emp:
        return jsonify({"error": "غير موجود"}), 404
    if not ensure_company_access(emp["company_id"]):
        return deny()
    emp = db.row_to_dict(emp)
    comp = db.row_to_dict(db.query("SELECT * FROM companies WHERE id=?", (emp["company_id"],), one=True))
    try:
        pdf = pdf_export.salary_certificate_pdf(emp, comp["name"])
    except pdf_export.PdfUnavailable as e:
        return jsonify({"error": str(e)}), 501
    return Response(pdf, mimetype="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename=salary_cert_{eid}.pdf"})


# ===========================================================================
# سجل التدقيق (Audit Log)
# ===========================================================================
@app.get("/api/audit")
@login_required
def audit_log():
    u = me()
    limit = min(_int_or_none(request.args.get("limit")) or 200, 500)
    offset = max(_int_or_none(request.args.get("offset")) or 0, 0)
    if u["role"] == "super_admin":
        cid = request.args.get("company_id")
        if cid:
            rows = db.query("SELECT * FROM audit_log WHERE company_id=? ORDER BY id DESC LIMIT ? OFFSET ?",
                            (cid, limit, offset))
        else:
            rows = db.query("SELECT * FROM audit_log ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))
    else:
        rows = db.query("SELECT * FROM audit_log WHERE company_id=? ORDER BY id DESC LIMIT ? OFFSET ?",
                        (u["company_id"], limit, offset))
    return jsonify(db.rows_to_list(rows))


# ---------------------------------------------------------------------------
def create_app():
    db.init_db()
    from scheduler import start_scheduler
    start_scheduler(app)
    return app


if __name__ == "__main__":
    create_app()
    print(f">> قاعدة البيانات جاهزة. التشغيل على {config.HOST}:{config.PORT} (debug={config.DEBUG})")
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
