# -*- coding: utf-8 -*-
"""
طبقة قاعدة البيانات (SQLite) لنظام إدارة الموارد البشرية متعدد الشركات.
تُنشئ الجداول، تدير الاتصال، تطبّق العزل (Multi-Tenancy) عبر company_id،
وتدير الهجرات (migrations) عبر PRAGMA user_version + فهارس للأداء + WAL.
"""
import os
import sqlite3

from flask import g

DB_PATH = os.path.join(os.path.dirname(__file__), "instance", "hrms.db")

# إصدار المخطط الحالي. يُزاد عند كل تغيير ويُطبّق في migrate().
SCHEMA_VERSION = 2

SCHEMA = """
-- الشركات
CREATE TABLE IF NOT EXISTS companies (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    name_en         TEXT,
    commercial_reg  TEXT,
    entity_type     TEXT,
    status          TEXT NOT NULL DEFAULT 'active',  -- active / inactive / archived
    eos_day_divisor INTEGER NOT NULL DEFAULT 26,
    eos_max_months  INTEGER NOT NULL DEFAULT 18,
    alert_lead_days INTEGER NOT NULL DEFAULT 30,
    annual_leave_days INTEGER NOT NULL DEFAULT 30,   -- رصيد الإجازة السنوية القانوني
    workweek_hours  INTEGER NOT NULL DEFAULT 48,     -- ساعات العمل الأسبوعية
    gosi_rate       REAL NOT NULL DEFAULT 0,         -- نسبة خصم التأمينات (للكويتيين)
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- المستخدمون (Super Admin له company_id = NULL)
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id      INTEGER REFERENCES companies(id),
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    full_name       TEXT,
    email           TEXT,
    phone           TEXT,
    role            TEXT NOT NULL DEFAULT 'employee',  -- super_admin / company_manager / employee
    employee_id     INTEGER REFERENCES employees(id),  -- لبوابة الخدمة الذاتية
    is_active       INTEGER NOT NULL DEFAULT 1,
    must_change_password INTEGER NOT NULL DEFAULT 0,
    totp_secret     TEXT,
    totp_enabled    INTEGER NOT NULL DEFAULT 0,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until    TEXT,
    last_login      TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_permissions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    perm_code   TEXT NOT NULL,
    expires_at  TEXT,
    UNIQUE(user_id, perm_code)
);

CREATE TABLE IF NOT EXISTS business_files (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id         INTEGER NOT NULL REFERENCES companies(id),
    file_no            TEXT,
    file_name          TEXT,
    status             TEXT,
    issue_date         TEXT,
    commercial_reg     TEXT,
    classification     TEXT,
    authority          TEXT,
    legal_entity_type  TEXT,
    ownership_category TEXT,
    workers_count      INTEGER DEFAULT 0,
    licenses_count     INTEGER DEFAULT 0,
    created_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS licenses (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id        INTEGER NOT NULL REFERENCES companies(id),
    name              TEXT NOT NULL,
    license_no        TEXT,
    issuing_authority TEXT,
    license_type      TEXT DEFAULT 'main',
    status            TEXT DEFAULT 'active',
    issue_date        TEXT,
    expiry_date       TEXT,
    allowed_workers   INTEGER DEFAULT 0,
    address           TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

-- الأقسام / الهيكل التنظيمي
CREATE TABLE IF NOT EXISTS departments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id  INTEGER NOT NULL REFERENCES companies(id),
    name        TEXT NOT NULL,
    parent_id   INTEGER REFERENCES departments(id),
    manager_id  INTEGER REFERENCES employees(id),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS employees (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id    INTEGER NOT NULL REFERENCES companies(id),
    department_id INTEGER REFERENCES departments(id),
    civil_id      TEXT,
    name          TEXT NOT NULL,
    email         TEXT,
    phone         TEXT,
    nationality   TEXT,
    worker_type   TEXT,
    job_title     TEXT,
    basic_salary  REAL DEFAULT 0,
    hire_date     TEXT,
    end_date      TEXT,
    end_reason    TEXT,
    status        TEXT DEFAULT 'active',   -- active / terminated / resigned
    license_id    INTEGER REFERENCES licenses(id),
    contract_type TEXT DEFAULT 'indefinite',
    contract_end  TEXT,                    -- لعقود محددة المدة
    annual_leave_balance REAL NOT NULL DEFAULT 0,
    photo         TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS permits (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id  INTEGER NOT NULL REFERENCES companies(id),
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,             -- residency / work_permit
    number      TEXT,
    start_date  TEXT,
    expiry_date TEXT,
    status      TEXT DEFAULT 'active',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS documents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id  INTEGER NOT NULL REFERENCES companies(id),
    entity_type TEXT,                      -- company / employee / license
    entity_id   INTEGER,
    title       TEXT,
    file_path   TEXT,
    expiry_date TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS deductions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id  INTEGER NOT NULL REFERENCES companies(id),
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    amount      REAL NOT NULL DEFAULT 0,
    reason      TEXT,
    ded_type    TEXT DEFAULT 'manual',     -- manual / violation
    date        TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- البدلات (لمسيّر الرواتب)
CREATE TABLE IF NOT EXISTS allowances (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id  INTEGER NOT NULL REFERENCES companies(id),
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    name        TEXT,
    amount      REAL NOT NULL DEFAULT 0,
    recurring   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS leaves (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id  INTEGER NOT NULL REFERENCES companies(id),
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    leave_type  TEXT,                      -- annual / sick / maternity / hajj / unpaid
    start_date  TEXT,
    end_date    TEXT,
    days        INTEGER DEFAULT 0,
    paid        INTEGER DEFAULT 1,
    status      TEXT DEFAULT 'pending',    -- pending / approved / rejected
    balance_deducted INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- الحضور والانصراف
CREATE TABLE IF NOT EXISTS attendance (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id   INTEGER NOT NULL REFERENCES companies(id),
    employee_id  INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    date         TEXT NOT NULL,
    check_in     TEXT,
    check_out    TEXT,
    hours        REAL DEFAULT 0,
    overtime_hours REAL DEFAULT 0,
    status       TEXT DEFAULT 'present',   -- present / absent / leave / holiday
    note         TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- الجزاءات والإنذارات التأديبية
CREATE TABLE IF NOT EXISTS disciplinary_actions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id   INTEGER NOT NULL REFERENCES companies(id),
    employee_id  INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    action_type  TEXT,                     -- notice / warning / suspension / fine
    description  TEXT,
    action_date  TEXT,
    created_by   TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- العُهد والأصول
CREATE TABLE IF NOT EXISTS assets (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id    INTEGER NOT NULL REFERENCES companies(id),
    employee_id   INTEGER REFERENCES employees(id) ON DELETE SET NULL,
    name          TEXT,
    serial_no     TEXT,
    assigned_date TEXT,
    returned_date TEXT,
    note          TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- تقييم الأداء
CREATE TABLE IF NOT EXISTS performance_reviews (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id   INTEGER NOT NULL REFERENCES companies(id),
    employee_id  INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    period       TEXT,
    score        REAL,
    reviewer     TEXT,
    notes        TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- التاريخ الوظيفي (ترقيات / تغيّر راتب / تغيّر قسم)
CREATE TABLE IF NOT EXISTS employment_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id    INTEGER NOT NULL REFERENCES companies(id),
    employee_id   INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    event_type    TEXT,                    -- promotion / salary_change / department_change / contract
    old_value     TEXT,
    new_value     TEXT,
    effective_date TEXT,
    note          TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- تسويات نهاية الخدمة المحفوظة (لقطة وقت الإنهاء)
CREATE TABLE IF NOT EXISTS eos_settlements (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id   INTEGER NOT NULL REFERENCES companies(id),
    employee_id  INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    reason       TEXT,
    end_date     TEXT,
    total_settlement REAL,
    snapshot     TEXT,                      -- JSON كامل لنتيجة الحساب
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- مسيّر الرواتب
CREATE TABLE IF NOT EXISTS payroll_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id   INTEGER NOT NULL REFERENCES companies(id),
    period       TEXT NOT NULL,            -- YYYY-MM
    status       TEXT DEFAULT 'draft',     -- draft / finalized
    note         TEXT,
    created_by   TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS payslips (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        INTEGER NOT NULL REFERENCES payroll_runs(id) ON DELETE CASCADE,
    company_id    INTEGER NOT NULL REFERENCES companies(id),
    employee_id   INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    basic_salary  REAL DEFAULT 0,
    allowances    REAL DEFAULT 0,
    overtime_pay  REAL DEFAULT 0,
    deductions    REAL DEFAULT 0,
    gosi          REAL DEFAULT 0,
    gross         REAL DEFAULT 0,
    net           REAL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- مركز الإشعارات داخل التطبيق
CREATE TABLE IF NOT EXISTS notifications (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id   INTEGER,
    user_id      INTEGER REFERENCES users(id) ON DELETE CASCADE,
    type         TEXT,
    title        TEXT,
    body         TEXT,
    is_read      INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id  INTEGER,
    user_id     INTEGER,
    username    TEXT,
    action      TEXT,
    entity_type TEXT,
    entity_id   INTEGER,
    details     TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS transfers (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id  INTEGER NOT NULL REFERENCES employees(id),
    from_company INTEGER,
    to_company   INTEGER,
    note         TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# فهارس الأداء
INDEXES = """
CREATE INDEX IF NOT EXISTS idx_employees_company ON employees(company_id);
CREATE INDEX IF NOT EXISTS idx_employees_license ON employees(license_id);
CREATE INDEX IF NOT EXISTS idx_employees_status ON employees(status);
CREATE INDEX IF NOT EXISTS idx_employees_dept ON employees(department_id);
CREATE INDEX IF NOT EXISTS idx_licenses_company ON licenses(company_id);
CREATE INDEX IF NOT EXISTS idx_licenses_expiry ON licenses(expiry_date);
CREATE INDEX IF NOT EXISTS idx_permits_company ON permits(company_id);
CREATE INDEX IF NOT EXISTS idx_permits_employee ON permits(employee_id);
CREATE INDEX IF NOT EXISTS idx_permits_expiry ON permits(expiry_date);
CREATE INDEX IF NOT EXISTS idx_documents_company ON documents(company_id);
CREATE INDEX IF NOT EXISTS idx_documents_expiry ON documents(expiry_date);
CREATE INDEX IF NOT EXISTS idx_deductions_employee ON deductions(employee_id);
CREATE INDEX IF NOT EXISTS idx_leaves_employee ON leaves(employee_id);
CREATE INDEX IF NOT EXISTS idx_attendance_employee ON attendance(employee_id);
CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date);
CREATE INDEX IF NOT EXISTS idx_payslips_run ON payslips(run_id);
CREATE INDEX IF NOT EXISTS idx_payslips_employee ON payslips(employee_id);
CREATE INDEX IF NOT EXISTS idx_audit_company ON audit_log(company_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_users_company ON users(company_id);
"""


def get_db():
    """يرجع اتصال قاعدة البيانات الخاص بالطلب الحالي."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA journal_mode = WAL")  # تقليل الأقفال عند تعدد المستخدمين
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _column_names(conn, table):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def migrate(conn):
    """هجرات تدريجية على قواعد البيانات القائمة بناءً على user_version."""
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version >= SCHEMA_VERSION:
        return

    # هجرة من الإصدار 0/1 → 2: إضافة الأعمدة الجديدة للجداول القائمة
    added = {
        "companies": [
            ("annual_leave_days", "INTEGER NOT NULL DEFAULT 30"),
            ("workweek_hours", "INTEGER NOT NULL DEFAULT 48"),
            ("gosi_rate", "REAL NOT NULL DEFAULT 0"),
        ],
        "users": [
            ("email", "TEXT"), ("phone", "TEXT"), ("employee_id", "INTEGER"),
            ("must_change_password", "INTEGER NOT NULL DEFAULT 0"),
            ("totp_secret", "TEXT"), ("totp_enabled", "INTEGER NOT NULL DEFAULT 0"),
            ("last_login", "TEXT"),
        ],
        "employees": [
            ("department_id", "INTEGER"), ("email", "TEXT"), ("phone", "TEXT"),
            ("contract_end", "TEXT"),
            ("annual_leave_balance", "REAL NOT NULL DEFAULT 0"),
        ],
        "leaves": [
            ("balance_deducted", "INTEGER NOT NULL DEFAULT 0"),
        ],
    }
    for table, cols in added.items():
        try:
            existing = _column_names(conn, table)
        except sqlite3.OperationalError:
            continue
        for col, decl in cols:
            if col not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")

    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()


def init_db():
    """ينشئ الجداول والفهارس ويطبّق الهجرات."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    migrate(conn)
    conn.executescript(INDEXES)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()
    conn.close()


def query(sql, params=(), one=False):
    cur = get_db().execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def execute(sql, params=()):
    db = get_db()
    cur = db.execute(sql, params)
    db.commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id


def executemany(sql, seq):
    db = get_db()
    cur = db.executemany(sql, seq)
    db.commit()
    cur.close()


def transaction():
    """سياق معاملة: يضمن commit عند النجاح وrollback عند الخطأ.

    الاستخدام:
        with db.transaction() as conn:
            conn.execute(...)
    """
    return _Transaction(get_db())


class _Transaction:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        self.conn.execute("BEGIN")
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        return False


def row_to_dict(row):
    return dict(row) if row is not None else None


def rows_to_list(rows):
    return [dict(r) for r in rows]


def log_action(company_id, user, action, entity_type=None, entity_id=None, details=None):
    """يسجل عملية في سجل التدقيق."""
    execute(
        """INSERT INTO audit_log (company_id, user_id, username, action, entity_type, entity_id, details)
           VALUES (?,?,?,?,?,?,?)""",
        (company_id, user.get("id") if user else None, user.get("username") if user else None,
         action, entity_type, entity_id, details),
    )
