from pathlib import Path

# modules/db.py -> modules/ -> raid-system/ (app root) -> raid_system/ (container,
# sibling of the app folder) / "db". Computed relative to this file so it keeps
# working if the app folder itself gets renamed/moved again, as long as db/
# stays a sibling of whatever the app folder is called.
DB_DIR = Path(__file__).parent.parent.parent / "db"

USERS_DB = DB_DIR / "users.db"
LIBRARY_DB = DB_DIR / "library.db"  # holds both the "books" catalog table and the "loans" log table
ATTENDANCE_DB = DB_DIR / "attendance.db"
CHAT_DB = DB_DIR / "chat.db"
BLOG_DB = DB_DIR / "blog.db"
ILDB_DB = DB_DIR / "ildb.db"


def all_databases():
    """Every .db file in DB_DIR, keyed by stem name (e.g. "users"), sorted
    alphabetically. Used by the /internal-database admin viewer to browse
    whichever databases exist without needing a hardcoded list."""
    return {p.stem: p for p in sorted(DB_DIR.glob("*.db"))}
