import sqlite3
from datetime import datetime
from functools import wraps
from io import BytesIO

from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, session, url_for
from werkzeug.utils import secure_filename

from modules.db import CHAT_DB, USERS_DB
from modules.levels import MANAGER_LEVEL, current_level, tier

chat = Blueprint("chat", __name__, template_folder="templates")


def staff_required(view):
    """dev/admin/data_manager/raid_staff only — viewer and external don't get chat."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        level = current_level()
        if level is None or tier(level) > MANAGER_LEVEL:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


SCHEMA = """
    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        is_group INTEGER NOT NULL DEFAULT 0,
        name TEXT,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS conversation_members (
        conversation_id INTEGER NOT NULL REFERENCES conversations(id),
        user_email TEXT NOT NULL,
        is_admin INTEGER NOT NULL DEFAULT 0,
        joined_at TEXT NOT NULL,
        PRIMARY KEY (conversation_id, user_email)
    );
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER NOT NULL REFERENCES conversations(id),
        sender_email TEXT NOT NULL,
        body TEXT,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS attachments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER NOT NULL REFERENCES messages(id),
        filename TEXT NOT NULL,
        mimetype TEXT,
        size INTEGER NOT NULL,
        data BLOB NOT NULL
    );
"""


def get_conn():
    """Connect to chat.db, creating the schema if the file is missing or empty."""
    conn = sqlite3.connect(CHAT_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def get_user_directory():
    """All users that have an email on file, ordered by name."""
    conn = sqlite3.connect(USERS_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT name, email FROM users WHERE email IS NOT NULL ORDER BY name").fetchall()
    conn.close()
    return rows


def get_name_map():
    return {row["email"]: row["name"] for row in get_user_directory()}


def now():
    return datetime.now().isoformat(timespec="seconds")


def get_membership(conn, conversation_id, email):
    return conn.execute(
        "SELECT * FROM conversation_members WHERE conversation_id = ? AND user_email = ?",
        (conversation_id, email),
    ).fetchone()


def list_conversations(conn, email):
    """Conversations for the sidebar, newest activity first."""
    rows = conn.execute("""
        SELECT c.id, c.is_group, c.name,
               (SELECT body FROM messages m WHERE m.conversation_id = c.id ORDER BY m.id DESC LIMIT 1) AS last_message,
               (SELECT created_at FROM messages m WHERE m.conversation_id = c.id ORDER BY m.id DESC LIMIT 1) AS last_at
        FROM conversations c
        JOIN conversation_members cm ON cm.conversation_id = c.id
        WHERE cm.user_email = ?
        ORDER BY COALESCE(last_at, c.created_at) DESC
    """, (email,)).fetchall()

    name_map = get_name_map()
    conversations = []
    for row in rows:
        item = dict(row)
        if row["is_group"]:
            item["title"] = row["name"] or "Group"
        else:
            other = conn.execute(
                "SELECT user_email FROM conversation_members WHERE conversation_id = ? AND user_email != ?",
                (row["id"], email),
            ).fetchone()
            other_email = other["user_email"] if other else None
            item["title"] = name_map.get(other_email, other_email or "Unknown")
        conversations.append(item)
    return conversations


@chat.route("/chat")
@staff_required
def index():
    email = session["user_email"]
    conn = get_conn()
    conversations = list_conversations(conn, email)
    conn.close()

    directory = [u for u in get_user_directory() if u["email"] != email]
    return render_template("chat_index.html", conversations=conversations, directory=directory)


@chat.route("/chat/dm/start", methods=["POST"])
@staff_required
def start_dm():
    email = session["user_email"]
    target = request.form.get("email", "").strip().lower()

    if not target or target == email:
        flash("Choose someone else to chat with.", "error")
        return redirect(url_for("chat.index"))

    conn = get_conn()
    existing = conn.execute("""
        SELECT c.id FROM conversations c
        WHERE c.is_group = 0
          AND EXISTS (SELECT 1 FROM conversation_members WHERE conversation_id = c.id AND user_email = ?)
          AND EXISTS (SELECT 1 FROM conversation_members WHERE conversation_id = c.id AND user_email = ?)
    """, (email, target)).fetchone()

    if existing:
        conversation_id = existing["id"]
    else:
        ts = now()
        cur = conn.execute(
            "INSERT INTO conversations (is_group, name, created_by, created_at) VALUES (0, NULL, ?, ?)",
            (email, ts),
        )
        conversation_id = cur.lastrowid
        conn.execute(
            "INSERT INTO conversation_members (conversation_id, user_email, is_admin, joined_at) VALUES (?, ?, 1, ?)",
            (conversation_id, email, ts),
        )
        conn.execute(
            "INSERT INTO conversation_members (conversation_id, user_email, is_admin, joined_at) VALUES (?, ?, 1, ?)",
            (conversation_id, target, ts),
        )
        conn.commit()
    conn.close()
    return redirect(url_for("chat.conversation", conversation_id=conversation_id))


@chat.route("/chat/group/create", methods=["POST"])
@staff_required
def create_group():
    email = session["user_email"]
    name = request.form.get("name", "").strip()
    members = [m.strip().lower() for m in request.form.getlist("members") if m.strip()]

    if not name:
        flash("Group name is required.", "error")
        return redirect(url_for("chat.index"))

    ts = now()
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO conversations (is_group, name, created_by, created_at) VALUES (1, ?, ?, ?)",
        (name, email, ts),
    )
    conversation_id = cur.lastrowid
    conn.execute(
        "INSERT INTO conversation_members (conversation_id, user_email, is_admin, joined_at) VALUES (?, ?, 1, ?)",
        (conversation_id, email, ts),
    )
    for member_email in members:
        if member_email != email:
            conn.execute(
                "INSERT OR IGNORE INTO conversation_members (conversation_id, user_email, is_admin, joined_at) VALUES (?, ?, 0, ?)",
                (conversation_id, member_email, ts),
            )
    conn.commit()
    conn.close()
    flash(f"Group '{name}' created.", "info")
    return redirect(url_for("chat.conversation", conversation_id=conversation_id))


@chat.route("/chat/<int:conversation_id>")
@staff_required
def conversation(conversation_id):
    email = session["user_email"]
    conn = get_conn()

    convo = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    if not convo:
        conn.close()
        abort(404)

    membership = get_membership(conn, conversation_id, email)
    if not membership:
        conn.close()
        abort(403)

    name_map = get_name_map()

    members = conn.execute(
        "SELECT user_email, is_admin FROM conversation_members WHERE conversation_id = ? ORDER BY is_admin DESC, user_email",
        (conversation_id,),
    ).fetchall()

    if convo["is_group"]:
        title = convo["name"] or "Group"
    else:
        other = next((m for m in members if m["user_email"] != email), None)
        title = name_map.get(other["user_email"], other["user_email"]) if other else "Chat"

    messages = conn.execute(
        "SELECT id, sender_email, body, created_at FROM messages WHERE conversation_id = ? ORDER BY id",
        (conversation_id,),
    ).fetchall()

    attachments_by_message = {}
    if messages:
        message_ids = [m["id"] for m in messages]
        placeholders = ",".join("?" for _ in message_ids)
        for att in conn.execute(
            f"SELECT id, message_id, filename, size FROM attachments WHERE message_id IN ({placeholders}) ORDER BY id",
            message_ids,
        ).fetchall():
            attachments_by_message.setdefault(att["message_id"], []).append(att)

    member_emails = {m["user_email"] for m in members}
    addable_users = [u for u in get_user_directory() if u["email"] not in member_emails]

    conversations = list_conversations(conn, email)
    directory = [u for u in get_user_directory() if u["email"] != email]

    conn.close()
    return render_template(
        "chat_conversation.html",
        convo=convo,
        title=title,
        messages=messages,
        attachments_by_message=attachments_by_message,
        members=members,
        name_map=name_map,
        my_email=email,
        is_admin=bool(membership["is_admin"]),
        addable_users=addable_users,
        conversations=conversations,
        directory=directory,
        active_id=conversation_id,
    )


@chat.route("/chat/<int:conversation_id>/send", methods=["POST"])
@staff_required
def send_message(conversation_id):
    email = session["user_email"]
    conn = get_conn()

    if not get_membership(conn, conversation_id, email):
        conn.close()
        abort(403)

    body = request.form.get("body", "").strip()
    files = [f for f in request.files.getlist("files") if f and f.filename]

    if not body and not files:
        conn.close()
        flash("Write a message or attach a file.", "error")
        return redirect(url_for("chat.conversation", conversation_id=conversation_id))

    cur = conn.execute(
        "INSERT INTO messages (conversation_id, sender_email, body, created_at) VALUES (?, ?, ?, ?)",
        (conversation_id, email, body or None, now()),
    )
    message_id = cur.lastrowid

    for f in files:
        data = f.read()
        if not data:
            continue
        filename = secure_filename(f.filename) or f.filename
        conn.execute(
            "INSERT INTO attachments (message_id, filename, mimetype, size, data) VALUES (?, ?, ?, ?, ?)",
            (message_id, filename, f.mimetype, len(data), data),
        )

    conn.commit()
    conn.close()
    return redirect(url_for("chat.conversation", conversation_id=conversation_id))


@chat.route("/chat/<int:conversation_id>/add-member", methods=["POST"])
@staff_required
def add_member(conversation_id):
    email = session["user_email"]
    conn = get_conn()

    convo = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    membership = get_membership(conn, conversation_id, email)

    if not convo or not convo["is_group"]:
        conn.close()
        abort(404)
    if not membership or not membership["is_admin"]:
        conn.close()
        flash("Only group admins can add members.", "error")
        return redirect(url_for("chat.conversation", conversation_id=conversation_id))

    new_email = request.form.get("email", "").strip().lower()
    if new_email:
        conn.execute(
            "INSERT OR IGNORE INTO conversation_members (conversation_id, user_email, is_admin, joined_at) VALUES (?, ?, 0, ?)",
            (conversation_id, new_email, now()),
        )
        conn.commit()
        flash("Member added.", "info")
    conn.close()
    return redirect(url_for("chat.conversation", conversation_id=conversation_id))


@chat.route("/chat/attachment/<int:attachment_id>")
@staff_required
def download_attachment(attachment_id):
    email = session["user_email"]
    conn = get_conn()
    row = conn.execute("""
        SELECT a.filename, a.mimetype, a.data, m.conversation_id
        FROM attachments a
        JOIN messages m ON m.id = a.message_id
        WHERE a.id = ?
    """, (attachment_id,)).fetchone()

    if not row:
        conn.close()
        abort(404)

    membership = get_membership(conn, row["conversation_id"], email)
    conn.close()
    if not membership:
        abort(403)

    return send_file(
        BytesIO(row["data"]),
        mimetype=row["mimetype"] or "application/octet-stream",
        as_attachment=True,
        download_name=row["filename"],
    )
