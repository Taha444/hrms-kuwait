# -*- coding: utf-8 -*-
"""النسخ الاحتياطي خارج الخادم — قرار المالك (2026-09-19).

**العطل المقيس** (DLV-16…21): لا نسَخ آليًّا متحقًَّقا منه، ولا اختباَر
استرجاع. بياناُت رواتٍب وإقاماٍت ومستنداٍت بلا نسخٍة مجرَّبة.

والقرار: نسُخ Railway المدمج (يفعّله المالك من لوحته) **و** نسخٌة ليلية
مشفَّرة إلى تخزيٍن خارجي (S3 / R2) — فلا يضيع كلُّ شيء إن ضاع الحساب
أو المنطقة.

**ما في النسخة:** كلُّ جداول القاعدة (سطٌر JSON لكل صفّ) + الملفاُت المرفوعة
(المستندات والسيلفي والتواقيع) + بياٌن بعدد صفوف كل جدول وبصمته. ويُشفَّر
الكلُّ بمفتاٍح لا يعرفه التخزين: من يملك الحاوية وحدها لا يقرأ الرواتب.

**والنسخُة التي لا تُسترجَع ليست نسخة** — فالاسترجاُع هنا أيًضا
(``restore_archive``)، ويُتحقَّق بعده أن عدَد صفوف كل جدول وبصمَة كل ملف
تطابق البيان. ويُختبر ذهابًا وإيابًا في ``tests/test_zzz_backup_roundtrip``.

الإعداد (متغيّرات البيئة)::

    BACKUP_S3_BUCKET        الحاوية (إلزامي لتفعيل الجدولة)
    BACKUP_ENCRYPTION_KEY   مفتاح Fernet — يُولَّد بـ``scripts/backup_now.py --new-key``
    BACKUP_S3_ENDPOINT      للتخزين المتوافق مع S3 غير AWS (Cloudflare R2 مثلًا)
    BACKUP_S3_ACCESS_KEY / BACKUP_S3_SECRET_KEY / BACKUP_S3_REGION
    BACKUP_S3_PREFIX        بادئة المفاتيح (افتراضًيا ``hrms-backups/``)
    BACKUP_RETENTION_DAYS   مدة الاحتفاظ (افتراضًيا 30، ويبقى أحدُث 7 دائمًا)
"""
from __future__ import annotations

import base64
import datetime as _dt
import decimal
import hashlib
import io
import json
import logging
import os
import struct
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine, inspect as sa_inspect, select, text
from sqlalchemy.engine import Engine

logger = logging.getLogger("hrms.backup")

FORMAT = 1
MAGIC = b"HRMSBK1\n"
CHUNK = 8 * 1024 * 1024


# ─── الإعداد ───────────────────────────────────────────────────────────

@dataclass
class BackupConfig:
    bucket: str
    key: str
    endpoint: str | None = None
    access_key: str | None = None
    secret_key: str | None = None
    region: str | None = None
    prefix: str = "hrms-backups/"
    retention_days: int = 30

    @classmethod
    def from_env(cls) -> "BackupConfig | None":
        bucket = os.environ.get("BACKUP_S3_BUCKET", "").strip()
        key = os.environ.get("BACKUP_ENCRYPTION_KEY", "").strip()
        if not bucket or not key:
            return None
        prefix = os.environ.get("BACKUP_S3_PREFIX", "hrms-backups/").strip() or "hrms-backups/"
        return cls(bucket=bucket, key=key,
                   endpoint=os.environ.get("BACKUP_S3_ENDPOINT") or None,
                   access_key=os.environ.get("BACKUP_S3_ACCESS_KEY") or None,
                   secret_key=os.environ.get("BACKUP_S3_SECRET_KEY") or None,
                   region=os.environ.get("BACKUP_S3_REGION") or None,
                   prefix=prefix if prefix.endswith("/") else prefix + "/",
                   retention_days=int(os.environ.get("BACKUP_RETENTION_DAYS", "30") or 30))


def new_key() -> str:
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode()


# ─── تسلسل القيم ───────────────────────────────────────────────────────

def _enc(v):
    if isinstance(v, _dt.datetime):
        return {"$dt": v.isoformat()}
    if isinstance(v, _dt.date):
        return {"$d": v.isoformat()}
    if isinstance(v, _dt.time):
        return {"$t": v.isoformat()}
    if isinstance(v, decimal.Decimal):
        return {"$dec": str(v)}
    if isinstance(v, (bytes, bytearray, memoryview)):
        return {"$b64": base64.b64encode(bytes(v)).decode()}
    return v


def _dec(v):
    if isinstance(v, dict) and len(v) == 1:
        (k, x), = v.items()
        if k == "$dt":
            return _dt.datetime.fromisoformat(x)
        if k == "$d":
            return _dt.date.fromisoformat(x)
        if k == "$t":
            return _dt.time.fromisoformat(x)
        if k == "$dec":
            return decimal.Decimal(x)
        if k == "$b64":
            return base64.b64decode(x)
    return v


# ─── التشفير على دفعات (لا تُحمَّل النسخة كلُّها في الذاكرة) ──────────────

def _encrypt_file(src: Path, dst: Path, key: str) -> None:
    from cryptography.fernet import Fernet

    f = Fernet(key.encode())
    with open(src, "rb") as fin, open(dst, "wb") as fout:
        fout.write(MAGIC)
        while True:
            chunk = fin.read(CHUNK)
            if not chunk:
                break
            tok = f.encrypt(chunk)
            fout.write(struct.pack(">I", len(tok)))
            fout.write(tok)


def _decrypt_file(src: Path, dst: Path, key: str) -> None:
    from cryptography.fernet import Fernet, InvalidToken

    f = Fernet(key.encode())
    with open(src, "rb") as fin, open(dst, "wb") as fout:
        if fin.read(len(MAGIC)) != MAGIC:
            raise ValueError("ليس ملف نسخة احتياطية لهذا النظام")
        while True:
            head = fin.read(4)
            if not head:
                break
            if len(head) != 4:
                raise ValueError("النسخة مبتورة")
            (n,) = struct.unpack(">I", head)
            tok = fin.read(n)
            if len(tok) != n:
                raise ValueError("النسخة مبتورة")
            try:
                fout.write(f.decrypt(tok))
            except InvalidToken as e:
                raise ValueError("مفتاح التشفير خاطئ أو النسخة معدَّلة") from e


# ─── الإنشاء ───────────────────────────────────────────────────────────

def _tables(engine: Engine) -> list[str]:
    from .database import Base

    names = set(Base.metadata.tables)
    live = set(sa_inspect(engine).get_table_names())
    return sorted(names & live) + (["alembic_version"] if "alembic_version" in live else [])


def create_archive(engine: Engine, upload_dir: str | None, out_path: Path, key: str,
                   meta: dict | None = None) -> dict:
    """يكتب نسخًة مشفَّرة إلى ``out_path`` ويعيد بيانها.

    **ولا نسخَة لقاعدٍة بلا جداول**: رابٌط خاطئ يفتح قاعدًة فارغة، فتخرج نسخٌة
    «ناجحة» لا تحوي شيًئا — ويطمئن إليها صاحبها حتى يحتاجها. فيُرفَض.
    """
    if not [t for t in _tables(engine) if t != "alembic_version"]:
        raise RuntimeError("القاعدة المصدر بلا جداول النظام — رابط خاطئ؟ لا تُكتب نسخة فارغة")
    manifest = {"format": FORMAT, "created_at": _dt.datetime.utcnow().isoformat() + "Z",
                "tables": {}, "files": {"count": 0, "bytes": 0, "sha256": {}}}
    manifest.update(meta or {})
    with tempfile.TemporaryDirectory() as tmp:
        plain = Path(tmp) / "backup.tar.gz"
        with tarfile.open(plain, "w:gz") as tar, engine.connect() as conn:
            for name in _tables(engine):
                buf = io.BytesIO()
                h = hashlib.sha256()
                n = 0
                for row in conn.execute(text(f'SELECT * FROM "{name}"')).mappings():
                    line = (json.dumps({k: _enc(v) for k, v in row.items()},
                                       ensure_ascii=False, sort_keys=True) + "\n").encode()
                    buf.write(line)
                    h.update(line)
                    n += 1
                data = buf.getvalue()
                ti = tarfile.TarInfo(f"db/{name}.jsonl")
                ti.size = len(data)
                tar.addfile(ti, io.BytesIO(data))
                manifest["tables"][name] = {"rows": n, "sha256": h.hexdigest()}
            if upload_dir and Path(upload_dir).is_dir():
                base = Path(upload_dir)
                for p in sorted(base.rglob("*")):
                    if not p.is_file():
                        continue
                    rel = p.relative_to(base).as_posix()
                    digest = hashlib.sha256(p.read_bytes()).hexdigest()
                    tar.add(p, arcname=f"files/{rel}")
                    manifest["files"]["sha256"][rel] = digest
                    manifest["files"]["count"] += 1
                    manifest["files"]["bytes"] += p.stat().st_size
            mdata = json.dumps(manifest, ensure_ascii=False, indent=1).encode()
            ti = tarfile.TarInfo("manifest.json")
            ti.size = len(mdata)
            tar.addfile(ti, io.BytesIO(mdata))
        _encrypt_file(plain, out_path, key)
    return manifest


# ─── الاسترجاع ─────────────────────────────────────────────────────────

def _is_empty(engine: Engine) -> bool:
    from .database import Base

    live = set(sa_inspect(engine).get_table_names())
    with engine.connect() as conn:
        for name in sorted(set(Base.metadata.tables) & live):
            if conn.execute(text(f'SELECT 1 FROM "{name}" LIMIT 1')).first():
                return False
    return True


def restore_archive(archive: Path, key: str, target_url: str, files_dir: str | None,
                    schema: str = "alembic", force: bool = False) -> dict:
    """يسترجع نسخًة في قاعدٍة **فارغة** ثم يتحقّق منها. يعيد تقرير التحقّق.

    لا يكتب فوق قاعدٍة فيها بيانات إلا بـ``force`` — فخطأٌ في الرابط لا
    يمحو الإنتاج. والمخطُط يُبنى بالترحيلات نفسها (``alembic``) لا بنسخٍة
    تقريبية منه، فتمضي الترحيلاُت اللاحقة عليه كما تمضي على الأصل.
    """
    from .database import Base

    with tempfile.TemporaryDirectory() as tmp:
        plain = Path(tmp) / "backup.tar.gz"
        _decrypt_file(archive, plain, key)
        with tarfile.open(plain, "r:gz") as tar:
            manifest = json.loads(tar.extractfile("manifest.json").read())
            if manifest.get("format") != FORMAT:
                raise ValueError(f"صيغة نسخة غير معروفة: {manifest.get('format')}")

            engine = create_engine(target_url)
            if schema == "alembic":
                _alembic_upgrade(target_url)
            else:
                Base.metadata.create_all(engine)
            if not force and not _is_empty(engine):
                raise RuntimeError("القاعدة الهدف ليست فارغة — لا يُكتب فوقها (استعمل force عن قصد)")

            live_cols = {t: {c["name"] for c in sa_inspect(engine).get_columns(t)}
                         for t in sa_inspect(engine).get_table_names()}
            dialect = engine.dialect.name
            with engine.begin() as conn:
                if dialect == "sqlite":
                    conn.execute(text("PRAGMA foreign_keys=OFF"))
                elif dialect == "postgresql":
                    # حلقاُت المفاتيح (الأقسام ↔ الموظفون ↔ المستخدمون) تمنع ترتيًبا
                    # يرضي القيود — فتُعلَّق مشغّلاتها أثناء الإدراج وحده.
                    conn.execute(text("SET session_replication_role = replica"))
                if "alembic_version" in live_cols:
                    conn.execute(text("DELETE FROM alembic_version"))
                for name, info in manifest["tables"].items():
                    if name not in live_cols:
                        raise RuntimeError(f"جدولٌ في النسخة لا وجود له في المخطط: {name}")
                    raw = tar.extractfile(f"db/{name}.jsonl").read()
                    if hashlib.sha256(raw).hexdigest() != info["sha256"]:
                        raise ValueError(f"بصمة الجدول {name} لا تطابق البيان")
                    rows = [{k: _dec(v) for k, v in json.loads(line).items() if k in live_cols[name]}
                            for line in raw.decode().splitlines() if line]
                    if rows:
                        cols = sorted(rows[0])
                        stmt = text(f'INSERT INTO "{name}" (' + ", ".join(f'"{c}"' for c in cols)
                                    + ") VALUES (" + ", ".join(f":{c}" for c in cols) + ")")
                        conn.execute(stmt, rows)
                if dialect == "postgresql":
                    conn.execute(text("SET session_replication_role = DEFAULT"))
                    for name in manifest["tables"]:
                        if "id" in live_cols.get(name, set()):
                            conn.execute(text(
                                f"SELECT setval(pg_get_serial_sequence('\"{name}\"', 'id'), "
                                f"COALESCE((SELECT MAX(id) FROM \"{name}\"), 1))"))
            if files_dir:
                dest = Path(files_dir)
                for m in tar.getmembers():
                    if not m.name.startswith("files/") or not m.isfile():
                        continue
                    rel = m.name[len("files/"):]
                    out = (dest / rel).resolve()
                    if dest.resolve() not in out.parents:
                        raise ValueError(f"مسار ملف خارج مجلد الاسترجاع: {rel}")
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_bytes(tar.extractfile(m).read())
    return verify_restore(manifest, target_url, files_dir)


def _alembic_upgrade(target_url: str) -> None:
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, DATABASE_URL=target_url)
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                   cwd=root, env=env, check=True)


def verify_restore(manifest: dict, target_url: str, files_dir: str | None) -> dict:
    """عدُد صفوف كل جدول وبصمُة كل ملف — مقابل البيان."""
    engine = create_engine(target_url)
    bad: list[str] = []
    with engine.connect() as conn:
        for name, info in manifest["tables"].items():
            n = conn.execute(text(f'SELECT COUNT(*) FROM "{name}"')).scalar()
            if n != info["rows"]:
                bad.append(f"{name}: {n} ≠ {info['rows']}")
    files_ok = 0
    if files_dir:
        for rel, digest in manifest["files"]["sha256"].items():
            p = Path(files_dir) / rel
            if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != digest:
                bad.append(f"ملف: {rel}")
            else:
                files_ok += 1
    if not [t for t in manifest["tables"] if t != "alembic_version"]:
        bad.append("النسخة بلا جداول — لا تُعدّ نسخة")
    return {"ok": not bad, "tables": len(manifest["tables"]),
            "rows": sum(t["rows"] for t in manifest["tables"].values()),
            "files": files_ok, "problems": bad, "created_at": manifest.get("created_at"),
            "commit": manifest.get("commit"), "migration_version": manifest.get("migration_version")}


# ─── التخزين الخارجي والاحتفاظ ────────────────────────────────────────

def _s3(cfg: BackupConfig):
    import boto3

    return boto3.client("s3", endpoint_url=cfg.endpoint, region_name=cfg.region,
                        aws_access_key_id=cfg.access_key, aws_secret_access_key=cfg.secret_key)


def object_name(cfg: BackupConfig, at: _dt.datetime) -> str:
    return f"{cfg.prefix}hrms-{at.strftime('%Y%m%dT%H%M%SZ')}.bkp"


def expired(keys: list[tuple[str, _dt.datetime]], now: _dt.datetime,
            retention_days: int, keep_min: int = 7) -> list[str]:
    """ما يُحذف: أقدُم من مدة الاحتفاظ — ويبقى أحدُث ``keep_min`` دائمًا."""
    ordered = sorted(keys, key=lambda kv: kv[1], reverse=True)
    cutoff = now - _dt.timedelta(days=retention_days)
    return [k for i, (k, at) in enumerate(ordered) if i >= keep_min and at < cutoff]


def run_backup(cfg: BackupConfig) -> dict:
    """ينشئ نسخًة، يرفعها، يطبّق الاحتفاظ. يرمي عند الفشل (فيُنبَّه المجدوِل)."""
    from .config import settings
    from .database import engine

    meta = {"migration_version": None, "commit": os.environ.get("RAILWAY_GIT_COMMIT_SHA")
            or os.environ.get("GIT_COMMIT") or None}
    try:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).first()
            meta["migration_version"] = row[0] if row else None
    except Exception:  # noqa: BLE001
        pass
    upload_dir = settings.upload_dir if settings.storage_backend == "local" else None
    now = _dt.datetime.utcnow()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "backup.bkp"
        manifest = create_archive(engine, upload_dir, out, cfg.key, meta)
        client = _s3(cfg)
        name = object_name(cfg, now)
        client.upload_file(str(out), cfg.bucket, name)
        size = out.stat().st_size
    listed = client.list_objects_v2(Bucket=cfg.bucket, Prefix=cfg.prefix).get("Contents", [])
    keys = [(o["Key"], o["LastModified"].replace(tzinfo=None)) for o in listed
            if o["Key"].endswith(".bkp")]
    removed = expired(keys, now, cfg.retention_days)
    for k in removed:
        client.delete_object(Bucket=cfg.bucket, Key=k)
    logger.info("backup: %s (%d bytes, %d rows, %d files), removed %d",
                name, size, sum(t["rows"] for t in manifest["tables"].values()),
                manifest["files"]["count"], len(removed))
    return {"object": name, "bytes": size, "tables": len(manifest["tables"]),
            "files": manifest["files"]["count"], "removed": removed,
            "files_note": None if upload_dir else "الملفات على S3 التطبيق — خارج هذه النسخة"}


def download(cfg: BackupConfig, name: str | None, dst: Path) -> str:
    """ينزّل نسخًة بعينها أو أحدَثها — ويعيد اسمها."""
    client = _s3(cfg)
    if not name:
        listed = client.list_objects_v2(Bucket=cfg.bucket, Prefix=cfg.prefix).get("Contents", [])
        listed = [o for o in listed if o["Key"].endswith(".bkp")]
        if not listed:
            raise RuntimeError("لا نسخ في الحاوية")
        name = max(listed, key=lambda o: o["LastModified"])["Key"]
    client.download_file(cfg.bucket, name, str(dst))
    return name


def last_success(db) -> _dt.datetime | None:
    """آخر نسخٍة ليلية نجحت — من سجلّ الجولات نفسه."""
    from . import models

    row = db.scalar(select(models.JobRun).where(
        models.JobRun.job == "backup", models.JobRun.status == "done"
    ).order_by(models.JobRun.finished_at.desc()).limit(1))
    return row.finished_at if row else None
