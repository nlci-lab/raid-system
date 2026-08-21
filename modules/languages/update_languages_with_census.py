"""Update the `languages` table's speaker counts/source using Census 2011 Table C-16.

For each row in `languages` (the Ethnologue-derived table), try to find a
matching mother tongue in `census2011_mother_tongue` (area_name = 'INDIA').
Census of India is the more authoritative source for India-specific speaker
counts, so where a confident name match is found, the language's
speakers_approx / census_year / source fields are overwritten with the
Census 2011 figures. Languages with no confident match keep their existing
Ethnologue-derived data untouched.

Matching is name-based only (exact, after normalization) -- no fuzzy
matching -- to avoid silently merging two different languages. Run this
after build_db_ethnologue.py and build_db_census2011.py have both populated
their tables.

Run with:
    python modules/languages/update_languages_with_census.py
"""

import re
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "db" / "languages.db"
CENSUS_SOURCE = "Census of India 2011, Table C-16 (Registrar General & Census Commissioner, India)"

GROUP_NAME_RE = re.compile(r"^\d+\s+(.*)$")
BRACKET_RE = re.compile(r"\[[^\]]*\]")


def normalize(name):
    if not name:
        return None
    name = BRACKET_RE.sub("", name)
    match = GROUP_NAME_RE.match(name.strip())
    if match:
        name = match.group(1)
    name = name.strip().strip(".")
    name = re.sub(r"\s+", " ", name)
    return name.lower()


def candidate_keys(name):
    """All normalized strings under which a census/Ethnologue name could match."""
    base = normalize(name)
    if not base:
        return []
    keys = {base}
    for part in re.split(r"[/,]", base):
        part = part.strip()
        if part:
            keys.add(part)
    return list(keys)


def build_census_lookup(conn):
    """Map normalized name -> (code, total_p, raw_name).

    Census C-16 lists a "group" row for each of the 122 mother-tongue
    groups (code a multiple of 1000, e.g. 6000 "6 HINDI") followed by that
    group's named constituent mother tongues (e.g. 6240 "Hindi", 6102
    "Bhojpuri", ...). Group totals are the conventionally-cited "speakers of
    X" figures for big umbrella languages (this is what Ethnologue/press
    figures for Hindi ~528M, Bengali ~97M etc. actually refer to), so group
    rows take priority; a specific-code row only fills in a name that no
    group row already claimed. If two *specific* rows from different groups
    collide on the same normalized name with different totals, the key is
    dropped as ambiguous.
    """
    rows = conn.execute(
        """
        SELECT mother_tongue_code, mother_tongue_name, total_p
        FROM census2011_mother_tongue
        WHERE area_name = 'INDIA' AND total_p IS NOT NULL AND total_p > 0
        """
    ).fetchall()

    group_rows = [r for r in rows if r[0] is not None and r[0] % 1000 == 0]
    specific_rows = [r for r in rows if r[0] is not None and r[0] % 1000 != 0 and r[0] % 1000 != 999]

    lookup = {}
    for code, name, total_p in group_rows:
        for key in candidate_keys(name):
            lookup[key] = (code, total_p, name)

    specific_candidates = {}
    dupes = set()
    for code, name, total_p in specific_rows:
        for key in candidate_keys(name):
            if key in lookup:
                continue  # already claimed by a group row
            if key in specific_candidates and specific_candidates[key][1] != total_p:
                dupes.add(key)
            specific_candidates.setdefault(key, (code, total_p, name))
    for key in dupes:
        specific_candidates.pop(key, None)

    lookup.update(specific_candidates)
    return lookup


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    lookup = build_census_lookup(conn)
    print(f"Built census name lookup with {len(lookup)} distinct keys.")

    languages = conn.execute("SELECT id, name, speakers_approx, source FROM languages").fetchall()

    matched, unmatched = [], []
    for lang in languages:
        found = None
        for key in candidate_keys(lang["name"]):
            if key in lookup:
                found = lookup[key]
                break
        if found:
            code, total_p, census_name = found
            matched.append((lang, census_name, total_p))
        else:
            unmatched.append(lang)

    print(f"Matched {len(matched)} / {len(languages)} languages to a Census 2011 mother tongue.")

    conn.executemany(
        """
        UPDATE languages
        SET speakers_approx = ?, census_year = 2011, source = ?
        WHERE id = ?
        """,
        [(total_p, CENSUS_SOURCE, lang["id"]) for lang, _, total_p in matched],
    )
    conn.commit()

    print("\nSample of updates (Ethnologue name -> Census mother tongue : new speakers_approx):")
    for lang, census_name, total_p in sorted(matched, key=lambda t: -t[2])[:20]:
        print(f"  {lang['name']!r:35s} -> {census_name!r:30s} : {total_p:,}")

    print(f"\n{len(unmatched)} languages left on Ethnologue-derived figures (no confident Census match).")

    conn.close()


if __name__ == "__main__":
    main()
