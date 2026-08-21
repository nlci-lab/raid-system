"""One-off conversion: split the RAID Library CSV into three SQLite databases
(books.db, loans.db, users.db, all under the top-level db/ folder)."""

import csv
import sqlite3
from pathlib import Path

MODULE_DIR = Path(__file__).parent
PROJECT_ROOT = MODULE_DIR.parent.parent
CSV_PATH = PROJECT_ROOT / "RAID Survey Library & Archieve - RAID Library.csv"
DB_DIR = PROJECT_ROOT / "db"
DB_DIR.mkdir(exist_ok=True)

BOOKS_DB = DB_DIR / "books.db"
USERS_DB = DB_DIR / "users.db"
LOANS_DB = DB_DIR / "loans.db"


def read_rows():
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    header_idx = next(i for i, row in enumerate(rows) if row[:2] == ["No.", "Book Title"])
    data = rows[header_idx + 1:]
    return [row for row in data if any(cell.strip() for cell in row)]


def build_books_db(data):
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
            remarks TEXT
        )
    """)
    conn.executemany(
        """INSERT INTO books
           (id, title, author, pub_year, genre, series, volume, bookcase, bookshelf, availability, remarks)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                int(row[0]),
                row[1].strip(),
                row[2].strip(),
                int(row[3]) if row[3].strip() else None,
                row[4].strip(),
                row[5].strip(),
                row[6].strip(),
                row[7].strip(),
                row[8].strip(),
                row[9].strip(),
                row[12].strip() if len(row) > 12 else "",
            )
            for row in data
        ],
    )
    conn.commit()
    conn.close()


def build_users_db(data):
    if USERS_DB.exists():
        USERS_DB.unlink()
    names = sorted({row[10].strip() for row in data if len(row) > 10 and row[10].strip()})
    conn = sqlite3.connect(USERS_DB)
    conn.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            library_code TEXT,
            email TEXT,
            role TEXT NOT NULL DEFAULT 'user'
        )
    """)
    conn.executemany("INSERT INTO users (name) VALUES (?)", [(name,) for name in names])
    conn.commit()
    conn.close()
    return {name: i + 1 for i, name in enumerate(names)}


def build_loans_db(data, user_ids):
    if LOANS_DB.exists():
        LOANS_DB.unlink()
    conn = sqlite3.connect(LOANS_DB)
    conn.execute("""
        CREATE TABLE loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            status TEXT
        )
    """)
    loans = [
        (int(row[0]), user_ids[row[10].strip()], row[9].strip())
        for row in data
        if len(row) > 10 and row[10].strip() and row[10].strip() in user_ids
    ]
    conn.executemany("INSERT INTO loans (book_id, user_id, status) VALUES (?, ?, ?)", loans)
    conn.commit()
    conn.close()


def main():
    data = read_rows()
    build_books_db(data)
    user_ids = build_users_db(data)
    build_loans_db(data, user_ids)
    print(f"books: {len(data)} rows -> {BOOKS_DB}")
    print(f"users: {len(user_ids)} rows -> {USERS_DB}")
    print(f"loans -> {LOANS_DB}")


if __name__ == "__main__":
    main()
