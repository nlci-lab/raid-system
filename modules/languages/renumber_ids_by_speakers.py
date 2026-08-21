"""Renumber `languages.id` so id=1 is the most-spoken language, id=2 next, etc.

Rows with a known speakers_approx are ordered descending by that figure;
rows with no known figure (NULL) sort after all of them, alphabetically by
name, so they still get a stable id.

SQLite won't let you freely renumber an INTEGER PRIMARY KEY in place without
risking collisions, so this rebuilds the table: create languages_new with
the same schema, copy rows across in the desired order (id reassigned by
insertion order via AUTOINCREMENT), drop the old table, rename the new one
back to `languages`, and recreate its indexes.

Run with:
    python modules/languages/renumber_ids_by_speakers.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "db" / "languages.db"

SCHEMA = """
CREATE TABLE languages_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    native_name TEXT,
    iso_639_1 TEXT,
    iso_639_3 TEXT,
    family TEXT NOT NULL,
    branch TEXT,
    script TEXT,
    word_order TEXT,
    classification TEXT NOT NULL,
    is_classical INTEGER NOT NULL DEFAULT 0,
    classical_since INTEGER,
    speakers_approx INTEGER,
    census_year INTEGER,
    source TEXT,
    primary_regions TEXT,
    status TEXT,
    endangerment TEXT,
    notes TEXT
);
"""

COLUMNS = [
    "name", "native_name", "iso_639_1", "iso_639_3", "family", "branch",
    "script", "word_order", "classification", "is_classical",
    "classical_since", "speakers_approx", "census_year", "source",
    "primary_regions", "status", "endangerment", "notes",
]


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DROP TABLE IF EXISTS languages_new")
    conn.executescript(SCHEMA)

    rows = conn.execute(
        f"""
        SELECT {", ".join(COLUMNS)}
        FROM languages
        ORDER BY
            CASE WHEN speakers_approx IS NULL THEN 1 ELSE 0 END,
            speakers_approx DESC,
            name ASC
        """
    ).fetchall()

    conn.executemany(
        f"INSERT INTO languages_new ({', '.join(COLUMNS)}) VALUES ({', '.join('?' for _ in COLUMNS)})",
        rows,
    )

    conn.executescript(
        """
        DROP TABLE languages;
        ALTER TABLE languages_new RENAME TO languages;
        CREATE INDEX idx_languages_family ON languages(family);
        CREATE INDEX idx_languages_name ON languages(name);
        """
    )
    conn.commit()

    print(f"Renumbered {len(rows)} languages by speakers_approx (id 1 = most spoken).")
    for row in conn.execute(
        "SELECT id, name, speakers_approx FROM languages ORDER BY id LIMIT 10"
    ):
        print(f"  {row[0]:>4}  {row[1]:35s} {row[2]:,}" if row[2] else f"  {row[0]:>4}  {row[1]}")
    print("  ...")
    for row in conn.execute(
        "SELECT id, name, speakers_approx FROM languages ORDER BY id DESC LIMIT 5"
    ):
        print(f"  {row[0]:>4}  {row[1]}")

    conn.close()


if __name__ == "__main__":
    main()
