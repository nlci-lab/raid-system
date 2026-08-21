"""Indian Language Database (ILDB) module.

Read-only viewer over db/ildb.db — the SQL copy of the NLCI-India BT
Language Database (see achieved/schema.sql and achieved/RAID_Digital_Ecosystem.md,
Ch. 6 "Indian Language Database"). Restricted to admins and data managers,
matching the "Admin only" Internal Database tile on the home page.
"""

import sqlite3
from functools import wraps

from flask import Blueprint, abort, render_template, request, session

from modules.db import ILDB_DB, USERS_DB

ildb = Blueprint("ildb", __name__, template_folder="templates")

MANAGER_ROLES = ("admin", "data_manager")


def get_conn():
    conn = sqlite3.connect(ILDB_DB)
    conn.row_factory = sqlite3.Row
    return conn


def _current_user_role():
    email = session.get("user_email")
    if not email:
        return None
    conn = sqlite3.connect(USERS_DB)
    try:
        row = conn.execute("SELECT role FROM users WHERE lower(email) = ?", (email.lower(),)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if _current_user_role() not in MANAGER_ROLES:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def _bars(rows):
    """Turn a list of (label, count) rows into bar-chart dicts scaled to the largest count."""
    pairs = [(row[0], row[1]) for row in rows]
    max_count = max((c for _, c in pairs), default=0) or 1
    return [{"label": label, "count": count, "pct": round(count * 100 / max_count, 1)} for label, count in pairs]


def _dashboard_stats(conn):
    total = conn.execute("SELECT COUNT(*) FROM language").fetchone()[0]
    spoken = conn.execute("SELECT COUNT(*) FROM language WHERE lg_status = 'Spoken'").fetchone()[0]
    extinct = conn.execute("SELECT COUNT(*) FROM language WHERE lg_status = 'Extinct'").fetchone()[0]
    families = conn.execute(
        "SELECT COUNT(DISTINCT lg_family) FROM language WHERE lg_family IS NOT NULL AND lg_family <> ''"
    ).fetchone()[0]

    status_rows = conn.execute(
        "SELECT COALESCE(NULLIF(lg_status, ''), 'Unknown') AS status, COUNT(*) AS c "
        "FROM language GROUP BY status ORDER BY c DESC"
    ).fetchall()
    zone_rows = conn.execute(
        "SELECT COALESCE(NULLIF(strategic_zone, ''), 'Unknown') AS zone, COUNT(DISTINCT language_id) AS c "
        "FROM zone_language_import GROUP BY zone ORDER BY c DESC"
    ).fetchall()

    return {
        "total": total,
        "spoken": spoken,
        "extinct": extinct,
        "families": families,
        "status_bars": _bars(status_rows),
        "zone_bars": _bars(zone_rows),
    }


DATABASE_VIEW_NAME = "All Languages (Combined)"


def _combined_view(conn):
    """One row per language with every related table's data joined/flattened in."""
    cols = ["language_id", "language_name", "iso_code", "grn", "lg_family", "lg_status", "egids", "lang_code",
            "alternate_names", "scripts", "hub_countries", "strategic_zones"]
    rows = conn.execute(
        """
        SELECT
          l.language_id, l.language_name, l.iso_code, l.grn, l.lg_family, l.lg_status, l.egids, l.lang_code,
          an.alternate_names, sc.scripts, hc.hub_countries, z.strategic_zones
        FROM language l
        LEFT JOIN (
            SELECT language_id, GROUP_CONCAT(alternate_name, ', ') AS alternate_names
            FROM alternate_name GROUP BY language_id
        ) an ON an.language_id = l.language_id
        LEFT JOIN (
            SELECT language_id, GROUP_CONCAT(DISTINCT script) AS scripts
            FROM script_language_import GROUP BY language_id
        ) sc ON sc.language_id = l.language_id
        LEFT JOIN (
            SELECT language_id, GROUP_CONCAT(DISTINCT hub_country) AS hub_countries
            FROM hub_country_language_import GROUP BY language_id
        ) hc ON hc.language_id = l.language_id
        LEFT JOIN (
            SELECT language_id, GROUP_CONCAT(DISTINCT strategic_zone) AS strategic_zones
            FROM zone_language_import GROUP BY language_id
        ) z ON z.language_id = l.language_id
        ORDER BY l.language_name
        """
    ).fetchall()
    return {
        DATABASE_VIEW_NAME: {
            "columns": cols,
            "rows": [["" if row[c] is None else row[c] for c in cols] for row in rows],
        }
    }


@ildb.route("/internal-database")
@admin_required
def index():
    conn = get_conn()
    tables = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    ]

    table = request.args.get("table")
    if table not in tables:
        table = tables[0] if tables else None

    sheets = {}
    for t in tables:
        cols = [col["name"] for col in conn.execute(f'PRAGMA table_info("{t}")').fetchall()]
        rows = conn.execute(f'SELECT * FROM "{t}"').fetchall()
        sheets[t] = {
            "columns": cols,
            "rows": [["" if row[c] is None else row[c] for c in cols] for row in rows],
        }

    db_sheets = _combined_view(conn)
    stats = _dashboard_stats(conn)
    conn.close()

    return render_template(
        "ildb_index.html",
        tables=tables,
        table=table,
        sheets=sheets,
        db_sheets=db_sheets,
        db_table=DATABASE_VIEW_NAME,
        **stats,
    )
