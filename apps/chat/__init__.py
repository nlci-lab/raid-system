"""Chat — rebuilt from zero (2026-09-11). v1 is a single shared room: every
logged-in staff member posts into and sees the same one message stream, no
DMs/separate conversations (that's a possible later extension, not this)."""

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from flask import Blueprint, abort, redirect, render_template, request, send_file, session, url_for
from werkzeug.utils import secure_filename

from apps.db import CHAT_DB, USERS_DB

chat = Blueprint("chat", __name__, template_folder="templates")

# Uploaded files live as a sibling of the app folder, same "code vs. data"
# split as db/, blogs/, guide/ — never committed to git, never inside core/.
UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "chat_uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

_SCHEMA = """
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_email TEXT NOT NULL,
        body TEXT,
        attachment_filename TEXT,
        attachment_original_name TEXT,
        created_at TEXT NOT NULL
    );
"""


def get_conn():
    conn = sqlite3.connect(CHAT_DB)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    # CREATE TABLE IF NOT EXISTS above is a no-op on a table that already
    # existed under the earlier text-only schema (body NOT NULL, no
    # attachment columns) — add what's missing and relax NOT NULL by
    # rebuilding, so file-only messages (no body) are actually allowed.
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(messages)").fetchall()}
    if "attachment_filename" not in cols:
        conn.execute("ALTER TABLE messages ADD COLUMN attachment_filename TEXT")
        conn.execute("ALTER TABLE messages ADD COLUMN attachment_original_name TEXT")
        conn.commit()
    return conn


def now():
    return datetime.now().isoformat(timespec="seconds")


def _display_time(iso_str):
    """Stored as full ISO (for correct sorting); shown as a short
    'Sep 11, 10:59 PM' rather than the raw ISO string."""
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%b %d, %I:%M %p").replace(" 0", " ")
    except ValueError:
        return iso_str


def _name_map():
    """email -> display name, for rendering sender names on messages."""
    conn = sqlite3.connect(USERS_DB)
    rows = conn.execute("SELECT email, name FROM users").fetchall()
    conn.close()
    return {r[0]: (r[1] or r[0]) for r in rows}


@chat.route("/chat")
def index():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM messages ORDER BY id ASC").fetchall()
    conn.close()

    names = _name_map()
    my_email = session.get("user_email", "")
    messages = [
        {
            "id": r["id"],
            "sender_email": r["sender_email"],
            "sender_name": "You" if r["sender_email"] == my_email else names.get(r["sender_email"], r["sender_email"]),
            "body": r["body"],
            "attachment_original_name": r["attachment_original_name"],
            "created_at": _display_time(r["created_at"]),
            "is_mine": r["sender_email"] == my_email,
        }
        for r in rows
    ]
    return render_template("chat_index.html", messages=messages)


@chat.route("/chat/send", methods=["POST"])
def send():
    body = request.form.get("body", "").strip()
    file = request.files.get("file")

    attachment_filename = None
    attachment_original_name = None
    if file and file.filename:
        original_name = secure_filename(file.filename)
        # Prefix with a random id so two people uploading "report.pdf" the
        # same minute never collide/overwrite each other on disk.
        attachment_filename = f"{uuid.uuid4().hex}_{original_name}"
        attachment_original_name = original_name
        file.save(UPLOADS_DIR / attachment_filename)

    if body or attachment_filename:
        conn = get_conn()
        conn.execute(
            """INSERT INTO messages
               (sender_email, body, attachment_filename, attachment_original_name, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (session.get("user_email", ""), body, attachment_filename, attachment_original_name, now()),
        )
        conn.commit()
        conn.close()
    return redirect(url_for("chat.index"))


@chat.route("/chat/attachment/<int:message_id>")
def download_attachment(message_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT attachment_filename, attachment_original_name FROM messages WHERE id = ?", (message_id,)
    ).fetchone()
    conn.close()
    if not row or not row["attachment_filename"]:
        abort(404)

    path = UPLOADS_DIR / row["attachment_filename"]
    if not path.is_file():
        abort(404)
    return send_file(path, download_name=row["attachment_original_name"], as_attachment=True)
