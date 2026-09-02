import sqlite3
from datetime import datetime
from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from modules.audit import log_action
from modules.db import BOOKS_DB, LOANS_DB, USERS_DB
from modules.levels import MANAGER_LEVEL, VIEWER_LEVEL, current_level, tier
from modules.library.sync_from_sheet import DEFAULT_CSV_URL, sync_books_from_sheet

library = Blueprint("library", __name__, template_folder="templates")

# New unified loans schema — no more separate requests/loans tables.
LOANS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS loans.loans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER NOT NULL REFERENCES books(id),
        status TEXT NOT NULL,
        requested_by INTEGER,
        requested_at TEXT,
        approved_by TEXT,
        approved_at TEXT,
        taken_at TEXT,
        expected_return_at TEXT,
        returned_at TEXT,
        returned_to TEXT
    );
"""


def _ensure_loans_table(conn):
    """Ensure loans.loans exists with the new unified schema.

    The pre-existing "loans" table (from build_db.py's old id/book_id/user_id/
    status shape) has the same name but different columns, so a plain
    "CREATE TABLE IF NOT EXISTS" would silently no-op against it and every
    new query (which references requested_by/approved_by/etc.) would fail
    with "no such column". Detect that case and rename the old table out of
    the way instead of dropping it, so historical rows aren't destroyed.
    """
    cols = {row[1] for row in conn.execute("PRAGMA loans.table_info(loans)")}
    if cols and "requested_by" not in cols:
        conn.execute("ALTER TABLE loans.loans RENAME TO loans_legacy")
    conn.executescript(LOANS_SCHEMA)
    conn.commit()


def get_conn():
    """Connect to books.db (which has books table) and attach loans.db
    (which has loans table) and users.db (for user lookups).
    Both databases are attached to enable joins across them."""
    conn = sqlite3.connect(BOOKS_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("ATTACH DATABASE ? AS loans", (str(LOANS_DB),))
    conn.execute("ATTACH DATABASE ? AS users", (str(USERS_DB),))
    _ensure_loans_table(conn)
    return conn


def now():
    return datetime.now().isoformat(timespec="seconds")


def _current_user(conn):
    email = session.get("user_email", "")
    if not email:
        return None
    return conn.execute(
        "SELECT id, name, level FROM users.users WHERE lower(email) = ?", (email.lower(),)
    ).fetchone()


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        level = current_level()
        if level is None or tier(level) > MANAGER_LEVEL:
            flash("You need admin or data manager access to manage book requests.", "error")
            return redirect(url_for("dashboard.index"))
        return view(*args, **kwargs)

    return wrapped


def viewer_required(view):
    """External (lvl-5) doesn't get the library — everyone else logged in does."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        level = current_level()
        if level is None or tier(level) > VIEWER_LEVEL:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def _pending_request_book_ids(conn, user):
    """Get the set of book_ids with pending requests by this user."""
    if not user:
        return set()
    rows = conn.execute(
        "SELECT DISTINCT book_id FROM loans.loans WHERE requested_by = ? AND status = 'pending'",
        (user["id"],),
    ).fetchall()
    return {row["book_id"] for row in rows}


def _book_availability(conn, book_id):
    """Derive current availability status for a book.
    Returns 'Taken' if an open issued loan exists (status='issued', returned_at IS NULL),
    otherwise 'At Stock'."""
    row = conn.execute(
        "SELECT 1 FROM loans.loans WHERE book_id = ? AND status = 'issued' AND returned_at IS NULL",
        (book_id,),
    ).fetchone()
    return "Taken" if row else "At Stock"


@library.route("/library")
@viewer_required
def index():
    conn = get_conn()
    # Display order = catalog "Sorting parameter" from the source spreadsheet:
    # 1. Genre  2. Series  3. Publish year (ascending)  4. Book title.
    # This is a query-time sort only — it has no relation to a book's physical
    # shelf position (shelf_name/case_number/case_id), which is assigned once
    # per book in arrival order and never renumbered. Keeping the two decoupled
    # means adding a book never reshuffles another book's shelf label; it just
    # changes where the new row lands in this ORDER BY.

    # Check if new schema columns exist; fall back to old schema if needed
    try:
        # Try new schema first (after sync)
        rows = conn.execute("""
            SELECT * FROM books
            ORDER BY genre, series, publish_year, title
        """).fetchall()
    except Exception:
        # Fall back to old schema (before first sync)
        rows = conn.execute("""
            SELECT * FROM books
            ORDER BY genre, series, pub_year, title
        """).fetchall()

    # Compute availability for each book; convert Row to dict with safe defaults
    books_with_availability = []
    for book in rows:
        book_dict = dict(book)
        # Support both old schema (pub_year) and new schema (publish_year)
        if "publish_year" not in book_dict and "pub_year" in book_dict:
            book_dict["publish_year"] = book_dict["pub_year"]
        # Ensure all expected fields exist (some may be NULL if schema is old)
        for field in ["ok", "scanned", "library_id", "l_id", "shelf_name", "case_number", "case_id", "link_to_toc", "publish_year"]:
            if field not in book_dict:
                book_dict[field] = None
        book_dict["availability"] = _book_availability(conn, book["id"])
        books_with_availability.append(book_dict)

    requested_ids = _pending_request_book_ids(conn, _current_user(conn))
    conn.close()
    return render_template("library_index.html", books=books_with_availability, requested_ids=requested_ids)


@library.route("/library/books/<int:book_id>/request", methods=["POST"])
@viewer_required
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

    # Check for existing pending request
    existing = conn.execute(
        "SELECT 1 FROM loans.loans WHERE book_id = ? AND requested_by = ? AND status = 'pending'",
        (book_id, user["id"]),
    ).fetchone()
    if existing:
        conn.close()
        flash(f"You already have a pending request for {book['title']}.", "error")
        return redirect(request.referrer or url_for("library.index"))

    conn.execute(
        """INSERT INTO loans.loans
           (book_id, status, requested_by, requested_at)
           VALUES (?, 'pending', ?, ?)""",
        (book_id, user["id"], now()),
    )
    conn.commit()
    conn.close()
    flash(f"Requested \"{book['title']}\". An admin will review your request.", "info")
    return redirect(request.referrer or url_for("library.index"))


@library.route("/library/requests/<int:loan_id>/accept", methods=["POST"])
@admin_required
def accept_request(loan_id):
    conn = get_conn()
    loan = conn.execute("SELECT * FROM loans.loans WHERE id = ?", (loan_id,)).fetchone()
    if not loan or loan["status"] != "pending":
        conn.close()
        flash("That request is no longer pending.", "error")
        return redirect(request.referrer or url_for("dashboard.index"))

    admin_email = session.get("user_email", "")
    decided_at = now()
    conn.execute(
        """UPDATE loans.loans
           SET status = 'issued', approved_by = ?, approved_at = ?, taken_at = ?
           WHERE id = ?""",
        (admin_email, decided_at, decided_at, loan_id),
    )
    conn.commit()
    conn.close()
    log_action("library", "accept_request", f"request #{loan_id} (book #{loan['book_id']}) issued to user #{loan['requested_by']}")
    flash("Request accepted — book marked as issued.", "info")
    return redirect(request.referrer or url_for("dashboard.index"))


@library.route("/library/requests/<int:loan_id>/reject", methods=["POST"])
@admin_required
def reject_request(loan_id):
    conn = get_conn()
    loan = conn.execute("SELECT status FROM loans.loans WHERE id = ?", (loan_id,)).fetchone()
    if not loan or loan["status"] != "pending":
        conn.close()
        flash("That request is no longer pending.", "error")
        return redirect(request.referrer or url_for("dashboard.index"))

    conn.execute(
        """UPDATE loans.loans
           SET status = 'rejected', approved_by = ?, approved_at = ?
           WHERE id = ?""",
        (session.get("user_email", ""), now(), loan_id),
    )
    conn.commit()
    conn.close()
    log_action("library", "reject_request", f"request #{loan_id}")
    flash("Request rejected.", "info")
    return redirect(request.referrer or url_for("dashboard.index"))


@library.route("/library/loans/<int:loan_id>/return", methods=["POST"])
@admin_required
def return_loan(loan_id):
    conn = get_conn()
    loan = conn.execute("SELECT * FROM loans.loans WHERE id = ?", (loan_id,)).fetchone()
    if not loan or loan["status"] != "issued":
        conn.close()
        flash("That loan is not currently active.", "error")
        return redirect(request.referrer or url_for("dashboard.index"))

    conn.execute(
        """UPDATE loans.loans
           SET status = 'returned', returned_at = ?, returned_to = ?
           WHERE id = ?""",
        (now(), session.get("user_email", ""), loan_id),
    )
    conn.commit()
    conn.close()
    log_action("library", "return_loan", f"loan #{loan_id} (book #{loan['book_id']})")
    flash("Book marked as returned.", "info")
    return redirect(request.referrer or url_for("dashboard.index"))


@library.route("/library/sync", methods=["POST"])
@admin_required
def sync_from_sheet():
    """Admin-only route to sync books from Google Sheets CSV export."""
    csv_url = request.form.get("csv_url") or DEFAULT_CSV_URL

    try:
        result = sync_books_from_sheet(csv_url)
        imported = result["imported"]
        skipped = result["skipped"]
        msg = f"Imported {imported} books"
        if skipped:
            msg += f" ({len(skipped)} rows skipped)"
        log_action("library", "sync_from_sheet", f"imported {imported} books, {len(skipped) if skipped else 0} skipped")
        flash(msg, "info")
        if skipped and len(skipped) <= 10:
            flash("Skipped rows: " + "; ".join(skipped[:10]), "warning")
    except Exception as e:
        log_action("library", "sync_from_sheet", f"failed: {str(e)}")
        flash(f"Sync failed: {str(e)}", "error")

    return redirect(request.referrer or url_for("library.index"))
