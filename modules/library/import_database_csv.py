"""One-off import: rebuild books.db from the new master catalog CSV
("RAID Survey Library & Archieve - database.csv"), replacing the old
Bookcase/Rack-based dataset. Also remaps the small number of active
loans.db book_id references so live loan history stays attached to the
correct title after the ID renumbering.
"""

import csv
import sqlite3
from pathlib import Path

MODULE_DIR = Path(__file__).parent
PROJECT_ROOT = MODULE_DIR.parent.parent
CSV_PATH = PROJECT_ROOT / "RAID Survey Library & Archieve - database.csv"
DB_DIR = PROJECT_ROOT / "db"
BOOKS_DB = DB_DIR / "books.db"
LOANS_DB = DB_DIR / "loans.db"

# old books.id -> new books.id, matched by title/author/volume against the
# CSV, needed because loans.db has live rows pointing at the old numbering.
LOAN_BOOK_ID_REMAP = {
    1: 303,    # A Bibliography of Dravidian Linguistics
    8: 326,    # A Descriptive Study of Dialect of Gade-Lohar
    216: 366,  # Indlish The Book for every English Speaking - Indian
    345: 64,   # People of India West Bengal (VL-XXXXIIIP2)
}


def read_rows():
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def build_books_db(rows):
    if BOOKS_DB.exists():
        BOOKS_DB.unlink()
    conn = sqlite3.connect(BOOKS_DB)
    conn.execute("""
        CREATE TABLE books (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            author TEXT,
            pub_year INTEGER,
            genre TEXT,
            series TEXT,
            volume TEXT,
            bookcase TEXT,
            bookshelf TEXT,
            availability TEXT,
            remarks TEXT,
            library_id TEXT,
            location_code TEXT,
            toc_link TEXT
        )
    """)

    taken_ids = {new_id for old_id, new_id in LOAN_BOOK_ID_REMAP.items() if old_id != 1}

    records = []
    for row in rows:
        book_id = int(row["_id"])
        pub_year_raw = row["publish_year"].strip()
        pub_year = int(pub_year_raw) if pub_year_raw and pub_year_raw != "0000" else None
        shelf = row["_shelf_name"].strip()
        case_number = row["_case_number"].strip()
        bookcase = f"Shelf {shelf}" if shelf else None
        bookshelf = f"Case {case_number}" if case_number else None
        availability = "Taken" if book_id in taken_ids else "At Stock"
        records.append((
            book_id,
            row["book_title"].strip(),
            row["author"].strip(),
            pub_year,
            row["genre"].strip(),
            row["series"].strip(),
            row["volume"].strip(),
            bookcase,
            bookshelf,
            availability,
            "",
            row["library_id"].strip(),
            row["L_id"].strip(),
            row["link_to_toc"].strip(),
        ))

    conn.executemany(
        """INSERT INTO books
           (id, title, author, pub_year, genre, series, volume, bookcase, bookshelf,
            availability, remarks, library_id, location_code, toc_link)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        records,
    )
    conn.commit()
    conn.close()
    return len(records)


def remap_loans():
    conn = sqlite3.connect(LOANS_DB)
    for old_id, new_id in LOAN_BOOK_ID_REMAP.items():
        conn.execute("UPDATE loans SET book_id = ? WHERE book_id = ?", (new_id, old_id))
    conn.commit()
    conn.close()


def main():
    rows = read_rows()
    count = build_books_db(rows)
    remap_loans()
    print(f"books: {count} rows -> {BOOKS_DB}")
    print(f"loans.db book_id remapped: {LOAN_BOOK_ID_REMAP}")


if __name__ == "__main__":
    main()
