import calendar
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from apps.audit import log_action
from apps.db import ATTENDANCE_DB, USERS_DB
from apps.levels import MANAGER_LEVEL, current_level, tier

attendance = Blueprint("attendance", __name__, template_folder="templates")

STATUSES = ("present", "absent", "leave")

# Real NLCI leave types, per the department's actual leave policy (AL/EL —
# Annual/Earned Leave, CL — Casual Leave, SL — Sick Leave). Default yearly
# eligibility (21/10/10) matches the department's standard allotment shown
# in Kannan K's 2026 leave-details email — same for every staff member
# unless an admin adjusts an individual's row in leave_balances.
LEAVE_TYPES = ("AL", "CL", "SL")
DEFAULT_ELIGIBLE = {"AL": 21, "CL": 10, "SL": 10}

# Work location, only meaningful when status == "present" -- office is the
# default so existing present rows (no location saved) read as in-office.
WORK_LOCATIONS = ("office", "wfh")

# Every self-marked leave starts pending until a manager approves it --
# legacy leave rows from before this feature have approval_status NULL,
# which is treated as approved everywhere below (they were already
# instant-effect under the old model, so this keeps that data unchanged).
APPROVAL_STATUSES = ("pending", "approved", "rejected")

# NLCI's real standard working hours (9:00 AM - 5:30 PM) -- see the
# raid_working_days_policy memory. Used both as the mark popup's default
# Entry/Exit Time and as the late-coming threshold below.
STANDARD_START_TIME = "09:00"
STANDARD_END_TIME = "17:30"

SCHEMA = """
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        status TEXT NOT NULL,
        leave_type TEXT,
        marked_by TEXT,
        marked_at TEXT NOT NULL,
        UNIQUE(user_id, date)
    );
    CREATE TABLE IF NOT EXISTS leave_balances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        year INTEGER NOT NULL,
        al_eligible INTEGER NOT NULL DEFAULT 21,
        cl_eligible INTEGER NOT NULL DEFAULT 10,
        sl_eligible INTEGER NOT NULL DEFAULT 10,
        UNIQUE(user_id, year)
    );
"""


def get_conn():
    """Connect to attendance.db, creating the schema if needed, and attach users.db so records can be joined."""
    conn = sqlite3.connect(ATTENDANCE_DB)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    # attendance.db predates leave_type/leave_balances (added 2026-09-12) --
    # CREATE TABLE IF NOT EXISTS above is a no-op against an already-existing
    # attendance table from before this feature, so add the missing column
    # explicitly, same pattern as apps/chat's attachment-column migration.
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(attendance)").fetchall()}
    if "leave_type" not in cols:
        conn.execute("ALTER TABLE attendance ADD COLUMN leave_type TEXT")
        conn.commit()
    if "entry_time" not in cols:
        conn.execute("ALTER TABLE attendance ADD COLUMN entry_time TEXT")
        conn.execute("ALTER TABLE attendance ADD COLUMN exit_time TEXT")
        conn.commit()
    if "work_location" not in cols:
        conn.execute("ALTER TABLE attendance ADD COLUMN work_location TEXT")
        conn.commit()
    if "reason" not in cols:
        conn.execute("ALTER TABLE attendance ADD COLUMN reason TEXT")
        conn.commit()
    if "approval_status" not in cols:
        conn.execute("ALTER TABLE attendance ADD COLUMN approval_status TEXT")
        conn.commit()
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


def manager_required(view):
    """dev/admin/director/senior manager/manager only (tier <= 1, i.e.
    lvl-0.x dev/tester variants and lvl-1.x admin variants) -- stricter
    than admin_required, since approving leave and seeing every staff
    member's requests is a manager action, not something raid_staff or
    data_manager should reach."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        level = current_level()
        if level is None or tier(level) > 1:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def now():
    return datetime.now().isoformat(timespec="seconds")


def _eligible_for(conn, user_id, year):
    """This user's eligible AL/CL/SL for a given year — their own
    leave_balances row if an admin has set one, else the department default."""
    row = conn.execute(
        "SELECT al_eligible, cl_eligible, sl_eligible FROM leave_balances WHERE user_id = ? AND year = ?",
        (user_id, year),
    ).fetchone()
    if row:
        return {"AL": row["al_eligible"], "CL": row["cl_eligible"], "SL": row["sl_eligible"]}
    return dict(DEFAULT_ELIGIBLE)


def _my_balance(conn):
    """This session's own logged-in user's AL/CL/SL eligible/used/remaining
    for the current year, for the big at-a-glance box on the mark page."""
    email = session.get("user_email")
    if not email:
        return None
    me = conn.execute("SELECT id, name FROM users.users WHERE email = ?", (email,)).fetchone()
    if not me:
        return None
    year = date.today().year
    today = date.today().isoformat()
    eligible = _eligible_for(conn, me["id"], year)
    used_rows = conn.execute(
        """SELECT leave_type, COUNT(*) AS used FROM attendance
           WHERE user_id = ? AND status = 'leave' AND leave_type IS NOT NULL AND strftime('%Y', date) = ?
           AND (approval_status = 'approved' OR approval_status IS NULL)
           GROUP BY leave_type""",
        (me["id"], str(year)),
    ).fetchall()
    used = {r["leave_type"]: r["used"] for r in used_rows}
    balance = {"user_name": me["name"], "year": year}
    for lt in LEAVE_TYPES:
        e = eligible[lt]
        us = used.get(lt, 0)
        balance[lt] = {"eligible": e, "used": us, "remaining": e - us}

    month_key = date.today().strftime("%Y-%m")

    # LOP (Loss of Pay) -- unexplained absences, not a leave type with its
    # own pool/cap, just running counts for the year and current month.
    lop_row = conn.execute(
        """SELECT
               SUM(CASE WHEN strftime('%Y', date) = ? THEN 1 ELSE 0 END) AS lop_year,
               SUM(CASE WHEN strftime('%Y-%m', date) = ? THEN 1 ELSE 0 END) AS lop_month
           FROM attendance WHERE user_id = ? AND status = 'absent'""",
        (str(year), month_key, me["id"]),
    ).fetchone()
    balance["LOP"] = {"year": lop_row["lop_year"] or 0, "month": lop_row["lop_month"] or 0}

    # Late Coming -- present days with an entry time after the department's
    # standard 9:00 AM start (see raid_working_days_policy memory).
    late_row = conn.execute(
        """SELECT
               SUM(CASE WHEN strftime('%Y', date) = ? THEN 1 ELSE 0 END) AS late_year,
               SUM(CASE WHEN strftime('%Y-%m', date) = ? THEN 1 ELSE 0 END) AS late_month
           FROM attendance
           WHERE user_id = ? AND status = 'present' AND entry_time IS NOT NULL AND entry_time > ?""",
        (str(year), month_key, me["id"], STANDARD_START_TIME),
    ).fetchone()
    balance["LATE"] = {"year": late_row["late_year"] or 0, "month": late_row["late_month"] or 0}

    # Early Leaving -- present days with an exit time before the department's
    # standard 5:30 PM end (see raid_working_days_policy memory).
    early_row = conn.execute(
        """SELECT
               SUM(CASE WHEN strftime('%Y', date) = ? THEN 1 ELSE 0 END) AS early_year,
               SUM(CASE WHEN strftime('%Y-%m', date) = ? THEN 1 ELSE 0 END) AS early_month
           FROM attendance
           WHERE user_id = ? AND status = 'present' AND exit_time IS NOT NULL AND exit_time < ?""",
        (str(year), month_key, me["id"], STANDARD_END_TIME),
    ).fetchone()
    balance["EARLY"] = {"year": early_row["early_year"] or 0, "month": early_row["early_month"] or 0}

    # Total worked time -- sum of (exit_time - entry_time) across every
    # present day this year that has an entry time saved, expressed as
    # hours/minutes/seconds (hours are not capped at 24 -- this is a
    # running total, not a clock). entry_time/exit_time only ever carry
    # HH:MM (from the <input type=time> in the mark popup), so seconds is
    # always 0 for a finished day, but the breakdown is kept in case
    # finer-grained times are ever recorded. Today, if the user has
    # checked in (entry_time set) but not out yet (exit_time still empty),
    # count the elapsed time up to right now -- so a still-in-progress
    # working day shows up live instead of only after checkout.
    worked_rows = conn.execute(
        """SELECT date, entry_time, exit_time FROM attendance
           WHERE user_id = ? AND status = 'present' AND strftime('%Y', date) = ?
           AND entry_time IS NOT NULL""",
        (me["id"], str(year)),
    ).fetchall()
    total_seconds = 0
    now_dt = datetime.now()
    for r in worked_rows:
        try:
            eh, em = (int(p) for p in r["entry_time"].split(":"))
        except (ValueError, AttributeError):
            continue
        if r["exit_time"]:
            try:
                xh, xm = (int(p) for p in r["exit_time"].split(":"))
            except ValueError:
                continue
            minutes = (xh * 60 + xm) - (eh * 60 + em)
        elif r["date"] == today:
            minutes = (now_dt.hour * 60 + now_dt.minute) - (eh * 60 + em)
        else:
            continue
        if minutes > 0:
            total_seconds += minutes * 60
    hours, rem = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    balance["WORKED"] = {"hours": hours, "minutes": minutes, "seconds": seconds}
    return balance


def _is_last_saturday(d_obj):
    """True if d_obj is the last Saturday of its month (rolling forward 7
    days lands in the next month)."""
    return d_obj.weekday() == 5 and (d_obj + timedelta(days=7)).month != d_obj.month


def _is_working_day(iso_date):
    """Mon-Fri, plus the last Saturday of each month (NLCI RAID's working
    half-day) -- every other Saturday and all Sundays are never markable."""
    y, m, d = (int(part) for part in iso_date.split("-"))
    d_obj = date(y, m, d)
    return d_obj.weekday() < 5 or _is_last_saturday(d_obj)


def _month_calendar(conn, user_id, year, month):
    """This user's attendance for one month as a list of weeks (Mon-Sun),
    each a list of 7 cells: None for padding outside the month, else
    {day, date, status, leave_type, entry_time, exit_time, work_location,
    reason, approval_status, is_today, is_future, is_weekend}."""
    rows = conn.execute(
        """SELECT date, status, leave_type, entry_time, exit_time, work_location, reason, approval_status
           FROM attendance WHERE user_id = ? AND strftime('%Y-%m', date) = ?""",
        (user_id, f"{year:04d}-{month:02d}"),
    ).fetchall()
    by_day = {r["date"]: r for r in rows}
    today = date.today().isoformat()

    weeks = []
    for week in calendar.Calendar(firstweekday=0).monthdayscalendar(year, month):
        week_cells = []
        for day_num in week:
            if day_num == 0:
                week_cells.append(None)
                continue
            d_obj = date(year, month, day_num)
            iso = d_obj.isoformat()
            rec = by_day.get(iso)
            week_cells.append({
                "day": day_num,
                "date": iso,
                "status": rec["status"] if rec else None,
                "leave_type": rec["leave_type"] if rec else None,
                "entry_time": rec["entry_time"] if rec else None,
                "exit_time": rec["exit_time"] if rec else None,
                "work_location": rec["work_location"] if rec else None,
                "reason": rec["reason"] if rec else None,
                "approval_status": rec["approval_status"] if rec else None,
                "is_today": iso == today,
                "is_future": iso > today,
                "is_weekend": not _is_working_day(iso),
            })
        weeks.append(week_cells)
    return weeks


@attendance.route("/attendance")
@admin_required
def index():
    day = request.args.get("date") or date.today().isoformat()

    month_param = request.args.get("month") or date.today().strftime("%Y-%m")
    try:
        cal_year, cal_month = (int(part) for part in month_param.split("-"))
    except ValueError:
        cal_year, cal_month = date.today().year, date.today().month

    conn = get_conn()
    users = conn.execute("SELECT id, name FROM users.users ORDER BY name").fetchall()
    marked = conn.execute("SELECT user_id, status, leave_type FROM attendance WHERE date = ?", (day,)).fetchall()
    my_balance = _my_balance(conn)

    my_email = session.get("user_email")
    me = conn.execute("SELECT id FROM users.users WHERE email = ?", (my_email,)).fetchone() if my_email else None
    calendar_weeks = _month_calendar(conn, me["id"], cal_year, cal_month) if me else None
    conn.close()

    marked_status = {row["user_id"]: row["status"] for row in marked}
    marked_leave_type = {row["user_id"]: row["leave_type"] for row in marked}

    # Prev/next month labels for the calendar's nav arrows.
    prev_year, prev_mon = (cal_year - 1, 12) if cal_month == 1 else (cal_year, cal_month - 1)
    next_year, next_mon = (cal_year + 1, 1) if cal_month == 12 else (cal_year, cal_month + 1)

    return render_template(
        "attendance_index.html",
        users=users, day=day, marked=marked_status, marked_leave_type=marked_leave_type,
        statuses=STATUSES, leave_types=LEAVE_TYPES, my_balance=my_balance,
        calendar_weeks=calendar_weeks,
        cal_month_label=f"{calendar.month_name[cal_month]} {cal_year}",
        cal_month_param=f"{cal_year:04d}-{cal_month:02d}",
        cal_prev=f"{prev_year:04d}-{prev_mon:02d}",
        cal_next=f"{next_year:04d}-{next_mon:02d}",
        standard_start_time=STANDARD_START_TIME,
        standard_end_time=STANDARD_END_TIME,
        today_iso=date.today().isoformat(),
    )


@attendance.route("/attendance/mark", methods=["POST"])
@admin_required
def mark():
    day = request.form.get("date") or date.today().isoformat()
    if day > date.today().isoformat():
        flash("Can't mark attendance for a future date.", "error")
        return redirect(url_for("attendance.index", date=day))
    if not _is_working_day(day):
        flash("Can't mark attendance on a weekend.", "error")
        return redirect(url_for("attendance.index", date=day))
    marker = session.get("user_email")
    conn = get_conn()
    user_ids = [row["id"] for row in conn.execute("SELECT id FROM users.users").fetchall()]
    for user_id in user_ids:
        status = request.form.get(f"status_{user_id}")
        if status not in STATUSES:
            continue
        leave_type = request.form.get(f"leave_type_{user_id}") if status == "leave" else None
        if leave_type not in LEAVE_TYPES:
            leave_type = None
        conn.execute(
            """
            INSERT INTO attendance (user_id, date, status, leave_type, marked_by, marked_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, date) DO UPDATE SET
                status = excluded.status,
                leave_type = excluded.leave_type,
                marked_by = excluded.marked_by,
                marked_at = excluded.marked_at
            """,
            (user_id, day, status, leave_type, marker, now()),
        )
    conn.commit()
    conn.close()
    log_action("attendance", "mark", f"marked attendance for {day}")
    flash(f"Attendance saved for {day}.", "info")
    return redirect(url_for("attendance.index", date=day))


@attendance.route("/attendance/mark_self", methods=["POST"])
@admin_required
def mark_self():
    """Self-service marking from the calendar popup on /attendance — marks
    (or clears) only the logged-in user's own row for one date, never
    anyone else's (per the department's own "don't show everyone's
    attendance" rule for this page)."""
    day = request.form.get("date")
    month = request.form.get("month") or date.today().strftime("%Y-%m")
    status = request.form.get("status", "")
    email = session.get("user_email")

    if not day or not email:
        flash("Invalid attendance entry.", "error")
        return redirect(url_for("attendance.index", month=month))
    # Leave and WFH are normally requested ahead of time, so those are the
    # only cases allowed on a future date -- present-in-office/absent still
    # can't be pre-marked.
    is_future_wfh_request = status == "present" and request.form.get("work_location") == "wfh"
    if day > date.today().isoformat() and status != "leave" and not is_future_wfh_request:
        flash("Can't mark attendance for a future date.", "error")
        return redirect(url_for("attendance.index", month=month))
    if not _is_working_day(day):
        flash("Can't mark attendance on a weekend.", "error")
        return redirect(url_for("attendance.index", month=month))

    conn = get_conn()
    me = conn.execute("SELECT id FROM users.users WHERE email = ?", (email,)).fetchone()
    if not me:
        conn.close()
        abort(403)

    if status == "":
        conn.execute("DELETE FROM attendance WHERE user_id = ? AND date = ?", (me["id"], day))
        log_action("attendance", "mark_self", f"{email} cleared {day}")
        flash(f"Cleared attendance for {day}.", "info")
    elif status in STATUSES:
        leave_type = request.form.get("leave_type") if status == "leave" else None
        if leave_type not in LEAVE_TYPES:
            leave_type = None
        # Entry/exit time and work location only mean anything for a day
        # you were actually in -- drop them for absent/leave so stale
        # values don't linger.
        entry_time = request.form.get("entry_time") or None
        exit_time = request.form.get("exit_time") or None
        work_location = request.form.get("work_location") or None
        if work_location not in WORK_LOCATIONS:
            work_location = None
        if status != "present":
            entry_time = exit_time = work_location = None
        elif work_location is None:
            work_location = "office"  # default when Present is picked with no explicit choice
        if status == "present" and not entry_time:
            # The Request WFH popup doesn't collect times at all (it's an
            # advance request, same as Request Leave) -- fall back to
            # standard hours same as the mark popup's own JS default.
            entry_time = STANDARD_START_TIME
            exit_time = STANDARD_END_TIME

        # A leave mark always starts pending -- it only counts against the
        # balance once a manager approves it (see _my_balance/
        # _leave_balance_summary). WFH also needs manager sign-off (per
        # Nidhin Joseph's real approval role for leave/WFH/IOU), though it
        # has no balance to gate -- approval there is just record-keeping,
        # visible on the manager dashboard same as a leave request. Reason
        # is kept for both leave and WFH, dropped for everything else.
        reason = (request.form.get("reason") or "").strip() or None
        if status == "leave":
            approval_status = "pending"
        elif status == "present" and work_location == "wfh":
            approval_status = "pending"
        else:
            reason = None
            approval_status = None

        conn.execute(
            """
            INSERT INTO attendance
                (user_id, date, status, leave_type, entry_time, exit_time, work_location, reason, approval_status, marked_by, marked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, date) DO UPDATE SET
                status = excluded.status,
                leave_type = excluded.leave_type,
                entry_time = excluded.entry_time,
                exit_time = excluded.exit_time,
                work_location = excluded.work_location,
                reason = excluded.reason,
                approval_status = excluded.approval_status,
                marked_by = excluded.marked_by,
                marked_at = excluded.marked_at
            """,
            (me["id"], day, status, leave_type, entry_time, exit_time, work_location, reason, approval_status, email, now()),
        )
        log_action("attendance", "mark_self", f"{email} marked {day} as {status}")
        if status == "leave":
            flash(f"Leave request submitted for {day} — pending manager approval.", "info")
        else:
            flash(f"Attendance saved for {day}.", "info")
    else:
        conn.close()
        flash("Invalid status.", "error")
        return redirect(url_for("attendance.index", month=month))

    conn.commit()
    conn.close()
    return redirect(url_for("attendance.index", month=month))


@attendance.route("/dashboard/raid-manager-dash")
@manager_required
def manager_dashboard():
    """Manager-only view: every leave AND WFH request (pending/approved/
    rejected) across the whole team, plus today's at-a-glance team status.
    Approving or rejecting a pending request happens right from this page.

    Lives under /dashboard (not /attendance) and is named distinctly from
    apps/dashboard's own pre-existing "Manager Dashboard" (library/access/
    users, at /dashboard/manager) so the two are never confused -- this one
    is specifically the RAID attendance approvals dashboard."""
    conn = get_conn()
    all_requests = conn.execute(
        """
        SELECT attendance.id, attendance.date, users.users.name AS user_name,
               attendance.status, attendance.leave_type, attendance.reason,
               attendance.approval_status, attendance.marked_at
        FROM attendance
        JOIN users.users ON users.users.id = attendance.user_id
        WHERE attendance.status = 'leave'
           OR (attendance.status = 'present' AND attendance.work_location = 'wfh')
        ORDER BY
            CASE COALESCE(attendance.approval_status, 'approved') WHEN 'pending' THEN 0 ELSE 1 END,
            attendance.date DESC
        """
    ).fetchall()

    today = date.today().isoformat()
    today_status = conn.execute(
        """
        SELECT users.users.name AS user_name, attendance.status, attendance.leave_type, attendance.work_location
        FROM users.users
        LEFT JOIN attendance ON attendance.user_id = users.users.id AND attendance.date = ?
        ORDER BY users.users.name
        """,
        (today,),
    ).fetchall()
    conn.close()

    return render_template(
        "attendance_manager.html",
        all_requests=all_requests, today_status=today_status, today=today,
    )


@attendance.route("/attendance/request/<int:record_id>/approve", methods=["POST"])
@manager_required
def approve_request(record_id):
    """Approves a pending leave OR WFH request (both use approval_status;
    see mark_self). Scoped to actually-pending rows so this can't be used
    to silently flip an already-decided or non-request row."""
    conn = get_conn()
    conn.execute(
        "UPDATE attendance SET approval_status = 'approved' WHERE id = ? AND approval_status = 'pending'",
        (record_id,),
    )
    conn.commit()
    conn.close()
    log_action("attendance", "approve_request", f"approved request #{record_id}")
    flash("Request approved.", "info")
    return redirect(url_for("attendance.manager_dashboard"))


@attendance.route("/attendance/request/<int:record_id>/reject", methods=["POST"])
@manager_required
def reject_request(record_id):
    conn = get_conn()
    conn.execute(
        "UPDATE attendance SET approval_status = 'rejected' WHERE id = ? AND approval_status = 'pending'",
        (record_id,),
    )
    conn.commit()
    conn.close()
    log_action("attendance", "reject_request", f"rejected request #{record_id}")
    flash("Request rejected.", "info")
    return redirect(url_for("attendance.manager_dashboard"))
