from pathlib import Path

DB_DIR = Path(__file__).parent.parent / "db"

USERS_DB = DB_DIR / "users.db"
BOOKS_DB = DB_DIR / "books.db"
LOANS_DB = DB_DIR / "loans.db"
ATTENDANCE_DB = DB_DIR / "attendance.db"
CHAT_DB = DB_DIR / "chat.db"
BLOG_DB = DB_DIR / "blog.db"
ILDB_DB = DB_DIR / "ildb.db"


def all_databases():
    """Every .db file in DB_DIR, keyed by stem name (e.g. "users"), sorted
    alphabetically. Used by the /internal-database admin viewer to browse
    whichever databases exist without needing a hardcoded list."""
    return {p.stem: p for p in sorted(DB_DIR.glob("*.db"))}
