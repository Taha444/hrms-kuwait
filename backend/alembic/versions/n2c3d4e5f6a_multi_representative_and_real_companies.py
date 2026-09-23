# -*- coding: utf-8 -*-
"""ممثّلو الشركة (متعدّد) + إضافة شركتين حقيقيتين بفروعهما — طلب المالك (2026-09-23).

**GC-11 — تعدُّد ممثّلي الشركة.** الحقلان الفرديان على ``companies``
(representative_name/civil_id) افترضا ممثلا واحدا يوقّع دائما. وشركات هذه
المجموعة العائلية يمثّلها شريكان أو أكثر بحسب من هو حاضر وقت التوقيع —
أحدهم قد يغيب عن معاملة بعينها والآخر لا (طلب صريح من المالك). فجدول
``company_representatives`` جديد يحمل كل من يصحّ أن يكون "الطرف الأول"،
ومن يولّد العقد يختار بينهم لتلك النسخة بعينها (انظر ``gov_contract_data
.resolve_representative``) بدل قيمة واحدة مفروضة على الجميع.

**الشركتان الجديدتان.** "شركة الاتحاد الخليجي للأقمشة" و"شركة ميلانو
المتحدة للأقمشة" كانتا مذكورتين في تعيين ممثّلي المجموعة لكن لم تكونا
مُنشأتين في النظام أصلا — الشركتان (1، 2) الموجودتان بيانات تجريبية
(demo) لا علاقة لهما بهما. فروعهما من نفس ملف «محلات الشركات بالعناوين»
الذي بُنيت عليه فروع الشركات الثلاث الأخرى (شركة النيل الأزرق، قمة النيل
الخالد، محمد أحمد علي إبراهيم وشريكه) في هذه القاعدة، **مع استبعاد صفّ
"المقر (ترخيص الشركة)"** من الفروع تماما كما استُبعد هناك (هو عنوان ترخيص
الشركة نفسها، لا محلا يحضر فيه موظفون). الإحداثيات (lat/lng) تُترك فارغة:
لم تُراجَع بعد في كويت فايندر كما رُوجعت فروع الشركات الثلاث في الترحيل
``k9f0a1b2c3d`` — تبقى فجوة معروفة حتى تُراجَع بنفس الطريقة.

**فجوة معروفة (لا تُغلق هنا):** الرقم المدني للسجل التجاري (commercial_reg)
ورقم ملف الشركة (file_number) ونوع الكيان القانوني لهاتين الشركتين غير
متوفّرين في المصدر المتاح، فتُركا فارغين بدل اختراع رقم يُطبع في مستند
رسمي — بخلاف "الرقم المدني للجهة" الظاهر في ملف العناوين، وهو رقم ترخيص
كل محل تجاري لا السجل التجاري للشركة (لا يُطابق commercial_reg الموجود
فعلا للشركات الثلاث الأخرى في هذه القاعدة).

**تمثيل ناقص:** "ابراهيم خالد أحمد ابراهيم" مذكور شريكا في ثلاث شركات
(ميلانو، محمد أحمد علي إبراهيم وشريكه، النيل الأزرق) لكن لا بطاقة مدنية
له بعد بين ما زُوِّد به النظام — فلا صفّ له هنا. يُضاف لاحقا متى وصلت
بطاقته، دون أن يمنع ذلك تسجيل من تتوفر بطاقته الآن.
"""
from __future__ import annotations

import secrets

import sqlalchemy as sa
from alembic import op

revision = "n2c3d4e5f6a"
down_revision = "m1b2c3d4e5f"
branch_labels = None
depends_on = None

#: الشركتان الجديدتان — بيانات المجموعة نفسها (eos/إجازة) المستخدمة للشركات
#: الثلاث الأخرى في هذه العائلة التجارية (النيل الأزرق، قمة النيل الخالد، محمد
#: أحمد علي إبراهيم وشريكه)، لا افتراضات مصنع عامة.
NEW_COMPANIES = [
    dict(name="شركة الاتحاد الخليجي للأقمشة", name_en="Gulf Union Textiles Co.",
        eos_day_divisor=26, eos_max_months=18, alert_lead_days=30, annual_leave_days=30),
    dict(name="شركة ميلانو المتحدة للأقمشة", name_en="Milano United Textiles Co.",
        eos_day_divisor=26, eos_max_months=18, alert_lead_days=30, annual_leave_days=30),
]

#: (اسم الشركة، رمز الفرع، اسم المحل، المحافظة، المحافظة EN، المنطقة، المبنى/المجمع،
#:  PACI أو None، نطاق السياج) — من ملف «محلات الشركات بالعناوين» (2026-09-19/23)،
#: بلا صفّ "المقر (ترخيص الشركة)" (انظر توضيح أعلى الملف).
GOV_EN = {
    "العاصمة": "Al Asima", "الأحمدي": "Al Ahmadi", "الجهراء": "Al Jahra",
    "الفروانية": "Al Farwaniyah", "مبارك الكبير": "Mubarak Al Kabeer", "حولي": "Hawalli",
}

BRANCHES = [
    # شركة الاتحاد الخليجي للأقمشة
    ("شركة الاتحاد الخليجي للأقمشة", "GUT02", "معرض أطلس فاشن للأقمشة",
     "العاصمة", "القبلة، سوق الصفاة", "16643078", 200),
    ("شركة الاتحاد الخليجي للأقمشة", "GUT06", "معرض ريم فاشن للأقمشة",
     "العاصمة", "القبلة، سوق الصفاة", "10229888", 200),
    ("شركة الاتحاد الخليجي للأقمشة", "GUT07", "سلفر فاشن لأقمشة التنجيد والستائر",
     "العاصمة", "القبلة، سوق الأقمشة بلوك 2", "10234492", 200),
    ("شركة الاتحاد الخليجي للأقمشة", "GUT08", "معرض وول سنتر للأقمشة",
     "العاصمة", "القبلة، سوق الأقمشة بلوك 2", "10234281", 200),
    ("شركة الاتحاد الخليجي للأقمشة", "GUT09", "خياط الأمين فاشن للسيدات وأقمشتها",
     "العاصمة", "القبلة، سوق الصفاة", "10231988", 200),
    ("شركة الاتحاد الخليجي للأقمشة", "GUT10", "خياط ليزا الصفاة للسيدات وأقمشتها",
     "العاصمة", "القبلة، سوق الصفاة", "10230918", 200),
    ("شركة الاتحاد الخليجي للأقمشة", "GUT13", "النيل الأزرق الذهبي للمجوهرات",
     "الأحمدي", "الفحيحيل، قيصرية أحمد عبدالله العجيل", "13805414", 200),
    # شركة ميلانو المتحدة للأقمشة
    ("شركة ميلانو المتحدة للأقمشة", "MUT02", "مجوهرات دار الشيخ الذهبية - الفحيحيل",
     "الأحمدي", "الفحيحيل، مبنى خالد الدبوس ومحمد المنيف", "14639948", 200),
    ("شركة ميلانو المتحدة للأقمشة", "MUT03", "شركة مترو فاشن للأقمشة",
     "العاصمة", "القبلة، سوق الصفاة", "10228818", 200),
    ("شركة ميلانو المتحدة للأقمشة", "MUT05", "مجوهرات دار الشيخ الذهبية - الفحيحيل (رمال)",
     "الأحمدي", "الفحيحيل، مبنى شركة رمال الكويت العقارية", "16603076", 200),
    ("شركة ميلانو المتحدة للأقمشة", "MUT06", "كنز فاشن لبيع أقمشة الستائر والمفروشات",
     "العاصمة", "القبلة، سوق الأقمشة بلوك 2", "10234396", 200),
    ("شركة ميلانو المتحدة للأقمشة", "MUT07", "مجوهرات دار الشيخ الذهبية - الجهراء",
     "الجهراء", "الجهراء، مبنى بنك وربة", "21706328", 200),
    ("شركة ميلانو المتحدة للأقمشة", "MUT08", "مجوهرات دار الشيخ الذهبية - القبلة",
     "العاصمة", "القبلة، مبنى أحمد أنور عبدالله العوضي (سوق العوضي)", "10194478", 200),
    ("شركة ميلانو المتحدة للأقمشة", "MUT09", "كهرمان جولد للمجوهرات الذهبية - الجهراء",
     "الجهراء", "الجهراء، مبنى بنك وربة", "21645596", 200),
    ("شركة ميلانو المتحدة للأقمشة", "MUT10", "مجوهرات دار الشيخ الذهبية - المباركية",
     "العاصمة", "القبلة، مجمع الأسواق بالمباركية", "14988558", 200),
    ("شركة ميلانو المتحدة للأقمشة", "MUT11", "معرض حنان فابريك للأقمشة",
     "العاصمة", "القبلة، سوق الأقمشة والبطانيات بلوك 1", "10225748", 200),
    ("شركة ميلانو المتحدة للأقمشة", "MUT12", "خياط ليزا فاشن للسيدات وأقمشتها",
     "العاصمة", "القبلة، سوق الصفاة", "10233975", 200),
    ("شركة ميلانو المتحدة للأقمشة", "MUTMR", "شركة مرمر للأقمشة",
     "العاصمة", "القبلة، سوق الأقمشة والبطانيات بلوك 1", "10226054", 200),
    # المصنع: بلا رقم آلي في الرخصة الصناعية (رصدته الرخصة نفسها). محافظته
    # العاصمة بالاستدلال — «الري» منطقة تابعة للعاصمة، بنفس ما استُدل به
    # على «مصنع النيل الأزرق للمجوهرات» (المرقاب) في هذه القاعدة سلفا.
    ("شركة ميلانو المتحدة للأقمشة", "MUTFAC", "مصنع دار الشيخ للمنتجات الذهبية",
     "العاصمة", "الري، قطعة 1 قسيمة 290", None, 100),
]

#: (اسم الشركة، الاسم، الاسم EN، الرقم المدني) — من بطاقات الشركاء المدنية
#: التي زوّد بها المالك (2026-09-22)، مطابَقة بتعيينه لممثّل كل شركة لا بما
#: هو مطبوع في خانة "المهنة/جهة العمل" خلف كل بطاقة شخصية (توضيح صريح منه:
#: تلك الخانة تخص عمل صاحب البطاقة الشخصي، لا تمثيله القانوني لشركة بعينها).
REPRESENTATIVES = [
    ("شركة النيل الازرق للمجوهرات", "خالد احمد علي ابراهيم", "Khaled Ahmad Ali Ibrahim", "262052600219"),
    ("شركة النيل الازرق للمجوهرات", "وليد محمد احمد ابراهيم", "Waleed Mohammad Ahmad Ibrahim", "270102000925"),
    ("شركة قمة النيل الخالد للتجارة العامة والمقاولات", "وليد محمد احمد ابراهيم",
     "Waleed Mohammad Ahmad Ibrahim", "270102000925"),
    ("شركة قمة النيل الخالد للتجارة العامة والمقاولات", "عبدالله محمد احمد ابراهيم",
     "Abdullah Mohammad Ahmad Ibrahim", "272092101149"),
    ("شركة محمد احمد على ابراهيم وشريكه", "خالد احمد علي ابراهيم",
     "Khaled Ahmad Ali Ibrahim", "262052600219"),
    ("شركة الاتحاد الخليجي للأقمشة", "وليد محمد احمد ابراهيم", "Waleed Mohammad Ahmad Ibrahim", "270102000925"),
    ("شركة الاتحاد الخليجي للأقمشة", "عبدالله محمد احمد ابراهيم",
     "Abdullah Mohammad Ahmad Ibrahim", "272092101149"),
    ("شركة ميلانو المتحدة للأقمشة", "خالد احمد علي ابراهيم", "Khaled Ahmad Ali Ibrahim", "262052600219"),
]


def upgrade() -> None:
    op.create_table(
        "company_representatives",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("name_en", sa.String(length=160), nullable=True),
        sa.Column("civil_id", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_company_representatives_company_id", "company_representatives", ["company_id"])

    conn = op.get_bind()

    for c in NEW_COMPANIES:
        existing = conn.execute(sa.text("SELECT id FROM companies WHERE name = :n"),
                                {"n": c["name"]}).first()
        if existing:
            continue
        conn.execute(sa.text(
            "INSERT INTO companies (name, name_en, status, eos_day_divisor, eos_max_months, "
            "alert_lead_days, annual_leave_days, created_at) "
            "VALUES (:name, :name_en, 'active', :eos_day_divisor, :eos_max_months, "
            ":alert_lead_days, :annual_leave_days, CURRENT_TIMESTAMP)"), c)

    company_ids = {row[0]: row[1] for row in conn.execute(
        sa.text("SELECT name, id FROM companies")).fetchall()}

    for name, code, shop, gov, area_building, paci, radius in BRANCHES:
        cid = company_ids.get(name)
        if cid is None:
            continue
        exists = conn.execute(sa.text("SELECT id FROM branches WHERE company_id = :cid AND code = :code"),
                              {"cid": cid, "code": code}).first()
        if exists:
            continue
        address = f"{gov} — {area_building}"
        if paci:
            address += f" — الرقم الآلي للعنوان: {paci}"
        conn.execute(sa.text(
            "INSERT INTO branches (company_id, name, code, governorate, governorate_en, "
            "geofence_radius_m, qr_secret, auto_checkout_minutes, address, is_headquarters, "
            "status, created_at) "
            "VALUES (:cid, :name, :code, :gov, :gov_en, :radius, :qr, 15, :addr, :hq, "
            "'active', CURRENT_TIMESTAMP)"),
            {"cid": cid, "name": shop, "code": code, "gov": gov, "gov_en": GOV_EN.get(gov),
             "radius": radius, "qr": secrets.token_hex(16), "addr": address, "hq": False})

    for name, rep_name, rep_name_en, civil_id in REPRESENTATIVES:
        cid = company_ids.get(name)
        if cid is None:
            continue
        exists = conn.execute(sa.text(
            "SELECT id FROM company_representatives WHERE company_id = :cid AND civil_id = :civ"),
            {"cid": cid, "civ": civil_id}).first()
        if exists:
            continue
        conn.execute(sa.text(
            "INSERT INTO company_representatives (company_id, name, name_en, civil_id, status, created_at) "
            "VALUES (:cid, :name, :name_en, :civ, 'active', CURRENT_TIMESTAMP)"),
            {"cid": cid, "name": rep_name, "name_en": rep_name_en, "civ": civil_id})


def downgrade() -> None:
    conn = op.get_bind()
    for name, _rep_name, _rep_name_en, civil_id in REPRESENTATIVES:
        conn.execute(sa.text(
            "DELETE FROM company_representatives WHERE civil_id = :civ AND company_id IN "
            "(SELECT id FROM companies WHERE name = :n)"), {"civ": civil_id, "n": name})
    for name, code, *_rest in BRANCHES:
        conn.execute(sa.text(
            "DELETE FROM branches WHERE code = :code AND company_id IN "
            "(SELECT id FROM companies WHERE name = :n)"), {"code": code, "n": name})
    for c in NEW_COMPANIES:
        conn.execute(sa.text("DELETE FROM companies WHERE name = :n"), {"n": c["name"]})
    op.drop_index("ix_company_representatives_company_id", table_name="company_representatives")
    op.drop_table("company_representatives")
