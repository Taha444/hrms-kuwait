# -*- coding: utf-8 -*-
"""قفٌل بلا مفتاح — شرُط شاشٍة لا يصدق لأيّ دور.

**من أين جاء**: كتلة التوقيع في شاشة الطلب كانت محروسة بـ``can(
"approve_request")``، ولا يحمل تلك الصلاحية أيّ دور افتراضي إلا
``super_admin``. فتصل الاستقالة مرحلة التوقيع ولا يملك أحٌد في الشركة زًرا
يتمّها — وقاعدة المالك المعلَنة تمنع منح ``super_admin`` أصًلا.

ولم يُمسك ذلك باختبار لأن اختبارات المسار تنادي الخادم مباشًرة: تمرّ من
باب لا يفتحه أحٌد من الشاشة. **فاختباٌر يمرّ من الخادم ولا يمرّ من الشاشة
يصادق على طريق لا يستطيع أحٌد أن يسلكه.**

وهذا الحارس يقيس الشكل العام للعيب لا حالته الواحدة.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend" / "scripts" / "ui_permission_gaps.py"


def test_no_screen_is_locked_behind_a_permission_nobody_can_hold():
    """لا شرَط شاشٍة على صلاحية خارج الكتالوج ولا يحملها دور.

    والأداة نفسها تُشغَّل — لا نسخٌة من منطقها هنا: نسختان لقاعدة واحدة
    تنحرف إحداهما، وأداة القياس تُقرأ يدًوا فيلزم أن يمسك الاختبارُ ما
    تمسكه هي.
    """
    r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True,
                       text=True, encoding="utf-8", cwd=str(ROOT))
    out = (r.stdout or "") + (r.returncode and (r.stderr or "") or "")
    assert r.returncode == 0, f"أقفاٌل بلا مفاتيح:\n{out}"


def test_the_sweep_does_not_count_its_own_explanation():
    """**وأداة القياس لا تُبلّغ عن نفسها.**

    التعليقات تذكر الصلاحيات المهجورة لتشرحها. وتعليقات JSX متعدّدة
    الأسطر لا تبدأ أسطُرها بعلامة — يبدأ التعليق بـ``{/*`` ثم تتلوه أسطٌر
    نًصّا محًضا. ففحص بداية السطر وحده عدّ شرح العطل عطًلا قائًما، وقد وقع
    ذلك فعًلا في أول تشغيل: ``approve_request`` ظهرت في تقرير أداٍة
    كُتبت لأجل إصلاحها.
    """
    r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True,
                       text=True, encoding="utf-8", cwd=str(ROOT))
    assert "approve_request" not in (r.stdout or ""), r.stdout
