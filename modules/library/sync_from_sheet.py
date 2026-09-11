"""Sync books from a Google Sheets CSV export into the books table.

This module replaces build_db.py and import_database_csv.py for ongoing
catalog syncs. Google Sheets must be published as CSV ("Publish to web"),
exported from the "database" tab.
"""

import csv
import sqlite3
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from modules.db import LIBRARY_DB

# Google Sheets "Publish to web" CSV export URL for the "database" tab
# (File > Share > Publish to web > select the "database" sheet > CSV).
DEFAULT_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ77xps4Ww4PvnNXBNyZLRgfXPJpcigxsF6zV99J-hI9vAmVXHWaCjZJ0nEKtAz9ymUipKqv51HoH45"
    "/pub?gid=1154456721&single=true&output=csv"
)


def sync_books_from_sheet(csv_url):
    """Fetch CSV from csv_url and rebuild the books table.

    Returns a dict: {"imported": N, "skipped": [...], "error": None}
    If total failure (unreachable URL, unparseable CSV), raises an exception.
    Skipped rows are collected but don't halt the sync.
    """
    # Fetch CSV
    try:
        with urlopen(csv_url, timeout=15) as response:
            csv_text = response.read().decode("utf-8-sig")
    except URLError as e:
        raise Exception(f"Failed to fetch CSV from URL: {e}")
    except Exception as e:
        raise Exception(f"Network error fetching CSV: {e}")

    # Parse CSV
    try:
        lines = csv_text.splitlines()
        reader = csv.DictReader(lines)
        if reader.fieldnames is None:
            raise Exception("CSV is empty or has no header row")
        rows = list(reader)
    except Exception as e:
        raise Exception(f"Failed to parse CSV: {e}")

    # Strip fieldnames and prepare for validation
    fieldnames = {name.strip(): name for name in reader.fieldnames}

    # Validate and transform rows. Columns whose sheet header starts with "_"
    # (_id, _ok, _scanned, _shelf_name, _case_number, _case_id) are skipped
    # entirely -- not read, not stored. Book identity is therefore no longer
    # tied to a stable sheet-provided id; each sync rebuilds the table from
    # scratch and SQLite assigns fresh autoincrement ids in CSV row order.
    book_records = []
    skipped = []
    for i, row in enumerate(rows, start=2):  # Start at 2 to account for header
        try:
            # Strip whitespace from all values
            row_clean = {k.strip(): v.strip() for k, v in row.items()}

            # Validate required fields
            book_title = row_clean.get("book_title", "").strip()

            if not book_title:
                skipped.append(f"Row {i}: missing book_title")
                continue

            # Parse publish_year carefully
            pub_year_str = row_clean.get("publish_year", "").strip()
            if pub_year_str and pub_year_str != "0000":
                try:
                    pub_year = int(pub_year_str)
                except ValueError:
                    pub_year = None
            else:
                pub_year = None

            book_records.append({
                "title": book_title,
                "genre": row_clean.get("genre", ""),
                "series": row_clean.get("series", ""),
                "publish_year": pub_year,
                "author": row_clean.get("author", ""),
                "volume": row_clean.get("volume", ""),
                "library_id": row_clean.get("library_id", ""),
                "l_id": row_clean.get("L_id", ""),
                "link_to_toc": row_clean.get("link_to_toc", ""),
            })
        except Exception as e:
            skipped.append(f"Row {i}: {str(e)}")
            continue

    # Rebuild books table (transaction: rollback on any failure). library.db
    # also holds the "loans" table (owned by modules/library/__init__.py) --
    # only "books" is dropped/recreated here, "loans" is untouched.
    conn = sqlite3.connect(LIBRARY_DB)
    try:
        # Drop old books table if it exists
        conn.execute("DROP TABLE IF EXISTS books")

        # Create new books table (id is autoincrement -- see note above about
        # book identity no longer being sheet-stable across resyncs)
        conn.execute("""
            CREATE TABLE books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                genre TEXT,
                series TEXT,
                publish_year INTEGER,
                author TEXT,
                volume TEXT,
                library_id TEXT,
                l_id TEXT,
                link_to_toc TEXT
            )
        """)

        # Insert all validated records
        for rec in book_records:
            conn.execute("""
                INSERT INTO books
                (title, genre, series, publish_year, author, volume, library_id, l_id, link_to_toc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rec["title"], rec["genre"], rec["series"], rec["publish_year"],
                rec["author"], rec["volume"], rec["library_id"], rec["l_id"], rec["link_to_toc"]
            ))

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise Exception(f"Database error during sync: {e}")
    finally:
        conn.close()

    return {
        "imported": len(book_records),
        "skipped": skipped,
        "error": None,
    }
