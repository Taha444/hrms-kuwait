# -*- coding: utf-8 -*-
"""تهيئة الاختبارات: قاعدة بيانات SQLite مؤقتة + عميل اختبار + بذور."""
import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(tempfile.gettempdir(), 'hrms_test.db')}"
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["UPLOAD_DIR"] = os.path.join(tempfile.gettempdir(), "hrms_test_uploads")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

# حذف قاعدة الاختبار القديمة إن وُجدت
_db = os.environ["DATABASE_URL"].replace("sqlite:///", "")
if os.path.exists(_db):
    os.remove(_db)

from app.database import Base, engine  # noqa: E402
from app import seed as seed_module  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    Base.metadata.drop_all(bind=engine)
    seed_module.run()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def login(client, civil_id, password):
    r = client.post("/api/auth/login", json={"civil_id": civil_id, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}
