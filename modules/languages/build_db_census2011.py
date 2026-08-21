"""Load Census of India 2011 Table C-16 (Population by Mother Tongue) into languages.db.

Source file: modules/languages/database/census2011_mother_tongue.csv, an
export of Table C-16 -- All-India and state/UT-wise population by mother
tongue, broken down by sex and rural/urban residence. The table lists, for
INDIA and each of the 35 states/UTs (2011 boundaries), 22 major "scheduled"
mother-tongue groups plus 100 further rationalised mother-tongue groups
(codes 1000-124000 in steps of 1000), each expanded into its named
constituent mother tongues (e.g. group 1000 "1 ASSAMESE" contains 1002
"Assamese", 1999 "1 Others") reported by the Registrar General.

This is loaded as its own table (not merged into `languages`) because it is
raw statistical source data at a different grain -- state x mother-tongue
counts -- rather than one row per language.

Run with:
    python modules/languages/build_db_census2011.py
"""

import csv
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent
CSV_PATH = BASE_DIR / "database" / "census2011_mother_tongue.csv"
DB_DIR = BASE_DIR.parent.parent / "db"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "languages.db"

COLUMNS = [
    "table_code", "state_code", "district_code", "subdistrict_code",
    "area_name", "mother_tongue_code", "mother_tongue_name",
    "total_p", "total_m", "total_f",
    "rural_p", "rural_m", "rural_f",
    "urban_p", "urban_m", "urban_f",
]


def parse_int(value):
    value = (value or "").strip()
    if not value:
        return None
    value = value.replace(",", "")
    try:
        return int(float(value))
    except ValueError:
        return None


def load_rows():
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        lines = f.readlines()
    # First 6 lines are the multi-row header block; data starts at line 7 (index 6).
    reader = csv.reader(lines[6:])
    rows = []
    for parts in reader:
        if not parts or not parts[0].strip():
            continue
        parts = (parts + [""] * len(COLUMNS))[: len(COLUMNS)]
        table_code, state_code, district_code, subdistrict_code, area_name, \
            mt_code, mt_name, tp, tm, tf, rp, rm, rf, up, um, uf = parts
        rows.append((
            table_code.strip(),
            parse_int(state_code),
            parse_int(district_code),
            parse_int(subdistrict_code),
            area_name.strip(),
            parse_int(mt_code),
            mt_name.strip(),
            parse_int(tp), parse_int(tm), parse_int(tf),
            parse_int(rp), parse_int(rm), parse_int(rf),
            parse_int(up), parse_int(um), parse_int(uf),
        ))
    return rows


def main():
    rows = load_rows()
    print(f"Loaded {len(rows)} rows from {CSV_PATH.name}")

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS census2011_mother_tongue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_code TEXT,
            state_code INTEGER,
            district_code INTEGER,
            subdistrict_code INTEGER,
            area_name TEXT NOT NULL,
            mother_tongue_code INTEGER,
            mother_tongue_name TEXT NOT NULL,
            total_p INTEGER,
            total_m INTEGER,
            total_f INTEGER,
            rural_p INTEGER,
            rural_m INTEGER,
            rural_f INTEGER,
            urban_p INTEGER,
            urban_m INTEGER,
            urban_f INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_c2011_area ON census2011_mother_tongue(area_name);
        CREATE INDEX IF NOT EXISTS idx_c2011_mt_code ON census2011_mother_tongue(mother_tongue_code);
        CREATE INDEX IF NOT EXISTS idx_c2011_mt_name ON census2011_mother_tongue(mother_tongue_name);
        CREATE INDEX IF NOT EXISTS idx_c2011_state ON census2011_mother_tongue(state_code);
        """
    )

    conn.execute("DELETE FROM census2011_mother_tongue")
    conn.execute("DELETE FROM sqlite_sequence WHERE name = 'census2011_mother_tongue'")

    conn.executemany(
        f"""
        INSERT INTO census2011_mother_tongue ({", ".join(COLUMNS)})
        VALUES ({", ".join("?" for _ in COLUMNS)})
        """,
        rows,
    )
    conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM census2011_mother_tongue").fetchone()[0]
    areas = conn.execute("SELECT COUNT(DISTINCT area_name) FROM census2011_mother_tongue").fetchone()[0]
    conn.close()
    print(f"Wrote {count} rows across {areas} areas (INDIA + states/UTs) to {DB_PATH}")


if __name__ == "__main__":
    main()
