# -*- coding: utf-8 -*-
"""P1-01 — هل يبقى ما نكتبه؟ قياس، لا افتراض.

**العطل**: قرص الحاوية يُمحى مع كل نشرة. السجلّ يبقى في القاعدة والملف
يختفي، فيبدو المستند موجوًدا في ملف الموظف حتى يُضغط زرّ التنزيل. وقد
وقع فعًلا.

**والقرار**: قرص Railway دائم (Volume) يُركَّب على مسار، ويوجَّه
``UPLOAD_DIR`` إليه. والخلفية تبقى ``local`` — فهي كتابة على قرص، وإنما
تغيّر أيُّ قرص.

**ولهذا لا يصلح الفحص القديم**: كان يَسِم ``local`` على الإنتاج
«degraded» بلا شرط. ومع القرص الدائم يبقى ``local`` وهو سليم — ففحص
يشتكي دائًما يُدرَّب الناس على تجاهله، ثم لا يُرى حين يشتكي بحقّ.

**ثلاث إشارات، أقواها ما يقيس الضرر نفسه:**

1. ``missing_files`` — عيّنة من المستندات الصادرة: كم منها سجلّه في
   القاعدة وملفه غير موجود؟ هذا **الضرر ذاته** لا وكيل عنه، ويُقاس على
   البيانات الحقيقية أًيا كان الضبط أو أسماء متغيّرات البيئة.

2. ``survived_restart`` — علامة تُكتب عند كل إقلاع. وجود علامة من إقلاع
   سابق يعني أن القرص نجا من استبدال حاوية — دليل تجريبي على الدوام،
   لا وعد به.

3. ``mount_hint`` — ``RAILWAY_VOLUME_MOUNT_PATH`` إن وُجد. إشارة مبكرة
   قبل أن تتوفّر الأولى أو الثانية، **وأضعفها**: تعتمد على اسم متغيّر
   تحدّده المنصّة وقد تغيّره. فلا يُبنى عليها حكم وحدها.

والأولى وحدها تكفي للإدانة؛ والثانية وحدها تكفي للبراءة؛ والثالثة
ترجيح لا حكم.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

from .config import settings

#: اسم ملف العلامة داخل مجلّد الرفع. نقطة في أوله فلا يظهر في أي تصفّح.
MARKER_NAME = ".persistence.json"

#: كم إقلاًعا نحتفظ به. الغرض إثبات النجاة لا حفظ التاريخ.
MAX_BOOTS = 20

#: متغيّر Railway حين يكون القرص الدائم مركًَّبا.
MOUNT_ENV = "RAILWAY_VOLUME_MOUNT_PATH"


def _marker_path() -> str:
    return os.path.join(settings.upload_dir, MARKER_NAME)


def _read_marker() -> dict:
    try:
        with open(_marker_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def record_boot() -> dict:
    """يسجّل هذا الإقلاع في العلامة، ويعيدها بعد التحديث.

    يُستدعى عند الإقلاع. الفشل هنا لا يُسقط التطبيق: قياس الدوام لا
    يستحقّ أن يمنع النظام من العمل.
    """
    data = _read_marker()
    boots = [b for b in (data.get("boots") or []) if isinstance(b, dict)]
    now = datetime.now(timezone.utc).isoformat()
    boots.append({"id": uuid.uuid4().hex[:12], "at": now})
    data = {
        "first_seen": data.get("first_seen") or now,
        "boots": boots[-MAX_BOOTS:],
        # العدّاد لا يُقصّ مع القائمة: نشرات كثيرة على قرص دائم تُبقيه
        # يكبر، وهو ما يميّز «نجا مراًرا» عن «كُتب لتوّه».
        "boot_count": int(data.get("boot_count") or 0) + 1,
    }
    try:
        os.makedirs(settings.upload_dir, exist_ok=True)
        with open(_marker_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except OSError:
        pass
    return data


def mount_hint() -> str | None:
    """مسار القرص الدائم كما تعلنه المنصّة، إن أعلنته."""
    return (os.environ.get(MOUNT_ENV) or "").strip() or None


def is_mount_point() -> bool:
    """هل مجلّد الرفع **نقطة تركيب** فعًلا؟ — قياس مباشر لا اسم متغيّر.

    ``os.path.ismount`` يسأل النظام نفسه: هل هذا المسار على جهاز غير
    جهاز أبيه؟ وهو أصدق من ``RAILWAY_VOLUME_MOUNT_PATH`` لأنه لا يعتمد
    على اسم تحدّده المنصّة وقد تغيّره — يقيس الواقع لا الإعلان.

    وأضفتُه بعد أن رأيت ضبط الإنتاج الفعلي: القرص مركَّب على
    ``/app/backend/uploads`` وهو **نفسه** ما يحسبه التطبيق
    (``WORKDIR /app/backend`` + ``upload_dir="./uploads"``) — ضبط سليم
    بلا متغيّر بيئة، وكان فحصي سيحذّر منه كذًبا لأنه داخل ``/app``.
    """
    try:
        return os.path.ismount(os.path.realpath(settings.upload_dir))
    except OSError:
        return False


def _under_mount() -> bool:
    mount = mount_hint()
    if not mount:
        return False
    try:
        up = os.path.realpath(settings.upload_dir)
        mp = os.path.realpath(mount)
        return up == mp or up.startswith(mp.rstrip(os.sep) + os.sep)
    except OSError:
        return False


def missing_files(db, sample: int = 50) -> dict:
    """كم مستنًدا صادًرا سجلُّه في القاعدة وملفه غير موجود؟

    **هذا الضرر نفسه لا وكيل عنه.** ولا يُقاس على المستندات المرفوعة
    وحدها بل على الصادرة (``is_issued``): تلك التي وُلّدت من النظام
    ويُحتجّ بها، وضياعها هو العطل المبلَّغ.

    **وحدُّ القياس هو عمر هذا القرص، لا عمر النظام.** أول كتابة كانت
    تعدّ كل مستند مفقود إدانًة للقرص — فجرّبتُ توجيه ``UPLOAD_DIR`` إلى
    مسار جديد فقرأت «42 من 42 مفقود»، والقرص لم يفقد شيًئا: المجلّد
    تغيّر لا أكثر.

    وهذا بالضبط ما يقع يوم يُوجَّه المسار إلى القرص الدائم لأول مرّة —
    فيتّهم الفحصُ الإصلاحَ نفسه، برقم مقنع. واتّهام كاذب مقنع أسوأ من
    لا فحص: يُدرَّب الناس على تجاهله.

    فما كُتب **قبل** بدء هذا القرص يُعدّ منفصًلا (``legacy_missing``):
    خبر يُبلَّغ ولا يُبنى عليه حكم على القرص الجاري.
    """
    from sqlalchemy import select

    from . import models
    from .storage import key_exists

    started = _disk_started_at()
    rows = db.scalars(
        select(models.Document)
        .where(models.Document.is_issued == True,  # noqa: E712
               models.Document.file_path.isnot(None))
        .order_by(models.Document.id.desc())
        .limit(max(1, sample))
    ).all()

    since, legacy = [], []
    for d in rows:
        if key_exists(d.file_path):
            continue
        made = d.created_at
        if made is not None and made.tzinfo is None:
            made = made.replace(tzinfo=timezone.utc)
        (since if (started and made and made >= started) else legacy).append(d.id)

    return {"checked": len(rows), "missing": len(since),
            "sample_ids": since[:10],
            # ما سبق هذا القرص: يُعرَض ولا يُدين.
            "legacy_missing": len(legacy),
            "disk_started_at": started.isoformat() if started else None}


def _disk_started_at():
    """متى بدأ هذا القرص يُكتب عليه — من العلامة نفسها."""
    raw = _read_marker().get("first_seen")
    if not raw:
        return None
    try:
        d = datetime.fromisoformat(raw)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def report(db=None) -> dict:
    """حالة دوام التخزين — بإشاراتها الثلاث وسببها.

    ``persistent`` ثلاثيّ عمًدا: ``True`` بدليل، ``False`` بدليل،
    و``None`` حين لا دليل بعد. و«لا أعرف» جواب صادق يُفحَص لاحًقا؛
    أما «سليم» بلا دليل فهو الذي أوقعنا في الضياع الصامت.
    """
    marker = _read_marker()
    boot_count = int(marker.get("boot_count") or 0)
    survived = boot_count >= 2
    under_mount = _under_mount()
    mounted = is_mount_point()

    lost = missing_files(db) if db is not None else None

    if lost and lost["checked"] and lost["missing"]:
        persistent, why = False, (
            f"{lost['missing']} من {lost['checked']} مستنًدا صادًرا **كُتب "
            "على هذا القرص** سجلُّه في القاعدة وملفه مفقود — القرص يفقد "
            "ما يُكتب عليه.")
    elif survived:
        persistent, why = True, (
            f"القرص نجا من {boot_count - 1} استبدال حاوية على الأقلّ.")
    elif mounted:
        persistent, why = True, (
            "مجلّد الرفع نقطة تركيب — قرص منفصل عن قرص الحاوية.")
    elif under_mount:
        persistent, why = True, (
            f"مجلّد الرفع داخل القرص الدائم المُعلَن ({mount_hint()}).")
    else:
        persistent, why = None, (
            "لا دليل بعد: أول إقلاع على هذا القرص ولا قرص دائم مُعلَن. "
            "تُحسَم بعد النشرة التالية، أو بضبط UPLOAD_DIR داخل مسار "
            "القرص الدائم.")

    if lost and lost.get("legacy_missing"):
        why = (f"{why} وإضافًة: {lost['legacy_missing']} مستنًدا أقدم من هذا "
               "القرص ملفُّه مفقود — ضياع سابق أو مسار قديم، لا حكم على "
               "القرص الجاري.")

    return {
        "persistent": persistent,
        "reason": why,
        "upload_dir": settings.upload_dir,
        "boot_count": boot_count,
        "survived_restart": survived,
        "mount_path": mount_hint(),
        "upload_dir_under_mount": under_mount,
        "upload_dir_is_mount_point": mounted,
        "missing_files": lost,
    }


def looks_ephemeral() -> bool:
    """هل يبدو مجلّد الرفع داخل صورة الحاوية؟

    الحاوية تعمل من ``/app``، ومحتواها يُستبدَل مع كل نشرة. مجلّد رفع
    داخله يعني ضياع كل مستند صادر عند النشرة التالية — **ما لم يكن
    المسار نفسه نقطة تركيب لقرص دائم**، وهو ضبط سليم رأيته في الإنتاج:
    القرص مركَّب على ``/app/backend/uploads`` وهو نفسه ما يحسبه التطبيق،
    فلا يلزم متغيّر بيئة أصًلا. وتحذير من ضبط سليم هو ما يُدرِّب الناس
    على تجاهل التحذيرات.

    ولا يُبنى على هذا رفضُ الإقلاع: إسقاط نظام يعمل قرار أثقل من
    التحذير، والقياس هنا استدلال على الشكل لا دليل قاطع (قد يُركَّب
    قرص دائم على مسار داخل ``/app`` بضبط غير معتاد). فيُقال بصوت
    مسموع، ويُحسَم في ``/health/deep`` بالأدلّة.
    """
    if not settings.is_production:
        return False
    if (settings.storage_backend or "local").lower() != "local":
        return False
    if _under_mount() or is_mount_point():
        return False
    try:
        up = os.path.realpath(settings.upload_dir)
    except OSError:
        return False
    app_root = os.path.realpath(os.path.dirname(os.path.dirname(__file__)))
    return up == app_root or up.startswith(app_root.rstrip(os.sep) + os.sep)


def warn_if_ephemeral() -> None:
    """يقولها بصوت مسموع عند الإقلاع — قبل أن يضيع أول مستند."""
    import logging

    if looks_ephemeral():
        logging.getLogger("app").error(
            "⚠ مجلّد الرفع (%s) داخل صورة الحاوية — كل مستند صادر يضيع "
            "مع النشرة التالية. اضبط UPLOAD_DIR على مسار داخل القرص "
            "الدائم (مثل /data/uploads). راجع "
            "docs/DEPLOY_RAILWAY_VOLUME.md",
            settings.upload_dir)
