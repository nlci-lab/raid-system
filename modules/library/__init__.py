import sqlite3
from datetime import datetime
from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from modules.audit import log_action
from modules.db import BOOKS_DB, LOANS_DB, USERS_DB

library = Blueprint("library", __name__, template_folder="templates")

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
    """Connect to books.db and attach users.db / loans.db so they can be joined."""
    conn = sqlite3.connect(BOOKS_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("ATTACH DATABASE ? AS users", (str(USERS_DB),))
    conn.execute("ATTACH DATABASE ? AS loans", (str(LOANS_DB),))
    conn.executescript(REQUESTS_SCHEMA)
    _ensure_audit_columns(conn)
    return conn


def now():
    return datetime.now().isoformat(timespec="seconds")


def _current_user(conn):
    email = session.get("user_email", "")
    if not email:
        return None
    return conn.execute(
        "SELECT id, name, role FROM users.users WHERE lower(email) = ?", (email.lower(),)
    ).fetchone()


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        conn = get_conn()
        try:
            user = _current_user(conn)
        finally:
            conn.close()
        if not user or user["role"] not in MANAGER_ROLES:
            flash("You need admin or data manager access to manage book requests.", "error")
            return redirect(url_for("dashboard.index"))
        return view(*args, **kwargs)

    return wrapped


def _pending_request_book_ids(conn, user):
    if not user:
        return set()
    rows = conn.execute(
        "SELECT book_id FROM loans.requests WHERE user_id = ? AND status = 'pending'",
        (user["id"],),
    ).fetchall()
    return {row["book_id"] for row in rows}


@library.route("/library")
def index():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM books ORDER BY id").fetchall()
    requested_ids = _pending_request_book_ids(conn, _current_user(conn))
    conn.close()
    return render_template("library_index.html", books=rows, requested_ids=requested_ids)


@library.route("/library/books/<int:book_id>/request", methods=["POST"])
def request_book(book_id):
    conn = get_conn()
    user = _current_user(conn)
    if not user:
        conn.close()
        flash("No library user record is linked to your account.", "error")
        return redirect(request.referrer or url_for("library.index"))

    book = conn.execute("SELECT title FROM books WHERE id = ?", (book_id,)).fetchone()
    if not book:
        conn.close()
        abort(404)

    existing = conn.execute(
        "SELECT 1 FROM loans.requests WHERE book_id = ? AND user_id = ? AND status = 'pending'",
        (book_id, user["id"]),
    ).fetchone()
    if existing:
        conn.close()
        flash(f"You already have a pending request for {book['title']}.", "error")
        return redirect(request.referrer or url_for("library.index"))

    conn.execute(
        "INSERT INTO loans.requests (book_id, user_id, status, requested_at) VALUES (?, ?, 'pending', ?)",
        (book_id, user["id"], now()),
    )
    conn.commit()
    conn.close()
    flash(f"Requested \"{book['title']}\". An admin will review your request.", "info")
    return redirect(request.referrer or url_for("library.index"))


@library.route("/library/requests/<int:request_id>/accept", methods=["POST"])
@admin_required
def accept_request(request_id):
    conn = get_conn()
    req = conn.execute("SELECT * FROM loans.requests WHERE id = ?", (request_id,)).fetchone()
    if not req or req["status"] != "pending":
        conn.close()
        flash("That request is no longer pending.", "error")
        return redirect(request.referrer or url_for("dashboard.index"))

    admin_email = session.get("user_email", "")
    decided_at = now()
    conn.execute(
        """
        INSERT INTO loans.loans (book_id, user_id, status, requested_at, issued_by, issued_at)
        VALUES (?, ?, 'Taken', ?, ?, ?)
        """,
        (req["book_id"], req["user_id"], req["requested_at"], admin_email, decided_at),
    )
    conn.execute("UPDATE books SET availability = 'Taken' WHERE id = ?", (req["book_id"],))
    conn.execute(
        "UPDATE loans.requests SET status = 'issued', decided_by = ?, decided_at = ? WHERE id = ?",
        (admin_email, decided_at, request_id),
    )
    conn.commit()
    conn.close()
    log_action("library", "accept_request", f"request #{request_id} (book #{req['book_id']}) issued to user #{req['user_id']}")
    flash("Request accepted — book marked as issued.", "info")
    return redirect(request.referrer or url_for("dashboard.index"))


@library.route("/library/requests/<int:request_id>/reject", methods=["POST"])
@admin_required
def reject_request(request_id):
    conn = get_conn()
    req = conn.execute("SELECT status FROM loans.requests WHERE id = ?", (request_id,)).fetchone()
    if not req or req["status"] != "pending":
        conn.close()
        flash("That request is no longer pending.", "error")
        return redirect(request.referrer or url_for("dashboard.index"))

    conn.execute(
        "UPDATE loans.requests SET status = 'rejected', decided_by = ?, decided_at = ? WHERE id = ?",
        (session.get("user_email", ""), now(), request_id),
    )
    conn.commit()
    conn.close()
    log_action("library", "reject_request", f"request #{request_id}")
    flash("Request rejected.", "info")
    return redirect(request.referrer or url_for("dashboard.index"))


@library.route("/library/loans/<int:loan_id>/return", methods=["POST"])
@admin_required
def return_loan(loan_id):
    conn = get_conn()
    loan = conn.execute("SELECT * FROM loans.loans WHERE id = ?", (loan_id,)).fetchone()
    if not loan or loan["status"] != "Taken":
        conn.close()
        flash("That loan is not currently active.", "error")
        return redirect(request.referrer or url_for("dashboard.index"))

    conn.execute(
        "UPDATE loans.loans SET status = 'Returned', returned_at = ?, returned_by = ? WHERE id = ?",
        (now(), session.get("user_email", ""), loan_id),
    )
    conn.execute("UPDATE books SET availability = 'At Stock' WHERE id = ?", (loan["book_id"],))
    conn.commit()
    conn.close()
    log_action("library", "return_loan", f"loan #{loan_id} (book #{loan['book_id']})")
    flash("Book marked as returned.", "info")
    return redirect(request.referrer or url_for("dashboard.index"))


