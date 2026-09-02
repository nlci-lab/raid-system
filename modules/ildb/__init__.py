"""Internal Database module.

Read-only data-table viewer over every .db file in db/ — the app's own
SQLite databases (users, books, chat, ildb, ...), picked one at a time via
the ?db= query param, one table at a time via ?table=. Admin-only, since
this now exposes users.db/audit_log alongside the original NLCI-India BT
Language Database data (see achieved/schema.sql and
achieved/RAID_Digital_Ecosystem.md, Ch. 6 "Indian Language Database").
"""

import sqlite3
from functools import wraps

from flask import Blueprint, abort, render_template, request

from modules.db import all_databases
from modules.levels import ILDB_LEVEL, current_level, tier

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
