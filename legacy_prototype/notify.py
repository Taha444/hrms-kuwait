# -*- coding: utf-8 -*-
"""
مركز الإشعارات: ينشئ إشعارًا داخل التطبيق ويرسله بالبريد/SMS اختياريًا.
"""
import db
from mailer import send_email
from sms import send_sms


def push(user_id, company_id, ntype, title, body, email=None, phone=None):
    """ينشئ إشعارًا داخليًا (+ بريد/SMS إن توفّرت بيانات الاتصال والتفعيل)."""
    db.execute(
        """INSERT INTO notifications (company_id, user_id, type, title, body)
           VALUES (?,?,?,?,?)""",
        (company_id, user_id, ntype, title, body),
    )
    if email:
        send_email(email, title, body)
    if phone:
        send_sms(phone, f"{title}: {body}")


def list_for_user(user_id, unread_only=False, limit=50):
    sql = "SELECT * FROM notifications WHERE user_id=?"
    params = [user_id]
    if unread_only:
        sql += " AND is_read=0"
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    return db.rows_to_list(db.query(sql, params))


def mark_read(notification_id, user_id):
    db.execute("UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?",
               (notification_id, user_id))


def mark_all_read(user_id):
    db.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (user_id,))


def unread_count(user_id):
    row = db.query("SELECT COUNT(*) AS n FROM notifications WHERE user_id=? AND is_read=0",
                   (user_id,), one=True)
    return row["n"] if row else 0
