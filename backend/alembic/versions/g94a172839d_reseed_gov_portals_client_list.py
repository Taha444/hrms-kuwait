# -*- coding: utf-8 -*-
"""Reseed government_portals with the client-authored comprehensive list (30 links, 8 categories)

Revision ID: g94a172839d
Revises: f849506172cd
Create Date: 2026-08-06

يمسح البذرة الأولى (7 روابط) ويستبدلها بالقائمة المعتمدة من الإدارة:
- 8 فئات: manpower, residency, civil_id, moci, municipality, customs, insurance, other_services
- ~30 رابط منظّم مع أوصاف عربية/إنجليزية
- الترتيب sort_order بمضاعفات 10 (يسمح بإدخال روابط لاحقة بينها)
"""
from typing import Sequence, Union

from alembic import op


revision: str = "g94a172839d"
down_revision: Union[str, None] = "f849506172cd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # امسح البذرة الأولى (7 روابط تجريبية)
    op.execute("DELETE FROM government_portals")

    # القائمة المعتمدة
    op.execute(r"""
INSERT INTO government_portals (name_ar, name_en, description_ar, description_en, url, category, icon, sort_order, is_active, created_at, updated_at) VALUES

-- ============ 1) العمل والعمالة (manpower) ============
('الهيئة العامة للقوى العاملة — خدمة أسهل', 'PAM — Ashal Service',
 'استقدام العمالة، إصدار وتجديد وإلغاء أذونات العمل، متابعة المعاملات، ملفات العمالة والرواتب',
 'Recruitment, work permit issue/renew/cancel, transaction tracking, worker files and payroll',
 'https://www.manpower.gov.kw/Pages/Services/Ashal.aspx', 'manpower', '👷', 10, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

('الخدمات الإلكترونية للهيئة العامة للقوى العاملة', 'PAM E-Services',
 'صفحة الخدمات الإلكترونية الرسمية لهيئة القوى العاملة',
 'Official e-services page for Public Authority of Manpower',
 'https://www.manpower.gov.kw/EServices.aspx', 'manpower', '📄', 20, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

('استفسارات خدمة أسهل', 'Ashal Enquiries',
 'الاستفسارات والدعم الخاص بخدمة أسهل',
 'Support and enquiries for the Ashal service',
 'https://www.manpower.gov.kw/Pages/Services/EnquiriesForAshal.aspx', 'manpower', '❓', 30, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

-- ============ 2) الإقامات والداخلية (residency) ============
('منصة الخدمات الإلكترونية لوزارة الداخلية', 'MOI E-Services Portal',
 'البوابة الرسمية لخدمات وزارة الداخلية — إقامات وتحويل وتجديد',
 'Official MOI portal for residency, transfer, and renewal',
 'https://eres.moi.gov.kw/', 'residency', '🛂', 10, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

('منصة خدمات الأفراد — وزارة الداخلية', 'MOI Individual Services',
 'خدمات الأفراد بمصادقة تطبيق هويتي',
 'Individual services with Hawyti mobile ID authentication',
 'https://eres.moi.gov.kw/individual', 'residency', '👤', 20, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

('تحويل الإقامة للشركات', 'Residency Transfer for Companies',
 'الرابط المباشر لطلب تحويل الإقامة بين الشركات',
 'Direct link for residency transfer between companies',
 'https://eres.moi.gov.kw/companies/residency/transfer/', 'residency', '🔄', 30, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

-- ============ 3) البطاقة المدنية (civil_id) ============
('الهيئة العامة للمعلومات المدنية (PACI) — الرئيسي', 'PACI Main Site',
 'الموقع الرئيسي للهيئة العامة للمعلومات المدنية',
 'Public Authority for Civil Information main site',
 'https://www.paci.gov.kw/', 'civil_id', '🏛️', 5, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

('الخدمات الإلكترونية — PACI', 'PACI E-Services',
 'بوابة الخدمات الإلكترونية للهيئة العامة للمعلومات المدنية',
 'PACI electronic services portal',
 'https://services.paci.gov.kw/', 'civil_id', '🪪', 10, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

('الاستعلام عن البطاقة المدنية وحالتها', 'Civil ID Card Inquiry',
 'استعلام عن حالة البطاقة المدنية وتاريخ الإصدار والانتهاء',
 'Check civil ID card status, issue and expiry',
 'https://services.paci.gov.kw/card/inquiry?lang=ar&serviceType=4', 'civil_id', '🔍', 20, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

('دليل معاملات الهيئة العامة للمعلومات المدنية', 'PACI Applications Guide',
 'دليل شامل لكل معاملات المعلومات المدنية',
 'Comprehensive guide for all PACI applications',
 'https://services.paci.gov.kw/applications-guide', 'civil_id', '📘', 30, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

('تغيير عنوان غير كويتي', 'Change of Address – Non-Kuwaiti',
 'دليل ومتطلبات تغيير عنوان الوافد، حضوريًا أو عبر تطبيق سهل',
 'Guide and requirements for expat address change (in-person or via Sahel app)',
 'https://services.paci.gov.kw/applications-guide/detail/change-of-address-%28non-kuwaiti%29/16', 'civil_id', '📍', 40, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

('نموذج إقرار السكن (PDF)', 'Address Declaration Form (PDF)',
 'تحميل نموذج إقرار السكن الرسمي',
 'Download the official address declaration form',
 'https://services.paci.gov.kw/pdf/Address-Declaration.pdf', 'civil_id', '📥', 50, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

('تطبيق هويتي — Kuwait Mobile ID', 'Hawyti — Kuwait Mobile ID',
 'المصادقة الحكومية والتوقيع الإلكتروني للدخول للخدمات الرسمية',
 'Government authentication and e-signature for accessing official services',
 'https://hawyti.paci.gov.kw/', 'civil_id', '🔐', 60, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

-- ============ 4) التجارة والشركات (moci) ============
('وزارة التجارة والصناعة — الخدمات الإلكترونية', 'MOCI E-Services',
 'بوابات تأسيس الشركات، التراخيص، السجل التجاري، والرخصة الذكية',
 'Company formation, licensing, commercial registry, and smart licenses',
 'https://www.moci.gov.kw/ar/e-service/', 'moci', '🏢', 10, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

('السجل التجاري ورخص الاستيراد', 'Commercial Registry & Import Licenses',
 'تجديدات السجل، شهادات، رخصة استيراد عامة/مؤقتة، تعديل الوكالات',
 'Registry renewals, certificates, general/temporary import licenses, agency amendments',
 'https://www.moci.gov.kw/ar/e-service/electronic-services-managing-commercial-registry/', 'moci', '📜', 20, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

('مركز الكويت للأعمال — تأسيس الشركات', 'Kuwait Business Center',
 'تأسيس الشركات وإصدار التراخيص التجارية بأنواعها',
 'Company formation and commercial licensing of all types',
 'https://www.moci.gov.kw/ar/e-service/kuwait-business-center/', 'moci', '🏗️', 30, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

('تعديل وتجديد تراخيص شركات الأشخاص', 'Persons'' Companies Licenses',
 'تجديد الترخيص، تعديل العنوان، الأنشطة، الاسم التجاري، الشركاء',
 'License renewal, address change, activities, trade name, partners',
 'https://moci.gov.kw/ar/e-service/digital-portal-managing-peoples-companies/', 'moci', '🔧', 40, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

-- ============ 5) البلدية والفروع (municipality) ============
('بلدية الكويت — الرئيسي', 'Kuwait Municipality — Main',
 'الموقع الرسمي لبلدية الكويت',
 'Kuwait Municipality official site',
 'https://www.baladia.gov.kw/', 'municipality', '🏛️', 10, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

('الاستعلام عن حالة معاملات تراخيص المحلات', 'Shop License Transactions Inquiry',
 'متابعة حالة معاملات تراخيص المحلات لدى البلدية',
 'Track municipality shop license transactions status',
 'https://kmapi.baladia.gov.kw/KMShopQuery/default.aspx', 'municipality', '🔍', 20, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

-- ============ 6) الجمارك والاستيراد (customs) ============
('الإدارة العامة للجمارك', 'General Customs Directorate',
 'تسجيل الشركات، التخليص الجمركي، الرسوم، التعرفة والتعليمات',
 'Company registration, customs clearance, fees, tariff and directives',
 'https://www.customs.gov.kw/', 'customs', '🛃', 10, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

('تسجيل أو تجديد شركة لدى الجمارك', 'Company Registration/Renewal — Customs',
 'يتطلب ترخيص التجارة ورخصة الاستيراد واعتماد التوقيع',
 'Requires trade license, import license, and signature authorization',
 'https://www.customs.gov.kw/Home/orgstatusrequest', 'customs', '📝', 20, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

-- ============ 7) التأمينات (insurance) ============
('المؤسسة العامة للتأمينات الاجتماعية (PIFSS)', 'PIFSS — Main',
 'الموقع الرئيسي للمؤسسة العامة للتأمينات الاجتماعية',
 'PIFSS main website',
 'https://www.pifss.gov.kw/', 'insurance', '🛡️', 10, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

('بوابة أصحاب الأعمال — التأمينات', 'PIFSS Business Portal',
 'بيانات العاملين، الاشتراكات، الكشوف الشهرية، المسجلين والمنتهية خدمتهم',
 'Employee data, subscriptions, monthly returns, active and terminated staff',
 'https://www.pifss.gov.kw/sites/Ar/Pages/eServices/BusinessPortal.aspx', 'insurance', '💼', 20, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

-- ============ 8) التصديقات والخدمات المساندة (other_services) ============
('غرفة تجارة وصناعة الكويت (KCCI) — الخدمات', 'KCCI E-Services',
 'العضوية، التصديقات، الشهادات والخدمات التجارية',
 'Membership, attestations, certificates, commercial services',
 'https://webservices.kcci.org.kw/', 'other_services', '🏛️', 10, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

('KCCI — تسجيل / إنشاء حساب', 'KCCI — Register / Sign-up',
 'تسجيل الدخول أو إنشاء حساب جديد لخدمات الغرفة',
 'Login or create a new account for chamber services',
 'https://webservices.kcci.org.kw/progeservices/register/first/M', 'other_services', '🔑', 20, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

('وزارة الصحة الكويتية', 'Ministry of Health',
 'الخدمات الإلكترونية للوزارة — خدمات شركات وتأمين صحي للوافدين',
 'MOH e-services — corporate services and expat health insurance',
 'https://www.moh.gov.kw/', 'other_services', '🏥', 30, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

('وزارة الخارجية الكويتية', 'Ministry of Foreign Affairs',
 'الخدمات القنصلية والتصديقات على المستندات من/إلى الخارج',
 'Consular services and attestations for foreign/outgoing documents',
 'https://www.mofa.gov.kw/ar/', 'other_services', '🌐', 40, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

('البوابة الإلكترونية الرسمية لدولة الكويت', 'Kuwait Official e-Gov Portal',
 'مرجع شامل لخدمات الإقامة، العمل، البطاقة المدنية، الشركات والتراخيص',
 'Comprehensive reference for residency, work, civil ID, companies and licenses',
 'https://www.e.gov.kw/', 'other_services', '🇰🇼', 50, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

('دليل خدمات قطاع الأعمال (e.gov)', 'Business e-Services Directory',
 'دليل خدمات الأعمال على البوابة الرسمية',
 'Business services directory on the official portal',
 'https://www.e.gov.kw/sites/kgoenglish/Pages/Business/Eservices.aspx', 'other_services', '📚', 60, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")


def downgrade() -> None:
    # نمسح الروابط اللي أضفناها ونعيد البذرة الأصلية (7 روابط)
    op.execute("DELETE FROM government_portals")
    op.execute("""
        INSERT INTO government_portals (name_ar, name_en, description_ar, url, category, sort_order, is_active, created_at, updated_at) VALUES
        ('بوابة مدني (PACI)', 'PACI Portal', 'الهيئة العامة للمعلومات المدنية', 'https://www.paci.gov.kw/', 'civil_id', 10, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
        ('ساحل — الخدمات الحكومية', 'Sahel Portal', 'بوابة ساحل الحكومية الشاملة', 'https://sahel.gov.kw/', 'other', 5, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
        ('وزارة التجارة والصناعة', 'MOCI Portal', 'رخص تجارية', 'https://www.moci.gov.kw/', 'moci', 20, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
        ('هيئة القوى العاملة (PAM)', 'PAM', 'إذن العمل', 'https://www.pam.gov.kw/', 'work_permits', 30, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
        ('الإدارة العامة للإقامة', 'DGR', 'تجديد الإقامات', 'https://moi.gov.kw/', 'residency', 40, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
        ('البلدية', 'Kuwait Municipality', 'تراخيص المحلات', 'https://www.baladia.gov.kw/', 'municipality', 50, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
        ('PIFSS', 'PIFSS', 'اشتراكات التأمينات', 'https://www.pifss.gov.kw/', 'insurance', 60, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """)
