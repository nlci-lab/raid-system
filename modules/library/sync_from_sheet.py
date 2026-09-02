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

MODULE_DIR = Path(__file__).parent
PROJECT_ROOT = MODULE_DIR.parent.parent
DB_DIR = PROJECT_ROOT / "db"
BOOKS_DB = DB_DIR / "books.db"

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

    # Validate and transform rows
    book_records = []
    skipped = []
    for i, row in enumerate(rows, start=2):  # Start at 2 to account for header
        try:
            # Strip whitespace from all values
            row_clean = {k.strip(): v.strip() for k, v in row.items()}

            # Validate required fields
            book_id_str = row_clean.get("_id", "").strip()
            book_title = row_clean.get("book_title", "").strip()

            if not book_id_str or not book_id_str.isdigit():
                skipped.append(f"Row {i}: missing or non-numeric _id")
                continue
            if not book_title:
                skipped.append(f"Row {i}: missing book_title")
                continue

            book_id = int(book_id_str)

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
                "id": book_id,
                "title": book_title,
                "ok": row_clean.get("_ok", ""),
                "scanned": row_clean.get("_scanned", ""),
                "genre": row_clean.get("genre", ""),
                "series": row_clean.get("series", ""),
                "publish_year": pub_year,
                "author": row_clean.get("author", ""),
                "volume": row_clean.get("volume", ""),
                "library_id": row_clean.get("library_id", ""),
                "l_id": row_clean.get("L_id", ""),
                "shelf_name": row_clean.get("_shelf_name", ""),
                "case_number": row_clean.get("_case_number", ""),
                "case_id": row_clean.get("_case_id", ""),
                "link_to_toc": row_clean.get("link_to_toc", ""),
            })
        except Exception as e:
            skipped.append(f"Row {i}: {str(e)}")
            continue

    # Rebuild books table (transaction: rollback on any failure)
    conn = sqlite3.connect(BOOKS_DB)
    try:
        # Drop old books table if it exists
        conn.execute("DROP TABLE IF EXISTS books")

        # Create new books table
        conn.execute("""
            CREATE TABLE books (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                ok TEXT,
                scanned TEXT,
                genre TEXT,
                series TEXT,
                publish_year INTEGER,
                author TEXT,
                volume TEXT,
                library_id TEXT,
                l_id TEXT,
                shelf_name TEXT,
                case_number TEXT,
                case_id TEXT,
                link_to_toc TEXT
            )
        """)

        # Insert all validated records
        for rec in book_records:
            conn.execute("""
                INSERT INTO books
                (id, title, ok, scanned, genre, series, publish_year, author, volume,
                 library_id, l_id, shelf_name, case_number, case_id, link_to_toc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rec["id"], rec["title"], rec["ok"], rec["scanned"],
                rec["genre"], rec["series"], rec["publish_year"],
                rec["author"], rec["volume"], rec["library_id"],
                rec["l_id"], rec["shelf_name"], rec["case_number"],
                rec["case_id"], rec["link_to_toc"]
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
