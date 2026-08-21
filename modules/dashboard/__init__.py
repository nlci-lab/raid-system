import sqlite3
from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from modules.access import SCHEMA as ACCESS_REQUESTS_SCHEMA
from modules.audit import log_action, recent_entries
from modules.db import BOOKS_DB, LOANS_DB, USERS_DB

dashboard = Blueprint("dashboard", __name__, template_folder="templates")

ROLES = ("tester", "admin", "data_manager", "user")
MANAGER_ROLES = ("admin", "data_manager")

REQUESTS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS loans.requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        requested_at TEXT NOT NULL
    );
"""

_REQUEST_AUDIT_COLUMNS = {
    "decided_by": "TEXT",
    "decided_at": "TEXT",
}

_LOAN_AUDIT_COLUMNS = {
    "requested_at": "TEXT",
    "issued_by": "TEXT",
    "issued_at": "TEXT",
    "returned_at": "TEXT",
    "returned_by": "TEXT",
}


def _ensure_audit_columns(conn):
    existing_requests = {row[1] for row in conn.execute("PRAGMA loans.table_info(requests)")}
    for name, ddl_type in _REQUEST_AUDIT_COLUMNS.items():
        if name not in existing_requests:
            conn.execute(f"ALTER TABLE loans.requests ADD COLUMN {name} {ddl_type}")

    existing_loans = {row[1] for row in conn.execute("PRAGMA loans.table_info(loans)")}
    for name, ddl_type in _LOAN_AUDIT_COLUMNS.items():
        if name not in existing_loans:
            conn.execute(f"ALTER TABLE loans.loans ADD COLUMN {name} {ddl_type}")

    conn.commit()


def get_conn():
    """Connect to users.db and attach books.db / loans.db so loans can be joined."""
    conn = sqlite3.connect(USERS_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("ATTACH DATABASE ? AS books", (str(BOOKS_DB),))
    conn.execute("ATTACH DATABASE ? AS loans", (str(LOANS_DB),))
    conn.executescript(REQUESTS_SCHEMA)
    conn.executescript(ACCESS_REQUESTS_SCHEMA)
    _ensure_audit_columns(conn)
    return conn


def _current_user_role(conn):
    email = session.get("user_email")
    if not email:
        return None
    row = conn.execute("SELECT role FROM users WHERE lower(email) = ?", (email.lower(),)).fetchone()
    return row["role"] if row else None


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        conn = get_conn()
        try:
            role = _current_user_role(conn)
        finally:
            conn.close()
        if role != "admin":
            flash("You need admin access for that.", "error")
            return redirect(url_for("dashboard.index"))
        return view(*args, **kwargs)

    return wrapped


def manager_required(view):
    """Admins and data managers: everything on the dashboard except role changes."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        conn = get_conn()
        try:
            role = _current_user_role(conn)
        finally:
            conn.close()
        if role not in MANAGER_ROLES:
            flash("You need admin or data manager access to view the dashboard.", "error")
            return redirect(url_for("hello"))
        return view(*args, **kwargs)

    return wrapped


@dashboard.route("/dashboard")
@manager_required
def index():
    conn = get_conn()
    is_admin = _current_user_role(conn) == "admin"
    users = conn.execute("SELECT * FROM users ORDER BY name").fetchall()
    loans = conn.execute("""
        SELECT loans.loans.id, books.books.title, users.name AS user_name, loans.loans.status,
               loans.loans.requested_at, loans.loans.issued_by, loans.loans.issued_at,
               loans.loans.returned_at, loans.loans.returned_by
        FROM loans.loans
        JOIN books.books ON books.books.id = loans.loans.book_id
        JOIN users ON users.id = loans.loans.user_id
        ORDER BY loans.loans.id
    """).fetchall()
    requests = conn.execute("""
        SELECT loans.requests.id, loans.requests.status, loans.requests.requested_at,
               books.books.title AS book_title, users.name AS user_name
        FROM loans.requests
        JOIN books.books ON books.books.id = loans.requests.book_id
        JOIN users ON users.id = loans.requests.user_id
        ORDER BY loans.requests.requested_at DESC, loans.requests.id DESC
    """).fetchall()
    access_requests = conn.execute(
        "SELECT * FROM access_requests ORDER BY requested_at DESC, id DESC"
    ).fetchall()
    conn.close()
    return render_template(
        "dashboard_index.html",
        users=users,
        loans=loans,
        requests=requests,
        access_requests=access_requests,
        roles=ROLES,
        is_admin=is_admin,
    )


@dashboard.route("/dashboard/users/add", methods=["POST"])
@manager_required
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


@dashboard.route("/dashboard/users/<int:user_id>/role", methods=["POST"])
@admin_required
def update_role(user_id):
    role = request.form.get("role", "")
    if role not in ROLES:
        abort(400)
    conn = get_conn()
    target = conn.execute("SELECT name FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
    conn.commit()
    conn.close()
    log_action("dashboard", "update_role", f"set role of user #{user_id} ({target['name'] if target else '?'}) to {role}")
    flash("Role updated.", "info")
    return redirect(url_for("dashboard.index"))


@dashboard.route("/dashboard/audit-log")
@admin_required
def audit_log():
    return render_template("audit_log.html", entries=recent_entries())
