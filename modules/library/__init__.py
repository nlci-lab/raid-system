import sqlite3
from datetime import datetime
from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from modules.audit import log_action
from modules.db import LIBRARY_DB, USERS_DB
from modules.levels import MANAGER_LEVEL, VIEWER_LEVEL, current_level, tier
from modules.library.sync_from_sheet import DEFAULT_CSV_URL, sync_books_from_sheet

library = Blueprint("library", __name__, template_folder="templates")

# Unified loans schema — books and loans both live in library.db now (one
# file, two tables), so no cross-db attach/prefix is needed between them
# *when library.db is the connection's main database* (this module's own
# get_conn()). dashboard.get_conn() attaches library.db under the alias
# "library" instead (main there is users.db) -- unqualified CREATE
# TABLE/ALTER TABLE/PRAGMA always target "main" regardless of attach order,
# so _ensure_loans_table takes a schema prefix to stay correct either way.
LOANS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS {prefix}loans (
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


def _ensure_loans_table(conn, prefix=""):
    """Ensure loans exists with the current unified schema.

    prefix is "" when library.db is the connection's main database (this
    module's own get_conn()), or "library." when it's attached under that
    alias instead (dashboard.get_conn()) -- unqualified DDL always targets
    "main", so the prefix must be explicit to land in the right database.

    A pre-existing "loans" table from an older shape (different columns)
    would make a plain "CREATE TABLE IF NOT EXISTS" silently no-op, and
    every query here (which references requested_by/approved_by/etc.) would
    fail with "no such column". Detect that case and rename the old table
    out of the way instead of dropping it, so historical rows aren't
    destroyed.
    """
    cols = {row[1] for row in conn.execute(f"PRAGMA {prefix}table_info(loans)")}
    if cols and "requested_by" not in cols:
        conn.execute(f"ALTER TABLE {prefix}loans RENAME TO loans_legacy")
    conn.executescript(LOANS_SCHEMA.format(prefix=prefix))
    conn.commit()


def get_conn():
    """Connect to library.db (books + loans tables) and attach users.db for
    user lookups."""
    conn = sqlite3.connect(LIBRARY_DB)
    conn.row_factory = sqlite3.Row
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
        "SELECT DISTINCT book_id FROM loans WHERE requested_by = ? AND status = 'pending'",
        (user["id"],),
    ).fetchall()
    return {row["book_id"] for row in rows}


def _my_requests(conn, user):
    """This user's requests that haven't turned into a loan yet — pending
    (awaiting review) and rejected (so they can see the outcome), most
    recent first. Once accepted, a request becomes an 'issued' loan and
    moves to _my_loans instead."""
    if not user:
        return []
    return conn.execute(
        """SELECT loans.id, loans.status, loans.requested_at, loans.approved_by, loans.approved_at,
                  books.title, books.author
           FROM loans JOIN books ON books.id = loans.book_id
           WHERE loans.requested_by = ? AND loans.status IN ('pending', 'rejected')
           ORDER BY loans.requested_at DESC, loans.id DESC""",
        (user["id"],),
    ).fetchall()


def _my_loans(conn, user):
    """This user's issued (currently held) and returned (history) loans,
    active loans first."""
    if not user:
        return []
    return conn.execute(
        """SELECT loans.id, loans.status, loans.taken_at, loans.expected_return_at,
                  loans.returned_at, loans.returned_to, books.title, books.author
           FROM loans JOIN books ON books.id = loans.book_id
           WHERE loans.requested_by = ? AND loans.status IN ('issued', 'returned')
           ORDER BY (loans.status = 'issued') DESC, loans.taken_at DESC, loans.id DESC""",
        (user["id"],),
    ).fetchall()


def _my_tab_counts(conn, user):
    """Cheap counts for the My Requests / My Loans tab badges — pending
    requests awaiting a decision, and loans currently issued (not
    returned). Computed regardless of which tab is active so the badges
    stay accurate no matter where the user lands."""
    if not user:
        return {"pending": 0, "issued": 0}
    pending = conn.execute(
        "SELECT COUNT(*) FROM loans WHERE requested_by = ? AND status = 'pending'",
        (user["id"],),
    ).fetchone()[0]
    issued = conn.execute(
        "SELECT COUNT(*) FROM loans WHERE requested_by = ? AND status = 'issued'",
        (user["id"],),
    ).fetchone()[0]
    return {"pending": pending, "issued": issued}


def _book_availability(conn, book_id):
    """Derive current availability status for a book.
    Returns 'Taken' if an open issued loan exists (status='issued', returned_at IS NULL),
    otherwise 'At Stock'."""
    row = conn.execute(
        "SELECT 1 FROM loans WHERE book_id = ? AND status = 'issued' AND returned_at IS NULL",
        (book_id,),
    ).fetchone()
    return "Taken" if row else "At Stock"


@library.route("/library")
@viewer_required
def index():
    conn = get_conn()
    user = _current_user(conn)

    tab = request.args.get("tab", "catalog")
    if tab not in ("catalog", "requests", "loans"):
        tab = "catalog"

    books_with_availability = []
    requested_ids = set()
    my_requests = []
    my_loans = []

    if tab == "catalog":
        # Display order = catalog "Sorting parameter" from the source spreadsheet:
        # 1. Genre  2. Series  3. Publish year (ascending)  4. Book title.
        # ok/scanned/shelf_name/case_number/case_id no longer exist (dropped along
        # with the sheet's underscore-prefixed columns) -- no physical shelf
        # location is tracked or displayed any more.
        rows = conn.execute("""
            SELECT * FROM books
            ORDER BY genre, series, publish_year, title
        """).fetchall()

        # Compute availability for each book; convert Row to dict with safe defaults
        for book in rows:
            book_dict = dict(book)
            # Ensure all expected fields exist (some may be NULL)
            for field in ["library_id", "l_id", "link_to_toc", "publish_year"]:
                if field not in book_dict:
                    book_dict[field] = None
            book_dict["availability"] = _book_availability(conn, book["id"])
            books_with_availability.append(book_dict)

        requested_ids = _pending_request_book_ids(conn, user)
    elif tab == "requests":
        my_requests = _my_requests(conn, user)
    elif tab == "loans":
        my_loans = _my_loans(conn, user)

    tab_counts = _my_tab_counts(conn, user)
    conn.close()
    return render_template(
        "library_index.html",
        tab=tab,
        has_library_user=user is not None,
        books=books_with_availability,
        requested_ids=requested_ids,
        my_requests=my_requests,
        my_loans=my_loans,
        tab_counts=tab_counts,
    )


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
        "SELECT 1 FROM loans WHERE book_id = ? AND requested_by = ? AND status = 'pending'",
        (book_id, user["id"]),
    ).fetchone()
    if existing:
        conn.close()
        flash(f"You already have a pending request for {book['title']}.", "error")
        return redirect(request.referrer or url_for("library.index"))

    conn.execute(
        """INSERT INTO loans
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
    loan = conn.execute("SELECT * FROM loans WHERE id = ?", (loan_id,)).fetchone()
    if not loan or loan["status"] != "pending":
        conn.close()
        flash("That request is no longer pending.", "error")
        return redirect(request.referrer or url_for("dashboard.index"))

    admin_email = session.get("user_email", "")
    decided_at = now()
    conn.execute(
        """UPDATE loans
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
    loan = conn.execute("SELECT status FROM loans WHERE id = ?", (loan_id,)).fetchone()
    if not loan or loan["status"] != "pending":
        conn.close()
        flash("That request is no longer pending.", "error")
        return redirect(request.referrer or url_for("dashboard.index"))

    conn.execute(
        """UPDATE loans
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
    loan = conn.execute("SELECT * FROM loans WHERE id = ?", (loan_id,)).fetchone()
    if not loan or loan["status"] != "issued":
        conn.close()
        flash("That loan is not currently active.", "error")
        return redirect(request.referrer or url_for("dashboard.index"))

    conn.execute(
        """UPDATE loans
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
