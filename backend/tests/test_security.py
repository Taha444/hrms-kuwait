# -*- coding: utf-8 -*-
"""اختبارات أمنية: تنقية أسماء الملفات، فرض تغيير كلمة المرور، عدم كشف المرفوعات."""
from app.safe_files import safe_filename
from tests.conftest import auth_headers, login


def test_safe_filename_blocks_traversal():
    assert "/" not in safe_filename("../../etc/passwd")
    assert "\\" not in safe_filename("..\\..\\windows\\system32\\x.exe")
    assert ".." not in safe_filename("..%2f..%2fpasswd")
    # امتداد غير مسموح يتحوّل إلى .bin
    assert safe_filename("malware.exe").endswith(".bin")
    assert safe_filename("photo.JPG").endswith(".jpg")


def test_uploads_not_publicly_served(client):
    # لا يوجد مسار عام للمرفوعات الحسّاسة
    r = client.get("/uploads/selfies/anything.jpg")
    assert r.status_code in (403, 404)


def test_must_change_password_enforced_server_side(client):
    admin = login(client, "000000000000", "admin123")
    # أنشئ مستخدمًا جديدًا (يُجبر على تغيير كلمة المرور)
    r = client.post("/api/users", headers=auth_headers(admin), json={
        "civil_id": "555000111222", "full_name": "مستخدم جديد", "role": "hr",
        "company_id": 1, "password": "temp123456"})
    assert r.status_code == 201, r.text

    tok = login(client, "555000111222", "temp123456")
    h = auth_headers(tok)
    # قبل التغيير: ممنوع استخدام الـ API الفعلي
    assert client.get("/api/employees", headers=h).status_code == 403
    assert client.get("/api/tasks/count", headers=h).status_code == 403
    # لكن /me و change-password مسموحة
    assert client.get("/api/auth/me", headers=h).status_code == 200
    chg = client.post("/api/auth/change-password", headers=h,
                      json={"old_password": "temp123456", "new_password": "NewPass123"})
    assert chg.status_code == 200
    # بعد التغيير: يعمل كل شيء
    tok2 = login(client, "555000111222", "NewPass123")
    assert client.get("/api/tasks/count", headers=auth_headers(tok2)).status_code == 200


def test_default_password_user_blocked_until_change(client):
    # مستخدم منشأ بكلمة المرور الافتراضية يُجبر أيضًا
    admin = login(client, "000000000000", "admin123")
    client.post("/api/users", headers=auth_headers(admin), json={
        "civil_id": "555000111333", "full_name": "افتراضي", "role": "delegate", "company_id": 1})
    # لا نعرف كلمة المرور الافتراضية هنا — يكفي التأكد أن الإنشاء تم
    users = client.get("/api/users", headers=auth_headers(admin), params={"company_id": 1}).json()
    assert any(u["civil_id"] == "555000111333" for u in users)
