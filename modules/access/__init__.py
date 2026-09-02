"""Access requests: lets a logged-in user ask an admin for permission to a
section they were denied (see the 403 handler in app.py)."""

import sqlite3
from datetime import datetime
from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from modules.audit import log_action
from modules.db import USERS_DB
from modules.levels import MANAGER_LEVEL, VIEWER_LEVEL, current_level, level_label, tier

access = Blueprint("access", __name__, template_folder="templates")

SCHEMA = """
    CREATE TABLE IF NOT EXISTS access_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT NOT NULL,
        section TEXT NOT NULL,
        reason TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        requested_at TEXT NOT NULL,
        decided_by TEXT,
        decided_at TEXT
    );
"""


def get_conn():
    conn = sqlite3.connect(USERS_DB)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def now():
    return datetime.now().isoformat(timespec="seconds")


def manager_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        level = current_level()
        if level is None or tier(level) > MANAGER_LEVEL:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


@access.route("/profile")
def profile():
    email = session.get("user_email", "")
    conn = sqlite3.connect(USERS_DB)
    conn.row_factory = sqlite3.Row
    user = conn.execute("SELECT * FROM users WHERE lower(email) = ?", (email.lower(),)).fetchone()
    conn.close()
    level = current_level()
    if not user or level is None or tier(level) > VIEWER_LEVEL:
        abort(403)
    return render_template("profile.html", user=user, email=email, level=level, level_label=level_label)


@access.route("/access-requests", methods=["POST"])
def submit_request():
    section = request.form.get("section", "").strip() or "an unknown section"
    reason = request.form.get("reason", "").strip()
    if not reason:
        flash("Please describe why you need access before submitting.", "error")
        return redirect(request.referrer or url_for("hello"))

    conn = get_conn()
    conn.execute(
        "INSERT INTO access_requests (user_email, section, reason, status, requested_at) "
        "VALUES (?, ?, ?, 'pending', ?)",
        (session["user_email"], section, reason, now()),
    )
    conn.commit()
    conn.close()
    flash("Your request has been sent to an admin for review.", "info")
    return redirect(url_for("hello"))


@access.route("/access-requests/<int:request_id>/resolve", methods=["POST"])
@manager_required
def resolve_request(request_id):
    decision = request.form.get("decision")
    if decision not in ("approved", "rejected"):
        abort(400)
    conn = get_conn()
    conn.execute(
        "UPDATE access_requests SET status = ?, decided_by = ?, decided_at = ? "
        "WHERE id = ? AND status = 'pending'",
        (decision, session.get("user_email", ""), now(), request_id),
    )
    conn.commit()
    conn.close()
    log_action("access", "resolve_request", f"request #{request_id} -> {decision}")
    flash("Access request updated.", "info")
    return redirect(url_for("dashboard.index"))
