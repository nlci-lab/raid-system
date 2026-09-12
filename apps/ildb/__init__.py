"""Internal Database module.

Read-only data-table viewer over every .db file in db/ — the app's own
SQLite databases (users, books, ildb, ...), picked one at a time via
the ?db= query param, one table at a time via ?table=. Admin-only, since
this now exposes users.db/audit_log alongside the original NLCI-India BT
Language Database data (see achieved/schema.sql and
achieved/RAID_Digital_Ecosystem.md, Ch. 6 "Indian Language Database").
"""

import sqlite3
from functools import wraps

from flask import Blueprint, abort, render_template, request

from apps.db import ILDB_DB, all_databases
from apps.levels import ILDB_LEVEL, current_level, tier

ildb = Blueprint("ildb", __name__, template_folder="templates")


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        level = current_level()
        if level is None or tier(level) > ILDB_LEVEL:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


@ildb.route("/internal-database")
@admin_required
def index():
    db_paths = all_databases()
    db_names = list(db_paths)

    active_db = request.args.get("db")
    if active_db not in db_paths:
        active_db = db_names[0] if db_names else None

    tables = []
    table = None
    columns = []
    rows = []

    if active_db:
        conn = sqlite3.connect(db_paths[active_db])
        conn.row_factory = sqlite3.Row
        try:
            tables = [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                ).fetchall()
            ]

            table = request.args.get("table")
            if table not in tables:
                table = tables[0] if tables else None

            if table:
                columns = [col["name"] for col in conn.execute(f'PRAGMA table_info("{table}")').fetchall()]
                rows = conn.execute(f'SELECT * FROM "{table}"').fetchall()
        finally:
            conn.close()

    return render_template(
        "ildb_index.html",
        db_names=db_names,
        active_db=active_db,
        tables=tables,
        table=table,
        columns=columns,
        rows=rows,
    )


# EGIDS (Expanded Graded Intergenerational Disruption Scale) bands, safest
# to most gone. "Safe" = still learned by children without institutional
# help (0-6a); everything from 6b down is losing ground. Order here is the
# display order for the vitality chart -- top to bottom, safe to extinct.
EGIDS_BANDS = [
    ("safe", "Safe / Institutional", ["0", "1", "2", "3", "4", "5"], "#22a06b"),
    ("vigorous", "Vigorous", ["6a"], "#2f8fd1"),
    ("threatened", "Threatened", ["6b"], "#d9a02c"),
    ("shifting", "Shifting", ["7"], "#e07b39"),
    ("moribund", "Moribund", ["8a", "8b"], "#d1493f"),
    ("dormant", "Dormant", ["9"], "#9a2f2f"),
    ("extinct", "Extinct", ["10"], "#6b7280"),
]


def health_snapshot():
    """The Director Dashboard's ILDB section -- a language-situation-at-a-
    glance rollup (EGIDS vitality spread, family/geographic/script
    diversity, endangerment headline), not row-level browsing (that's
    index() above) and not just a data-completeness readout. Read-only;
    tolerates any table being missing/empty."""
    conn = sqlite3.connect(ILDB_DB)
    conn.row_factory = sqlite3.Row
    try:
        existing = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }

        def count(table):
            if table not in existing:
                return 0
            return conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]

        def group_counts(table, col):
            if table not in existing:
                return []
            rows = conn.execute(
                f'SELECT {col} AS k, COUNT(*) AS n FROM "{table}" '
                f"WHERE {col} IS NOT NULL AND TRIM({col}) != '' "
                f"GROUP BY {col} ORDER BY n DESC"
            ).fetchall()
            return [{"name": r["k"], "count": r["n"]} for r in rows]

        total = count("language")

        egids_counts = {}
        if total and "language" in existing:
            for row in conn.execute(
                "SELECT egids AS k, COUNT(*) AS n FROM language "
                "WHERE egids IS NOT NULL AND TRIM(egids) != '' GROUP BY egids"
            ).fetchall():
                egids_counts[row["k"]] = row["n"]

        vitality = []
        for key, label, codes, color in EGIDS_BANDS:
            n = sum(egids_counts.get(c, 0) for c in codes)
            vitality.append({
                "key": key,
                "label": label,
                "color": color,
                "count": n,
                "pct": round(100 * n / total) if total else 0,
            })

        safe_n = vitality[0]["count"] + vitality[1]["count"]  # safe + vigorous
        endangered_n = sum(v["count"] for v in vitality[2:6])  # threatened..dormant
        extinct_n = vitality[6]["count"]
        # Whatever's tracked but doesn't map to a known EGIDS code at all
        # (blank/unrecognized) -- surfaced separately so it isn't silently
        # dropped from the total.
        unclassified_n = total - (safe_n + endangered_n + extinct_n)

        def pct_filled(col):
            if not total or "language" not in existing:
                return 0
            filled = conn.execute(
                f'SELECT COUNT(*) FROM language WHERE {col} IS NOT NULL AND TRIM({col}) != \'\''
            ).fetchone()[0]
            return round(100 * filled / total)

        # Cap each breakdown list to a top-N "at a glance" view instead of a
        # long scroll -- the full list is one click away via /internal-database.
        TOP_N = 8

        def top_n(rows):
            return rows[:TOP_N], max(0, len(rows) - TOP_N)

        families, families_more = top_n(group_counts("language", "lg_family"))
        zones, zones_more = top_n(group_counts("zone_language_import", "strategic_zone"))
        scripts, scripts_more = top_n(group_counts("script_language_import", "script"))

        return {
            "total_languages": total,
            "safe_count": safe_n,
            "endangered_count": endangered_n,
            "extinct_count": extinct_n,
            "unclassified_count": unclassified_n,
            "vitality": vitality,
            "families": families,
            "families_more": families_more,
            "zones": zones,
            "zones_more": zones_more,
            "scripts": scripts,
            "scripts_more": scripts_more,
            "pct_iso_code": pct_filled("iso_code"),
            "pct_egids": pct_filled("egids"),
            "alternate_name_count": count("alternate_name"),
        }
    finally:
        conn.close()
