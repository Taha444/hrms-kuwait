# -*- coding: utf-8 -*-
"""P1-01 — دوام التخزين يُقاس، ولا يُفترَض من اسم الخلفية.

**قرار المالك**: قرص Railway دائم. والخلفية تبقى ``local`` — هي كتابة
على قرص، وإنما يتغيّر أيُّ قرص.

**ولهذا لم يعد الفحص القديم صالًحا**: كان يَسِم ``local`` على الإنتاج
«degraded» بلا شرط. ومع القرص الدائم يبقى ``local`` وهو سليم — ففحص
يشتكي دائًما يُدرَّب الناس على تجاهله، ثم لا يُرى حين يشتكي بحقّ.

**ثلاث إشارات، أقواها ما يقيس الضرر نفسه**: مستندات صادرة سجلُّها في
القاعدة وملفها مفقود. تعمل أًيا كان الضبط أو أسماء متغيّرات المنصّة —
بخلاف قراءة متغيّر بيئة، وهي أضعفها لأن اسمه بيد المنصّة.

و``persistent`` ثلاثيّ عمًدا: ``True`` بدليل، ``False`` بدليل،
و``None`` حين لا دليل بعد. و«لا أعرف» جواب صادق يُفحَص لاحًقا؛ أما
«سليم» بلا دليل فهو الذي أوقع الضياع الصامت أصًلا.
"""
from __future__ import annotations

import json
import os
from datetime import datetime

import pytest
from sqlalchemy import select

from app import models, storage_persistence as sp
from app.config import settings
from app.database import SessionLocal


@pytest.fixture
def clean_marker(tmp_path, monkeypatch):
    """مجلّد رفع خاص بهذا الاختبار — العلامة الحقيقية لا تُمسّ."""
    d = tmp_path / "uploads"
    d.mkdir()
    monkeypatch.setattr(settings, "upload_dir", str(d))
    monkeypatch.delenv(sp.MOUNT_ENV, raising=False)
    return d


def test_the_first_boot_claims_nothing(clean_marker):
    """**جوهر الصدق**: أول إقلاع لا يُعلَن سليًما ولا معطوًبا."""
    sp.record_boot()
    r = sp.report()
    assert r["persistent"] is None, r
    assert r["reason"], "حالة بلا سبب"
    assert r["boot_count"] == 1


def test_surviving_a_restart_is_evidence(clean_marker):
    """وبقاء العلامة عبر إقلاع ثانٍ دليل تجريبي لا وعد."""
    sp.record_boot()
    sp.record_boot()                       # نشرة ثانية، القرص نفسه
    r = sp.report()
    assert r["persistent"] is True, r
    assert r["survived_restart"] is True
    assert r["boot_count"] == 2


def test_a_wiped_disk_does_not_look_survived(clean_marker):
    """وقرص يُمحى لا يبدو ناجًيا: العلامة تذهب معه.

    وهذا ما كان يقع فعًلا — النشرة تمسح القرص فيبدأ العدّ من الصفر.
    """
    sp.record_boot()
    os.remove(os.path.join(str(clean_marker), sp.MARKER_NAME))
    sp.record_boot()                       # حاوية جديدة، قرص ممسوح
    r = sp.report()
    assert r["persistent"] is None, r
    assert r["survived_restart"] is False


def test_a_declared_mount_is_a_weaker_but_real_signal(clean_marker, monkeypatch):
    """والقرص الدائم المُعلَن يُحسم به قبل توفّر دليل النجاة."""
    monkeypatch.setenv(sp.MOUNT_ENV, str(clean_marker.parent))
    sp.record_boot()
    r = sp.report()
    assert r["persistent"] is True, r
    assert r["upload_dir_under_mount"] is True


def test_a_mount_elsewhere_does_not_count(clean_marker, monkeypatch, tmp_path):
    """ولا يكفي وجود قرص دائم: يجب أن يقع مجلّد الرفع **داخله**.

    وهو الخطأ الأرجح عملًيا: يُضاف القرص ويُنسى ``UPLOAD_DIR``، فيبدو
    كل شيء مضبوًطا والكتابة على قرص الحاوية.
    """
    other = tmp_path / "elsewhere"
    other.mkdir()
    monkeypatch.setenv(sp.MOUNT_ENV, str(other))
    sp.record_boot()
    r = sp.report()
    assert r["persistent"] is None, r
    assert r["upload_dir_under_mount"] is False


def test_missing_files_convict_regardless_of_every_other_signal(clean_marker):
    """**الإشارة الأقوى**: ملفات ضائعة تُدين ولو بدت كل الإشارات سليمة.

    الضرر نفسه لا وكيل عنه — ولا ينفع معه أن العلامة نجت.
    """
    sp.record_boot()
    sp.record_boot()                       # دليل نجاة… ومع ذلك:

    db = SessionLocal()
    made = None
    try:
        cid = db.scalar(select(models.Company.id).order_by(models.Company.id))
        eid = db.scalar(select(models.Employee.id).order_by(models.Employee.id))
        doc = models.Document(
            company_id=cid, entity_type="employee", entity_id=eid,
            document_type_code="probe_lost", title="مستند ضائع",
            file_path="generated/does_not_exist_at_all.pdf",
            is_issued=True, is_current=True, version=1)
        db.add(doc)
        db.commit()
        made = doc.id
        r = sp.report(db)
    finally:
        if made:
            db.execute(models.Document.__table__.delete().where(
                models.Document.id == made))
            db.commit()
        db.close()

    assert r["persistent"] is False, r
    assert r["missing_files"]["missing"] >= 1, r["missing_files"]
    assert "مفقود" in r["reason"], r["reason"]


def test_the_marker_is_hidden_and_not_a_document(clean_marker):
    """والعلامة لا تظهر كملف مستخدم: نقطة في أولها وحجمها ثابت."""
    sp.record_boot()
    assert sp.MARKER_NAME.startswith("."), sp.MARKER_NAME
    for _ in range(60):
        sp.record_boot()
    data = json.loads((clean_marker / sp.MARKER_NAME).read_text(encoding="utf-8"))
    assert len(data["boots"]) <= sp.MAX_BOOTS, len(data["boots"])
    # والعدّاد لا يُقصّ مع القائمة: «نجا مراًرا» غير «كُتب لتوّه».
    assert data["boot_count"] > sp.MAX_BOOTS


def test_a_broken_marker_does_not_break_the_boot(clean_marker):
    """وعلامة تالفة لا تُسقط الإقلاع: قياس الدوام لا يمنع النظام."""
    (clean_marker / sp.MARKER_NAME).write_text("ليس JSON", encoding="utf-8")
    sp.record_boot()
    r = sp.report()
    assert r["boot_count"] == 1, r


def test_an_upload_dir_inside_the_image_is_called_out(monkeypatch):
    """والتحذير عند الإقلاع يسبق ضياع أول مستند."""
    app_dir = os.path.dirname(os.path.dirname(sp.__file__))
    monkeypatch.setattr(settings, "upload_dir", os.path.join(app_dir, "uploads"))
    monkeypatch.setattr(type(settings), "is_production",
                        property(lambda self: True))
    monkeypatch.delenv(sp.MOUNT_ENV, raising=False)
    assert sp.looks_ephemeral() is True


def test_a_volume_path_is_not_called_out(monkeypatch, tmp_path):
    """ولا يُحذَّر من مسار سليم: تحذير على كل شيء يعني لا شيء."""
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "data" / "uploads"))
    monkeypatch.setattr(type(settings), "is_production",
                        property(lambda self: True))
    monkeypatch.delenv(sp.MOUNT_ENV, raising=False)
    assert sp.looks_ephemeral() is False


def test_health_stops_complaining_about_a_healthy_local_disk(client, monkeypatch,
                                                             tmp_path):
    """**ما تغيّر عملًيا**: قرص دائم لا يُوسَم degraded إلى الأبد.

    الفحص القديم كان يشتكي من ``local`` على الإنتاج بلا شرط — ومع
    القرص الدائم يبقى ``local`` وهو سليم.
    """
    d = tmp_path / "vol" / "uploads"
    d.mkdir(parents=True)
    monkeypatch.setattr(settings, "upload_dir", str(d))
    monkeypatch.setenv(sp.MOUNT_ENV, str(tmp_path / "vol"))
    monkeypatch.setattr(type(settings), "is_production",
                        property(lambda self: True))
    sp.record_boot()

    from tests.conftest import auth_headers, login
    hdr = auth_headers(login(client, "000000000000", "admin123"))
    r = client.get("/api/health/deep", headers=hdr)
    assert r.status_code in (200, 503), r.status_code
    storage = r.json()["checks"]["storage"]
    assert storage["status"] == "ok", storage
    assert storage["persistence"]["persistent"] is True, storage


def test_moving_the_upload_dir_is_not_an_accusation(clean_marker):
    """**اتّهام كاذب مقنع أسوأ من لا فحص.**

    أول كتابة عدّت كل مستند مفقود إدانًة للقرص: جرّبتُ توجيه
    ``UPLOAD_DIR`` إلى مسار جديد فقرأت «42 من 42 مفقود» — والقرص لم
    يفقد شيًئا، المجلّد تغيّر لا أكثر.

    وهذا ما يقع يوم يُوجَّه المسار إلى القرص الدائم لأول مرّة: يتّهم
    الفحصُ الإصلاحَ نفسه برقم مقنع، فيُدرَّب الناس على تجاهله.
    """
    # الحالة تُبنى هنا ولا تُستعار مما يخلّفه غيره: أول كتابة اعتمدت
    # على مستندات تركتها اختبارات أخرى، فمرّت في المجموعة وسقطت منفردة.
    db = SessionLocal()
    made = None
    try:
        cid = db.scalar(select(models.Company.id).order_by(models.Company.id))
        eid = db.scalar(select(models.Employee.id).order_by(models.Employee.id))
        doc = models.Document(
            company_id=cid, entity_type="employee", entity_id=eid,
            document_type_code="probe_legacy", title="مستند سابق للقرص",
            file_path="generated/written_before_this_disk.pdf",
            is_issued=True, is_current=True, version=1,
            created_at=datetime(2020, 1, 1))
        db.add(doc)
        db.commit()
        made = doc.id

        sp.record_boot()                   # القرص يبدأ **بعد** ذلك المستند
        rep = sp.report(db)
        lost = rep["missing_files"]
    finally:
        if made:
            db.execute(models.Document.__table__.delete().where(
                models.Document.id == made))
            db.commit()
        db.close()

    # مستند أقدم من هذا القرص: يُعدّ إرًثا لا إدانة.
    assert lost["checked"] > 0, "لا مستندات صادرة — القياس فارغ"
    assert lost["missing"] == 0, (
        f"اتُّهم القرص بملفات كُتبت قبله: {lost}"
    )
    assert lost["legacy_missing"] > 0, (
        "لم يُرصد الإرث أصًلا — فالتمييز غير مقيس"
    )
    assert rep["persistent"] is not False, rep["reason"]
    # ويُقال ولا يُخفى: خبر يُبلَّغ.
    assert "أقدم من هذا القرص" in rep["reason"], rep["reason"]


def test_a_loss_after_the_disk_started_still_convicts(clean_marker):
    """ولا يصير التمييز باًبا خلفًيا: ما ضاع بعد بدء القرص يُدين."""
    sp.record_boot()
    db = SessionLocal()
    made = None
    try:
        cid = db.scalar(select(models.Company.id).order_by(models.Company.id))
        eid = db.scalar(select(models.Employee.id).order_by(models.Employee.id))
        doc = models.Document(
            company_id=cid, entity_type="employee", entity_id=eid,
            document_type_code="probe_recent_loss", title="ضاع بعد البدء",
            file_path="generated/vanished_after_start.pdf",
            is_issued=True, is_current=True, version=1)
        db.add(doc)
        db.commit()
        made = doc.id
        rep = sp.report(db)
    finally:
        if made:
            db.execute(models.Document.__table__.delete().where(
                models.Document.id == made))
            db.commit()
        db.close()
    assert rep["persistent"] is False, rep
    assert rep["missing_files"]["missing"] >= 1, rep["missing_files"]


def test_a_mount_point_inside_the_app_tree_is_not_a_warning(monkeypatch):
    """**الحالة التي كشفها ضبط الإنتاج الفعلي.**

    القرص مركَّب على ``/app/backend/uploads`` — وهو **نفسه** ما يحسبه
    التطبيق (``WORKDIR /app/backend`` + ``upload_dir="./uploads"``)،
    فلا يلزم متغيّر بيئة أصًلا. ضبط سليم بلا ضبط.

    وفحصي كان سيحذّر منه كذًبا لأنه داخل ``/app``. وتحذير من ضبط سليم
    هو بالضبط ما يُدرِّب الناس على تجاهل التحذيرات — العيب الذي بُني
    هذا الملف كلّه لتجنّبه.

    والقاعدة الصحيحة ليست «تجنّب /app» بل «لا تُركّب فوق محتًوى
    تحمله الصورة». و``backend/uploads`` مستبعَد في ``.dockerignore``.
    """
    app_dir = os.path.dirname(os.path.dirname(sp.__file__))
    path = os.path.join(app_dir, "uploads")
    monkeypatch.setattr(settings, "upload_dir", path)
    monkeypatch.setattr(type(settings), "is_production",
                        property(lambda self: True))
    monkeypatch.delenv(sp.MOUNT_ENV, raising=False)

    # بلا تركيب: تحذير محقّ.
    monkeypatch.setattr(sp, "is_mount_point", lambda: False)
    assert sp.looks_ephemeral() is True

    # وبتركيب فعلي على المسار نفسه: لا تحذير.
    monkeypatch.setattr(sp, "is_mount_point", lambda: True)
    assert sp.looks_ephemeral() is False, (
        "حُذِّر من قرص دائم مركَّب — إنذار كاذب على ضبط سليم"
    )


def test_a_mount_point_is_evidence_on_the_first_boot(clean_marker, monkeypatch):
    """وهو دليل **فوري**: لا ينتظر نشرة ثانية ولا اسم متغيّر بيئة.

    ``os.path.ismount`` يسأل النظام: هل هذا المسار على جهاز غير جهاز
    أبيه؟ — قياس للواقع لا للإعلان.
    """
    monkeypatch.setattr(sp, "is_mount_point", lambda: True)
    sp.record_boot()
    r = sp.report()
    assert r["persistent"] is True, r
    assert r["upload_dir_is_mount_point"] is True
    assert r["boot_count"] == 1, "احتاج نشرة ثانية رغم وجود دليل فوري"


def test_the_docs_match_the_production_mount(monkeypatch):
    """والدليل يذكر المسار الذي يعمل بلا ضبط — لا مساًرا يحتاجه.

    نصيحة تخالف ما يعمل فعًلا تُنتج ضبًطا ثانًيا لا لزوم له.
    """
    from pathlib import Path

    doc = Path(__file__).resolve().parents[2] / "docs" / "DEPLOY_RAILWAY_VOLUME.md"
    if not doc.exists():
        return
    text = doc.read_text(encoding="utf-8")
    assert "/app/backend/uploads" in text, "الدليل لا يذكر المسار العامل"
    assert "لا تُركّب القرص فوق مسار" in text, (
        "الدليل ما زال يقول «تجنّب /app» بدل القاعدة الصحيحة"
    )
