"""Numeric access-level tiers, replacing the old text `role` column.

Lower number = more privileged. Single source of truth for the thresholds
used across access/attendance/blog/dashboard/ildb/library.

Levels can carry an optional decimal sub-level (e.g. 1.1, 1.3) — these are
purely organizational/reporting labels within their whole-number tier and
carry the *same permissions* as that tier. All permission checks must
compare on tier(level), the floored whole number, never the raw level.

There is no such thing as an int level — every level, whole-tier or
sub-level, is a float. `users.level` is declared REAL (SQLite forces float
storage on every value regardless of what's inserted), and every constant
below is a float literal to match — never write a bare `1`, always `1.0`.

Every gated module should call current_level() (not query users.level
itself) so a real dev's "view as" override is honored everywhere uniformly.
"""

import sqlite3

from flask import session

from modules.db import USERS_DB

ANONYMOUS_LEVEL = 6.0

LEVEL_NAMES = {
    0.0: "dev",
    1.0: "admin",
    2.0: "data_manager",
    3.0: "raid_staff",
    4.0: "viewer",
    5.0: "external",
}

# Optional organizational sub-labels for specific decimal levels — same
# permissions as their whole-number tier, just a more specific title for
# display/reporting. Not every decimal needs an entry here; undefined
# decimals just show their tier's generic name.
SUB_LEVEL_LABELS = {
    0.1: "developer",
    0.2: "technical tester",
    0.3: "non-technical tester",
    0.4: "outside developer",
    0.5: "outside tester",
    1.1: "director",
    1.2: "senior manager",
    1.3: "manager",
}

# Sub-levels that get routed to their own dedicated dashboard instead of the
# shared one — value is the Flask endpoint name. Currently content-identical
# to the shared dashboard; each is its own template/route so it can diverge
# later without touching the others. A level not listed here (including
# plain 1.0 or 0.0) just uses the shared dashboard.index.
SUB_LEVEL_DASHBOARD_ENDPOINTS = {
    0.1: "dashboard.developer_dashboard",
    0.2: "dashboard.technical_tester_dashboard",
    0.3: "dashboard.non_technical_tester_dashboard",
    0.4: "dashboard.outside_developer_dashboard",
    0.5: "dashboard.outside_tester_dashboard",
    1.1: "dashboard.director_dashboard",
    1.2: "dashboard.senior_manager_dashboard",
    1.3: "dashboard.manager_dashboard",
}


def tier(level):
    """The whole-number tier a (possibly decimal) level belongs to, still as
    a float. All permission checks compare against this, never the raw
    level, so sub-levels share their tier's permissions exactly."""
    return float(int(level))


def level_label(level):
    """Human label for a level: its specific sub-label if one is defined,
    else its tier's generic name."""
    if level in SUB_LEVEL_LABELS:
        return SUB_LEVEL_LABELS[level]
    if tier(level) == ANONYMOUS_LEVEL:
        return "anonymous"
    return LEVEL_NAMES.get(tier(level), "unknown")


def real_level():
    """The DB-stored level for the current session, ignoring any dev
    'view as' override. None if not logged in."""
    email = session.get("user_email")
    if not email:
        return None
    conn = sqlite3.connect(USERS_DB)
    try:
        row = conn.execute("SELECT level FROM users WHERE lower(email) = ?", (email.lower(),)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def current_level():
    """Effective level for every permission check in the app: a real lvl-0
    dev's 'view as' override if one is set (session['view_as_level']), else
    the real DB level. Only a true dev (tier(real_level()) == 0.0) can have
    an override — see modules.dashboard.set_view_as."""
    level = real_level()
    if level is not None and tier(level) == 0.0:
        override = session.get("view_as_level")
        if override is not None:
            return override
    return level


ADMIN_LEVEL = 1.0     # dashboard page, level changes, audit log — dev/admin only
                       # (also the ceiling for any future dev-only "backdoor" routes,
                       # which would additionally need to check level == 0.0)
ILDB_LEVEL = 1.0       # /internal-database — dev/admin only (browses every .db
                       # file in db/, including users.db/audit_log, not just ildb.db)
MANAGER_LEVEL = 3.0    # manager actions (attendance marking, blog creation, library
                       # accept/reject/return, access-request resolution) and
                       # chat/attendance *visibility* — dev/admin/data_manager/raid_staff
VIEWER_LEVEL = 4.0     # profile page, languages, library browsing/requests —
                       # everyone logged in except external (lvl-5)

# lvl-6 "anonymous" (not logged in) has no DB row — it's whoever
# app.py's require_login lets through via PUBLIC_ENDPOINTS. Currently only
# the home page is public for anonymous visitors.
