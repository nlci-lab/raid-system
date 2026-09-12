import subprocess
import sqlite3
from datetime import datetime
from functools import wraps

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, session, url_for

from apps.access import SCHEMA as ACCESS_REQUESTS_SCHEMA
from apps.audit import log_action, recent_entries
from apps.config import PROJECT_ROOT
from apps.db import LIBRARY_DB, USERS_DB
from apps.ildb import health_snapshot as ildb_health_snapshot
from apps.library import _ensure_books_table, _ensure_loans_table
from apps.server_status import get_status, read_error_log
from apps.levels import (
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
    """Connect to users.db and attach library.db (books + loans tables) so
    they can be joined against users.

    loans is the unified request+loan table owned by apps/library (see
    apps/library/__init__.py's LOANS_SCHEMA / _ensure_loans_table). This
    module only reads it — it no longer creates its own separate requests
    table or migrates loan columns; that's the library module's job.
    """
    conn = sqlite3.connect(USERS_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("ATTACH DATABASE ? AS library", (str(LIBRARY_DB),))
    conn.executescript(ACCESS_REQUESTS_SCHEMA)
    _ensure_books_table(conn, prefix="library.")  # idempotent — safe whichever route hits it first
    _ensure_loans_table(conn, prefix="library.")  # idempotent — safe whichever route hits it first
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
    # library.loans is now the single unified table for the whole request/loan
    # lifecycle (see apps/library). "loans" here = actually issued history
    # (issued or returned); "requests" = still awaiting an admin decision.
    # Old columns are aliased back to their old names so the templates,
    # which were never touched, keep working unmodified.
    loans = conn.execute("""
        SELECT library.loans.id, library.books.title, users.name AS user_name, library.loans.status,
               library.loans.requested_at, library.loans.approved_by AS issued_by, library.loans.taken_at AS issued_at,
               library.loans.returned_at, library.loans.returned_to AS returned_by
        FROM library.loans
        JOIN library.books ON library.books.id = library.loans.book_id
        JOIN users ON users.id = library.loans.requested_by
        WHERE library.loans.status IN ('issued', 'returned')
        ORDER BY library.loans.id
    """).fetchall()
    requests = conn.execute("""
        SELECT library.loans.id, library.loans.status, library.loans.requested_at,
               library.books.title AS book_title, users.name AS user_name
        FROM library.loans
        JOIN library.books ON library.books.id = library.loans.book_id
        JOIN users ON users.id = library.loans.requested_by
        WHERE library.loans.status = 'pending'
        ORDER BY library.loans.requested_at DESC, library.loans.id DESC
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
    """The dashboard hub -- a tile grid linking to all 13 dashboards in the
    app as separate tiles (no consolidation), same visual style as the home
    page's Quick Access grid. A sub-leveled user (director, manager,
    developer, ...) still auto-lands on their own labeled variant of the
    admin dashboard first (unchanged, see SUB_LEVEL_DASHBOARD_ENDPOINTS)
    since that's just org-labeling of an identity, not a preference about
    browsing; anyone landing on the hub itself (plain dev/admin, or a
    sub-leveled user who clicks back to Dashboard from elsewhere) sees all
    13 dashboards -- their own admin variant included -- as individual
    tiles, since that's the whole point of the hub."""
    own_dashboard = SUB_LEVEL_DASHBOARD_ENDPOINTS.get(current_level())
    if own_dashboard:
        return redirect(url_for(own_dashboard))
    return render_template("dashboard_hub.html")


@dashboard.route("/dashboard/admin")
@admin_required
def admin_dashboard():
    """The actual admin dashboard content (Access Requests, Users, Server
    Status, Terminal, File Explorer) -- what used to be the only thing at
    plain /dashboard. Still reachable directly here; /dashboard itself is
    now the hub above. Book Requests/Loans were deliberately removed --
    that's the RAID Librarian Dash's job (library.admin_panel), not
    system admin's; raid-system-admin owns access/users/server ops, not
    library operations.

    Server Status + the error log are admin-page-specific (not part of
    _dashboard_context(), which every sub-level dashboard shares) -- no
    other role needs process/resource health, and it's only meaningful
    where the actual admin actions (user/access management) already live."""
    return render_template(
        "dashboard_index.html",
        server_status=get_status(),
        error_log=read_error_log(),
        **_dashboard_context(),
    )


@dashboard.route("/dashboard/director")
@admin_required
def director_dashboard():
    """NLCI Director's view -- deliberately mission-output only (ILDB's
    Indian-language-situation rollup), not RAID's internal ops. Attendance,
    library throughput, audit log, and RAID Bot usage were considered and
    dropped (2026-09-12): those are RAID-internal, not director-relevant.
    A survey-stage tracker and a G:\\ Drive report-archive metric were also
    considered as future mission-output candidates -- neither exists as
    queryable data anywhere yet, so neither is built. ILDB alone is the
    finished scope for now."""
    return render_template("dashboard_director.html", ildb=ildb_health_snapshot())


@dashboard.route("/dashboard/senior-manager")
@admin_required
def senior_manager_dashboard():
    """Same content as Director Dashboard (ILDB language-situation rollup) --
    copied over 2026-09-12 rather than sharing director_dashboard()'s route
    directly, so it can diverge later without touching Director's."""
    return render_template("dashboard_senior_manager.html", ildb=ildb_health_snapshot())



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


@dashboard.route("/dashboard/admin/terminal", methods=["POST"])
@admin_required
def run_terminal_command():
    """Runs an arbitrary shell command on the server the app is running on
    and returns its output.

    FULL, UNRESTRICTED ACCESS BY DELIBERATE, EXPLICIT INSTRUCTION
    (2026-09-12) -- gated only by the same admin_required as the rest of
    /dashboard/admin (tier <= ADMIN_LEVEL, i.e. dev AND admin sub-levels:
    director/senior-manager/manager too). Martin's own words: "give full
    permission terminal, later we will fix permission to this page for
    0.0" -- the intent is to restrict the whole /dashboard/admin page to
    real lvl-0.0 only in a follow-up change, not yet done. Until that
    lands, anyone who can reach /dashboard/admin has a real shell on
    whichever machine is running this Flask process (raid-server in
    production). Every command is written to the audit log regardless of
    success/failure, so there's at least a record while this stays this
    open.
    """
    command = (request.get_json(silent=True) or {}).get("command", "").strip()
    if not command:
        return jsonify(error="No command given."), 400

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        stdout, stderr, returncode = result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        stdout, stderr, returncode = "", "Command timed out after 30s.", -1
    except Exception as e:
        stdout, stderr, returncode = "", f"Failed to run command: {e}", -1

    log_action("dashboard", "run_terminal_command", f"ran `{command}` (exit {returncode})")
    return jsonify(stdout=stdout, stderr=stderr, returncode=returncode)


def _safe_resolve(rel_path):
    """Resolve a browser-supplied relative path against PROJECT_ROOT,
    refusing anything that escapes it (../.. tricks, absolute paths).
    Returns None if the resolved target isn't actually under PROJECT_ROOT.

    This boundary is a UX/sanity choice, not a real security boundary --
    the Terminal above already grants an unrestricted shell in the same
    admin-tier page, so anyone who could escape this would just use that
    instead. It exists so File Explorer behaves like a normal file browser
    (rooted somewhere sensible) rather than exposing the whole filesystem
    by default."""
    base = PROJECT_ROOT.resolve()
    try:
        target = (base / (rel_path or "")).resolve()
    except (OSError, ValueError):
        return None
    if target != base and base not in target.parents:
        return None
    return target


@dashboard.route("/dashboard/admin/files")
@admin_required
def browse_files():
    """Directory listing under PROJECT_ROOT, JSON for the File Explorer's
    own JS (static/js/file_explorer.js) to render -- not a full page."""
    target = _safe_resolve(request.args.get("path", ""))
    if target is None or not target.exists():
        return jsonify(error="That path doesn't exist."), 400
    if target.is_file():
        return jsonify(error="That's a file, not a directory."), 400

    entries = []
    try:
        children = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except OSError as e:
        return jsonify(error=f"Couldn't list directory: {e}"), 400
    for p in children:
        try:
            stat = p.stat()
        except OSError:
            continue
        entries.append({
            "name": p.name,
            "is_dir": p.is_dir(),
            "size": None if p.is_dir() else stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
        })

    base = PROJECT_ROOT.resolve()
    rel = target.relative_to(base)
    rel_str = "" if str(rel) == "." else str(rel).replace("\\", "/")
    parent = "" if rel_str == "" else "/".join(rel_str.split("/")[:-1])

    return jsonify(
        path=rel_str,
        parent=None if rel_str == "" else parent,
        entries=entries,
    )


@dashboard.route("/dashboard/admin/files/read")
@admin_required
def read_file():
    """Read-only text preview of one file under PROJECT_ROOT. Anything
    beyond viewing (editing, deleting, moving) is what the Terminal is
    for -- no point duplicating that here."""
    target = _safe_resolve(request.args.get("path", ""))
    if target is None or not target.is_file():
        return jsonify(error="That's not a file."), 400
    try:
        if target.stat().st_size > 300_000:
            return jsonify(error="File is over 300KB — too large to preview here. Use the Terminal instead.")
        content = target.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return jsonify(error=f"Couldn't read file: {e}"), 400
    return jsonify(content=content)
