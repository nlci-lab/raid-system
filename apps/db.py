import sqlite3
from pathlib import Path

# apps/db.py -> apps/ -> raid-system/ (app root) -> raid_system/ (container,
# sibling of the app folder) / "db". Computed relative to this file so it keeps
# working if the app folder itself gets renamed/moved again, as long as db/
# stays a sibling of whatever the app folder is called.
DB_DIR = Path(__file__).parent.parent.parent / "db"

# First-run bootstrap: on a genuinely fresh checkout (only core/ exists, no
# sibling db/ folder yet — e.g. a brand-new dev clone, not raid-server, which
# already has a real populated db/ that deploys never touch — see
# migrations/README.md), sqlite3.connect() below would otherwise fail with
# "unable to open database file" because the parent directory doesn't exist.
# Same idea as apps/blog's BLOGS_DIR.mkdir(exist_ok=True), just for db/.
# parents=True too, defensively, in case DB_DIR's own parent (the
# raid_system/ container) is somehow also missing.
DB_DIR.mkdir(parents=True, exist_ok=True)

USERS_DB = DB_DIR / "users.db"
LIBRARY_DB = DB_DIR / "library.db"  # holds both the "books" catalog table and the "loans" log table
ATTENDANCE_DB = DB_DIR / "attendance.db"
BLOG_DB = DB_DIR / "blog.db"
CHAT_DB = DB_DIR / "chat.db"
ILDB_DB = DB_DIR / "ildb.db"

# The base `users` table itself. Every other module (auth, library,
# dashboard, blog, access, ai_chat, attendance, audit) reads it,
# ATTACHes it, or ALTERs it onto an assumed-existing table — but none of
# them ever CREATE it: apps/auth._ensure_user_detail_columns() only adds
# extra columns (password_hash, login_count, ...) onto a `users` table it
# assumes is already there, and apps/access, apps/audit each create their
# OWN sibling tables (access_requests, audit_log) in users.db, not `users`
# itself. On a real fresh users.db (no sibling db/ folder at all, or an
# empty file created by sqlite3.connect() with no schema yet) every one of
# those call sites previously failed with
# "sqlite3.OperationalError: no such table: users" on first real request.
# Created here, at import time, since apps.db is the first/most central
# module every other app.* module imports — this always runs before any
# query against `users` anywhere else. `level` defaults to 5.0 (external)
# to match apps/migrate_to_levels.py's DEFAULT_LEVEL / the non-nlife.in
# fallback in apps/auth._register_user; everything else auth adds via
# ALTER TABLE the first time a user logs in or registers.
_USERS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        level REAL NOT NULL DEFAULT 5.0
    );
"""


def _ensure_users_table():
    conn = sqlite3.connect(USERS_DB)
    try:
        conn.executescript(_USERS_SCHEMA)
        conn.commit()
    finally:
        conn.close()


_ensure_users_table()


def all_databases():
    """Every .db file in DB_DIR, keyed by stem name (e.g. "users"), sorted
    alphabetically. Used by the /internal-database admin viewer to browse
    whichever databases exist without needing a hardcoded list."""
    return {p.stem: p for p in sorted(DB_DIR.glob("*.db"))}
