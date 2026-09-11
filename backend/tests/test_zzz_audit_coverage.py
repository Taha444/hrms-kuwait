# -*- coding: utf-8 -*-
"""سلطٌة تُسحَب بلا سطر تدقيق — وشقيقُتها تُقيَّد.

**القياس**: كلُّ مساٍر يغيّر البيانات (``POST``/``PUT``/``PATCH``/
``DELETE``) ويكتب فعًلا، هل يُقيَّد في التدقيق؟ — مباشرًة أو بواسطٍة
تُدقِّق عنه. وأنذر الكنُس الأول عشرين موضًعا، وسقط سبعٌة منها حين تَبِع
الواسطة: حاالُت نهاية الخدمة كلُّها تمرّ بـ``_advance`` الذي يقيّد بقبٍل
وبعٍد ومعرّف ارتباط.

وبقي ثلاثَة عشر. **وأكثرُها لا يُدقَّق بحّق** ولا يُعَدّ عطًلا:

- حالُة الجولة التعريفية وتفضيُل قناة الإشعار — شأٌن شخصي.
- نقراُت صندوق المهامّ (التقاط · إطلاق · إنجاز) — والصفُّ نفسه يحمل من
  التقطها ومتى أُنجزت، فسطٌر لكل نقرة ضجيٌج يُغرِق ما يُقرأ.
- ``pro.add_note`` يكتب ``GovLog`` — وهو **هو** السجل.
- و``twofa.enroll`` يولّد سًرّا لم يُفعَّل بعد، والحدُث الأمني الحقيقي
  ``totp_enable`` مدقٌَّق بسطره.

**وأربعٌة تمسّ سلطًة أو إعداًدا، وأقواها**: ``users.reset_matrix`` يحذف
**كلَّ منحٍة دقيقة** من مستخدم ولا يقيّد شيًئا — و``copy_permissions``
بعده باثنَي عشر سطًرا يقيّد. شقيقتان على الكائن نفسه: إحداهما تحفظ من
غيّر السلطة والأخرى لا. ولم يكن يستقبل ``Request`` أصًلا، فلا عنواَن ولا
أداة.

وسطٌر يقول «أُعيد إلى الافتراضي» لا يكفي: من يراجع بعد شهٍر يحتاج **ما
فُقد بعينه**، لا الحكم.
"""
from __future__ import annotations

import ast
import pathlib
import re

from sqlalchemy import delete as sa_delete, select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

ADMIN = ("000000000000", "admin123")
HR1 = ("100000000002", "hr12345")

#: مواضٌع لا تُدقَّق بقرار، وكلٌّ منها بعلّته — تُسمّى صراحًة فلا يمرّ
#: موضٌع جديد صامًتا في ظلّها.
_DELIBERATELY_UNAUDITED = {
    ("selfservice.py", "complete_tour"): "حالُة جولٍة تعريفية — شأٌن شخصي",
    ("selfservice.py", "reset_tour"): "حالُة جولٍة تعريفية — شأٌن شخصي",
    ("notification_settings.py", "update_preferences"): "تفضيُل قناٍة شخصي",
    ("tasks.py", "update_status"): "الصفُّ يحمل حالَته ووقت إنجازها",
    ("tasks.py", "claim_task"): "الصفُّ يحمل من التقطها ومتى",
    ("tasks.py", "release_task"): "الصفُّ يحمل من التقطها ومتى",
    ("tasks.py", "bulk_task_action"): "نقراُت صندوٍق — والصفُّ يحمل نتيجتها",
    ("tasks.py", "retry_delivery"): "delivery_attempts على الصفّ نفسه",
    ("pro.py", "add_note"): "يكتب GovLog — وهو هو السجل",
    ("twofa.py", "enroll"): "سٌّر لم يُفعَّل — وtotp_enable مدقٌَّق بسطره",
}

MUT = {"post", "put", "patch", "delete"}


def _unaudited() -> list[tuple[str, int, str]]:
    """يتبع الواسطة مستوى واحًدا — وإلا أنذر كاذًبا في نصف المواضع."""
    root = pathlib.Path(__file__).resolve().parents[1] / "app" / "routers"
    out = []
    for p in sorted(root.rglob("*.py")):
        text = p.read_text(encoding="utf-8")
        lines = text.splitlines()
        tree = ast.parse(text)
        bodies = {n.name: "\n".join(lines[n.lineno - 1:
                                          getattr(n, "end_lineno", n.lineno)])
                  for n in ast.walk(tree)
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        auditing = {n for n, b in bodies.items() if "audit(" in b}
        for n in ast.walk(tree):
            if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            verbs = {getattr(d.func if isinstance(d, ast.Call) else d, "attr", None)
                     for d in n.decorator_list} & MUT
            if not verbs:
                continue
            body = bodies[n.name]
            if not any(w in body for w in ("db.commit()", "db.add(",
                                           "db.delete(", "db.execute(")):
                continue
            if "audit(" in body:
                continue
            if set(re.findall(r"\b(_\w+)\s*\(", body)) & auditing:
                continue
            out.append((p.name, n.lineno, n.name))
    return out


# ---------------------------------------------------------------------------
# الكنس
# ---------------------------------------------------------------------------

def test_no_new_mutating_endpoint_escapes_the_audit():
    """**الحارس الدائم**: لا مساَر كتابٍة جديد بلا سطر تدقيق.

    ومن أراد استثناًء سمّاه في ``_DELIBERATELY_UNAUDITED`` مع علّته —
    فقراٌر مكتوٌب بعلّته يُراجَع، وسهٌو صامٌت لا.
    """
    stray = [(f, ln, n) for f, ln, n in _unaudited()
             if (f, n) not in _DELIBERATELY_UNAUDITED]
    assert not stray, "مساراٌت تكتب ولا تُقيَّد:\n" + "\n".join(
        f"  {f}:{ln}  {n}()" for f, ln, n in stray)


def test_every_declared_exception_is_still_a_real_endpoint():
    """**واستثناٌء لموضٍع زال استثناٌء يُخفي غيره.**

    فالقائمُة تُنظَّف كما تُكتب: كلُّ ما فيها لا بدّ أن يكون ما زال
    مساَر كتابٍة غير مدقَّق، وإلا صار حرًفا ميًتا يوسّع الثقب.
    """
    live = {(f, n) for f, _ln, n in _unaudited()}
    dead = sorted(k for k in _DELIBERATELY_UNAUDITED if k not in live)
    assert not dead, f"استثناءاٌت لم تبقَ لها مواضع: {dead}"


# ---------------------------------------------------------------------------
# وسحُب السلطة يُقيَّد بما فُقد
# ---------------------------------------------------------------------------

def _grant(user_id: int, code: str = "employees.export") -> None:
    db = SessionLocal()
    try:
        db.add(models.UserPermission(user_id=user_id, perm_code=code))
        db.commit()
    finally:
        db.close()


def _hr_user_id() -> int:
    db = SessionLocal()
    try:
        return db.scalar(select(models.User.id).where(
            models.User.civil_id == HR1[0]))
    finally:
        db.close()


def test_resetting_the_matrix_records_what_was_removed(client):
    """**جوهر البند**: يُقيَّد ما فُقد بعينه لا الحكم وحده."""
    uid = _hr_user_id()
    _grant(uid)
    try:
        r = client.post(f"/api/users/{uid}/matrix/reset",
                        headers=auth_headers(login(client, *ADMIN)))
        assert r.status_code == 200, r.text[:300]

        db = SessionLocal()
        try:
            row = db.scalar(select(models.AuditLog).where(
                models.AuditLog.action == "reset_permission_matrix",
                models.AuditLog.entity_type == "user",
                models.AuditLog.entity_id == uid,
            ).order_by(models.AuditLog.id.desc()))
        finally:
            db.close()
        assert row is not None, "سُحبت منٌح بلا سطر تدقيق"
        assert "employees.export" in (row.before_json or {}).get("granted", []), \
            row.before_json
        assert (row.after_json or {}).get("granted") == []
    finally:
        db = SessionLocal()
        try:
            db.execute(sa_delete(models.UserPermission).where(
                models.UserPermission.user_id == uid))
            db.execute(sa_delete(models.AuditLog).where(
                models.AuditLog.action == "reset_permission_matrix"))
            db.commit()
        finally:
            db.close()


def test_the_two_sibling_endpoints_both_record_authority_changes():
    """وشقيقتان على السلطة نفسها لا تفترقان في التقييد."""
    import inspect

    from app.routers import users as U

    for fn in (U.reset_matrix, U.copy_permissions):
        assert "audit(" in inspect.getsource(fn), fn.__name__
