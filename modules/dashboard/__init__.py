import sqlite3
from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from modules.access import SCHEMA as ACCESS_REQUESTS_SCHEMA
from modules.audit import log_action, recent_entries
from modules.db import BOOKS_DB, LOANS_DB, USERS_DB
from modules.library import _ensure_loans_table
from modules.levels import (
    ADMIN_LEVEL,
    ANONYMOUS_LEVEL,
    LEVEL_NAMES,
    SUB_LEVEL_DASHBOARD_ENDPOINTS,
    current_level,
    level_label,
    real_level,
    tier,
)

dashboard = Blueprint("dashboard", __name__, template_folder="templates")

def get_conn():
    """Connect to users.db and attach books.db / loans.db so loans can be joined.

    loans.loans is the unified request+loan table owned by modules/library
    (see modules/library/__init__.py's LOANS_SCHEMA / _ensure_loans_table).
    This module only reads it — it no longer creates its own separate
    requests table or migrates loan columns; that's the library module's job.
    """
    conn = sqlite3.connect(USERS_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("ATTACH DATABASE ? AS books", (str(BOOKS_DB),))
    conn.execute("ATTACH DATABASE ? AS loans", (str(LOANS_DB),))
    conn.executescript(ACCESS_REQUESTS_SCHEMA)
    _ensure_loans_table(conn)  # idempotent — safe whichever route hits it first
    return conn


def admin_required(view):
    """The whole dashboard is dev/admin only (lvl <= 1) — data_manager and
    raid_staff no longer get a dashboard page at all."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        level = current_level()
        if level is None or tier(level) > ADMIN_LEVEL:
            flash("You need admin access for that.", "error")
            return redirect(url_for("hello"))
        return view(*args, **kwargs)

    return wrapped


@dashboard.route("/dev/view-as", methods=["POST"])
def set_view_as():
    """Lets a real (non-simulated) lvl-0 dev preview the app as any level in
    real time, via a session override — never touches the DB. Only the
    permission checks are affected; the dev's actual identity/DB row never
    changes, so they can always switch back."""
    r_level = real_level()
    if r_level is None or tier(r_level) != 0.0:
        abort(403)
    raw = request.form.get("level", "")
    if raw == "__reset__":
        session.pop("view_as_level", None)
    else:
        try:
            level = float(raw)
        except ValueError:
            abort(400)
        if level < 0.0 or level > ANONYMOUS_LEVEL:
            abort(400)
        session["view_as_level"] = level
    return redirect(request.referrer or url_for("hello"))


def _dashboard_context():
    """Shared data-gathering for the dashboard and each sub-level's own copy
    of it. Currently identical content everywhere; each route renders its
    own template so they can diverge later without touching the others."""
    conn = get_conn()
    is_admin = tier(current_level()) <= ADMIN_LEVEL
    users = conn.execute("SELECT * FROM users ORDER BY name").fetchall()
    # loans.loans is now the single unified table for the whole request/loan
    # lifecycle (see modules/library). "loans" here = actually issued history
    # (issued or returned); "requests" = still awaiting an admin decision.
    # Old columns are aliased back to their old names so the templates,
    # which were never touched, keep working unmodified.
    loans = conn.execute("""
        SELECT loans.loans.id, books.books.title, users.name AS user_name, loans.loans.status,
               loans.loans.requested_at, loans.loans.approved_by AS issued_by, loans.loans.taken_at AS issued_at,
               loans.loans.returned_at, loans.loans.returned_to AS returned_by
        FROM loans.loans
        JOIN books.books ON books.books.id = loans.loans.book_id
        JOIN users ON users.id = loans.loans.requested_by
        WHERE loans.loans.status IN ('issued', 'returned')
        ORDER BY loans.loans.id
    """).fetchall()
    requests = conn.execute("""
        SELECT loans.loans.id, loans.loans.status, loans.loans.requested_at,
               books.books.title AS book_title, users.name AS user_name
        FROM loans.loans
        JOIN books.books ON books.books.id = loans.loans.book_id
        JOIN users ON users.id = loans.loans.requested_by
        WHERE loans.loans.status = 'pending'
        ORDER BY loans.loans.requested_at DESC, loans.loans.id DESC
    """).fetchall()
    access_requests = conn.execute(
        "SELECT * FROM access_requests ORDER BY requested_at DESC, id DESC"
    ).fetchall()
    conn.close()
    return {
        "users": users,
        "loans": loans,
        "requests": requests,
        "access_requests": access_requests,
        "level_names": LEVEL_NAMES,
        "level_label": level_label,
        "tier": tier,
        "is_admin": is_admin,
    }


@dashboard.route("/dashboard")
@admin_required
def index():
    own_dashboard = SUB_LEVEL_DASHBOARD_ENDPOINTS.get(current_level())
    if own_dashboard:
        return redirect(url_for(own_dashboard))
    return render_template("dashboard_index.html", **_dashboard_context())


@dashboard.route("/dashboard/director")
@admin_required
def director_dashboard():
    return render_template("dashboard_director.html", **_dashboard_context())


@dashboard.route("/dashboard/senior-manager")
@admin_required
def senior_manager_dashboard():
    return render_template("dashboard_senior_manager.html", **_dashboard_context())


@dashboard.route("/dashboard/manager")
@admin_required
def manager_dashboard():
    return render_template("dashboard_manager.html", **_dashboard_context())


@dashboard.route("/dashboard/developer")
@admin_required
def developer_dashboard():
    return render_template("dashboard_developer.html", **_dashboard_context())


@dashboard.route("/dashboard/technical-tester")
@admin_required
def technical_tester_dashboard():
    return render_template("dashboard_technical_tester.html", **_dashboard_context())


@dashboard.route("/dashboard/non-technical-tester")
@admin_required
def non_technical_tester_dashboard():
    return render_template("dashboard_non_technical_tester.html", **_dashboard_context())


@dashboard.route("/dashboard/outside-developer")
@admin_required
def outside_developer_dashboard():
    return render_template("dashboard_outside_developer.html", **_dashboard_context())


@dashboard.route("/dashboard/outside-tester")
@admin_required
def outside_tester_dashboard():
    return render_template("dashboard_outside_tester.html", **_dashboard_context())


@dashboard.route("/dashboard/users/add", methods=["POST"])
@admin_required
def add_user():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower() or None
    library_code = request.form.get("library_code", "").strip() or None
    if not name:
        flash("Name is required.", "error")
    else:
        conn = sqlite3.connect(USERS_DB)
        try:
            conn.execute(
                "INSERT INTO users (name, email, library_code) VALUES (?, ?, ?)",
                (name, email, library_code),
            )
            conn.commit()
            flash(f"Added user {name}.", "info")
        except sqlite3.IntegrityError:
            flash(f"A user named {name} already exists.", "error")
        finally:
            conn.close()
    return redirect(url_for("dashboard.index"))


@dashboard.route("/dashboard/users/<int:user_id>/level", methods=["POST"])
@admin_required
def update_level(user_id):
    raw_level = request.form.get("level", "")
    try:
        level = float(raw_level)
    except ValueError:
        abort(400)
    if level < 0.0 or tier(level) not in LEVEL_NAMES:
        abort(400)
    conn = get_conn()
    target = conn.execute("SELECT name FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.execute("UPDATE users SET level = ? WHERE id = ?", (level, user_id))
    conn.commit()
    conn.close()
    log_action("dashboard", "update_level", f"set level of user #{user_id} ({target['name'] if target else '?'}) to {level_label(level)} (lvl-{level:g})")
    flash("Level updated.", "info")
    return redirect(url_for("dashboard.index"))


@dashboard.route("/dashboard/audit-log")
@admin_required
def audit_log():
    return render_template("audit_log.html", entries=recent_entries())
