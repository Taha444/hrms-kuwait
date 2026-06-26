# -*- coding: utf-8 -*-
"""تهيئة pytest: قاعدة بيانات مؤقتة معزولة + عميل اختبار."""
import os
import tempfile

import pytest


@pytest.fixture(scope="session", autouse=True)
def _isolated_db():
    """يوجّه قاعدة البيانات إلى ملف مؤقت ويزرع بيانات تجريبية."""
    import db
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db.DB_PATH = path
    import seed
    seed.DB_PATH = path
    seed.dbmod.DB_PATH = path
    seed.run()
    yield
    for suffix in ("", "-shm", "-wal"):
        try:
            os.remove(path + suffix)
        except OSError:
            pass


@pytest.fixture
def app_client():
    from app import app
    app.testing = True
    return app.test_client()


def _login(client, username="admin", password="admin123"):
    return client.post("/api/login", json={"username": username, "password": password})


@pytest.fixture
def admin(app_client):
    _login(app_client)
    return app_client


@pytest.fixture
def manager1(app_client):
    _login(app_client, "manager1", "manager123")
    return app_client
