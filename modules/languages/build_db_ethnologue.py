"""Rebuild languages.db from the full Ethnologue (SIL) India-country-data export.

Source file: modules/languages/database/ethnologue_india.csv (475 languages,
Ethnologue-style export with EGIDS vitality, population, script, typology,
classification and other fields). This replaces the smaller hand-curated
100-ish language set previously built by build_db.py with the complete
Ethnologue "languages of India" listing, while keeping the existing schema
(languages / language_families / writing_systems) so the Flask blueprint and
template in modules/languages/ keep working unchanged.

Run with:
    python modules/languages/build_db_ethnologue.py
"""

import csv
import re
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent
CSV_PATH = BASE_DIR / "database" / "ethnologue_india.csv"
DB_DIR = BASE_DIR.parent.parent / "db"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "languages.db"

SOURCE = "Ethnologue (SIL International), India country data export"

# The 22 languages of the Eighth Schedule of the Indian Constitution, by
# ISO 639-3 code, plus each language's classical-status grant year (if any).
SCHEDULED_EIGHTH = {
    "asm", "ben", "brx", "dgo", "guj", "hin", "kan", "kas", "knn", "mai",
    "mal", "mni", "mar", "npi", "ory", "pan", "san", "sat", "snd", "tam",
    "tel", "urd",
}
CLASSICAL_SINCE = {
    "tam": 2004,
    "san": 2005,
    "tel": 2008,
    "kan": 2008,
    "mal": 2013,
    "ory": 2014,
    "pli": 2024,   # Pali
    "mar": 2024,
    "asm": 2024,
    "ben": 2024,
}

# A handful of well-known ISO 639-1 codes for languages that appear in the
# Ethnologue export under their ISO 639-3 code. Most minority/tribal
# languages have no 639-1 code, so this stays a short manual list.
ISO_639_1 = {
    "hin": "hi", "ben": "bn", "mar": "mr", "tel": "te", "tam": "ta",
    "guj": "gu", "urd": "ur", "kan": "kn", "ory": "or", "mal": "ml",
    "pan": "pa", "asm": "as", "san": "sa", "npi": "ne", "snd": "sd",
    "kas": "ks", "eng": "en", "fra": "fr", "por": "pt", "jpn": "ja",
    "kor": "ko", "cmn": "zh", "arb": "ar", "uig": "ug", "mya": "my",
    "div": "dv", "sin": "si", "bod": "bo", "dzo": "dz",
}

FAMILY_DESCRIPTIONS = {
    "Afro-Asiatic": "A family centred on the Middle East and North/Horn of Africa; represented in India only by Arabic (Mesopotamian and Standard) communities, not indigenous to India.",
    "Indo-European": "Represented in India chiefly by the Indo-Aryan branch, descended from Old Indo-Aryan (Vedic/Classical Sanskrit); also includes Dardic languages such as Kashmiri and Shina. The largest language family in India by speaker count.",
    "Dravidian": "A family largely confined to South Asia, with four major branches (South, South-Central, Central, North Dravidian). Includes the classical literary languages Tamil, Telugu, Kannada and Malayalam.",
    "Austroasiatic": "In India represented by the Munda branch (Santali, Mundari, Ho, Kharia, Korku, Sora, Juang, etc.) in the eastern/central tribal belt, and the Khasic and Nicobarese branches in the Northeast and Andaman & Nicobar Islands.",
    "Sino-Tibetan": "Represented in India by numerous Tibeto-Burman languages of the Himalayas and Northeast, including the Bodo-Garo, Kuki-Chin, Naga, Tani and Tibetic groups.",
    "Great Andamanese": "A small, now nearly extinct family indigenous to the Andaman Islands, generally treated as a language isolate family unrelated to any mainland Indian family.",
    "Ongan": "Also called Angan or South Andamanese; comprises Onge, Jarawa and Sentinelese, spoken by indigenous Andamanese communities and unrelated to Great Andamanese.",
    "Tai-Kadai": "A family centred on mainland Southeast Asia and southern China (Ethnologue: Kra-Dai); represented in India by Tai (Shan-related) languages such as Khamti, Aiton, Phake and Khamyang spoken by Buddhist communities of eastern Assam and Arunachal Pradesh.",
    "Language isolate": "A language with no demonstrated relationship to any other known language or family. India's examples include Nihali (Maharashtra-Madhya Pradesh border) and Burushaski (Ladakh).",
    "Turkic": "A family spread from Turkey to Siberia; represented in India only by small, endangered Uyghur-speaking communities.",
    "Koreanic": "Represented in India only by Korean, spoken as a foreign/heritage language, not indigenous.",
    "Japonic": "Represented in India only by Japanese, spoken as a foreign/heritage language, not indigenous.",
    "Creole": "Contact languages that developed a new native-speaker community from a lexifier language mixed with local languages, e.g. Nagamese (Assamese-based) and the Portuguese-based creoles of the west coast.",
    "Pidgin": "Simplified contact languages without a native-speaker community, used as a lingua franca between groups without a shared first language, e.g. Nefamese in Arunachal Pradesh.",
    "Sign language": "Visual-gestural languages of Deaf communities, e.g. Indian Sign Language and West Bengal Sign Language, unrelated in structure to the surrounding spoken languages.",
    "Mixed language": "A language formed by systematic mixture of elements from two or more source languages, rather than by normal inheritance from a single parent, e.g. Moundadan Chetti (Kannada-Malayalam-Tamil).",
    "Unclassified": "Languages whose genealogical classification is not resolved in this dataset.",
}

FAMILY_SYNONYMS = {
    "Austro-Asiatic": "Austroasiatic",
    "Kra-Dai": "Tai-Kadai",
}

EGIDS_TO_ENDANGERMENT = {
    "6b": "Vulnerable",
    "7": "Vulnerable",
    "8a": "Definitely Endangered",
    "8b": "Severely Endangered",
    "9": "Critically Endangered",
    "10": "Extinct",
    "x10": "Extinct",
}

WORD_ORDER_RE = re.compile(r"\b(SOV|SVO|VSO|VOS|OSV|OVS)\b")
SCRIPT_TAG_RE = re.compile(r"\s*\[[A-Za-z]+\]")
MOJIBAKE_CHARS = ("Ã", "â€", "Â", "�")


def clean_text(value):
    """Trim, drop empties, and best-effort fix any mis-decoded UTF-8 text."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None

    def score(text):
        return sum(text.count(marker) for marker in MOJIBAKE_CHARS)

    try:
        candidate = value.encode("cp1252").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        candidate = None
    if candidate and score(candidate) < score(value):
        return candidate
    return value


def parse_int(value):
    value = clean_text(value)
    if not value:
        return None
    value = value.replace(",", "")
    try:
        return int(float(value))
    except ValueError:
        return None


def parse_float(value):
    value = clean_text(value)
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def normalize_family(classification):
    """Split an Ethnologue Classification string into (family, branch)."""
    if not classification:
        return "Unclassified", None
    tokens = [t.strip() for t in classification.split(",") if t.strip()]
    if not tokens:
        return "Unclassified", None

    head = tokens[0]
    head = FAMILY_SYNONYMS.get(head, head)

    if head == "Andamanese":
        rest = tokens[1:]
        if rest and "South Andamanese" in rest[0]:
            return "Ongan", ", ".join(rest) or None
        return "Great Andamanese", ", ".join(rest) or None

    branch = ", ".join(tokens[1:]) or None
    return head, branch


def _script_name(sentence):
    name = SCRIPT_TAG_RE.sub("", sentence)
    name = name.split(",")[0].strip()
    return name or None


def first_script(scripts_field):
    """Pull a clean primary script name out of the verbose Scripts column.

    The Scripts field lists every script ever used for a language as
    period-separated sentences (e.g. "Braille script [Brai]. Devanagari
    script [Deva], primary usage."), with the sentence for the modern/main
    script usually flagged "primary usage" -- but not always listed first
    (accessibility scripts like Braille are often listed first). Prefer the
    sentence flagged "primary usage"; otherwise fall back to the first
    still-in-use, non-Braille script mentioned.
    """
    scripts_field = clean_text(scripts_field)
    if not scripts_field:
        return None
    sentences = [s.strip() for s in scripts_field.split(".") if s.strip()]
    if not sentences:
        return None

    for sentence in sentences:
        if "primary usage" in sentence.lower():
            name = _script_name(sentence)
            if name:
                return name

    candidates = [s for s in sentences if "no longer in use" not in s.lower()] or sentences
    for sentence in candidates:
        name = _script_name(sentence)
        if name and name.lower() != "braille script":
            return name
    return _script_name(candidates[0])


def word_order(typology_field):
    typology_field = clean_text(typology_field)
    if not typology_field:
        return None
    match = WORD_ORDER_RE.search(typology_field)
    return match.group(1) if match else None


def egids_endangerment(egids_code, egids_label):
    egids_code = (egids_code or "").strip().lower()
    if egids_code in EGIDS_TO_ENDANGERMENT:
        return EGIDS_TO_ENDANGERMENT[egids_code]
    label = clean_text(egids_label)
    if label and "extinct" in label.lower():
        return "Extinct"
    return None


def build_notes(row):
    parts = []
    alt = clean_text(row["Alternate_Names"])
    if alt:
        parts.append(f"Also known as: {alt}.")
    dialects = clean_text(row["Dialect_Names"])
    if dialects:
        parts.append(f"Dialects: {dialects}.")
    relationships = clean_text(row["Relationships"])
    if relationships:
        parts.append(relationships)
    remarks = clean_text(row["General_Remarks"])
    if remarks:
        parts.append(remarks)
    religion = clean_text(row["Religion"])
    if religion:
        parts.append(f"Religion: {religion}.")
    return " ".join(parts) or None


def build_status(row):
    official = clean_text(row["Official_Recognition"])
    if official:
        return official
    label = clean_text(row["EGIDS_Label"])
    return f"EGIDS: {label}" if label else None


def speakers_and_year(row):
    for field in ("All_Users", "L1_Users", "Population_Total"):
        value = parse_int(row[field])
        if value:
            return value, parse_int(row["Population_Year"])
    return None, parse_int(row["Population_Year"])


def load_rows():
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    rows = load_rows()
    print(f"Loaded {len(rows)} rows from {CSV_PATH.name}")

    languages = []
    locations = []
    families_seen = {}
    scripts_seen = {}

    for row in rows:
        iso3 = clean_text(row["iso"])
        name = clean_text(row["Uninverted_Name"]) or clean_text(row["Language_Name"])
        native_name = clean_text(row["Autonym"])
        family, branch = normalize_family(clean_text(row["Classification"]))
        families_seen.setdefault(family, FAMILY_DESCRIPTIONS.get(family, None))

        script = first_script(row["Scripts"])
        if script:
            scripts_seen.setdefault(script, None)

        speakers, census_year = speakers_and_year(row)

        is_classical = 1 if iso3 in CLASSICAL_SINCE else 0
        classical_since = CLASSICAL_SINCE.get(iso3)
        if iso3 in SCHEDULED_EIGHTH:
            classification = "Scheduled" + (f", Classical ({classical_since})" if classical_since else "")
        else:
            classification = "Non-Scheduled" + (f", Classical ({classical_since})" if classical_since else "")

        languages.append((
            name,
            native_name,
            ISO_639_1.get(iso3),
            iso3,
            family,
            branch,
            script,
            word_order(row["Typology"]),
            classification,
            is_classical,
            classical_since,
            speakers,
            census_year,
            SOURCE,
            clean_text(row["Location"]) or clean_text(row["Subdivision"]),
            build_status(row),
            egids_endangerment(row["EGIDS"], row["EGIDS_Label"]),
            build_notes(row),
        ))

        # languages is deleted/reset and inserted in this same row order below,
        # so AUTOINCREMENT will assign len(languages) as this row's id.
        locations.append((
            len(languages),
            iso3,
            clean_text(row["Country_Code"]),
            clean_text(row["Country_Namee"]),
            clean_text(row["Subdivision"]),
            clean_text(row["Location"]),
            parse_float(row["Latitude"]),
            parse_float(row["Longitude"]),
        ))

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS language_families (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT
        );
        CREATE TABLE IF NOT EXISTS writing_systems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            type TEXT,
            description TEXT
        );
        CREATE TABLE IF NOT EXISTS languages (
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
        CREATE INDEX IF NOT EXISTS idx_languages_family ON languages(family);
        CREATE INDEX IF NOT EXISTS idx_languages_name ON languages(name);
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            language_id INTEGER NOT NULL,
            iso_639_3 TEXT,
            country_code TEXT,
            country_name TEXT,
            subdivision TEXT,
            location TEXT,
            latitude REAL,
            longitude REAL,
            FOREIGN KEY (language_id) REFERENCES languages(id)
        );
        CREATE INDEX IF NOT EXISTS idx_locations_language_id ON locations(language_id);
        CREATE INDEX IF NOT EXISTS idx_locations_iso_639_3 ON locations(iso_639_3);
        CREATE INDEX IF NOT EXISTS idx_locations_subdivision ON locations(subdivision);
        """
    )

    conn.execute("DELETE FROM languages")
    conn.execute("DELETE FROM language_families")
    conn.execute("DELETE FROM writing_systems")
    conn.execute("DELETE FROM locations")
    conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('languages', 'language_families', 'writing_systems', 'locations')")

    conn.executemany(
        "INSERT INTO language_families (name, description) VALUES (?, ?)",
        sorted(families_seen.items()),
    )
    conn.executemany(
        "INSERT INTO writing_systems (name, type, description) VALUES (?, NULL, NULL)",
        [(name,) for name in sorted(scripts_seen)],
    )
    conn.executemany(
        """
        INSERT INTO languages (
            name, native_name, iso_639_1, iso_639_3, family, branch, script,
            word_order, classification, is_classical, classical_since,
            speakers_approx, census_year, source, primary_regions, status,
            endangerment, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        languages,
    )
    conn.executemany(
        """
        INSERT INTO locations (
            language_id, iso_639_3, country_code, country_name,
            subdivision, location, latitude, longitude
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        locations,
    )
    conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM languages").fetchone()[0]
    fam_count = conn.execute("SELECT COUNT(*) FROM language_families").fetchone()[0]
    script_count = conn.execute("SELECT COUNT(*) FROM writing_systems").fetchone()[0]
    loc_count = conn.execute("SELECT COUNT(*) FROM locations").fetchone()[0]
    conn.close()
    print(f"Wrote {count} languages, {fam_count} families, {script_count} writing systems, "
          f"{loc_count} locations to {DB_PATH}")


if __name__ == "__main__":
    main()
