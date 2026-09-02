"""One-off migration: users.role (TEXT) -> users.level (REAL).

Run once per database copy (local already done — this is now only needed
for production). Safe to re-run: it no-ops if `level` already exists.
`level` is declared REAL, not INTEGER — there's no int level, only floats
(see modules/levels.py) — so every value here is a float literal too.

    python modules/migrate_to_levels.py [path/to/users.db]
"""

import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = Path(__file__).parent.parent / "db" / "users.db"

ROLE_TO_LEVEL = {
    "admin": 1.0,
    "data_manager": 2.0,
}
NLIFE_USER_LEVEL = 4.0
DEFAULT_LEVEL = 5.0  # non-nlife.in `user` rows keep this (schema default too)

DEV_EMAILS = {"martin_mathew@nlife.in"}


def migrate(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
        if "level" in existing_cols:
            print(f"{db_path}: 'level' column already present, skipping.")
            return

        conn.execute(f"ALTER TABLE users ADD COLUMN level REAL NOT NULL DEFAULT {DEFAULT_LEVEL}")

        for role, level in ROLE_TO_LEVEL.items():
            conn.execute("UPDATE users SET level = ? WHERE role = ?", (level, role))

        conn.execute(
            "UPDATE users SET level = ? WHERE role = 'user' AND lower(email) LIKE '%@nlife.in'",
            (NLIFE_USER_LEVEL,),
        )

        for email in DEV_EMAILS:
            cur = conn.execute("UPDATE users SET level = 0.0 WHERE lower(email) = ?", (email.lower(),))
            if cur.rowcount:
                print(f"{db_path}: set {email} to level 0.0 (dev)")

        conn.execute("ALTER TABLE users DROP COLUMN role")
        conn.commit()

        print(f"{db_path}: migrated.")
        for row in conn.execute("SELECT id, name, email, level FROM users ORDER BY id"):
            print(f"  #{row['id']:>3} level={row['level']} {row['email'] or '(no email)'} — {row['name']}")
    finally:
        conn.close()


if __name__ == "__main__":
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    migrate(db_path)
