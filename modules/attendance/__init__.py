import sqlite3
from datetime import date, datetime
from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from modules.audit import log_action
from modules.db import ATTENDANCE_DB, USERS_DB
from modules.levels import MANAGER_LEVEL, current_level, tier

attendance = Blueprint("attendance", __name__, template_folder="templates")

STATUSES = ("present", "absent", "leave")

SCHEMA = """
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        status TEXT NOT NULL,
        marked_by TEXT,
        marked_at TEXT NOT NULL,
        UNIQUE(user_id, date)
    );
"""


def get_conn():
    """Connect to attendance.db, creating the schema if needed, and attach users.db so records can be joined."""
    conn = sqlite3.connect(ATTENDANCE_DB)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("ATTACH DATABASE ? AS users", (str(USERS_DB),))
    return conn


def admin_required(view):
    """dev/admin/data_manager/raid_staff only — also gates viewing attendance
    at all, not just marking it."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        level = current_level()
        if level is None or tier(level) > MANAGER_LEVEL:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def now():
    return datetime.now().isoformat(timespec="seconds")


@attendance.route("/attendance")
@admin_required
def index():
    day = request.args.get("date") or date.today().isoformat()
    conn = get_conn()
    users = conn.execute("SELECT id, name FROM users.users ORDER BY name").fetchall()
    marked = conn.execute("SELECT user_id, status FROM attendance WHERE date = ?", (day,)).fetchall()
    conn.close()
    marked_map = {row["user_id"]: row["status"] for row in marked}
    return render_template("attendance_index.html", users=users, day=day, marked=marked_map, statuses=STATUSES)


@attendance.route("/attendance/mark", methods=["POST"])
@admin_required
def mark():
    day = request.form.get("date") or date.today().isoformat()
    marker = session.get("user_email")
    conn = get_conn()
    user_ids = [row["id"] for row in conn.execute("SELECT id FROM users.users").fetchall()]
    for user_id in user_ids:
        status = request.form.get(f"status_{user_id}")
        if status not in STATUSES:
            continue
        conn.execute(
            """
            INSERT INTO attendance (user_id, date, status, marked_by, marked_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, date) DO UPDATE SET
                status = excluded.status,
                marked_by = excluded.marked_by,
                marked_at = excluded.marked_at
            """,
            (user_id, day, status, marker, now()),
        )
    conn.commit()
    conn.close()
    log_action("attendance", "mark", f"marked attendance for {day}")
    flash(f"Attendance saved for {day}.", "info")
    return redirect(url_for("attendance.index", date=day))


@attendance.route("/attendance/history")
@admin_required
def history():
    conn = get_conn()
    records = conn.execute(
        """
        SELECT attendance.date, users.users.name AS user_name, attendance.status,
               attendance.marked_by, attendance.marked_at
        FROM attendance
        JOIN users.users ON users.users.id = attendance.user_id
        ORDER BY attendance.date DESC, users.users.name
        """
    ).fetchall()
    summary = conn.execute(
        """
        SELECT users.users.name AS user_name,
               SUM(CASE WHEN attendance.status = 'present' THEN 1 ELSE 0 END) AS present_count,
               SUM(CASE WHEN attendance.status = 'absent' THEN 1 ELSE 0 END) AS absent_count,
               SUM(CASE WHEN attendance.status = 'leave' THEN 1 ELSE 0 END) AS leave_count,
               COUNT(*) AS total
        FROM attendance
        JOIN users.users ON users.users.id = attendance.user_id
        GROUP BY users.users.name
        ORDER BY users.users.name
        """
    ).fetchall()
    conn.close()
    return render_template("attendance_history.html", records=records, summary=summary)
