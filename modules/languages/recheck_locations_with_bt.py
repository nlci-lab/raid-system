"""Recheck/supplement `locations` with the NLCI BT database's State/Location columns.

Source file: achieved/NLCI-India BT Language Database - GS - BT DB.csv (709
rows). This is the same file `bt_info` was already built from, but the
build that populated bt_info dropped its State/Map/Location/
Estimated_Population columns entirely -- they were never captured anywhere
in languages.db. This script recovers them and adds them to `locations` as
a second, clearly-labelled source (source='nlci_bt').

IMPORTANT: this does NOT reuse bt_info.language_id. That column is stale --
it was resolved against some earlier numbering of the `languages` table
(e.g. speakers-sorted) and no longer lines up with the current one (e.g.
bt_info's Hindi row points at language_id=1, which is now "Adi"). Matching
is instead redone here directly against the live `languages` table by
ISO 639-3 code, so it's correct regardless of what state bt_info is in.

Existing Ethnologue-sourced rows in `locations` are untouched and retagged
source='ethnologue'; nothing is deleted or overwritten.

Run with:
    python modules/languages/recheck_locations_with_bt.py
"""

import csv
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent
CSV_PATH = BASE_DIR.parent.parent / "achieved" / "NLCI-India BT Language Database - GS - BT DB.csv"
DB_PATH = BASE_DIR.parent.parent / "db" / "languages.db"

# Postal-style state/UT codes used in the BT database's State column.
STATE_CODE_TO_NAME = {
    "AN": "Andaman and Nicobar Islands", "AP": "Andhra Pradesh", "AR": "Arunachal Pradesh",
    "AS": "Assam", "BH": "Bihar", "CH": "Chhattisgarh", "DD": "Daman and Diu",
    "GJ": "Gujarat", "GOA": "Goa", "HP": "Himachal Pradesh", "HR": "Haryana",
    "JH": "Jharkhand", "JK": "Jammu and Kashmir", "KA": "Karnataka", "KL": "Kerala",
    "LA": "Lakshadweep", "MH": "Maharashtra", "ML": "Meghalaya", "MN": "Manipur",
    "MP": "Madhya Pradesh", "MZ": "Mizoram", "NL": "Nagaland", "OD": "Odisha",
    "PB": "Punjab", "PY": "Puducherry", "RJ": "Rajasthan", "SI": "Sikkim",
    "SK": "Sikkim", "TG": "Telangana", "TN": "Tamil Nadu", "TR": "Tripura",
    "UK": "Uttarakhand", "UP": "Uttar Pradesh", "WB": "West Bengal",
    "INDIA": None, "NIL": None,
}


def clean_text(value):
    if value is None:
        return None
    value = value.strip()
    return value or None


def load_rows():
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        r = csv.reader(f)
        next(r)  # section-grouping row
        return list(csv.DictReader(f, fieldnames=next(r)))


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "ALTER TABLE locations ADD COLUMN source TEXT NOT NULL DEFAULT 'ethnologue'"
    ) if "source" not in [r[1] for r in conn.execute("PRAGMA table_info(locations)")] else None
    conn.execute(
        "ALTER TABLE locations ADD COLUMN state_code TEXT"
    ) if "state_code" not in [r[1] for r in conn.execute("PRAGMA table_info(locations)")] else None
    conn.execute("CREATE INDEX IF NOT EXISTS idx_locations_source ON locations(source)")

    iso_to_language_id = {
        iso3.strip().lower(): lang_id
        for lang_id, iso3 in conn.execute(
            "SELECT id, iso_639_3 FROM languages WHERE iso_639_3 IS NOT NULL"
        )
    }

    rows = load_rows()
    print(f"Loaded {len(rows)} rows from {CSV_PATH.name}")

    conn.execute("DELETE FROM locations WHERE source = 'nlci_bt'")

    inserted = 0
    skipped_unmatched = 0
    skipped_no_state_no_location = 0

    for row in rows:
        sl_no = clean_text(row.get("sl_no"))
        if not sl_no:
            continue
        iso_code = clean_text(row.get("ISO_Code"))
        language_id = iso_to_language_id.get((iso_code or "").lower())
        if not language_id:
            skipped_unmatched += 1
            continue

        state_code = clean_text(row.get("State"))
        location = clean_text(row.get("Location"))
        if not state_code and not location:
            skipped_no_state_no_location += 1
            continue

        state_name = STATE_CODE_TO_NAME.get((state_code or "").upper(), state_code)

        conn.execute(
            """
            INSERT INTO locations (
                language_id, iso_639_3, country_code, country_name,
                subdivision, location, latitude, longitude, source, state_code
            ) VALUES (?, ?, 'IN', 'India', ?, ?, NULL, NULL, 'nlci_bt', ?)
            """,
            (
                language_id,
                clean_text(row.get("ISO_Code")),
                state_name,
                location,
                state_code,
            ),
        )
        inserted += 1

    conn.execute(
        "UPDATE locations SET source = 'ethnologue' WHERE source IS NULL"
    )
    conn.commit()

    print(f"Inserted {inserted} nlci_bt location rows "
          f"({skipped_unmatched} skipped: no language match in bt_info; "
          f"{skipped_no_state_no_location} skipped: no State or Location value)")

    # Cross-check: languages where the two sources disagree on state/subdivision.
    mismatches = conn.execute(
        """
        SELECT l.name, e.subdivision AS ethnologue_subdivision,
               GROUP_CONCAT(DISTINCT b.subdivision) AS nlci_bt_states
        FROM languages l
        JOIN locations e ON e.language_id = l.id AND e.source = 'ethnologue'
        JOIN locations b ON b.language_id = l.id AND b.source = 'nlci_bt'
        WHERE e.subdivision IS NOT NULL
          AND b.subdivision IS NOT NULL
          AND e.subdivision != b.subdivision
        GROUP BY l.id
        HAVING NOT (',' || GROUP_CONCAT(DISTINCT b.subdivision) || ',' LIKE '%,' || e.subdivision || ',%')
        ORDER BY l.name
        """
    ).fetchall()
    print(f"\n{len(mismatches)} languages where Ethnologue's primary subdivision "
          f"isn't among the NLCI BT database's state(s):")
    for name, eth_sub, bt_states in mismatches:
        print(f"  {name}: ethnologue={eth_sub!r}  nlci_bt={bt_states!r}")

    conn.close()


if __name__ == "__main__":
    main()
