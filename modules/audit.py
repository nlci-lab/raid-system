"""Shared audit trail for actions taken by admins and data managers.

Any route that lets a manager-level role mutate data should call
log_action() right before commit() so the dashboard audit log shows who
changed what, when, and from where.
"""

import sqlite3
from datetime import datetime

from flask import request, session

from modules.db import USERS_DB

SCHEMA = """
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor_email TEXT NOT NULL,
        actor_role TEXT,
        module TEXT NOT NULL,
        action TEXT NOT NULL,
        details TEXT,
        ip_address TEXT,
        created_at TEXT NOT NULL
    );
"""


def _now():
    return datetime.now().isoformat(timespec="seconds")


def log_action(module, action, details=""):
    """Record a write made by the currently logged-in user."""
    conn = sqlite3.connect(USERS_DB)
    try:
        conn.executescript(SCHEMA)
        email = session.get("user_email", "")
        role_row = conn.execute(
            "SELECT role FROM users WHERE lower(email) = ?", (email.lower(),)
        ).fetchone() if email else None
        conn.execute(
            "INSERT INTO audit_log (actor_email, actor_role, module, action, details, ip_address, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                email,
                role_row[0] if role_row else None,
                module,
                action,
                details,
                request.remote_addr if request else None,
                _now(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def recent_entries(limit=200):
    conn = sqlite3.connect(USERS_DB)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        return conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    finally:
        conn.close()
