# -*- coding: utf-8 -*-
"""سجٌّل حضوٍر مفتوٌح واحٌد لكل موظف — قيٌد في القاعدة لا فحٌص قبل الكتابة.

**العطل**: ``check_in`` يقرأ ثم يكتب::

    open_rec = db.scalar(select(AttendanceRecord).where(
        employee_id == emp.id, check_out_at.is_(None)))
    if open_rec:
        raise HTTPException(409, "لديك تسجيل حضور مفتوح بالفعل")
    ...
    db.add(AttendanceRecord(...))

وبين القراءة والكتابة نافذٌة: نقرتان على الشاشة في اللحظة نفسها تقرآن
«لا سجّل مفتوح» فتُنشئان اثنين. ثم ``_finalize_out`` يأخذ **أحدهما**
بـ``order_by(check_in_at.desc())``، فيبقى الآخر مفتوًحا إلى الأبد:

- دقائُق عمٍل تُحتسب مرتين أو تُفقَد،
- وسجٌّل مفتوٌح أبدًيا يمنع كلَّ حضوٍر لاحق (الفحص نفسه يردّ 409)،
- وكشُف راتٍب يُبنى على أيامٍ لم تقع.

**والقفُل في القاعدة لا في الشيفرة.** وهو المنطُق نفسه المكتوب في
``job_lock``: «القاعدة هي الشيء الوحيد الذي تتشاركه كل النسخ، فهي موضع
القفل الطبيعي» — والفحُص قبل الكتابة لا يرى الطلَب الموازي.

**وفهٌرس جزئّي يعبّر عن الشرط بحرفه**: التفرُّد مشروٌط بـ
``check_out_at IS NULL``، فالسجالُت المنصرفة لا يحدّها شيء. وPostgreSQL
وSQLite يدعمانه كلاهما.

**والترحيُل يفحص قبل أن يفرض.** قاعدٌة فيها نسخٌة قائمة يسقط عليها إنشاُء
الفهرس، فتفشل النشرُة كلُّها — وترحيٌل يسقط على قاعدة العميل أسوأ من
العطل الذي يُصلحه. فيُقاس أوًّلا، وإن وُجد تكراٌر **أُبقي الأحدث** وأُغلق
ما قبله بوقت حضوره (لا حذًفا: سجلُّ حضوٍر دليٌل لا يُمحى).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f4a5b6c7d8e"
down_revision = "e3f4a5b6c7d"
branch_labels = None
depends_on = None

_IX = "ux_attendance_one_open_per_employee"


def upgrade() -> None:
    bind = op.get_bind()

    # 1) **يُقاس قبل أن يُفرَض** — وإلا سقطت النشرة على قاعدٍة فيها تكرار.
    dupes = bind.execute(sa.text("""
        SELECT employee_id, COUNT(*) AS n
        FROM attendance_records
        WHERE check_out_at IS NULL
        GROUP BY employee_id
        HAVING COUNT(*) > 1
    """)).fetchall()

    for employee_id, _n in dupes:
        # **ويُبقى الأحدث ويُغلق ما قبله** — لا يُحذف: سجلُّ حضوٍر دليٌل.
        # ويُغلق بوقت حضوره نفسه (صفُر دقائق) فلا يُختَلق عمٌل لم يقع،
        # ويُعرَف أنه أُغلق بالترحيل لا ببصمة.
        bind.execute(sa.text("""
            UPDATE attendance_records
               SET check_out_at = check_in_at,
                   worked_minutes = 0,
                   status = 'auto_closed'
             WHERE employee_id = :emp
               AND check_out_at IS NULL
               AND id <> (
                   SELECT id FROM attendance_records
                    WHERE employee_id = :emp AND check_out_at IS NULL
                    ORDER BY check_in_at DESC, id DESC
                    LIMIT 1)
        """), {"emp": employee_id})

    # 2) والقيُد نفسه — مشروٌط بأن السجّل ما زال مفتوًحا.
    op.create_index(_IX, "attendance_records", ["employee_id"], unique=True,
                    postgresql_where=sa.text("check_out_at IS NULL"),
                    sqlite_where=sa.text("check_out_at IS NULL"))


def downgrade() -> None:
    op.drop_index(_IX, table_name="attendance_records")
